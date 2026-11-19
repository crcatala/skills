import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("pf", Path(__file__).with_name("pf.py"))
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)

ASSET = {
    "id": "barrel-8d63c4", "title": "Barrel", "class": "prop", "kit": "pirate-cove-2ebea4",
    "has_skeleton": False, "hd": {"triangles": 2420},
    "download": {"mjs": "https://polyfork.dev/cdn/barrel-8d63c4.mjs",
                 "glb": "https://polyfork.dev/cdn/barrel-8d63c4.glb"},
    "export_formats": {"obj": {"url": "https://polyfork.dev/dl/barrel-8d63c4.obj", "available": True,
                               "also_fetch": "https://polyfork.dev/dl/barrel-8d63c4.mtl"}},
    "params_url": "https://polyfork.dev/cdn/barrel-8d63c4-params.json",
}
MODULE = b"""/* header
 *   import { createAsset } from './barrel-8d63c4.mjs';
 *   import { animate } from 'https://polyfork.dev/cdn/clips.mjs';
 */
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { helper } from './lib/helper.mjs';
// import { gone } from './commented.mjs';
export default function createAsset() {}
"""
FILES = {
    "https://polyfork.dev/api/assets/barrel-8d63c4": json.dumps(ASSET).encode(),
    "https://polyfork.dev/cdn/barrel-8d63c4.mjs": MODULE,
    "https://polyfork.dev/cdn/lib/helper.mjs": b"export const helper = 1;\nconst base = 'https://polyfork.dev/cdn/';\n",
    "https://polyfork.dev/cdn/barrel-8d63c4.glb": b"glb",
    "https://polyfork.dev/dl/barrel-8d63c4.obj": b"obj",
    "https://polyfork.dev/dl/barrel-8d63c4.mtl": b"mtl",
    "https://polyfork.dev/cdn/barrel-8d63c4-params.json": b'{"params": {}}',
}


def fake_fetch(calls):
    def fetch(url, auth=False):
        pf.check_url(url)
        calls.append((url, auth))
        if url not in FILES:
            raise pf.PfError(f"HTTP 404 for {url}")
        return FILES[url]
    return fetch


class PolyforkSkillTests(unittest.TestCase):
    def test_only_polyfork_https_urls_are_fetched(self):
        pf.check_url("https://polyfork.dev/cdn/x.mjs")
        for bad in ["http://polyfork.dev/cdn/x.mjs", "https://evil.example/x.mjs",
                    "https://polyfork.dev.evil.example/x", "file:///etc/passwd"]:
            with self.assertRaises(pf.PfError):
                pf.check_url(bad)

    def test_ids_are_validated(self):
        self.assertEqual(pf.check_id("barrel-8d63c4"), "barrel-8d63c4")
        for bad in ["../etc", "Barrel", "a/b", "", "x?y"]:
            with self.assertRaises(pf.PfError):
                pf.check_id(bad)

    def test_scan_ignores_comments_and_three_and_finds_siblings(self):
        src = MODULE.decode() + "const m = await import(new URL('stage.mjs', import.meta.url).href);\n" \
            "const here = new URL('.', import.meta.url);\nimport x from 'lodash';\n"
        relative, other, runtime = pf.scan_module(src)
        self.assertEqual(relative, ["./lib/helper.mjs", "./stage.mjs"])
        self.assertEqual(other, ["lodash"])
        self.assertEqual(runtime, [])

    def test_scan_reports_runtime_polyfork_urls(self):
        _, _, runtime = pf.scan_module("const CDN = 'https://polyfork.dev/cdn/';\n")
        self.assertEqual(runtime, ["https://polyfork.dev/cdn/"])

    def test_dependencies_cannot_escape_destination(self):
        dest = Path("/tmp/x")
        root = "https://polyfork.dev/cdn/a.mjs"
        self.assertEqual(pf.local_target(dest, root, "https://polyfork.dev/cdn/lib/b.mjs"), dest / "lib" / "b.mjs")
        with self.assertRaises(pf.PfError):
            pf.local_target(dest, root, "https://polyfork.dev/api/secret.mjs")

    def test_vendor_writes_files_crawls_imports_and_records_manifest(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(pf, "fetch_bytes", fake_fetch(calls)), \
                patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as out:
            code = pf.main(["vendor", "barrel-8d63c4", "--dest", tmp, "--format", "mjs", "--format", "obj"])
            self.assertEqual(code, 0)
            dest = Path(tmp)
            for name in ["barrel-8d63c4.mjs", "lib/helper.mjs", "barrel-8d63c4.obj", "barrel-8d63c4.mtl",
                         "barrel-8d63c4-params.json"]:
                self.assertTrue((dest / name).exists(), name)
            manifest = json.loads((dest / pf.MANIFEST).read_text())
            entry = manifest["assets"]["barrel-8d63c4"]
            self.assertEqual(entry["edition"], "low")
            self.assertEqual(entry["files"]["lib/helper.mjs"]["sha256"], pf.sha256(FILES["https://polyfork.dev/cdn/lib/helper.mjs"]))
            self.assertIn("Polyfork licence", manifest["license"])
            self.assertIn("reaches https://polyfork.dev/cdn/ at runtime", out.getvalue())
            self.assertFalse(any(auth for _, auth in calls), "low poly files must not send the key")

    def test_manifest_keeps_earlier_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            pf.save_manifest(tmp, {"source": pf.ORIGIN, "assets": {"a": {"files": {}}}})
            m = pf.load_manifest(tmp)
            m["assets"]["b"] = {"files": {}}
            pf.save_manifest(tmp, m)
            self.assertEqual(sorted(pf.load_manifest(tmp)["assets"]), ["a", "b"])

    def test_missing_optional_dependency_is_a_warning(self):
        files = {"https://polyfork.dev/cdn/kit.mjs": b"const m = await import(new URL('materials.mjs', import.meta.url).href);\n"}

        def fetch(url, auth=False):
            if url not in files:
                raise pf.PfError(f"HTTP 404 for {url}")
            return files[url]
        with tempfile.TemporaryDirectory() as tmp, patch.object(pf, "fetch_bytes", fetch):
            found, warnings = {}, []
            pf.vendor_module("https://polyfork.dev/cdn/kit.mjs", Path(tmp), False, found, warnings)
            self.assertEqual(list(found), ["kit.mjs"])
            self.assertTrue(any("materials.mjs" in w for w in warnings))

    def test_hd_requires_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(pf.PfError) as ctx:
                pf.fetch_bytes("https://polyfork.dev/dl/barrel-8d63c4-hd.mjs", auth=True)
        self.assertIn("POLYFORK_API_KEY", str(ctx.exception))

    def test_zip_entries_cannot_escape(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil.txt", "x")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(pf.PfError):
                pf.safe_extract(zipfile.ZipFile(buf), Path(tmp) / "kit")
            self.assertFalse((Path(tmp) / "evil.txt").exists())

    def test_safe_extract_writes_nested_files(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("parts/a.glb", "a")
            zf.writestr("kit.mjs", "k")
        with tempfile.TemporaryDirectory() as tmp:
            names = pf.safe_extract(zipfile.ZipFile(buf), Path(tmp) / "kit")
            self.assertEqual(sorted(names), ["kit.mjs", "parts/a.glb"])


if __name__ == "__main__":
    unittest.main()
