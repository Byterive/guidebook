"""0.2.0: guide pages for How to run, Setup, Data and Troubleshooting (R01 to R09, R12 to R17)."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from helpers import STATUS, make_project  # noqa: F401  (sets sys.path)

from guidebook import frontmatter as fm
from guidebook.__main__ import main
from guidebook.collect import collect
from guidebook.config import make_version
from guidebook.explain import Explainer
from guidebook.facts import FactStore, extract, howto_state
from guidebook.pages import Builder

SECTIONS = """
## How to run
CONFIRMED 2026-11-05:
- Run `python app.py` from the project folder; you should see `hi`.
- Run `python test.py`.

## Setup
GUESSED (from README; confirm at the next wrap-up):
- Python 3.10 or newer.

## Data
UNKNOWN. Question: which data does this project use?

## Troubleshooting
| What you see | Why | What to do |
|---|---|---|
| No module named x | path not set | set PYTHONPATH |
"""


def project(tmp, sections=SECTIONS):
    return make_project(Path(tmp), {"PROJECT_STATUS.md": STATUS + sections})


class HowtoFacts(unittest.TestCase):
    def test_state_from_first_word(self):
        self.assertEqual(howto_state("CONFIRMED 2026-11-05:\n- x"), "CONFIRMED")
        self.assertEqual(howto_state("GUESSED (from README)\n> x"), "GUESSED")
        self.assertEqual(howto_state("UNKNOWN. Question: what?"), "UNKNOWN")
        self.assertEqual(howto_state("- plain content with no marker"), "CONFIRMED")
        self.assertEqual(howto_state(""), "UNKNOWN")

    def test_one_fact_per_section_with_its_own_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            src = next(s for s in collect(root) if s.path == "PROJECT_STATUS.md")
            facts = {f.section: f for f in extract(src) if f.kind == "howto"}
            self.assertEqual(set(facts), {"how-to-run", "setup", "data", "troubleshooting"})
            self.assertEqual({k: f.state for k, f in facts.items()},
                             {"how-to-run": "CONFIRMED", "setup": "GUESSED", "data": "UNKNOWN", "troubleshooting": "CONFIRMED"})
            hashes = {f.source_hash for f in facts.values()}
            self.assertEqual(len(hashes), 4)

    def test_editing_one_section_changes_only_its_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = {f.section: f.source_hash for s in collect(root) if s.path == "PROJECT_STATUS.md" for f in extract(s) if f.kind == "howto"}
            (root / "PROJECT_STATUS.md").write_text(STATUS + SECTIONS.replace("Python 3.10 or newer.", "Python 3.11."), encoding="utf-8")
            after = {f.section: f.source_hash for s in collect(root) if s.path == "PROJECT_STATUS.md" for f in extract(s) if f.kind == "howto"}
            self.assertEqual([k for k in before if before[k] != after[k]], ["setup"])

    def test_no_sections_no_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            facts = FactStore(root / ".guidebook" / "facts.json")
            facts.update(collect(root))
            self.assertEqual(facts.by_kind("howto"), [])

    def test_secrets_in_a_section_are_scrubbed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, "\n## Setup\nCONFIRMED\n- Set key sk-abcdefghijklmnopqrstuvwx first.\n")
            src = next(s for s in collect(root) if s.path == "PROJECT_STATUS.md")
            text = next(f.text for f in extract(src) if f.kind == "howto")
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", text)


def build(root, version="layman"):
    store = FactStore(root / ".guidebook" / "facts.json")
    src = collect(root)
    store.update(src)
    return dict(Builder(store, src, make_version(version), "Bike Shop").build())


class HowtoPages(unittest.TestCase):
    def test_four_pages_in_the_agreed_places(self):
        with tempfile.TemporaryDirectory() as tmp:
            pages = build(project(tmp))
            for rel in ("1-start/how-to-run.md", "1-start/setup.md", "4-reference/data.md", "4-reference/troubleshooting.md"):
                self.assertIn(rel, pages)

    def test_steps_are_numbered_with_what_you_should_see(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = fm.parse(build(project(tmp))["1-start/how-to-run.md"])[1]
            self.assertIn("1. Run `python app.py` from the project folder", body)
            self.assertIn("What you should see: `hi`", body)
            self.assertIn("2. Run `python test.py`", body)
            self.assertIn("What you should see: not known", body)      # the source gave none: never invented

    def test_state_wears_an_existing_status_colour(self):
        with tempfile.TemporaryDirectory() as tmp:
            pages = build(project(tmp))
            body = lambda rel: fm.parse(pages[rel])[1]
            self.assertIn("Status: PASSED.", body("1-start/how-to-run.md"))     # CONFIRMED
            self.assertIn("Status: UNTESTED.", body("1-start/setup.md"))        # GUESSED
            self.assertIn("Status: UNKNOWN.", body("4-reference/data.md"))      # UNKNOWN

    def test_unknown_section_still_gets_a_page_with_its_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = fm.parse(build(project(tmp))["4-reference/data.md"])[1]
            self.assertIn("**UNKNOWN, question:** which data does this project use?", body)

    def test_troubleshooting_is_a_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = fm.parse(build(project(tmp))["4-reference/troubleshooting.md"])[1]
            self.assertIn("| What you see | Why | What to do |", body)
            self.assertIn("| No module named x | path not set | set PYTHONPATH |", body)

    def test_a_bulleted_troubleshooting_section_becomes_a_three_column_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, """
