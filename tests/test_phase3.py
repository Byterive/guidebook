import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import make_project  # noqa: F401  (puts src/ on sys.path)
from guidebook.__main__ import main
from guidebook.build import SitePage, badges, build_guide, fix_links
from guidebook.config import load_config

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"
VERSIONS = ("layman", "client-or-investor", "maintainer", "quick-start")


def copy_fixture(dest: Path) -> Path:
    shutil.copytree(FIXTURE, dest, dirs_exist_ok=True)
    return dest


def snapshot(root: Path):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = copy_fixture(Path(cls.tmp.name) / "proj")
        assert main(["pages", str(cls.root), "--no-model"]) == 0
        assert main(["build", str(cls.root)]) == 0
        cls.out = cls.root / "docs" / "guide"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_landing_lists_every_version(self):
        html = self.read("index.html")
        for v in VERSIONS:
            self.assertIn(f'href="{v}/index.html"', html)
        self.assertIn("Bike Shop Helper", html)

    def test_each_version_has_its_own_site_with_assets(self):
        for v in VERSIONS:
            for f in ("index.html", "style.css", "search.js"):
                self.assertTrue((self.out / v / f).is_file(), f"{v}/{f}")

    def test_manifest_contract_and_two_identical_copies(self):
        m = json.loads(self.read("guide.manifest.json"))
        self.assertEqual((m["contract"], m["brand"], m["output"]), (1, "Bike Shop Helper", "docs/guide"))
        self.assertEqual([v["name"] for v in m["versions"]], list(VERSIONS))
        self.assertEqual(self.read("guide.manifest.json"), (self.root / ".guidebook" / "manifest.json").read_text(encoding="utf-8"))
        status = [p for p in m["versions"][0]["pages"] if p["rel"] == "2-status/status.md"][0]
        self.assertEqual(status["html"], "2-status/status.html")

    def test_version_switcher_in_header(self):
        html = self.read("layman/2-status/status.html")
        self.assertIn("Version: layman", html)
        self.assertIn('href="../../maintainer/2-status/status.html"', html)
        self.assertIn('href="../../index.html">All versions', html)

    def test_switcher_falls_back_to_version_home_when_page_missing(self):
        html = self.read("maintainer/3-decisions/decisions.html")      # layman has no decisions page
        self.assertIn('href="../../layman/index.html"', html)

    def test_other_versions_list_comes_from_manifest(self):
        html = self.read("layman/2-status/status.html")
        nav = html.split("Other versions of this page:")[1].split("</nav>")[0]
        self.assertIn('aria-label="Other versions of this page"', html)
        self.assertIn('href="../../maintainer/2-status/status.html">maintainer</a>', nav)
        self.assertNotIn(">layman</a>", nav, "the current version is not listed as 'other'")

    def test_no_other_versions_list_when_page_exists_only_here(self):
        self.assertNotIn("Other versions of this page", self.read("maintainer/3-decisions/decisions.html"))

    def test_status_words_are_badges_with_the_word_inside(self):
        html = self.read("layman/2-status/status.html")
        for w in ("PASSED", "DOUBTFUL", "FAILED", "UNTESTED", "UNKNOWN"):
            self.assertIn(f'<span class="badge b-{w.lower()}">{w}</span>', html)

    def test_theme_uses_the_documented_status_colours(self):
        css = self.read("layman/style.css")
        for color in ("#2F7D6D", "#E2A93B", "#B4483C", "#4A5862", "#3F6C9A"):
            self.assertIn(color, css)

    def test_search_script_has_entries(self):
        js = self.read("layman/search.js")
        self.assertIn("Status of each part", js)
        self.assertNotIn("__ENTRIES__", js)
        self.assertIn("quick-start/index.html", self.read("search.js"))

    def test_every_page_has_title_and_relative_links(self):
        for f in self.out.rglob("*.html"):
            html = f.read_text(encoding="utf-8")
            self.assertRegex(html, r"<title>.+</title>", f.name)
            self.assertNotIn('href="/', html)
            self.assertNotIn("http://", html.replace("http://www.w3.org", ""))


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = copy_fixture(Path(self.tmp.name) / "proj")
        main(["pages", str(self.root), "--no-model"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_is_deterministic(self):
        main(["build", str(self.root)])
        first = snapshot(self.root / "docs" / "guide")
        main(["build", str(self.root)])
        self.assertEqual(first, snapshot(self.root / "docs" / "guide"))

    def test_proposed_and_draft_pages_are_not_built(self):
        base = self.root / "docs" / "guide-src" / "layman"
        (base / "2-status" / "status.proposed.md").write_text("---\ntitle: P\nsummary: s\n---\n\nx\n", encoding="utf-8")
        (base / "_draft.md").write_text("---\ntitle: D\nsummary: s\n---\n\nx\n", encoding="utf-8")
        main(["build", str(self.root)])
        out = self.root / "docs" / "guide" / "layman"
        self.assertFalse((out / "_draft.html").exists())
        self.assertFalse((out / "2-status" / "status.proposed.html").exists())

    def test_user_written_page_is_built_and_html_is_escaped(self):
        page = self.root / "docs" / "guide-src" / "layman" / "1-start" / "hello.md"
        page.write_text('---\ntitle: Hi <script>alert(1)</script>\nsummary: A "quoted" <b>summary</b>.\n---\n\nHello.\n', encoding="utf-8")
        main(["build", str(self.root)])
        out = self.root / "docs" / "guide" / "layman" / "1-start"
        self.assertNotIn("<script>alert(1)</script>", (out / "hello.html").read_text(encoding="utf-8"))
        self.assertIn("&lt;script&gt;", (out / "hello.html").read_text(encoding="utf-8"))
        self.assertNotIn("<b>summary</b>", (out / "index.html").read_text(encoding="utf-8"))

    def test_version_without_pages_is_reported_and_others_still_build(self):
        shutil.rmtree(self.root / "docs" / "guide-src" / "client-or-investor")
        cfg = load_config(self.root)
        rep = build_guide(self.root, self.root / "docs" / "guide-src", self.root / "docs" / "guide", cfg.brand, cfg.versions)
        self.assertEqual(rep.missing, ["client-or-investor"])
        self.assertIn("layman", rep.built)
        landing = (self.root / "docs" / "guide" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("client-or-investor/index.html", landing)

    def test_nothing_to_build_returns_error_code(self):
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        self.assertEqual(main(["build", str(empty)]), 1)

    def test_links_resolve_only_inside_their_own_version(self):
        pages = {"2-status/status.md": SitePage("2-status/status.md", {"summary": "S"}, "")}
        out = fix_links('<a href="status.md">x</a> <a href="../3-decisions/decisions.md">y</a>', "2-status/other.md", pages)
        self.assertIn('href="status.html" title="S"', out)
        self.assertIn('href="../3-decisions/decisions.md"', out, "a page missing from this version is not linked across versions")

    def test_badges_skip_code_and_pre(self):
        out = badges("<p>PASSED and <code>FAILED</code></p><pre>UNKNOWN</pre>")
        self.assertIn('<span class="badge b-passed">PASSED</span>', out)
        self.assertNotIn("b-failed", out)
        self.assertNotIn("b-unknown", out)

    def test_single_version_has_no_switcher(self):
        (self.root / ".guidebook" / "guide.json").write_text(json.dumps({"versions": ["layman"]}), encoding="utf-8")
        main(["build", str(self.root)])
        html = (self.root / "docs" / "guide" / "layman" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("Version:", html)
        self.assertNotIn("Other versions", html)

    def test_pages_command_still_works_after_build(self):
        self.assertEqual(main(["pages", str(self.root), "--no-model"]), 0)


class Browser(unittest.TestCase):
    """375 px width, dark mode, contrast, focus and `/` search on every built page. Skipped when playwright or Chrome/Edge is missing."""

    def test_browser_quality_bar(self):
        with tempfile.TemporaryDirectory() as d:
            root = copy_fixture(Path(d) / "proj")
            main(["pages", str(root), "--no-model"])
            main(["build", str(root)])
            r = subprocess.run([sys.executable, str(Path(__file__).parent / "browser_check.py"), str(root / "docs" / "guide")], capture_output=True, text=True)
            if r.returncode == 3:
                self.skipTest(r.stderr.strip())
            self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
