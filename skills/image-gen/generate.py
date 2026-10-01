#!/usr/bin/env python3
"""Generate or edit persistent image files with OpenAI GPT Image or xAI Grok Imagine.

The wrapper talks to each provider's REST API directly with the standard library,
so it has no SDK dependencies. Each provider is a small adapter that validates the
shared options against what that provider actually supports and builds its request.
Unsupported options fail loudly instead of being silently dropped.
"""

import argparse
import base64
import copy
import json
import math
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path("/tmp/image-gen")
TRANSPARENT_FORMATS = {"png", "webp"}
OUTPUT_EXTENSION_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}

# Request fields that dedicated options control; --extra may not override them, or it
# could bypass the per-provider validation (for example sending background to xAI).
RESERVED_FIELDS = {
    "model": "--model", "prompt": "the prompt argument", "n": "--n",
    "size": "--size, --aspect-ratio, or --resolution", "aspect_ratio": "--aspect-ratio",
    "resolution": "--resolution", "quality": "--quality", "background": "--transparent",
    "output_format": "--format", "output_compression": "--compression",
    "image": "--image", "images": "--image", "mask": "--mask",
    "response_format": "the wrapper (it always requests base64)",
}

# Ratios both providers accept. OpenAI also accepts any other W:H ratio up to 3:1.
COMMON_ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2",
    "19.5:9", "9:19.5", "20:9", "9:20",
]


class UsageError(Exception):
    """A request the chosen provider cannot fulfil; reported before any API call."""


def parse_ratio(value):
    try:
        width, height = (float(part) for part in value.split(":"))
    except ValueError:
        raise UsageError(f"Invalid aspect ratio '{value}'; use W:H, for example 16:9.")
    if not (math.isfinite(width) and math.isfinite(height)) or width <= 0 or height <= 0:
        raise UsageError(f"Invalid aspect ratio '{value}'; use W:H, for example 16:9.")
    return width / height


def round16(value):
    return max(16, int(round(value / 16)) * 16)


