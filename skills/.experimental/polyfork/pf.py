#!/usr/bin/env python3
"""Polyfork catalogue client: search, inspect and vendor low poly 3D assets into a project.

Standard library only. Browsing and low poly files need no key. POLYFORK_API_KEY (sent as a
Bearer token) unlocks kit zips (free account) and HD editions (Pro or Lifetime).

    pf.py search "wooden barrel" --class prop
    pf.py get barrel-8d63c4
    pf.py vendor barrel-8d63c4 --dest public/models/polyfork
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ORIGIN = "https://polyfork.dev"
MANIFEST = "polyfork.manifest.json"
LICENSE_NOTE = ("Polyfork licence (https://polyfork.dev/licensing): ship these files inside your game; "
                "do not redistribute them as standalone assets.")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}$")
CLASSES = ["prop", "building", "vehicle", "character", "animal", "ultra", "attachment", "terrain", "hand"]
MESH_FORMATS = ["fbx", "usdz", "usda", "obj"]
TIMEOUT = 60


class PfError(Exception):
    pass


# ---------------------------------------------------------------- HTTP

def check_url(url):
    """Only ever talk to polyfork.dev over https, whatever a response points at."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc != "polyfork.dev":
        raise PfError(f"refusing non-Polyfork URL: {url}")
    return url


def fetch_bytes(url, auth=False):
    check_url(url)
    headers = {"User-Agent": "polyfork-skill/1 (+agent skill)", "Accept": "*/*"}
    if auth:
        key = os.environ.get("POLYFORK_API_KEY", "")
        if not key:
            raise PfError(f"{url} needs POLYFORK_API_KEY (a free account for kit zips, Pro/Lifetime for HD)")
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            body = json.loads(e.read().decode("utf-8", "replace"))
            detail = body.get("error") or body.get("message") or body.get("note") or ""
        except Exception:
            pass
        raise PfError(f"HTTP {e.code} for {url}" + (f": {detail}" if detail else "")) from None
    except urllib.error.URLError as e:
        raise PfError(f"network error for {url}: {e.reason}") from None


def api(path, params=None, auth=False):
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "", False)})
    url = f"{ORIGIN}/api{path}" + (f"?{query}" if query else "")
    use_auth = auth or bool(os.environ.get("POLYFORK_API_KEY"))
    return json.loads(fetch_bytes(url, auth=use_auth))


def check_id(asset_id):
    if not ID_RE.match(asset_id or ""):
        raise PfError(f"not a Polyfork id: {asset_id!r} (ids look like barrel-8d63c4)")
    return asset_id


# ---------------------------------------------------------------- formatting

def size_str(size):
    if not size:
        return "?"
    return "x".join(f"{size.get(k, 0):g}" for k in ("x", "y", "z")) + "m"


def flags(row):
    out = []
    if row.get("has_skeleton"):
        out.append("skeleton")
    if row.get("has_rig"):
        out.append("rig")
    if row.get("has_ik"):
        out.append(f"ik:{row.get('ik_type')}")
    if row.get("remixable"):
        out.append("knobs")
    if row.get("hd"):
        out.append("hd")
    if row.get("has_night"):
        out.append("night")
    return ",".join(out) or "-"


def row_line(row):
    return (f"{row['id']}  |  {row.get('title', '')}  |  {row.get('class', '')}  |  "
            f"{row.get('triangles', '?')} tris  |  {size_str(row.get('size_m'))}  |  {flags(row)}")


def emit(data, as_json, render):
    if as_json:
        print(json.dumps(data, indent=1))
    else:
        render(data)


# ---------------------------------------------------------------- browse commands

def cmd_search(a):
    data = api("/assets", {"q": a.query, "class": a.cls, "kit": a.kit, "ik": a.ik,
                           "max_triangles": a.max_triangles, "per_page": a.limit})

    def render(d):
        for row in d.get("assets", []):
            print(row_line(row))
        print(f"-- {len(d.get('assets', []))} of {d.get('total', '?')}; coverage: {d.get('coverage', 'n/a')}")
        if d.get("coverage") in ("none", "poor", "filtered_out") and d.get("coverage_note"):
            print(f"-- {d['coverage_note']}")
    emit(data, a.json, render)


