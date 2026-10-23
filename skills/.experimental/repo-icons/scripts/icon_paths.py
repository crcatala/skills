"""Where tools look for a repository's icon, and how a repo's file list is classified.

Pure functions over a list of repository-relative paths, shared by scan.py and
apply_icon.py. No network or filesystem access here, so it is easy to test.

The lookup order mirrors T3 Code's project icon resolver
(pingdotgg/t3code, apps/server/src/project/ProjectFaviconResolver.ts). GitHub
itself has no repository icon; the README header image is a separate, purely
visual convention.
"""

import re

# Checked in order; the first existing file wins.
WELL_KNOWN_ICON_PATHS = (
    "favicon.svg",
    "favicon.ico",
    "favicon.png",
    "public/favicon.svg",
    "public/favicon.ico",
    "public/favicon.png",
    "app/favicon.ico",
    "app/favicon.png",
    "app/icon.svg",
    "app/icon.png",
    "app/icon.ico",
    "src/favicon.ico",
    "src/favicon.svg",
    "src/app/favicon.ico",
    "src/app/icon.svg",
    "src/app/icon.png",
    "assets/icon.svg",
    "assets/icon.png",
    "assets/logo.svg",
    "assets/logo.png",
    ".idea/icon.svg",
    "Resources/AppIcon.icns",
    "AppIcon.icns",
)

# Checked after the well-known paths: a <link rel="icon" href="..."> in one of
# these files, resolved under public/ and then the repo root.
ICON_SOURCE_FILES = (
    "index.html",
    "public/index.html",
    "app/routes/__root.tsx",
    "src/routes/__root.tsx",
    "app/root.tsx",
    "src/root.tsx",
    "src/index.html",
)

# Repo-level override, checked before the well-known paths.
PROJECT_FILE = "t3.json"

IMAGE_EXTENSIONS = (".svg", ".png", ".ico", ".icns", ".webp", ".jpg", ".jpeg", ".gif", ".avif")

_LINK_ICON_RE = re.compile(
    r"<link\b(?=[^>]*\brel=[\"'](?:icon|shortcut icon)[\"'])(?=[^>]*\bhref=[\"']([^\"'?]+))[^>]*>",
    re.I,
)
_OBJ_REL_RE = re.compile(r"\brel\s*:\s*[\"'](?:icon|shortcut icon)[\"']", re.I)
_OBJ_HREF_RE = re.compile(r"\bhref\s*:\s*[\"']([^\"'?]+)", re.I)

_LOGO_NAME_RE = re.compile(
    r"(^|/)[^/]*(logo|icon|favicon|brand|mark|emblem|mascot)[^/]*\.(svg|png|ico|icns|webp|jpe?g)$",
    re.I,
)
_LOGO_NOISE_RE = re.compile(
    r"(^|/)(node_modules|vendor|third_party|dist|build|coverage|fixtures?|__snapshots__|"
    r"test|tests|spec|\.github)/|"
    r"(^|/)(icons?)/(?!icon\.)|"  # icon packs: icons/arrow.svg, not icons/icon.png
    r"\d+x\d+",  # sized platform variants such as Square150x150Logo.png
    re.I,
)


def extract_icon_href(source):
    """Return the href of the first rel="icon" link in HTML or a JS object literal."""
    match = _LINK_ICON_RE.search(source)
    if match:
        return match.group(1)
    for run in source.split("}"):
        if _OBJ_REL_RE.search(run):
            href = _OBJ_HREF_RE.search(run)
            if href:
                return href.group(1)
    return None


def resolve_icon_href(href, paths):
    """Map an icon href to a file in the repo, as T3 Code does. None if absent."""
    if href.startswith("data:"):
        return None
    clean = href.lstrip("/")
    for candidate in ("public/" + clean, clean):
        if candidate in paths:
            return candidate
    return None


def find_well_known(paths):
    """First well-known icon path present in the repo, or None."""
    for candidate in WELL_KNOWN_ICON_PATHS:
        if candidate in paths:
            return candidate
    return None


def shadowing_paths(paths, target):
    """Well-known paths that exist and would be picked before `target`."""
    if target not in WELL_KNOWN_ICON_PATHS:
        return []
    earlier = WELL_KNOWN_ICON_PATHS[: WELL_KNOWN_ICON_PATHS.index(target)]
    return [p for p in earlier if p in paths]


def logo_like(paths, exclude=(), limit=5):
    """Files whose names look like a logo or icon, outside vendored/test noise.

    Shallower paths and SVGs sort first: they are the likeliest originals.
    """
    hits = [
        p
        for p in paths
        if _LOGO_NAME_RE.search(p) and not _LOGO_NOISE_RE.search(p) and p not in exclude
    ]
    hits.sort(key=lambda p: (p.count("/"), not p.lower().endswith(".svg"), p))
    return hits[:limit]


def classify(paths, read_file):
    """Classify a repository's icon state.

    paths: set of repository-relative file paths.
    read_file: callable(path) -> str or None, used for t3.json and icon source files.

    Returns a dict:
      status:   "ok" (a tool like T3 Code finds an icon), "nonstandard" (logo-like
                files exist but nothing standard), or "none"
      icon:     path that would be used (status "ok"), else None
      via:      how it was found: "t3.json", "well-known", or the source file name
      note:     extra detail, for example an inline data: favicon
      logos:    other logo-like files worth reusing
    """
    paths = set(paths)
    result = {"status": "none", "icon": None, "via": None, "note": None, "logos": []}

    if PROJECT_FILE in paths:
        import json

        try:
            icon_path = (json.loads(read_file(PROJECT_FILE) or "{}") or {}).get("iconPath")
        except (ValueError, AttributeError):
            icon_path = None
            result["note"] = "t3.json does not parse"
        if icon_path and icon_path.strip() in paths:
            result.update(status="ok", icon=icon_path.strip(), via="t3.json")

    if result["status"] != "ok":
        found = find_well_known(paths)
        if found:
            result.update(status="ok", icon=found, via="well-known")

    if result["status"] != "ok":
        for source in ICON_SOURCE_FILES:
            if source not in paths:
                continue
            href = extract_icon_href(read_file(source) or "")
            if not href:
                continue
            if href.startswith("data:"):
                result["note"] = f"{source} uses an inline data: favicon, which T3 Code cannot use"
                continue
            target = resolve_icon_href(href, paths)
            if target:
                result.update(status="ok", icon=target, via=source)
                break

    result["logos"] = logo_like(paths, exclude={result["icon"]})
    if result["status"] == "none" and result["logos"]:
        result["status"] = "nonstandard"
    return result
