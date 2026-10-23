import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import apply_icon  # noqa: E402
import gallery  # noqa: E402
import icon_paths  # noqa: E402
import scan  # noqa: E402


def no_files(_path):
    return None


class ClassifyTests(unittest.TestCase):
    def test_well_known_path_is_found(self):
        result = icon_paths.classify({"README.md", "public/favicon.svg"}, no_files)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["icon"], "public/favicon.svg")
        self.assertEqual(result["via"], "well-known")

    def test_well_known_order_wins(self):
        result = icon_paths.classify({"assets/icon.png", "favicon.ico"}, no_files)
        self.assertEqual(result["icon"], "favicon.ico")

    def test_t3_json_icon_path_comes_first(self):
        files = {"t3.json": json.dumps({"iconPath": "site/logo.svg"})}
        result = icon_paths.classify({"t3.json", "site/logo.svg", "favicon.ico"}, files.get)
        self.assertEqual((result["icon"], result["via"]), ("site/logo.svg", "t3.json"))

    def test_link_icon_in_index_html_resolves_under_public(self):
        files = {"index.html": '<link rel="icon" type="image/svg+xml" href="/logo.svg" />'}
        result = icon_paths.classify({"index.html", "public/logo.svg"}, files.get)
        self.assertEqual((result["icon"], result["via"]), ("public/logo.svg", "index.html"))

    def test_inline_data_favicon_is_reported_not_used(self):
        files = {"index.html": '<link rel="icon" href="data:image/svg+xml,%3Csvg%3E" />'}
        result = icon_paths.classify({"index.html"}, files.get)
        self.assertEqual(result["status"], "none")
        self.assertIn("data:", result["note"])

    def test_nested_logo_is_nonstandard(self):
        result = icon_paths.classify({"site/logo.svg", "docs/brand/alt.svg"}, no_files)
        self.assertEqual(result["status"], "nonstandard")
        self.assertEqual(result["logos"][0], "site/logo.svg")

    def test_noise_is_not_a_logo(self):
        paths = {
            "node_modules/pkg/logo.svg",
            "src-tauri/icons/Square150x150Logo.png",
            "src/icons/arrow-icon.svg",
            "tests/fixtures/logo.png",
        }
        self.assertEqual(icon_paths.classify(paths, no_files)["status"], "none")

    def test_shadowing_paths(self):
        paths = {"favicon.ico", "assets/icon.png"}
        self.assertEqual(icon_paths.shadowing_paths(paths, "assets/icon.png"), ["favicon.ico"])
        self.assertEqual(icon_paths.shadowing_paths(paths, "favicon.ico"), [])

    def test_object_literal_icon_link(self):
        src = "links: [{ rel: 'stylesheet', href: '/app.css' }, { rel: 'icon', href: '/favicon.png' }]"
        self.assertEqual(icon_paths.extract_icon_href(src), "/favicon.png")


class RecentSourcesTests(unittest.TestCase):
    def repo(self, name, pushed, **flags):
        return {"nameWithOwner": name, "pushedAt": pushed, "defaultBranchRef": {"name": "main"}, **flags}

    def test_filters_forks_archived_empty_stale_and_duplicates(self):
        recent = "2999-01-01T00:00:00Z"
        repos = [
            self.repo("o/keep", recent),
            self.repo("o/keep", recent),
            self.repo("o/fork", recent, isFork=True),
            self.repo("o/archived", recent, isArchived=True),
            self.repo("o/empty", recent, isEmpty=True),
            self.repo("o/stale", "2000-01-01T00:00:00Z"),
        ]
        self.assertEqual([r["nameWithOwner"] for r in scan.recent_sources(repos, 30)], ["o/keep"])


