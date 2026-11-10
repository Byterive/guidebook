import json
import tempfile
import unittest
from pathlib import Path

from helpers import make_project  # noqa: F401  (also puts src/ on sys.path)
from guidebook import frontmatter as fm
from guidebook.collect import collect
from guidebook.facts import FactStore
from guidebook.hashing import normalize, sources_hash, text_hash
from guidebook.scrub import scrub


class Hashing(unittest.TestCase):
    def test_line_endings_and_trailing_space_do_not_change_hash(self):
        self.assertEqual(text_hash("a  \r\nb\r\n"), text_hash("a\nb"))

    def test_real_change_changes_hash(self):
        self.assertNotEqual(text_hash("a"), text_hash("b"))

    def test_sources_hash_ignores_order(self):
        self.assertEqual(sources_hash({"a": "1", "b": "2"}), sources_hash({"b": "2", "a": "1"}))

    def test_normalize(self):
        self.assertEqual(normalize("\n\nx \n\n"), "x")


class Scrub(unittest.TestCase):
    def cases(self):
        return {
            "token": "key sk-abcdefghijklmnopqrstuvwx here",
            "email": "mail me at jane.doe@example.com",
            "path": r"see C:\Users\jane\project\x.py",
            "assignment": "password = hunter2hunter2",
            "account-id": "account id: 123456789012",
            "private-key": "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----",
        }

    def test_each_rule_fires_and_removes_the_secret(self):
        needles = {"token": "sk-abcdef", "email": "jane.doe", "path": "jane", "assignment": "hunter2", "account-id": "123456789012", "private-key": "abc\n"}
        for name, text in self.cases().items():
            clean, fired = scrub(text)
            self.assertIn(name, fired, name)
            self.assertNotIn(needles[name], clean, name)

    def test_plain_text_untouched(self):
        self.assertEqual(scrub("A plain sentence about tokens of appreciation."), ("A plain sentence about tokens of appreciation.", []))


class Frontmatter(unittest.TestCase):
    def page(self, body="Body text."):
        return fm.make_page("T", "One sentence.", ["a", "b"], "layman", ["x.md", "y.md"], "h1", body)

    def test_roundtrip(self):
        meta, body = fm.parse(self.page())
        self.assertEqual((meta["title"], meta["generated"], meta["sources"], meta["keywords"], meta["version"]), ("T", True, ["x.md", "y.md"], ["a", "b"], "layman"))
        self.assertEqual(body.strip(), "Body text.")

    def test_pristine_page_may_be_overwritten(self):
        self.assertEqual(fm.edit_state(self.page()), "pristine")

    def test_edited_generated_page_is_protected(self):
        self.assertEqual(fm.edit_state(self.page().replace("Body text.", "Body text, edited by me.")), "edited")

    def test_crlf_save_by_an_editor_is_not_an_edit(self):
        self.assertEqual(fm.edit_state(self.page().replace("\n", "\r\n")), "pristine")

    def test_page_without_generated_flag_is_the_users(self):
        self.assertEqual(fm.edit_state("---\ntitle: Mine\nsummary: s\n---\n\nHi\n"), "user")
        self.assertEqual(fm.edit_state("No frontmatter at all"), "user")

    def test_generated_false_is_the_users(self):
        self.assertEqual(fm.edit_state("---\ntitle: x\ngenerated: false\n---\n\nHi\n"), "user")


class Collect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_project(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_skips_secrets_caches_and_gitignored(self):
        paths = {s.path for s in collect(self.root)}
        self.assertTrue({"PROJECT_BRIEF.md", "README.md", "app.py"} <= paths)
        for bad in (".env", "secrets/key.txt", "server.pem", "ignored.md", "__pycache__/x.pyc"):
            self.assertNotIn(bad, paths)

    def test_kickoff_files_come_first(self):
        kinds = [s.kind for s in collect(self.root)]
        self.assertEqual(kinds, sorted(kinds, key=lambda k: ["kickoff", "readme", "doc", "config", "code", "test", "other"].index(k)))

    def test_guidebook_ignore_file(self):
        (self.root / ".guidebook").mkdir()
        (self.root / ".guidebook" / "ignore").write_text("app.py\n", encoding="utf-8")
        self.assertNotIn("app.py", {s.path for s in collect(self.root)})

    def test_collect_never_writes(self):
        before = {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()}
        collect(self.root)
        after = {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / ".guidebook").exists())


