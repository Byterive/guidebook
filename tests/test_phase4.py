import contextlib
import http.client
import io
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from helpers import make_project  # noqa: F401  (puts src/ on sys.path)
from guidebook.__main__ import main
from guidebook.engine import status, update
from guidebook.serve import make_server

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def quiet(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(args))
    return code, out.getvalue()


def make_guide(dest: Path) -> Path:
    shutil.copytree(FIXTURE, dest, dirs_exist_ok=True)
    quiet("pages", str(dest), "--no-model")
    quiet("build", str(dest))
    return dest


def edit(path: Path, old, new):
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8", newline="")


class Status(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_guide(Path(self.tmp.name) / "proj")

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_guide_is_ok_and_exit_zero(self):
        rep = status(self.root)
        self.assertTrue(rep.ok, rep.lines())
        code, out = quiet("status", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("html: fresh", out)

    def test_changed_source_makes_exactly_its_pages_stale_with_the_reason(self):
        edit(self.root / "NEXT.md", "Back up the orders file.", "Back up the orders file twice.")
        rep = status(self.root)
        self.assertEqual({p.rel for p in rep.stale}, {"1-start/next-steps.md", "home.md"})  # the quick-start home lists the steps
        self.assertEqual(rep.stale[0].changed, ["NEXT.md"])
        code, out = quiet("status", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("1 source changed since the last build: NEXT.md", out)

    def test_unused_source_change_is_not_stale(self):
        edit(self.root / "app.py", "hi", "hello")
        self.assertTrue(status(self.root).ok)

    def test_status_never_writes(self):
        edit(self.root / "NEXT.md", "Fix", "Repair")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        status(self.root)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_deleted_page_is_missing(self):
        (self.root / "docs/guide-src/layman/2-status/status.md").unlink()
        rep = status(self.root)
        self.assertEqual([(p.version, p.rel, p.state) for p in rep.stale], [("layman", "2-status/status.md", "missing")])

    def test_html_out_of_date_after_a_page_changes_until_build(self):
        page = self.root / "docs/guide-src/layman/home.md"
        page.write_text(page.read_text(encoding="utf-8") + "\nMy note.\n", encoding="utf-8")
        self.assertEqual(status(self.root).html, "out of date")
        quiet("build", str(self.root))
        self.assertEqual(status(self.root).html, "fresh")

    def test_html_not_built(self):
        (self.root / "docs/guide/guide.manifest.json").unlink()
        self.assertEqual(status(self.root).html, "not built")

    def test_scrub_check_flags_sensitive_text_in_pages(self):
        page = self.root / "docs/guide-src/layman/1-start/mine.md"
        page.write_text("---\ntitle: Mine\nsummary: s\n---\n\nMail jane@example.com\n", encoding="utf-8")
        rep = status(self.root)
        self.assertFalse(rep.ok)
        self.assertEqual(rep.scrub_hits, ["docs/guide-src/layman/1-start/mine.md"])

    def test_user_pages_orphans_and_proposals_are_reported_not_stale(self):
        base = self.root / "docs/guide-src/layman"
        (base / "1-start" / "mine.md").write_text("---\ntitle: Mine\nsummary: s\n---\n\nHi\n", encoding="utf-8")
        (base / "2-status" / "status.proposed.md").write_text("x", encoding="utf-8")
        quiet("build", str(self.root))
        rep = status(self.root)
        self.assertTrue(rep.ok)
        self.assertEqual(rep.proposals, ["layman/2-status/status.proposed.md"])

    def test_orphan_generated_page_is_reported(self):
        src = self.root / "docs/guide-src/layman/4-reference/risks.md"
        shutil.copyfile(src, src.with_name("old-risks.md"))
        self.assertEqual(status(self.root).orphans, ["layman/4-reference/old-risks.md"])

    def test_commit_is_recorded_or_not_known(self):
        self.assertIn("not known", "\n".join(status(self.root).lines()))     # temp project is not a git repo


class Update(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_guide(Path(self.tmp.name) / "proj")
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, prompt):
        self.calls.append(prompt)
        return "A short plain explanation."

    def test_nothing_changed_nothing_happens(self):
        rep = update(self.root, no_model=True)
        self.assertTrue(rep.nothing_to_do)
        self.assertEqual((rep.written, rep.proposed, rep.built), ([], [], {}))

    def test_only_affected_pages_are_rewritten_and_html_rebuilt(self):
        edit(self.root / "NEXT.md", "Back up the orders file.", "Back up the orders file twice.")
        untouched = self.root / "docs/guide-src/layman/2-status/status.md"
        before = untouched.read_bytes()
        rep = update(self.root, no_model=True)
        self.assertEqual(sorted(rep.written), sorted([f"{v}/1-start/next-steps.md" for v in ("layman", "client-or-investor", "maintainer")] + ["quick-start/home.md"]))
        self.assertEqual(untouched.read_bytes(), before)
        self.assertIn("twice", (self.root / "docs/guide/layman/1-start/next-steps.html").read_text(encoding="utf-8"))
        self.assertTrue(status(self.root).ok)

    def test_model_called_only_for_affected_pages(self):
        edit(self.root / "PROJECT_STATUS.md", "| PASSED | 12 tests |", "| FAILED | 12 tests |")
        rep = update(self.root, version="layman", runner=self.runner)
        self.assertEqual(rep.calls, 2, "layman index and status pages use PROJECT_STATUS.md; terms and risks pages are model-free")
        self.assertEqual(len(self.calls), 2)
        rep2 = update(self.root, version="layman", runner=self.runner)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(rep2.nothing_to_do)

    def test_no_model_never_calls_and_keeps_existing_explanations(self):
        edit(self.root / "PROJECT_STATUS.md", "| PASSED | 12 tests |", "| FAILED | 12 tests |")
        update(self.root, version="layman", runner=self.runner)
        page = self.root / "docs/guide-src/layman/2-status/status.md"
        self.assertIn("A short plain explanation.", page.read_text(encoding="utf-8"))
        edit(self.root / "NEXT.md", "Fix", "Repair")
        calls = len(self.calls)
        update(self.root, version="layman", no_model=True, runner=self.runner)
        self.assertEqual(len(self.calls), calls)
        self.assertIn("A short plain explanation.", page.read_text(encoding="utf-8"), "a page whose sources did not change keeps its explanation")

    def test_edited_page_is_protected_and_proposal_written(self):
        page = self.root / "docs/guide-src/layman/2-status/status.md"
        page.write_text(page.read_text(encoding="utf-8") + "\nMy own note.\n", encoding="utf-8")
        mine = page.read_bytes()
        edit(self.root / "PROJECT_STATUS.md", "| PASSED | 12 tests |", "| FAILED | 12 tests |")
        rep = update(self.root, no_model=True)
        self.assertEqual(page.read_bytes(), mine)
        self.assertEqual(rep.proposed, ["layman/2-status/status.md"])
        self.assertIn("FAILED", page.with_name("status.proposed.md").read_text(encoding="utf-8"))
        again = status(self.root)
        self.assertTrue(again.ok, again.lines())
        self.assertEqual(again.proposals, ["layman/2-status/status.proposed.md"])
        self.assertTrue(update(self.root, no_model=True).nothing_to_do, "a waiting proposal is not rewritten again")

    def test_edited_page_with_unchanged_sources_is_kept_silently(self):
        page = self.root / "docs/guide-src/layman/2-status/status.md"
        page.write_text(page.read_text(encoding="utf-8") + "\nMy own note.\n", encoding="utf-8")
        rep = update(self.root, no_model=True)
        self.assertEqual(rep.proposed, [])
        self.assertEqual(rep.skipped_edited, ["layman/2-status/status.md"])
        self.assertFalse(page.with_name("status.proposed.md").exists())

    def test_user_page_is_never_touched(self):
        mine = self.root / "docs/guide-src/layman/2-status/status.md"
        mine.write_text("---\ntitle: Mine\nsummary: Mine.\n---\n\nHand written.\n", encoding="utf-8")
        edit(self.root / "PROJECT_STATUS.md", "| PASSED | 12 tests |", "| FAILED | 12 tests |")
        update(self.root, no_model=True)
        self.assertIn("Hand written.", mine.read_text(encoding="utf-8"))
        self.assertFalse(mine.with_name("status.proposed.md").exists())

    def test_dry_run_writes_nothing_at_all(self):
        edit(self.root / "NEXT.md", "Fix", "Repair")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        rep = update(self.root, dry_run=True, no_model=True)
        self.assertTrue(rep.written)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_unknown_version_is_an_error(self):
        with self.assertRaises(ValueError):
            update(self.root, version="nope", no_model=True)
        self.assertEqual(quiet("update", str(self.root), "--version", "nope")[0], 2)

    def test_call_cap_per_run(self):
        edit(self.root / "PROJECT_STATUS.md", "| PASSED | 12 tests |", "| FAILED | 12 tests |")
        rep = update(self.root, version="layman", max_calls=1, runner=self.runner)
        self.assertEqual((rep.calls, len(rep.capped)), (1, 1))

    def test_update_after_a_deleted_page_recreates_it(self):
        (self.root / "docs/guide-src/layman/2-status/status.md").unlink()
        rep = update(self.root, no_model=True)
        self.assertIn("layman/2-status/status.md", rep.written)
        self.assertTrue(status(self.root).ok)

    def test_cli_update_and_status_roundtrip(self):
        edit(self.root / "NEXT.md", "Fix", "Repair")
        self.assertEqual(quiet("status", str(self.root))[0], 1)
        code, out = quiet("update", str(self.root), "--no-model")
        self.assertEqual(code, 0)
        self.assertIn("pages written: 4", out)
        self.assertEqual(quiet("status", str(self.root))[0], 0)


class Banner(unittest.TestCase):
    def test_static_banner_has_command_and_no_private_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_guide(Path(d) / "proj")
            html = (root / "docs/guide/layman/index.html").read_text(encoding="utf-8")
            self.assertIn('id="gb-banner"', html)
            self.assertIn("guidebook update", html)
            self.assertNotIn(d, html)
            self.assertTrue((root / "docs/guide/live.js").is_file())
            self.assertTrue((root / "docs/guide/layman/live.js").is_file())
            self.assertIn('<script src="live.js" defer>', (root / "docs/guide/index.html").read_text(encoding="utf-8"))


class Serve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = make_guide(Path(cls.tmp.name) / "proj")
        cls.srv = make_server(cls.root, port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def req(self, method, path, headers=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        h.update(headers or {})
        c.request(method, path, headers=h)
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, body

    def test_binds_to_loopback_only(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")
        with self.assertRaises(ValueError):
            make_server(self.root, port=0, host="0.0.0.0")
        with self.assertRaises(ValueError):
            make_server(self.root, port=0, host="192.168.1.5")

    def test_serves_the_guide(self):
        code, body = self.req("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(b"Bike Shop Helper", body)
        self.assertEqual(self.req("GET", "/layman/2-status/status.html")[0], 200)

    def test_status_endpoint(self):
        code, body = self.req("GET", "/__guidebook/status")
        data = json.loads(body)
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertIn("html: fresh", data["lines"])

    def test_wrong_host_header_is_refused(self):
        self.assertEqual(self.req("GET", "/", host="evil.example.com")[0], 403)
        self.assertEqual(self.req("GET", "/__guidebook/status", host=f"evil.example.com:{self.port}")[0], 403)

    def test_only_the_output_folder_is_reachable(self):
        for path in ("/../.guidebook/facts.json", "/%2e%2e/.guidebook/state.json", "/.guidebook/facts.json", "/../PROJECT_BRIEF.md"):
            self.assertEqual(self.req("GET", path)[0], 404, path)

    def test_update_needs_post_and_guard_header(self):
        self.assertIn(self.req("GET", "/__guidebook/update")[0], (404, 405))
        self.assertEqual(self.req("POST", "/__guidebook/update")[0], 403)
        self.assertEqual(self.req("POST", "/__guidebook/update", {"X-Guidebook": "1", "Origin": "http://evil.example.com"})[0], 403)
        self.assertEqual(self.req("POST", "/__guidebook/update", {"X-Guidebook": "1"}, host="evil.example.com")[0], 403)
        self.assertEqual(self.req("PUT", "/x")[0], 405)

    def test_update_button_runs_update_without_the_model_and_refreshes(self):
        edit(self.root / "NEXT.md", "Back up the orders file.", "Back up the orders file twice.")
        code, body = self.req("GET", "/__guidebook/status")
        self.assertFalse(json.loads(body)["ok"])
        code, body = self.req("POST", "/__guidebook/update", {"X-Guidebook": "1", "Origin": f"http://127.0.0.1:{self.port}"})
        data = json.loads(body)
        self.assertEqual(code, 200, body)
        self.assertEqual(data["calls"], 0)
        self.assertEqual(len(data["written"]), 4)
        self.assertTrue(data["status"]["ok"])
        self.assertIn(b"twice", self.req("GET", "/layman/1-start/next-steps.html")[1])

    def test_missing_guide_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                make_server(d, port=0)


if __name__ == "__main__":
    unittest.main()


class IndexerSafety(unittest.TestCase):
    """A project indexer writes INDEX.md; on Windows and macOS that is the same file name as index.md."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_guide(Path(self.tmp.name) / "proj")
        self.base = self.root / "docs/guide-src/layman"

    def test_home_page_is_home_md_and_html_is_index(self):
        self.assertTrue((self.base / "home.md").is_file())
        self.assertTrue((self.root / "docs/guide/layman/index.html").is_file())
        self.assertFalse((self.root / "docs/guide/layman/home.html").exists())

    def test_indexer_files_are_not_guide_pages(self):
        (self.base / "INDEX.md").write_text("# Index\n\n<!-- GENERATED by tools/build_index.py. Do not edit. -->\n", encoding="utf-8")
        (self.base / "1-start" / "INDEX.md").write_text("# Index\n", encoding="utf-8")
        before = status(self.root)
        self.assertTrue(before.ok, before)
        quiet("build", str(self.root))
        self.assertEqual([q for q in (self.root / "docs/guide").rglob("*.html") if q.name == "INDEX.html"], [])
        code, _ = quiet("update", str(self.root), "--no-model")
        self.assertEqual(code, 0)
        self.assertTrue((self.base / "home.md").is_file())

    def test_old_generated_index_md_is_replaced_by_home_md(self):
        home = self.base / "home.md"
        (self.base / "index.md").write_text(home.read_text(encoding="utf-8"), encoding="utf-8")
        home.unlink()
        quiet("update", str(self.root), "--no-model")
        self.assertTrue(home.is_file())
        self.assertFalse((self.base / "index.md").exists() and (self.base / "index.md").read_text(encoding="utf-8") != "")

    def test_old_index_md_overwritten_by_an_indexer_is_replaced(self):
        home = self.base / "home.md"
        home.unlink()
        (self.base / "index.md").write_text("# Index: x\n\n<!-- GENERATED by tools/build_index.py. Do not edit. -->\n", encoding="utf-8")
        quiet("update", str(self.root), "--no-model")
        self.assertIn("generated: true", home.read_text(encoding="utf-8"))
        self.assertFalse(list(self.base.glob("index.md")) and "GENERATED by tools/build_index.py" in (self.base / "index.md").read_text(encoding="utf-8"))

    def test_old_hand_written_index_md_is_kept_as_home_md(self):
        home = self.base / "home.md"
        home.unlink()
        (self.base / "index.md").write_text("---\ntitle: Mine\nsummary: s\n---\n\nMy own front page.\n", encoding="utf-8")
        quiet("update", str(self.root), "--no-model")
        self.assertIn("My own front page.", home.read_text(encoding="utf-8"))