def data_url(path, allowed_mimes, max_chars):
    """Encode a local image as a data URL, enforcing the provider's type and size limits."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise UsageError(f"Input image does not exist or is not a file: {path}")
    mime, _ = mimetypes.guess_type(path.name)
    if mime not in allowed_mimes:
        allowed = ", ".join(sorted(m.split("/")[1] for m in allowed_mimes))
        raise UsageError(f"Unsupported input image type for {path.name}; use one of: {allowed}.")
    encoded = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    if len(encoded) > max_chars:
        raise UsageError(f"Input image is too large once encoded: {path}")
    return encoded


def image_reference(value, allowed_mimes, max_chars):
    if value.startswith(("https://", "http://", "data:")):
        return value
    return data_url(value, allowed_mimes, max_chars)


class OpenAIProvider:
    name = "openai"
    label = "OpenAI GPT Image"
    env_key = "OPENAI_API_KEY"
    base_url_env = "OPENAI_BASE_URL"
    default_base_url = "https://api.openai.com/v1"
    default_model = "gpt-image-2.5-flare"
    # Validation follows the GPT Image 2.x rules; DALL-E takes a different request shape.
    model_prefixes = ("gpt-image", "chatgpt-image")
    qualities = ["low", "medium", "high", "xhigh", "max", "auto"]
    max_images = 16
    max_n = 10
    input_mimes = {"image/png", "image/jpeg", "image/webp"}
    max_data_url_chars = 20_971_520

    # Size limits for the GPT Image 2.x custom-resolution models.
    max_edge = 3840
    min_pixels = 655_360
    max_pixels = 8_294_400

    def size_for(self, args):
        """Map --size, or --aspect-ratio and --resolution, to a WIDTHxHEIGHT string."""
        if args.size:
            return args.size
        ratio_given = args.aspect_ratio not in (None, "auto")
        if not ratio_given and not args.resolution:
            return "auto"
        ratio = parse_ratio(args.aspect_ratio) if ratio_given else 1.0
        if max(ratio, 1 / ratio) > 3:
            raise UsageError("OpenAI supports aspect ratios up to 3:1.")
        if args.resolution == "2k":
            # 2k means a 2048px long edge, matching OpenAI's 2048x2048 and 2048x1152 presets.
            long_edge = 2048
            width, height = (long_edge, long_edge / ratio) if ratio >= 1 else (long_edge * ratio, long_edge)
        else:
            # 1k keeps about a megapixel so wide ratios stay above the minimum pixel count.
            area = 1024 * 1024
            width, height = math.sqrt(area * ratio), math.sqrt(area / ratio)
        width, height = round16(width), round16(height)
        while width * height < self.min_pixels:
            width, height = round16(width * 1.05), round16(height * 1.05)
        return f"{width}x{height}"

    def output_format(self, args):
        """Use --format, else the --output extension, else PNG, so the saved path matches --output."""
        suffix = Path(args.output).suffix.lower() if args.output else ""
        from_output = OUTPUT_EXTENSION_FORMATS.get(suffix)
        if args.format and from_output and args.format != from_output:
            raise UsageError(f"--format {args.format} conflicts with the --output extension {suffix}.")
        return args.format or from_output or "png"

    def validate_size(self, size):
        if size == "auto":
            return
        try:
            width, height = (int(part) for part in size.lower().split("x"))
        except ValueError:
            raise UsageError(f"Invalid size '{size}'; use WIDTHxHEIGHT, for example 1536x1024.")
        if width <= 0 or height <= 0:
            raise UsageError(f"Invalid size '{size}'; both edges must be positive.")
        if width % 16 or height % 16:
            raise UsageError(f"Size {size} is invalid: both edges must be multiples of 16.")
        if max(width, height) > self.max_edge:
            raise UsageError(f"Size {size} is invalid: edges must be at most {self.max_edge}px.")
        if max(width, height) / min(width, height) > 3:
            raise UsageError(f"Size {size} is invalid: aspect ratio must be at most 3:1.")
        if not self.min_pixels <= width * height <= self.max_pixels:
            raise UsageError(
                f"Size {size} is invalid: total pixels must be between "
                f"{self.min_pixels:,} and {self.max_pixels:,}.")

    def build(self, args):
        output_format = self.output_format(args)
        if args.transparent and output_format not in TRANSPARENT_FORMATS:
            raise UsageError("Transparent backgrounds require PNG or WebP output "
                             "(--format png|webp, or an --output path ending in .png or .webp).")
        if args.compression is not None and output_format == "png":
            raise UsageError("--compression applies only to jpeg or webp output.")
        if args.mask and not args.image:
            raise UsageError("--mask requires --image; it applies to the first input image.")

        size = self.size_for(args)
        self.validate_size(size)
        body = {
            "model": args.model,
            "prompt": args.prompt,
            "n": args.n,
            "size": size,
            "quality": args.quality,
            "output_format": output_format,
        }
        if args.transparent:
            body["background"] = "transparent"
        if args.compression is not None:
            body["output_compression"] = args.compression

        if not args.image:
            return "images/generations", body
        body["images"] = [
            {"image_url": image_reference(image, self.input_mimes, self.max_data_url_chars)}
            for image in args.image
        ]
        if args.mask:
            body["mask"] = {"image_url": data_url(args.mask, {"image/png"}, self.max_data_url_chars)}
        return "images/edits", body


class XAIProvider:
    name = "xai"
    label = "xAI Grok Imagine"
    env_key = "XAI_API_KEY"
    base_url_env = "XAI_BASE_URL"
    default_base_url = "https://api.x.ai/v1"
    default_model = "grok-imagine-image-2.0"
    model_prefixes = ("grok-",)
    qualities = ["low", "medium"]
    quality_models = {"grok-imagine-image-2.0"}
    max_images = 3
    max_n = 10
    input_mimes = {"image/png", "image/jpeg"}
    max_data_url_chars = 28 * 1024 * 1024  # about 20 MiB of raw image bytes

    def build(self, args):
        if args.transparent:
            raise UsageError(
                "xAI Grok Imagine cannot produce transparent backgrounds: it always returns an "
                "opaque image, and asking for transparency in the prompt only paints a fake "
                "checkerboard into the pixels. Use --provider openai (gpt-image-2.5-flare) for "
                "transparent output, or drop --transparent.")
        unsupported = [flag for flag, value in (
            ("--size", args.size), ("--format", args.format),
            ("--compression", args.compression), ("--mask", args.mask),
        ) if value is not None]
        if unsupported:
            raise UsageError(
                f"{', '.join(unsupported)} {'is' if len(unsupported) == 1 else 'are'} not supported "
                "by xAI; use --aspect-ratio/--resolution, or --provider openai.")
        if args.aspect_ratio not in (None, "auto", *COMMON_ASPECT_RATIOS):
            raise UsageError(
                f"xAI does not support aspect ratio {args.aspect_ratio}; use one of: "
                f"auto, {', '.join(COMMON_ASPECT_RATIOS)}.")

        body = {"model": args.model, "prompt": args.prompt, "n": args.n, "response_format": "b64_json"}
        if args.aspect_ratio:
            body["aspect_ratio"] = args.aspect_ratio
        if args.resolution:
            body["resolution"] = args.resolution
        # Only grok-imagine-image-2.0 accepts quality; the older models reject the field.
        if args.model in self.quality_models:
            body["quality"] = args.quality
        elif args.quality_explicit:
            raise UsageError(f"--quality is only supported by {', '.join(sorted(self.quality_models))}.")

        if not args.image:
            return "images/generations", body
        references = [
            {"url": image_reference(image, self.input_mimes, self.max_data_url_chars), "type": "image_url"}
            for image in args.image
        ]
        if len(references) == 1:
            body["image"] = references[0]
        else:
            body["images"] = references
        return "images/edits", body


PROVIDERS = {provider.name: provider for provider in (OpenAIProvider(), XAIProvider())}


def resolve_provider(args):
    """Pick the provider from --provider, else from the model name, else OpenAI.

    OpenAI is the default because it supports every shared option, including
    transparent backgrounds.
    """
    if args.provider:
        provider = PROVIDERS[args.provider]
        if args.model and not args.model.startswith(provider.model_prefixes):
            other = next((p for p in PROVIDERS.values() if args.model.startswith(p.model_prefixes)), None)
            if other:
                raise UsageError(f"Model {args.model} belongs to --provider {other.name}, not {provider.name}.")
        return provider
    if args.model:
        for provider in PROVIDERS.values():
            if args.model.startswith(provider.model_prefixes):
                return provider
        raise UsageError(f"Cannot infer the provider for model {args.model}; pass --provider.")
    return PROVIDERS["openai"]


def image_extension(content):
    """Return the file extension matching an image's magic bytes."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    raise RuntimeError("The API returned an image in an unrecognized format.")


