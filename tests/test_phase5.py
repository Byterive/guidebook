import contextlib
import dataclasses
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import make_project
from guidebook.__main__ import main
from guidebook.config import Config, load_config
from guidebook.engine import status

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


def fresh_project(tmp, with_guide_json=False):
    dest = Path(tmp) / "proj"
    shutil.copytree(FIXTURE, dest)
    if not with_guide_json:
        (dest / ".guidebook" / "guide.json").unlink()
        (dest / ".guidebook").rmdir()
    return dest


def files(root: Path):
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


class Init(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = fresh_project(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_without_approval_it_proposes_and_writes_nothing(self):
        before = files(self.root)
        code, out, _ = run("init", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(files(self.root), before)
        for name in ("layman", "client-or-investor", "maintainer", "quick-start"):
            self.assertIn(name, out)
        self.assertIn("nothing written yet. To approve: guidebook init", out)
        self.assertIn("--yes", out)

    def test_every_proposal_has_a_reason(self):
        out = run("init", str(self.root))[1]
        line = [ln for ln in out.splitlines() if ln.strip().startswith("client-or-investor")][0]
        self.assertRegex(line, r"\d+ status items")

    def test_dry_run_lists_exactly_the_files_that_approval_creates(self):
        before = files(self.root)
        code, out, _ = run("init", str(self.root), "--dry-run")
        self.assertEqual((code, files(self.root)), (0, before))
        listed = {ln.strip() for ln in out.splitlines() if ln.startswith("  ") and "/" in ln or ln.strip() in (".guidebook/guide.json",)}
        listed = {x for x in listed if not x.startswith(("layman ", "client", "maintainer ", "quick"))}
        self.assertIn("nothing written", out)
        self.assertGreater(len(listed), 20)
        code, _, _ = run("init", str(self.root), "--yes")
        self.assertEqual(code, 0)
        created = files(self.root) - before
        self.assertEqual(created, {x for x in listed if x in created or x in files(self.root)})
        self.assertEqual(created, listed, f"only in created: {sorted(created - listed)}; only in dry-run: {sorted(listed - created)}")

    def test_approval_writes_config_builds_guide_and_status_is_fresh(self):
        code, out, _ = run("init", str(self.root), "--versions", "layman,quick-start", "--yes")
        self.assertEqual(code, 0, out)
        cfg = load_config(self.root)
        self.assertEqual([v.name for v in cfg.versions], ["layman", "quick-start"])
        self.assertEqual((cfg.brand, cfg.output, cfg.publish), ("proj", "docs/guide", "local"))
        self.assertTrue((self.root / "docs/guide/index.html").is_file())
        self.assertTrue((self.root / ".guidebook/ignore").is_file())
        self.assertEqual(run("status", str(self.root))[0], 0)

    def test_init_is_no_model_unless_asked(self):
        code, out, _ = run("init", str(self.root), "--yes")
        self.assertIn("model calls: 0", out)
        self.assertIn("(--no-model)", out)

    def test_already_set_up_is_left_alone(self):
        run("init", str(self.root), "--versions", "layman", "--yes")
        cfg_text = (self.root / ".guidebook/guide.json").read_text(encoding="utf-8")
        snap = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".guidebook" not in p.parts[-3:-1]}
        code, out, _ = run("init", str(self.root), "--versions", "layman,quick-start", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("already set up", out)
        self.assertEqual((self.root / ".guidebook/guide.json").read_text(encoding="utf-8"), cfg_text)
        self.assertFalse((self.root / "docs/guide/quick-start").exists())

    def test_kickoff_disabled_means_nothing_happens(self):
        (self.root / ".kickoff").mkdir()
        (self.root / ".kickoff/guide.json").write_text(json.dumps({"contract": 1, "enabled": False}), encoding="utf-8")
        before = files(self.root)
        code, out, _ = run("init", str(self.root), "--yes")
        self.assertEqual(code, 0)
        self.assertIn("disabled", out)
        self.assertEqual(files(self.root), before)
        self.assertEqual(run("status", str(self.root))[0], 0)
        self.assertEqual(run("update", str(self.root))[0], 0)

    def test_kickoff_versions_are_used_and_its_file_is_not_touched(self):
        (self.root / ".kickoff").mkdir()
        text = json.dumps({"contract": 1, "enabled": True, "brand": "Kick Brand", "versions": ["layman"], "output": "docs/g", "publish": "local", "hub": ""})
        (self.root / ".kickoff/guide.json").write_text(text, encoding="utf-8")
        code, out, _ = run("init", str(self.root), "--yes")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.root / ".kickoff/guide.json").read_text(encoding="utf-8"), text)
        self.assertTrue((self.root / "docs/g/layman/index.html").is_file())
        self.assertFalse((self.root / "docs/guide").exists())
        self.assertIn("Kick Brand", (self.root / "docs/g/index.html").read_text(encoding="utf-8"))

    def test_project_with_only_a_readme_gets_a_thin_proposal_with_a_warning(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / "p"
        root.mkdir()
        (root / "README.md").write_text("# Tool\n\nA small tool that renames photos.\n", encoding="utf-8")
        code, out, _ = run("init", str(root))
        self.assertEqual(code, 0)
        self.assertIn("layman", out)
        self.assertIn("quick-start", out)
        self.assertNotIn("client-or-investor", out)
        self.assertNotIn("maintainer", out)
        self.assertIn("No kickoff files", out)
        self.assertIn("README and be marked unconfirmed", out)
        tmp.cleanup()

    def test_empty_folder_has_nothing_to_read(self):
        tmp = tempfile.TemporaryDirectory()
        code, out, _ = run("init", tmp.name, "--yes")
        self.assertEqual(code, 1)
        self.assertIn("nothing to read", out)
        self.assertEqual(files(Path(tmp.name)), set())
        tmp.cleanup()

    def test_secrets_are_not_read_by_init(self):
        (self.root / ".env").write_text("TOKEN=abcdefgh12345678\n", encoding="utf-8")
        run("init", str(self.root), "--yes")
        blob = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in self.root.rglob("*") if p.is_file() and p.name != ".env")
        self.assertNotIn("abcdefgh12345678", blob)


class Contract(unittest.TestCase):
    def test_version_flag(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["--version"])
        self.assertRegex(out.getvalue(), r"^guidebook \d+\.\d+\.\d+ \(kickoff contract 1\)")

    def test_higher_contract_warns_but_still_works(self):
        with tempfile.TemporaryDirectory() as d:
            root = fresh_project(d)
            run("init", str(root), "--yes")
            (root / ".kickoff").mkdir()
            (root / ".kickoff/guide.json").write_text(json.dumps({"contract": 2, "versions": ["layman"], "brand": "X"}), encoding="utf-8")
            code, out, err = run("status", str(root))
            self.assertIn("contract 2", err)
            self.assertIn("layman", out)

    def test_doc_names_every_config_field_and_manifest_key(self):
        doc = (ROOT / "docs" / "kickoff-contract.md").read_text(encoding="utf-8")
        for f in dataclasses.fields(Config):
            if f.name != "warnings":
                self.assertIn(f"`{f.name}`", doc, f"docs/kickoff-contract.md does not mention config field {f.name}")
        for key in ("guide.manifest.json", "--dry-run", "--yes", "--no-model", "init", "update", "status"):
            self.assertIn(key, doc)
        meta = re.match(r"---\n(.*?)\n---", doc, re.S).group(1)
        for k in ("title", "summary", "keywords", "status", "updated"):
            self.assertIn(k + ":", meta)

    def test_manifest_matches_the_documented_shape(self):
        with tempfile.TemporaryDirectory() as d:
            root = fresh_project(d)
            run("init", str(root), "--yes")
            m = json.loads((root / "docs/guide/guide.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(set(m), {"contract", "brand", "output", "versions"})
            self.assertEqual(set(m["versions"][0]), {"name", "audience", "depth", "reader", "dir", "pages"})
            self.assertEqual(set(m["versions"][0]["pages"][0]), {"rel", "html", "title", "summary", "section"})
            self.assertNotRegex(json.dumps(m), r"\d{4}-\d\d-\d\d \d\d:\d\d")


class PluginFiles(unittest.TestCase):
    def fm(self, path):
        text = path.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        self.assertIsNotNone(m, f"{path} has no frontmatter")
        return {k.strip(): v.strip() for k, v in (ln.split(":", 1) for ln in m.group(1).splitlines() if ":" in ln)}, text

    def test_manifest_fields(self):
        data = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "guidebook")
        self.assertEqual(data["author"]["name"], "Junaid Iqbal")
        self.assertEqual(data["homepage"], "https://byterive.com")
        self.assertEqual(data["repository"], "https://github.com/Byterive/guidebook")
        self.assertEqual(data["license"], "MIT")
        self.assertTrue((ROOT / "README.md").is_file() and (ROOT / "LICENSE").is_file())

    def test_command_and_skill_frontmatter(self):
        meta, text = self.fm(ROOT / "commands" / "guide.md")
        self.assertTrue(meta["description"])
        for sub in ("init", "status", "update", "serve"):
            self.assertIn(f"## {sub}", text)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/guidebook", text)
        meta, text = self.fm(ROOT / "skills" / "guidebook" / "SKILL.md")
        self.assertEqual(meta["name"], "guidebook")
        self.assertTrue(len(meta["description"]) > 40)

    def test_command_text_only_uses_flags_the_cli_has(self):
        text = (ROOT / "commands" / "guide.md").read_text(encoding="utf-8") + (ROOT / "skills" / "guidebook" / "SKILL.md").read_text(encoding="utf-8")
        for flag in set(re.findall(r"(?<![-\w])(--[a-z][a-z-]+)", text)):
            ok = False
            for sub in ("init", "update", "serve", "pages"):
                r = subprocess.run([sys.executable, str(ROOT / "bin" / "guidebook"), sub, "--help"], capture_output=True, text=True)
                ok = ok or flag in r.stdout
            self.assertTrue(ok, f"flag {flag} in the plugin text is not a guidebook flag")

    def test_launcher_runs_without_pythonpath_and_status_works(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(ROOT / "bin" / "guidebook"), "--version"], capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("kickoff contract 1", r.stdout)
            root = fresh_project(d)
            r = subprocess.run([sys.executable, str(ROOT / "bin" / "guidebook"), "init", str(root), "--yes"], capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = subprocess.run([sys.executable, str(ROOT / "bin" / "guidebook"), "status", str(root)], capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_theme_is_packaged(self):
        pp = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("theme/*", pp)
        self.assertTrue((ROOT / "src" / "guidebook" / "theme" / "live.js").is_file())


if __name__ == "__main__":
    unittest.main()