## Troubleshooting
CONFIRMED
- The server will not start
""")
            body = fm.parse(build(root)["4-reference/troubleshooting.md"])[1]
            self.assertIn("| What you see | Why | What to do |", body)
            self.assertIn("| The server will not start | not known | not known |", body)

    def test_no_heading_means_no_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            pages = build(project(tmp, """
## Setup
CONFIRMED
- Install Python.
"""))
            self.assertIn("1-start/setup.md", pages)
            for rel in ("1-start/how-to-run.md", "4-reference/data.md", "4-reference/troubleshooting.md"):
                self.assertNotIn(rel, pages)

    def test_only_the_standard_and_full_versions_get_them_quick_start_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            for v in ("layman", "client-or-investor", "teammate", "maintainer"):
                self.assertIn("1-start/how-to-run.md", build(root, v), v)
            quick = build(root, "quick-start")
            self.assertEqual([r for r in quick if r.endswith(("how-to-run.md", "setup.md", "data.md", "troubleshooting.md"))], [])

    def test_editing_one_section_changes_only_its_page_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = {r: fm.parse(t)[0]["source_hash"] for r, t in build(root).items()}
            (root / "PROJECT_STATUS.md").write_text(STATUS + SECTIONS.replace("Python 3.10 or newer.", "Python 3.11."), encoding="utf-8")
            after = {r: fm.parse(t)[0]["source_hash"] for r, t in build(root).items()}
            howto = ("1-start/how-to-run.md", "1-start/setup.md", "4-reference/data.md", "4-reference/troubleshooting.md")
            self.assertEqual(sorted(r for r in howto if before[r] != after[r]), ["1-start/setup.md"])

    def test_status_home_and_risks_keep_their_hash_when_a_howto_section_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = {r: fm.parse(t)[0]["source_hash"] for r, t in build(root).items()}
            (root / "PROJECT_STATUS.md").write_text(STATUS + SECTIONS.replace("Python 3.10 or newer.", "Python 3.11."), encoding="utf-8")
            after = {r: fm.parse(t)[0]["source_hash"] for r, t in build(root).items()}
            for rel in ("home.md", "2-status/status.md", "4-reference/risks.md"):
                if rel in before:
                    self.assertEqual(before[rel], after[rel], rel)

    def test_the_same_input_gives_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            self.assertEqual(build(root), build(root))

    def test_secrets_never_reach_a_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp, """
