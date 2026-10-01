import base64
import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import generate

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


BOTH_KEYS = {"OPENAI_API_KEY": "test-openai", "XAI_API_KEY": "test-xai"}


def prepare(*argv, env=BOTH_KEYS):
    """Run prepare() with only the given API keys set, capturing any stderr note."""
    args = generate.build_parser().parse_args(["a prompt", *argv])
    environment = {key: value for key, value in os.environ.items() if key not in BOTH_KEYS}
    with mock.patch.dict(os.environ, {**environment, **env}, clear=True), \
            contextlib.redirect_stderr(io.StringIO()):
        return generate.prepare(args)


class ProviderResolutionTests(unittest.TestCase):
    def test_defaults_to_openai_flare(self):
        provider, endpoint, body = prepare()
        self.assertEqual(provider.name, "openai")
        self.assertEqual(endpoint, "images/generations")
        self.assertEqual(body["model"], "gpt-image-2.5-flare")
        self.assertEqual(body["quality"], "medium")

    def test_transparent_without_provider_uses_openai(self):
        provider, _, body = prepare("--transparent")
        self.assertEqual(provider.name, "openai")
        self.assertEqual(body["background"], "transparent")
        self.assertEqual(body["output_format"], "png")

    def test_infers_xai_from_grok_model(self):
        provider, _, body = prepare("--model", "grok-imagine-image-quality")
        self.assertEqual(provider.name, "xai")
        self.assertNotIn("quality", body)

    def test_xai_defaults_to_grok_imagine_2(self):
        provider, _, body = prepare("--provider", "xai")
        self.assertEqual(body["model"], "grok-imagine-image-2.0")
        self.assertEqual(body["quality"], "medium")
        self.assertEqual(body["response_format"], "b64_json")
        self.assertNotIn("aspect_ratio", body)

    def test_rejects_mismatched_provider_and_model(self):
        with self.assertRaisesRegex(generate.UsageError, "belongs to --provider xai"):
            prepare("--provider", "openai", "--model", "grok-imagine-image-2.0")

    def test_rejects_unknown_model_without_provider(self):
        with self.assertRaisesRegex(generate.UsageError, "Cannot infer"):
            prepare("--model", "mystery-model")


class KeyFallbackTests(unittest.TestCase):
    XAI_ONLY = {"XAI_API_KEY": "test-xai"}

    def test_falls_back_to_xai_when_only_its_key_is_set(self):
        provider, _, body = prepare(env=self.XAI_ONLY)
        self.assertEqual(provider.name, "xai")
        self.assertEqual(body["model"], "grok-imagine-image-2.0")

    def test_fallback_is_announced_on_stderr(self):
        args = generate.build_parser().parse_args(["a prompt"])
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, self.XAI_ONLY, clear=True), contextlib.redirect_stderr(stderr):
            generate.prepare(args)
        self.assertIn("OPENAI_API_KEY is not set; using --provider xai", stderr.getvalue())

    def test_no_fallback_when_request_needs_openai(self):
        for argv in (["--transparent"], ["--size", "1536x864"], ["--quality", "max"], ["--format", "webp"]):
            provider, _, _ = prepare(*argv, env=self.XAI_ONLY)
            self.assertEqual(provider.name, "openai", argv)

    def test_no_fallback_when_provider_or_model_is_explicit(self):
        self.assertEqual(prepare("--provider", "openai", env=self.XAI_ONLY)[0].name, "openai")
        self.assertEqual(prepare("--model", "gpt-image-2.5-sunburst", env=self.XAI_ONLY)[0].name, "openai")

    def test_no_fallback_without_either_key_or_with_openai_key(self):
        self.assertEqual(prepare(env={})[0].name, "openai")
        self.assertEqual(prepare(env={"OPENAI_API_KEY": "test-openai"})[0].name, "openai")

    def test_accepts_reports_whether_the_other_provider_can_serve_a_request(self):
        parser = generate.build_parser()
        xai = generate.PROVIDERS["xai"]
        self.assertTrue(generate.accepts(xai, parser.parse_args(["a prompt", "--aspect-ratio", "16:9"])))
        self.assertFalse(generate.accepts(xai, parser.parse_args(["a prompt", "--transparent"])))