def cmd_get(a):
    d = api(f"/assets/{check_id(a.id)}")
    knobs = {}
    if d.get("params_url"):
        try:
            knobs = json.loads(fetch_bytes(check_url(d["params_url"])))
        except PfError as e:
            knobs = {"error": str(e)}
    if a.json:
        print(json.dumps({"asset": d, "params": knobs}, indent=1))
        return
    print(row_line(d))
    print(f"page: {d.get('page')}   thumbnail: {d.get('thumbnail')}")
    print(f"kit: {d.get('kit') or '-'}   draw calls: {d.get('draw_calls')}   mass: {d.get('mass_kg')} kg")
    if d.get("description"):
        print(f"about: {d['description']}")
    print(f"low poly: mjs {d.get('download', {}).get('mjs')}  glb {d.get('download', {}).get('glb')}")
    fmts = [k for k, v in (d.get("export_formats") or {}).items() if v.get("available")]
    print(f"other formats: {', '.join(fmts) or '-'}")
    if d.get("hd"):
        print(f"HD edition: {d['hd'].get('triangles')} tris (needs Pro/Lifetime key)")
    if d.get("has_skeleton"):
        print("animation: Mixamo-named humanoid skeleton; see SKILL.md 'Characters and animation'")
    elif d.get("animation"):
        print(f"animation: {d['animation']}")
    params = knobs.get("params") or {}
    if params:
        print("knobs:")
        for name, k in params.items():
            opts = k.get("options")
            extra = f" options={opts}" if opts else ""
            if k.get("min") is not None:
                extra += f" range={k.get('min')}..{k.get('max')}"
            print(f"  {name} ({k.get('type')}, default {k.get('default')!r}){extra}: {k.get('describe', '')}")
    if knobs.get("presets"):
        print(f"presets: {', '.join(knobs['presets'])}")


def cmd_matching(a):
    d = api(f"/assets/{check_id(a.id)}/matching")

    def render(d):
        for row in d.get("matches", [])[: a.limit]:
            print(row_line(row))
        if d.get("scene"):
            print(f"-- scene preview: {d['scene']}")
    emit(d, a.json, render)


def cmd_variant(a):
    d = api(f"/assets/{check_id(a.id)}/variant", {"want": a.want})

    def render(d):
        print(f"call: {d.get('call')}   confidence: {d.get('confidence')}")
        print(f"matched: {', '.join(d.get('matched') or []) or '-'}")
        if d.get("glb_note"):
            print(f"note: {d['glb_note']}")
    emit(d, a.json, render)


def cmd_kits(a):
    d = api("/kits")
    kits = d.get("kits", [])
    if a.query:
        q = a.query.lower()
        kits = [k for k in kits if q in k.get("title", "").lower() or q in k.get("id", "")]

    def render(_):
        for k in kits:
            print(f"{k['id']}  |  {k.get('title')}  |  {k.get('status')}  |  "
                  f"{k.get('parts_published')}/{k.get('parts_planned')} parts")
    emit({"kits": kits}, a.json, render)


def cmd_kit(a):
    d = api(f"/kits/{check_id(a.id)}")

    def render(d):
        print(f"{d.get('title')}  ({d.get('status')}, {len(d.get('parts', []))} parts)  {d.get('page')}")
        for row in d.get("parts", []):
            print(row_line(row))
    emit(d, a.json, render)


# ---------------------------------------------------------------- vendoring

COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
STATIC_IMPORT = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(\s*|^\s*import\s+)(['"])([^'"]+)\1""", re.M)
URL_IMPORT = re.compile(r"""new\s+URL\(\s*(['"])([^'"]+)\1\s*,\s*import\.meta\.url""")
POLYFORK_LITERAL = re.compile(r"""['"`](https://polyfork\.dev/[^'"`\s]*)""")


def strip_comments(src):
    src = COMMENT_BLOCK.sub("", src)
    return "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("//"))


def scan_module(src):
    """Return (relative deps, other specifiers, polyfork.dev URLs used at runtime)."""
    code = strip_comments(src)
    specs = [m.group(2) for m in STATIC_IMPORT.finditer(code)] + [m.group(2) for m in URL_IMPORT.finditer(code)]
    relative, other = [], []
    for s in specs:
        if s in (".", "./"):
            continue  # new URL('.', import.meta.url): the module's own folder, not a file
        if s.startswith("./") or s.startswith("../") or (s.endswith(".mjs") and "/" not in s and ":" not in s):
            relative.append(s if s.startswith(".") else f"./{s}")
        elif s == "three" or s.startswith("three/"):
            continue
        else:
            other.append(s)
    runtime = sorted({m.group(1) for m in POLYFORK_LITERAL.finditer(code)})
    return sorted(set(relative)), sorted(set(other)), runtime


def local_target(dest, root_url, url):
    """Map a dependency URL to a path under dest, refusing anything outside the root module's folder."""
    root_dir = PurePosixPath(urllib.parse.urlsplit(root_url).path).parent
    path = PurePosixPath(urllib.parse.urlsplit(url).path)
    try:
        rel = path.relative_to(root_dir)
    except ValueError:
        raise PfError(f"dependency {url} is outside {root_dir}/; vendor it by hand if you need it") from None
    if ".." in rel.parts or not rel.parts:
        raise PfError(f"unsafe dependency path: {url}")
    return Path(dest, *rel.parts)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def vendor_module(url, dest, auth, files, warnings, root_url=None, seen=None):
    """Download an ES module and, recursively, the sibling modules it imports."""
    root_url = root_url or url
    seen = seen if seen is not None else set()
    if url in seen:
        return
    seen.add(url)
    try:
        data = fetch_bytes(url, auth=auth)
    except PfError as e:
        if url == root_url:
            raise
        # kit.mjs, for one, imports some siblings only when they exist (in a kit zip, not on the CDN).
        warnings.append(f"skipped dependency {PurePosixPath(url).name}: {e}")
        return
    target = local_target(dest, root_url, url)
    write_file(target, data)
    files[target.relative_to(dest).as_posix()] = {"url": url, "sha256": sha256(data)}
    relative, other, runtime = scan_module(data.decode("utf-8", "replace"))
    name = target.name
    for spec in other:
        warnings.append(f"{name} imports {spec!r}: not vendored; resolve it yourself")
    for ref in runtime:
        warnings.append(f"{name} reaches {ref} at runtime: the game still depends on polyfork.dev for that")
    for spec in relative:
        vendor_module(urllib.parse.urljoin(url, spec), dest, auth, files, warnings, root_url, seen)


def load_manifest(dest):
    path = Path(dest, MANIFEST)
    if path.exists():
        return json.loads(path.read_text())
    return {"source": ORIGIN, "license": LICENSE_NOTE, "assets": {}, "helpers": {}, "kits": {}}


def save_manifest(dest, manifest):
    for key in ("assets", "helpers", "kits"):
        manifest.setdefault(key, {})
        manifest[key] = dict(sorted(manifest[key].items()))
    write_file(Path(dest, MANIFEST), (json.dumps(manifest, indent=2) + "\n").encode())


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def vendor_asset(asset_id, dest, formats, hd=False, bake=None):
    d = api(f"/assets/{check_id(asset_id)}")
    files, warnings = {}, []
    if hd and not d.get("hd"):
        raise PfError(f"{asset_id} has no HD edition")
    for fmt in formats:
        if fmt == "mjs":
            url = f"{ORIGIN}/dl/{asset_id}-hd.mjs" if hd else d["download"]["mjs"]
            vendor_module(check_url(url), dest, hd, files, warnings)
        elif fmt == "glb":
            url = f"{ORIGIN}/dl/{asset_id}-hd.glb" if hd else d["download"]["glb"]
            data = fetch_bytes(check_url(url), auth=hd)
            write_file(Path(dest, PurePosixPath(url).name), data)
            files[PurePosixPath(url).name] = {"url": url, "sha256": sha256(data)}
        elif fmt in MESH_FORMATS:
            if hd:
                raise PfError(f"--hd supports mjs and glb only, not {fmt}")
            info = (d.get("export_formats") or {}).get(fmt) or {}
            if not info.get("available"):
                raise PfError(f"{asset_id} has no {fmt} export")
            for url in filter(None, [info.get("url"), info.get("also_fetch")]):
                data = fetch_bytes(check_url(url))
                name = PurePosixPath(urllib.parse.urlsplit(url).path).name
                write_file(Path(dest, name), data)
                files[name] = {"url": url, "sha256": sha256(data)}
        else:
            raise PfError(f"unknown format {fmt!r}")
    if bake:
        query = urllib.parse.urlencode(urllib.parse.parse_qsl(bake, keep_blank_values=True))
        url = f"{ORIGIN}/cdn/{asset_id}-remix.glb?{query}"
        data = fetch_bytes(check_url(url), auth=bool(os.environ.get("POLYFORK_API_KEY")))
        name = f"{asset_id}.remix-{sha256(bake.encode())[:8]}.glb"
        write_file(Path(dest, name), data)
        files[name] = {"url": url, "sha256": sha256(data), "bake": bake}
    if d.get("params_url"):
        data = fetch_bytes(check_url(d["params_url"]))
        name = f"{asset_id}-params.json"
        write_file(Path(dest, name), data)
        files[name] = {"url": d["params_url"], "sha256": sha256(data)}
    entry = {"title": d.get("title"), "class": d.get("class"), "kit": d.get("kit"),
             "edition": "hd" if hd else "low", "has_skeleton": bool(d.get("has_skeleton")),
             "files": files, "vendored_at": now()}
    if d.get("has_skeleton"):
        warnings.append(f"{asset_id} is a character: animation clips are NOT vendored (see SKILL.md)")
    return entry, warnings


def cmd_vendor(a):
    dest = Path(a.dest)
    manifest = load_manifest(dest)
    formats = a.format or ["mjs"]
    all_warnings = []
    for asset_id in a.ids:
        entry, warnings = vendor_asset(asset_id, dest, formats, hd=a.hd, bake=a.bake)
        key = f"{asset_id}-hd" if a.hd else asset_id
        manifest["assets"][key] = entry
        save_manifest(dest, manifest)
        print(f"vendored {key}: {', '.join(entry['files'])}")
        all_warnings += warnings
    report_warnings(all_warnings)
    print(f"manifest: {dest / MANIFEST}")


HELPERS_NOTE = {
    "clips": ("clips.mjs fetches its clip data from polyfork.dev at runtime by design (Mixamo-derived, "
              "not redistributed as files). For an offline game, use mixamo.mjs with clips you download "
              "from Mixamo yourself, or CC0 clips."),
}


def cmd_helper(a):
    dest = Path(a.dest)
    manifest = load_manifest(dest)
    all_warnings = []
    for name in a.names:
        name = check_id(name.removesuffix(".mjs"))
        files, warnings = {}, []
        vendor_module(f"{ORIGIN}/cdn/{name}.mjs", dest, False, files, warnings)
        manifest["helpers"][name] = {"files": files, "vendored_at": now()}
        save_manifest(dest, manifest)
        print(f"vendored helper {name}: {', '.join(files)}")
        if "clips.mjs" in files:
            warnings.append(HELPERS_NOTE["clips"])
        all_warnings += warnings
    report_warnings(all_warnings)


def safe_extract(zf, dest):
    root = Path(dest).resolve()
    names = []
    for info in zf.infolist():
        target = (root / info.filename).resolve()
        if root != target and root not in target.parents:
            raise PfError(f"zip entry escapes destination: {info.filename}")
        if info.is_dir():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(info))
        names.append(target.relative_to(root).as_posix())
    return names