## Setup
CONFIRMED
- Set key sk-abcdefghijklmnopqrstuvwx first.
""")
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", build(root)["1-start/setup.md"])


class HowtoBuild(unittest.TestCase):
    """Write the pages and build the HTML for a throwaway project (no model)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = project(cls.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            assert main(["pages", str(cls.root), "--no-model"]) == 0
            assert main(["build", str(cls.root)]) == 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_frontmatter_and_manifest_carry_the_howto_kind(self):
        meta = fm.parse((self.root / "docs/guide-src/layman/1-start/setup.md").read_text(encoding="utf-8"))[0]
        self.assertEqual((meta["kind"], meta["howto_section"]), ("howto", "setup"))
        manifest = json.loads((self.root / "docs/guide/guide.manifest.json").read_text(encoding="utf-8"))
        layman = next(v for v in manifest["versions"] if v["name"] == "layman")
        by_rel = {p["rel"]: p for p in layman["pages"]}
        self.assertEqual((by_rel["1-start/setup.md"]["kind"], by_rel["1-start/setup.md"]["howto_section"]), ("howto", "setup"))
        self.assertEqual(by_rel["1-start/setup.md"]["section"], "1-start")       # the old folder field is untouched
        self.assertNotIn("kind", by_rel["2-status/status.md"])

    def test_html_shows_a_badge_for_each_state(self):
        read = lambda rel: (self.root / "docs/guide/layman" / rel).read_text(encoding="utf-8")
        self.assertIn('class="badge b-passed">PASSED', read("1-start/how-to-run.html"))
        self.assertIn('class="badge b-untested">UNTESTED', read("1-start/setup.html"))
        self.assertIn('class="badge b-unknown">UNKNOWN', read("4-reference/data.html"))

    def test_status_is_fresh_after_a_build_and_stale_after_one_section_edit(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["status", str(self.root)]), 0)
        status = self.root / "PROJECT_STATUS.md"
        old = status.read_text(encoding="utf-8")
        try:
            status.write_text(old.replace("Python 3.10 or newer.", "Python 3.12."), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["status", str(self.root)]), 1)
            stale = [ln for ln in out.getvalue().splitlines() if ln.strip().startswith("stale")]
            self.assertTrue(any("setup.md" in ln for ln in stale))
            self.assertFalse(any("how-to-run.md" in ln or "data.md" in ln or "troubleshooting.md" in ln for ln in stale))
        finally:
            status.write_text(old, encoding="utf-8")


CONFIRMED_BOTH = """
## How to run
CONFIRMED 2026-11-05:
- Run `python app.py`; you should see `hi`.

## Setup
CONFIRMED 2026-11-05:
- Install Python 3.10 or newer.
"""


SETUP_ONLY = """
## Setup
CONFIRMED
- Install Python.
"""


class QuickStartBox(unittest.TestCase):
    def home(self, tmp, sections, version="quick-start"):
        return fm.parse(build(project(tmp, sections), version)["home.md"])[1]

    def test_box_appears_when_setup_and_how_to_run_are_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = self.home(tmp, CONFIRMED_BOTH)
            self.assertIn("## First run", body)
            self.assertIn("1. Install Python 3.10 or newer.", body)
            self.assertIn("2. Run `python app.py`. You should see: `hi`.", body)
            self.assertLess(body.index("## First run"), body.index("## Where things stand"))

    def test_box_shows_at_most_five_items(self):
        runs = "".join(f"- Do run {i}.\n" for i in range(1, 5))
        setups = "".join(f"- Do setup {i}.\n" for i in range(1, 5))
        many = "## How to run\nCONFIRMED 2026-11-05:\n" + runs + "\n## Setup\nCONFIRMED 2026-11-05:\n" + setups
        with tempfile.TemporaryDirectory() as tmp:
            body = self.home(tmp, many)
            box = body.split("## First run")[1].split("## Where things stand")[0]
            self.assertEqual(len([l for l in box.splitlines() if l[:2].rstrip(".").isdigit()]), 5)

    def test_box_is_hidden_when_either_section_is_a_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotIn("## First run", self.home(tmp, SECTIONS))      # Setup is GUESSED here
            self.assertNotIn("## First run", self.home(tmp, SETUP_ONLY))      # no How to run

    def test_other_versions_do_not_get_the_box(self):
        with tempfile.TemporaryDirectory() as tmp:
            for v in ("layman", "teammate"):
                self.assertNotIn("## First run", self.home(tmp, CONFIRMED_BOTH, v))