class Facts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_project(Path(self.tmp.name))
        self.store = FactStore(self.root / ".guidebook" / "facts.json")
        self.store.update(collect(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_extracts_each_kind_with_sources(self):
        purpose = self.store.by_kind("purpose")
        self.assertIn("bike repairs", purpose[0].text)
        self.assertEqual(purpose[0].sources, ["PROJECT_BRIEF.md"])
        self.assertTrue(purpose[0].confirmed)
        self.assertEqual({f.status for f in self.store.by_kind("result")}, {"PASSED", "UNTESTED"})
        self.assertEqual(len(self.store.by_kind("decision")), 1)
        self.assertEqual(len(self.store.by_kind("step")), 2)
        self.assertEqual(len(self.store.by_kind("risk")), 1)
        self.assertEqual([f.text for f in self.store.by_kind("term")], ["Order: one repair job."])

    def test_readme_purpose_is_marked_unconfirmed(self):
        readme = [f for f in self.store.facts if f.sources == ["README.md"] and f.kind == "purpose"]
        self.assertEqual(len(readme), 1)
        self.assertFalse(readme[0].confirmed)

    def test_only_changed_sources_are_re_extracted(self):
        self.store.save()
        again = FactStore(self.root / ".guidebook" / "facts.json")
        self.assertEqual(again.update(collect(self.root)), ([], []))
        (self.root / "NEXT.md").write_text("# NEXT\n\n1. Brand new step.\n", encoding="utf-8")
        changed, removed = again.update(collect(self.root))
        self.assertEqual((changed, removed), (["NEXT.md"], []))
        self.assertEqual([f.text for f in again.by_kind("step")], ["Brand new step."])

    def test_new_extractor_version_rebuilds_cached_facts(self):
        import guidebook.facts as facts_mod
        self.store.save()
        raw = json.loads((self.root / ".guidebook" / "facts.json").read_text(encoding="utf-8"))
        raw["extractor_version"] = "old"
        (self.root / ".guidebook" / "facts.json").write_text(json.dumps(raw), encoding="utf-8")
        again = FactStore(self.root / ".guidebook" / "facts.json")
        changed, _ = again.update(collect(self.root))
        self.assertIn("PROJECT_BRIEF.md", changed)
        self.assertEqual(again.version, facts_mod.EXTRACTOR_VERSION)

    def test_decision_text_names_why_and_rejected(self):
        self.assertEqual(self.store.by_kind("decision")[0].text, "2026-10-01: Use SQLite. Why: simple. Rejected: Postgres")

    def test_deleted_source_drops_its_facts(self):
        (self.root / "DECISIONS.md").unlink()
        changed, removed = self.store.update(collect(self.root))
        self.assertEqual(removed, ["DECISIONS.md"])
        self.assertEqual(self.store.by_kind("decision"), [])

    def test_secrets_in_sources_never_reach_the_cache(self):
        (self.root / "DECISIONS.md").write_text("# D\n\n- 2026-10-02 | Mail bob@corp.com with password: swordfish99 | x | y\n", encoding="utf-8")
        self.store.update(collect(self.root))
        self.store.save()
        raw = (self.root / ".guidebook" / "facts.json").read_text(encoding="utf-8")
        self.assertNotIn("bob@corp.com", raw)
        self.assertNotIn("swordfish99", raw)
        self.assertTrue(any(f.scrubbed for f in self.store.facts))

    def test_saved_file_is_valid_json_with_hashes(self):
        self.store.save()
        data = json.loads((self.root / ".guidebook" / "facts.json").read_text(encoding="utf-8"))
        self.assertTrue(all(f["source_hash"] and f["sources"] for f in data["facts"]))
        self.assertIn("PROJECT_BRIEF.md", data["source_hashes"])


if __name__ == "__main__":
    unittest.main()


class MixedStatusCells(unittest.TestCase):
    def facts(self, table):
        from guidebook.facts import extract
        from guidebook.collect import Source
        text = "---\ntitle: S\nsummary: s\nkeywords: [a]\nstatus: confirmed\nupdated: 2026-01-01\n---\n\n" + table
        return extract(Source("PROJECT_STATUS.md", "kickoff", text, text_hash(text)))

    def test_mixed_cell_takes_the_weakest_word_and_keeps_the_note(self):
        facts = self.facts("| Phase | Goal | Status | Evidence |\n|---|---|---|---|\n| 2 Writer | w | PASSED (stub) / UNTESTED (real) | 53 tests |\n| 3 Build | b | PASSED (copy) | ok |\n| 4 Prose | p | tests PASSED earlier | text |\n")
        res = {f.text.split(":")[0]: f for f in facts if f.kind == "result"}
        self.assertEqual(res["2 Writer"].status, "UNTESTED")
        self.assertIn("PASSED (stub) / UNTESTED (real)", res["2 Writer"].text)
        self.assertEqual(res["3 Build"].status, "PASSED")
        self.assertNotIn("4 Prose", res)