class ReadmeTests(unittest.TestCase):
    IMG = '<img src="assets/icon.png" width="40" height="40" align="top" alt="" />'

    def test_atx_title_becomes_html_with_image(self):
        text, status = apply_icon.update_readme_text("# My Tool\n\nIntro\n", "assets/icon.png")
        self.assertEqual(status, "updated")
        self.assertEqual(text.splitlines()[0], f"<h1>{self.IMG} My Tool</h1>")
        self.assertTrue(text.endswith("Intro\n"))

    def test_html_title_without_image_gets_one(self):
        text, _ = apply_icon.update_readme_text('<h1 align="center">Tool</h1>\n', "assets/icon.png")
        self.assertEqual(text.splitlines()[0], f'<h1 align="center">{self.IMG} Tool</h1>')

    def test_title_with_image_is_left_alone(self):
        original = '<h1><img src="site/logo.svg" /> tool</h1>\n'
        text, status = apply_icon.update_readme_text(original, "assets/icon.png")
        self.assertEqual(text, original)
        self.assertIn("already", status)

    def test_markdown_title_is_left_for_a_human(self):
        original = "# The `tk` CLI\n"
        text, status = apply_icon.update_readme_text(original, "assets/icon.png")
        self.assertEqual(text, original)
        self.assertIn("by hand", status)

    def test_heading_inside_code_fence_is_ignored(self):
        original = "```\n# not a title\n```\n# Real\n"
        text, _ = apply_icon.update_readme_text(original, "assets/icon.png")
        self.assertIn("# not a title", text)
        self.assertIn(f"<h1>{self.IMG} Real</h1>", text)

    def test_no_title(self):
        _, status = apply_icon.update_readme_text("Just text\n\n## Section\n", "assets/icon.png")
        self.assertIn("no top-level title", status)


class ApplyIconTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image

        self.Image = Image
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.repo = os.path.join(self.dir, "repo")
        os.makedirs(self.repo)
        with open(os.path.join(self.repo, "README.md"), "w") as fh:
            fh.write("# Demo\n")

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, haze=False):
        im = self.Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        if haze:
            im.paste((200, 200, 200, 20), (100, 100, 900, 900))
        im.paste((255, 0, 0, 255), (400, 300, 600, 700))  # tall red bar, off-square
        path = os.path.join(self.dir, "src.png")
        im.save(path)
        return path

    def run_apply(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()):
            return apply_icon.main(["--repo-dir", self.repo, *extra])

    def test_raster_is_trimmed_squared_and_resized(self):
        self.assertEqual(self.run_apply("--source", self.source()), 0)
        out = self.Image.open(os.path.join(self.repo, "assets/icon.png"))
        self.assertEqual(out.size, (512, 512))
        bbox = out.getchannel("A").getbbox()
        self.assertGreater(bbox[3] - bbox[1], 480)  # the tall side fills the canvas
        with open(os.path.join(self.repo, "README.md")) as fh:
            self.assertIn('src="assets/icon.png"', fh.read())

    def test_faint_backdrop_is_removed(self):
        self.run_apply("--source", self.source(haze=True))
        alpha = self.Image.open(os.path.join(self.repo, "assets/icon.png")).getchannel("A")
        hist = alpha.histogram()
        self.assertLess(sum(hist[1:41]) / sum(hist), 0.02)

    def test_svg_is_copied_and_existing_icon_needs_force(self):
        svg = os.path.join(self.dir, "logo.svg")
        with open(svg, "w") as fh:
            fh.write('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.assertEqual(self.run_apply("--source", svg), 0)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "assets/icon.svg")))
        self.assertEqual(self.run_apply("--source", self.source()), 1)
        self.assertEqual(self.run_apply("--source", self.source(), "--force"), 0)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "assets/icon.svg")))
        self.assertTrue(os.path.exists(os.path.join(self.repo, "assets/icon.png")))


class GalleryTests(unittest.TestCase):
    def test_page_has_one_radio_group_per_repo_with_keep_redo_skip(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "a.png")
            Image.new("RGBA", (64, 64), (0, 128, 255, 255)).save(img)
            page = gallery.build(
                {
                    "repos": [
                        {"repo": "o/a", "candidates": [{"id": "pixel-16bit", "file": img}], "current": img},
                        {"repo": "o/<b>", "candidates": [{"id": "sticker", "file": img}]},
                    ]
                }
            )
        self.assertIn('name="o/a" value="pixel-16bit"', page)
        self.assertIn('name="o/a" value="keep"', page)
        self.assertIn('name="o/a" value="redo"', page)
        self.assertNotIn('name="o/&lt;b&gt;" value="keep"', page)
        self.assertIn("o/&lt;b&gt;", page)
        self.assertNotIn("o/<b>", page)
        self.assertIn("repo-icons picks", page)
        self.assertNotIn("{{", page)


if __name__ == "__main__":
    unittest.main()