class HowtoModel(unittest.TestCase):
    """The model only adds an 'In plain words' part on top; the deterministic page is always there, and the cache is by section hash."""

    def build_with(self, root, cache, calls):
        store = FactStore(root / ".guidebook" / "facts.json")
        src = collect(root)
        store.update(src)
        ex = Explainer(Path(cache), lambda prompt: calls.append(prompt) or "Plain words here.", max_calls=50)
        return dict(Builder(store, src, make_version("layman"), "Bike Shop").build(ex)), ex

    def test_plain_words_go_on_top_and_unknown_sections_get_none(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as cache:
            calls = []
            pages, _ = self.build_with(project(tmp), cache, calls)
            run = fm.parse(pages["1-start/how-to-run.md"])[1]
            self.assertTrue(run.startswith("## In plain words") and "Plain words here." in run.split("## Steps")[0])
            self.assertIn("## Steps", run)                                  # the deterministic page is still there
            self.assertNotIn("In plain words", pages["4-reference/data.md"])    # UNKNOWN: nothing to explain
            self.assertFalse(any("UNKNOWN, question" in c for c in calls))

    def test_only_the_edited_section_calls_the_model_again(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as cache:
            root = project(tmp)
            first = []
            self.build_with(root, cache, first)
            again = []
            _, ex = self.build_with(root, cache, again)
            self.assertEqual(again, [])                                     # everything cached
            (root / "PROJECT_STATUS.md").write_text(STATUS + SECTIONS.replace("Python 3.10 or newer.", "Python 3.11."), encoding="utf-8")
            after = []
            self.build_with(root, cache, after)
            setup_calls = [c for c in after if "Python 3.11." in c]
            self.assertEqual(len(setup_calls), 1)
            self.assertFalse(any("python app.py" in c for c in after))      # how-to-run was not re-asked

    def test_no_model_still_writes_every_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["pages", str(project(tmp)), "--no-model"]), 0)
            self.assertTrue((Path(tmp) / "docs/guide-src/layman/1-start/how-to-run.md").is_file())


if __name__ == "__main__":
    unittest.main()


class Defang(unittest.TestCase):
    """Model text may not carry raw HTML, but a '<' inside backticks must read as typed."""

    def test_angle_bracket_outside_code_is_escaped_inside_code_is_kept(self):
        from guidebook.explain import defang
        out = defang("Open <b>x</b> and a file named `<page>.proposed.md`.")
        self.assertIn("&lt;b>x&lt;/b>", out)
        self.assertIn("`<page>.proposed.md`", out)

    def test_defang_repairs_old_cached_text_and_is_safe_twice(self):
        from guidebook.explain import defang
        once = defang("a file named `&lt;page>.proposed.md` and <i>raw</i>")
        self.assertEqual(once, "a file named `<page>.proposed.md` and &lt;i>raw&lt;/i>")
        self.assertEqual(defang(once), once)

    def test_rendered_page_shows_the_typed_name(self):
        import markdown
        from guidebook.explain import defang
        html = markdown.markdown(defang("See `<page>.proposed.md`."))
        self.assertIn("<code>&lt;page&gt;.proposed.md</code>", html)
        self.assertNotIn("&amp;lt;", html)