def output_paths(output, prefix, extensions):
    """Create output paths whose extensions match the returned image bytes."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    names = [f"{prefix}-{timestamp}-{index + 1}{extension}" for index, extension in enumerate(extensions)]
    if output is None:
        return [DEFAULT_OUTPUT_DIR / name for name in names]

    destination = Path(output)
    # An extension means an explicit filename; otherwise it is a directory.
    if not destination.suffix:
        return [destination / name for name in names]
    # Keep the requested spelling when it names the same format (.jpeg or .JPG for .jpg).
    requested_format = OUTPUT_EXTENSION_FORMATS.get(destination.suffix.lower())
    extensions = [destination.suffix if requested_format == OUTPUT_EXTENSION_FORMATS[extension] else extension
                  for extension in extensions]
    if len(extensions) == 1:
        return [destination.with_suffix(extensions[0])]
    return [destination.with_name(f"{destination.stem}-{index + 1}{extension}")
            for index, extension in enumerate(extensions)]


def post_json(url, api_key, body, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            detail = parsed.get("error", parsed)
            if isinstance(detail, dict):
                detail = detail.get("message") or json.dumps(detail)
        except ValueError:
            pass
        hint = " (rate limited; wait and retry, or request fewer images)" if error.code == 429 else ""
        raise RuntimeError(f"HTTP {error.code}{hint}: {detail}") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach the API: {error.reason}") from None
    except TimeoutError:
        # Providers reply only once the image is finished, so large or max-quality
        # requests can exceed the read timeout.
        raise RuntimeError(f"No response within {timeout:g}s; retry with a larger --timeout.") from None
    except OSError as error:
        raise RuntimeError(f"Connection failed: {error}") from None
    try:
        return json.loads(raw)
    except ValueError:
        raise RuntimeError(f"The API returned a non-JSON response: {raw[:200]!r}") from None


def decode_images(response):
    images = []
    for item in response.get("data") or []:
        encoded = item.get("b64_json")
        if not encoded:
            raise RuntimeError("The API response did not include image data "
                               "(the request may have been filtered by moderation).")
        try:
            content = base64.b64decode(encoded)
        except ValueError:
            raise RuntimeError("The API returned invalid base64 image data.") from None
        images.append((content, image_extension(content)))
    if not images:
        raise RuntimeError("The API response did not include any images.")
    return images


def redact_images(body):
    """Shorten inline image data so dry runs stay readable."""
    def shorten(value):
        if isinstance(value, str) and value.startswith("data:") and len(value) > 80:
            return f"{value[:40]}...<{len(value)} chars>"
        if isinstance(value, dict):
            return {key: shorten(item) for key, item in value.items()}
        if isinstance(value, list):
            return [shorten(item) for item in value]
        return value
    return shorten(body)


def parse_extra(values):
    extra = {}
    for item in values:
        key, separator, raw = item.partition("=")
        if not separator or not key:
            raise UsageError(f"--extra expects KEY=VALUE, got '{item}'.")
        try:
            extra[key] = json.loads(raw)
        except ValueError:
            extra[key] = raw
    return extra


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate or edit images with OpenAI GPT Image (default) or xAI Grok Imagine.")
    parser.add_argument("prompt", nargs="+", help="Image-generation or image-editing instruction")
    parser.add_argument("--provider", choices=sorted(PROVIDERS),
                        help="openai (default) or xai; inferred from --model when omitted")
    parser.add_argument("--model", help="Model ID (default: gpt-image-2.5-flare for openai, "
                                        "grok-imagine-image-2.0 for xai)")
    parser.add_argument("--n", type=int, default=1, help="Number of images (default: 1, max: 10)")
    parser.add_argument("--aspect-ratio", help="W:H ratio such as 1:1, 16:9, 9:16, or auto")
    parser.add_argument("--resolution", choices=["1k", "2k"], help="Output resolution tier")
    parser.add_argument("--size", help="Exact WIDTHxHEIGHT (openai only; overrides aspect ratio/resolution)")
    parser.add_argument("--quality", help="openai: low, medium, high, xhigh, max, auto; "
                                          "xai: low, medium (default: medium)")
    parser.add_argument("--transparent", action="store_true",
                        help="Transparent background (openai only; png or webp output)")
    parser.add_argument("--format", choices=["png", "jpeg", "webp"], help="Output format (openai only; default: png)")
    parser.add_argument("--compression", type=int, help="0-100 for jpeg/webp output (openai only)")
    parser.add_argument("--image", action="append",
                        help="Input image path or URL to edit or use as a reference; repeatable "
                             "(openai: up to 16, xai: up to 3)")
    parser.add_argument("--mask", help="PNG mask for the first --image; transparent pixels mark the edit area (openai only)")
    parser.add_argument("--extra", action="append", default=[], metavar="KEY=VALUE",
                        help="Extra provider request field; VALUE is parsed as JSON when possible. Repeatable.")
    parser.add_argument("--output", "-o", help="Output file (one image) or directory/prefix (multiple)")
    parser.add_argument("--timeout", type=float, default=300, help="Request timeout in seconds (default: 300)")
    parser.add_argument("--dry-run", action="store_true", help="Print the request without calling the API")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print structured result metadata")
    return parser


def build_request(provider, args):
    """Validate args for one provider and return (endpoint, body) without modifying args."""
    args = copy.copy(args)
    args.model = args.model or provider.default_model
    args.quality_explicit = args.quality is not None
    args.quality = args.quality or "medium"
    if args.quality not in provider.qualities:
        raise UsageError(f"{provider.label} supports --quality {', '.join(provider.qualities)}.")
    if not 1 <= args.n <= provider.max_n:
        raise UsageError(f"--n must be between 1 and {provider.max_n}.")
    if args.image and len(args.image) > provider.max_images:
        raise UsageError(f"{provider.label} accepts at most {provider.max_images} input images.")
    if args.compression is not None and not 0 <= args.compression <= 100:
        raise UsageError("--compression must be between 0 and 100.")
    endpoint, body = provider.build(args)
    for key, value in parse_extra(args.extra).items():
        if key in RESERVED_FIELDS or key in body:
            owner = RESERVED_FIELDS.get(key, "another option")
            raise UsageError(f"--extra cannot set '{key}'; it is controlled by {owner}.")
        body[key] = value
    return endpoint, body


def accepts(provider, args):
    """Whether the provider, with its default model, can serve this request."""
    candidate = copy.copy(args)
    candidate.provider, candidate.model = provider.name, None
    try:
        build_request(provider, candidate)
    except UsageError:
        return False
    return True


def fallback_provider(provider, args):
    """Switch from the default provider when only the other provider's key is set.

    Applies only when neither --provider nor --model was given and the other
    provider supports every requested option (so --transparent never falls back).
    """
    if args.provider or args.model or os.environ.get(provider.env_key):
        return None
    other = next(p for p in PROVIDERS.values() if p is not provider)
    if os.environ.get(other.env_key) and accepts(other, args):
        return other
    return None


def prepare(args):
    """Resolve the provider and build (provider, endpoint, body) or raise UsageError."""
    args.prompt = " ".join(args.prompt) if isinstance(args.prompt, list) else args.prompt
    provider = resolve_provider(args)
    fallback = fallback_provider(provider, args)
    if fallback:
        print(f"Note: {provider.env_key} is not set; using --provider {fallback.name} "
              f"({fallback.default_model}) instead.", file=sys.stderr)
        provider = fallback
    endpoint, body = build_request(provider, args)
    return provider, endpoint, body


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        provider, endpoint, body = prepare(args)
    except UsageError as error:
        parser.error(str(error))

    base_url = os.environ.get(provider.base_url_env, provider.default_base_url).rstrip("/")
    url = f"{base_url}/{endpoint}"
    if args.dry_run:
        print(json.dumps({"provider": provider.name, "url": url, "body": redact_images(body)}, indent=2))
        return

    api_key = os.environ.get(provider.env_key)
    if not api_key:
        other = next(p for p in PROVIDERS.values() if p is not provider)
        print(f"Error: {provider.env_key} is required for --provider {provider.name}.", file=sys.stderr)
        if os.environ.get(other.env_key) and accepts(other, args):
            print(f"{other.env_key} is set, and --provider {other.name} ({other.default_model}) "
                  "supports this request.", file=sys.stderr)
        sys.exit(1)

    try:
        response = post_json(url, api_key, body, args.timeout)
        images = decode_images(response)
    except RuntimeError as error:
        print(f"Error: {provider.label} request failed: {error}", file=sys.stderr)
        sys.exit(1)

    paths = output_paths(args.output, provider.name, [extension for _, extension in images])
    requested = Path(args.output) if args.output else None
    if requested and requested.suffix and paths[0].suffix != requested.suffix:
        # xAI chooses its own output format, so the extension can differ from --output.
        print(f"Note: {provider.label} returned {paths[0].suffix[1:].upper()} data, so the file is saved "
              f"with a {paths[0].suffix} extension; use the printed path.", file=sys.stderr)
    results = []
    for (content, _), path in zip(images, paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        results.append({"path": str(path), "bytes": len(content)})

    if args.json_output:
        metadata = {key: value for key, value in response.items() if key != "data"}
        print(json.dumps({
            "provider": provider.name,
            "model": body["model"],
            "prompt": args.prompt,
            "request": {key: value for key, value in redact_images(body).items() if key != "prompt"},
            "response": metadata,
            "images": results,
        }, indent=2))
    else:
        for result in results:
            print(result["path"])


if __name__ == "__main__":
    main()