class TransparencyTests(unittest.TestCase):
    def test_xai_refuses_transparency_and_points_to_openai(self):
        for argv in (["--provider", "xai"], ["--model", "grok-imagine-image-2.0"]):
            with self.assertRaisesRegex(generate.UsageError, "cannot produce transparent.*--provider openai"):
                prepare("--transparent", *argv)

    def test_transparency_requires_alpha_format(self):
        with self.assertRaisesRegex(generate.UsageError, "PNG or WebP"):
            prepare("--transparent", "--format", "jpeg")
        with self.assertRaisesRegex(generate.UsageError, "PNG or WebP"):
            prepare("--transparent", "--output", "icon.jpg")
        _, _, body = prepare("--transparent", "--format", "webp")
        self.assertEqual(body["output_format"], "webp")


class OpenAISizeTests(unittest.TestCase):
    def size(self, *argv):
        return prepare(*argv)[2]["size"]

    def test_auto_when_no_shape_requested(self):
        self.assertEqual(self.size(), "auto")
        self.assertEqual(self.size("--aspect-ratio", "auto"), "auto")

    def test_maps_ratio_and_resolution_to_valid_sizes(self):
        self.assertEqual(self.size("--aspect-ratio", "1:1"), "1024x1024")
        self.assertEqual(self.size("--aspect-ratio", "16:9", "--resolution", "2k"), "2048x1152")
        self.assertEqual(self.size("--aspect-ratio", "9:16", "--resolution", "2k"), "1152x2048")
        self.assertEqual(self.size("--resolution", "2k"), "2048x2048")
        for ratio in generate.COMMON_ASPECT_RATIOS + ["21:9", "3:1", "1:3"]:
            for resolution in ("1k", "2k"):
                size = self.size("--aspect-ratio", ratio, "--resolution", resolution)
                generate.PROVIDERS["openai"].validate_size(size)

    def test_explicit_size_is_validated(self):
        self.assertEqual(self.size("--size", "1536x864"), "1536x864")
        for bad in ("1000x1000", "4096x2160", "3840x960", "640x640", "big", "0x0", "16x0"):
            with self.assertRaises(generate.UsageError):
                self.size("--size", bad)

    def test_rejects_ratio_beyond_three_to_one(self):
        with self.assertRaisesRegex(generate.UsageError, "3:1"):
            self.size("--aspect-ratio", "4:1")

    def test_rejects_non_finite_or_zero_ratios(self):
        for bad in ("nan:1", "inf:1", "0:1", "16:", "wide"):
            with self.assertRaisesRegex(generate.UsageError, "Invalid aspect ratio"):
                self.size("--aspect-ratio", bad)


class OptionValidationTests(unittest.TestCase):
    def test_xai_rejects_openai_only_options(self):
        for argv in (["--size", "1024x1024"], ["--format", "png"], ["--compression", "80"]):
            with self.assertRaisesRegex(generate.UsageError, "not supported by xAI"):
                prepare("--provider", "xai", *argv)

    def test_xai_rejects_unsupported_ratio(self):
        with self.assertRaisesRegex(generate.UsageError, "does not support aspect ratio 21:9"):
            prepare("--provider", "xai", "--aspect-ratio", "21:9")

    def test_quality_is_checked_per_provider(self):
        self.assertEqual(prepare("--quality", "max")[2]["quality"], "max")
        with self.assertRaisesRegex(generate.UsageError, "low, medium"):
            prepare("--provider", "xai", "--quality", "high")
        with self.assertRaisesRegex(generate.UsageError, "only supported by"):
            prepare("--model", "grok-imagine-image", "--quality", "low")

    def test_compression_only_for_lossy_formats(self):
        with self.assertRaisesRegex(generate.UsageError, "jpeg or webp"):
            prepare("--compression", "80")
        self.assertEqual(prepare("--format", "jpeg", "--compression", "80")[2]["output_compression"], 80)

    def test_limits_n_and_input_images(self):
        with self.assertRaises(generate.UsageError):
            prepare("--n", "11")
        urls = [arg for index in range(4) for arg in ("--image", f"https://example.com/{index}.png")]
        with self.assertRaisesRegex(generate.UsageError, "at most 3"):
            prepare("--provider", "xai", *urls)

    def test_extra_fields_are_json_parsed(self):
        _, _, body = prepare("--extra", "moderation=low", "--extra", "partial_images=0")
        self.assertEqual(body["moderation"], "low")
        self.assertEqual(body["partial_images"], 0)

    def test_extra_cannot_override_validated_fields(self):
        for argv in (["--provider", "xai", "--extra", "background=transparent"],
                     ["--provider", "xai", "--extra", "output_format=png"],
                     ["--extra", "model=dall-e-3"],
                     ["--extra", "size=4096x4096"],
                     ["--provider", "xai", "--extra", "response_format=url"]):
            with self.assertRaisesRegex(generate.UsageError, "--extra cannot set"):
                prepare(*argv)

    def test_dall_e_models_are_not_inferred_as_openai(self):
        with self.assertRaisesRegex(generate.UsageError, "Cannot infer"):
            prepare("--model", "dall-e-3")


class EditRequestTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.source = Path(self.directory.name) / "source.png"
        self.source.write_bytes(PNG_BYTES)

    def tearDown(self):
        self.directory.cleanup()

    def test_openai_edit_uses_images_array_and_mask(self):
        _, endpoint, body = prepare("--image", str(self.source), "--image", "https://example.com/b.jpg",
                                    "--mask", str(self.source))
        self.assertEqual(endpoint, "images/edits")
        self.assertTrue(body["images"][0]["image_url"].startswith("data:image/png;base64,"))
        self.assertEqual(body["images"][1], {"image_url": "https://example.com/b.jpg"})
        self.assertTrue(body["mask"]["image_url"].startswith("data:image/png;base64,"))

    def test_mask_requires_image(self):
        with self.assertRaisesRegex(generate.UsageError, "requires --image"):
            prepare("--mask", str(self.source))

    def test_xai_single_and_multi_reference_shapes(self):
        _, endpoint, body = prepare("--provider", "xai", "--image", str(self.source))
        self.assertEqual(endpoint, "images/edits")
        self.assertEqual(body["image"]["type"], "image_url")
        self.assertNotIn("images", body)
        _, _, body = prepare("--provider", "xai", "--image", str(self.source), "--image", "https://example.com/b.png")
        self.assertEqual(len(body["images"]), 2)
        self.assertNotIn("image", body)

    def test_rejects_missing_and_unsupported_inputs(self):
        with self.assertRaisesRegex(generate.UsageError, "does not exist"):
            prepare("--image", str(Path(self.directory.name) / "missing.png"))
        webp = Path(self.directory.name) / "source.webp"
        webp.write_bytes(b"RIFF0000WEBP")
        prepare("--image", str(webp))
        with self.assertRaisesRegex(generate.UsageError, "Unsupported input image type"):
            prepare("--provider", "xai", "--image", str(webp))


class OutputFormatTests(unittest.TestCase):
    def test_openai_format_follows_output_extension(self):
        self.assertEqual(prepare("--output", "hero.webp")[2]["output_format"], "webp")
        self.assertEqual(prepare("--output", "hero.JPG")[2]["output_format"], "jpeg")
        self.assertEqual(prepare("--output", "assets/batch")[2]["output_format"], "png")
        self.assertEqual(prepare("--format", "webp", "--output", "hero.webp")[2]["output_format"], "webp")

    def test_openai_rejects_format_conflicting_with_output(self):
        with self.assertRaisesRegex(generate.UsageError, "conflicts with the --output extension"):
            prepare("--format", "png", "--output", "hero.webp")