def cmd_kit_vendor(a):
    kit_id = check_id(a.id)
    url = f"{ORIGIN}/dl/kit-{kit_id}.zip"
    data = fetch_bytes(url, auth=True)
    dest = Path(a.dest)
    names = safe_extract(zipfile.ZipFile(io.BytesIO(data)), dest / kit_id)
    manifest = load_manifest(dest)
    manifest["kits"][kit_id] = {"url": url, "sha256": sha256(data), "folder": kit_id,
                                "file_count": len(names), "vendored_at": now()}
    save_manifest(dest, manifest)
    print(f"vendored kit {kit_id}: {len(names)} files in {dest / kit_id}")
    report_warnings([HELPERS_NOTE["clips"]] if any(n.endswith("clips.mjs") for n in names) else [])


def cmd_whoami(a):
    if os.environ.get("POLYFORK_API_KEY"):
        d = api("/me", auth=True)
    else:
        d = {"key": "POLYFORK_API_KEY is not set", "access": api("/assets", {"per_page": 1}).get("access")}
    print(json.dumps(d, indent=1))


def report_warnings(warnings):
    for w in dict.fromkeys(warnings):
        print(f"warning: {w}")


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(prog="pf.py", description="Polyfork catalogue: search, inspect, vendor.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search the catalogue")
    s.add_argument("query")
    s.add_argument("--class", dest="cls", choices=CLASSES)
    s.add_argument("--kit")
    s.add_argument("--ik", choices=["1", "legs", "arm"])
    s.add_argument("--max-triangles", type=int)
    s.add_argument("--limit", type=int, default=15)
    s.set_defaults(fn=cmd_search)

    for name, fn, helptext in [("get", cmd_get, "one asset with its knobs"),
                               ("matching", cmd_matching, "assets that go with this one"),
                               ("kit", cmd_kit, "one kit and its parts")]:
        s = sub.add_parser(name, help=helptext)
        s.add_argument("id")
        if name == "matching":
            s.add_argument("--limit", type=int, default=12)
        s.set_defaults(fn=fn)

    s = sub.add_parser("variant", help="plain words to a createAsset() call")
    s.add_argument("id")
    s.add_argument("want")
    s.set_defaults(fn=cmd_variant)

    s = sub.add_parser("kits", help="list kits")
    s.add_argument("query", nargs="?")
    s.set_defaults(fn=cmd_kits)

    s = sub.add_parser("vendor", help="download assets into a project folder and record them")
    s.add_argument("ids", nargs="+")
    s.add_argument("--dest", required=True)
    s.add_argument("--format", action="append", choices=["mjs", "glb"] + MESH_FORMATS,
                   help="repeatable; default mjs")
    s.add_argument("--hd", action="store_true", help="HD edition (POLYFORK_API_KEY on Pro/Lifetime)")
    s.add_argument("--bake", help="also save a server-baked GLB, e.g. 'look=shading:toon' or 'p={\"tallness\":1.2}'")
    s.set_defaults(fn=cmd_vendor)

    s = sub.add_parser("helper", help="vendor Polyfork runtime helpers (merge, stage, clips, kit, ...)")
    s.add_argument("names", nargs="+")
    s.add_argument("--dest", required=True)
    s.set_defaults(fn=cmd_helper)

    s = sub.add_parser("kit-vendor", help="download a whole kit zip (free account key)")
    s.add_argument("id")
    s.add_argument("--dest", required=True)
    s.set_defaults(fn=cmd_kit_vendor)

    s = sub.add_parser("whoami", help="key status and remaining remix budget")
    s.set_defaults(fn=cmd_whoami)

    for s in sub.choices.values():
        s.add_argument("--json", action="store_true", help="raw JSON instead of the compact view")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except PfError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