class PostJsonTests(unittest.TestCase):
    def post(self, **urlopen):
        with mock.patch.object(generate.urllib.request, "urlopen", **urlopen):
            return generate.post_json("https://api.example.test/v1/images", "key", {}, 5)

    def response(self, payload):
        context = mock.MagicMock()
        context.__enter__.return_value.read.return_value = payload
        return context

    def http_error(self, code, payload):
        return urllib.error.HTTPError("https://api.example.test", code, "error", {}, io.BytesIO(payload))

    def test_returns_parsed_json(self):
        self.assertEqual(self.post(return_value=self.response(b'{"data": []}')), {"data": []})

    def test_read_timeout_becomes_a_clear_error(self):
        with self.assertRaisesRegex(RuntimeError, "No response within 5s; retry with a larger --timeout"):
            self.post(side_effect=TimeoutError("timed out"))

    def test_non_json_response_becomes_a_clear_error(self):
        with self.assertRaisesRegex(RuntimeError, "non-JSON response"):
            self.post(return_value=self.response(b"<html>bad gateway</html>"))

    def test_http_error_reports_provider_message(self):
        payload = json.dumps({"error": {"message": "Invalid size"}}).encode()
        with self.assertRaisesRegex(RuntimeError, "HTTP 400: Invalid size"):
            self.post(side_effect=self.http_error(400, payload))

    def test_rate_limit_adds_hint(self):
        with self.assertRaisesRegex(RuntimeError, "HTTP 429 \\(rate limited"):
            self.post(side_effect=self.http_error(429, b"slow down"))

    def test_connection_errors_become_clear_errors(self):
        with self.assertRaisesRegex(RuntimeError, "Could not reach the API"):
            self.post(side_effect=urllib.error.URLError("name resolution failed"))
        with self.assertRaisesRegex(RuntimeError, "Connection failed"):
            self.post(side_effect=ConnectionResetError("reset by peer"))


class OutputTests(unittest.TestCase):
    def test_detects_formats(self):
        self.assertEqual(generate.image_extension(PNG_BYTES), ".png")
        self.assertEqual(generate.image_extension(b"\xff\xd8\xff\xe0"), ".jpg")
        self.assertEqual(generate.image_extension(b"RIFF\x00\x00\x00\x00WEBPVP8 "), ".webp")
        with self.assertRaises(RuntimeError):
            generate.image_extension(b"GIF89a")

    def test_output_paths(self):
        self.assertEqual(generate.output_paths("out/hero.jpg", "openai", [".png"]), [Path("out/hero.png")])
        self.assertEqual(generate.output_paths("out/icon.png", "xai", [".jpg", ".jpg"]),
                         [Path("out/icon-1.jpg"), Path("out/icon-2.jpg")])
        self.assertEqual(generate.output_paths("out/hero.jpeg", "openai", [".jpg"]), [Path("out/hero.jpeg")])
        self.assertEqual(generate.output_paths("out/HERO.PNG", "openai", [".png"]), [Path("out/HERO.PNG")])
        self.assertEqual(generate.output_paths("out/alley.jpg", "xai", [".png", ".jpg"]),
                         [Path("out/alley-1.png"), Path("out/alley-2.jpg")])
        default = generate.output_paths(None, "xai", [".jpg"])[0]
        self.assertEqual(default.parent, generate.DEFAULT_OUTPUT_DIR)
        self.assertTrue(default.name.startswith("xai-"))
        directory = generate.output_paths("out/batch", "openai", [".png"])[0]
        self.assertEqual(directory.parent, Path("out/batch"))

    def test_decode_images_reports_missing_data(self):
        encoded = base64.b64encode(PNG_BYTES).decode()
        self.assertEqual(generate.decode_images({"data": [{"b64_json": encoded}]})[0][1], ".png")
        for response in ({"data": []}, {"data": [{"url": "https://example.com/x.png"}]},
                         {"data": [{"b64_json": "not base64!"}]}):
            with self.assertRaises(RuntimeError):
                generate.decode_images(response)

    def test_dry_run_redacts_inline_images(self):
        body = {"images": [{"image_url": "data:image/png;base64," + "A" * 200}]}
        redacted = generate.redact_images(body)["images"][0]["image_url"]
        self.assertIn("<222 chars>", redacted)


if __name__ == "__main__":
    unittest.main()
