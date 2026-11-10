"""Page builder: facts -> Markdown pages for one version. Deterministic: the same facts, config and cache give the same bytes.
Pages follow style-guide/site/content-rules.md (short sentences, defined words, honest status words, "not known")."""
import re
from dataclasses import dataclass

from .frontmatter import HOME, make_page
from .hashing import sources_hash, text_hash

MAX_ROWS = 80
STATUS_ORDER = ("PASSED", "DOUBTFUL", "UNKNOWN", "UNTESTED", "FAILED")
STATUS_MEANING = {
    "PASSED": "checked, and it worked",
    "DOUBTFUL": "works in part, or the check is weak",
    "UNKNOWN": "nobody knows yet",
    "UNTESTED": "written but never checked",
    "FAILED": "checked, and it did not work",
}
HOWTO_PAGES = {     # section key -> (page path, shape, title, summary)
    "how-to-run": ("1-start/how-to-run.md", "how-to", "How to run it", "The commands that run the project, one step at a time."),
    "setup": ("1-start/setup.md", "how-to", "What to set up first", "What must be installed or configured before the first run."),
    "data": ("4-reference/data.md", "result", "Data used", "Where the data comes from and where it lives."),
    "troubleshooting": ("4-reference/troubleshooting.md", "troubleshooting", "When something goes wrong", "What usually goes wrong, why it happens and what to do."),
}
# A section's state wears the colour of an existing status word. No new colours.
STATE_WORD = {"CONFIRMED": "PASSED", "GUESSED": "UNTESTED", "UNKNOWN": "UNKNOWN"}
STATE_NOTE = {
    "CONFIRMED": "This section was checked against the project.",
    "GUESSED": "This section was guessed from the project's files. Nobody has confirmed it yet.",
    "UNKNOWN": "Nobody has written this down yet.",
}
_MARK = re.compile(r"^(CONFIRMED|GUESSED|UNKNOWN)\b[.:,]?\s*")
_EXPECT = re.compile(r"(?i)(?:\byou should see\b|\bexpected?\b|\bgives\b|\breal output[^:]*:)\s*:?\s*(.+?)\.?\s*$")
_ROW = re.compile(r"^(?P<item>.*?): (?P<word>PASSED|DOUBTFUL|UNKNOWN|UNTESTED|FAILED)(?: \((?P<detail>.*)\))?$")


@dataclass
class Page:
    rel: str
    shape: str          # how-to | term | result | troubleshooting
    title: str
    summary: str
    body: str
    sources: list
    explain_key: str = ""       # set when a model explanation may be added to this page
    explain_facts: str = ""
    source_hash_override: str = ""
    kind: str = ""              # "howto" for the four status-section pages (manifest kind)
    howto_section: str = ""     # which section: how-to-run, setup, data or troubleshooting


def _facts_hash(facts, extra=""):
    """Hash of the facts a page is built from (not of the whole source file), so an edit elsewhere in the file leaves the page alone."""
    return text_hash("\n".join(f"{f.id}|{f.state}|{f.text}" for f in facts) + "\n" + extra)


def _cell(text):
    return str(text).replace("|", "/").replace("\n", " ").strip()


def _where(sources, note=""):
    lines = ["## Where this comes from", ""]
    lines += [f"- `{s}`" for s in sources] or ["- the project's file list (names only)"]
    if note:
        lines += ["", note]
    return "\n".join(lines)


def _definitions():
    rows = "\n".join(f"| {w} | {STATUS_MEANING[w]} |" for w in STATUS_ORDER)
    return "## What the status words mean\n\n| Word | Meaning |\n|---|---|\n" + rows


def _capped(rows):
    shown = rows[:MAX_ROWS]
    more = len(rows) - len(shown)
    return shown, (f"\n\n{more} more are in the source files." if more > 0 else "")


def _status_rows(facts):
    out = []
    for f in facts:
        m = _ROW.match(f.text)
        out.append((m["item"], m["word"], m["detail"] or "not known") if m else (f.text, f.status or "UNKNOWN", "not known"))
    return out


def _counts(rows):
    n = {w: sum(1 for r in rows if r[1] == w) for w in STATUS_ORDER}
    return [f"- {w}: {c} item{'s' if c != 1 else ''}" for w, c in n.items() if c]


def _howto_items(text):
    """(note, items, table lines) of a status section. The first line holds the CONFIRMED / GUESSED / UNKNOWN word; its rest is a note.
    Items are the bullet or quoted lines (wrapped lines are joined); table lines are kept as written."""
    note, items, table = "", [], []
    for i, raw in enumerate(ln for ln in text.split("\n") if ln.strip()):
        line = raw.strip()
        if i == 0 and _MARK.match(line.lstrip("> ").strip()):
            note = _MARK.sub("", line.lstrip("> ").strip(), count=1).strip(" :")
            if note.startswith("(") and note.endswith(")") and note.count("(") == 1:
                note = note[1:-1].strip()
            continue
        if line.startswith("|"):
            table.append(line)
            continue
        body = re.sub(r"^(?:>\s*)?(?:[-*]|\d+\.)?\s*", "", line)
        if raw[:1] in (" ", "\t") and items:
            items[-1] += " " + body
        else:
            items.append(body)
    return note, items, table


def _expected(item):
    """(action, what you should see) from one step. The expected result is only what the step itself says; otherwise 'not known'."""
    m = _EXPECT.search(item)
    if not m:
        return item.strip(), "not known"
    action = item[:m.start()].strip(" ,;:") or item.strip()
    return action, m.group(1).strip()


def howto_body(section, fact):
    """Markdown body for one status section, for a reader who has never seen the project. Deterministic: no model."""
    note, items, table = _howto_items(fact.text)
    head = f"Status: {STATE_WORD[fact.state]}. {STATE_NOTE[fact.state]}"
    if fact.state == "UNKNOWN":
        said = " ".join([note] + items)
        m = re.search(r"(?i)\bquestion[:]\s*(.*)", said)
        return f"{head}\n\n**UNKNOWN, question:** {m.group(1).strip() if m and m.group(1).strip() else 'not known'}"
    if note:
        head += f"\n\nNote from the project: {note}"
    if section in ("how-to-run", "setup"):
        if not items:
            return head + "\n\nNo steps are written down. Not known."
        steps = []
        for i, item in enumerate(items, 1):
            action, expect = _expected(item)
            steps.append(f"{i}. {action}\n\n    What you should see: {expect}")
        return head + "\n\n## Steps\n\nDo these in order.\n\n" + "\n\n".join(steps)
    if section == "troubleshooting":
        if table:
            return head + "\n\n" + "\n".join(table)
        rows = "\n".join(f"| {_cell(i)} | not known | not known |" for i in items) or "| not known | not known | not known |"
        return head + "\n\n| What you see | Why | What to do |\n|---|---|---|\n" + rows
    return head + "\n\n" + ("\n".join(table) + "\n" if table else "") + "\n".join(f"- {i}" for i in items)


class Builder:
    def __init__(self, store, source_list, spec, brand):
        self.store, self.source_list, self.spec, self.brand = store, source_list, spec, brand

    def _in_scope(self, f):
        if not self.spec.scope:
            return True
        return any(s == p or s.startswith(p + "/") for s in f.sources for p in self.spec.scope)

    def facts(self, kind):
        return [f for f in self.store.by_kind(kind) if self._in_scope(f)]

    def _srcs(self, facts):
        return sorted({s for f in facts for s in f.sources})

    def _page(self, rel, shape, title, summary, body, facts=(), srcs=None, **kw):
        return Page(rel, shape, title, summary, body, self._srcs(facts) if srcs is None else srcs, **kw)

    # ---- individual pages -------------------------------------------------
    def overview(self, others=()):
        purpose, results = self.facts("purpose"), self.facts("result")
        rows = _status_rows(results)
        one = self.spec.depth == "one-page"
        parts = [f"## What this is\n"]
        if purpose:
            parts.append(purpose[0].text)
            if not purpose[0].confirmed:
                parts.append("\nThis comes from the README. No project brief confirms it.")
        else:
            parts.append("What this project is for is not known. No brief or README states it.")
        box = self._first_run() if one and "howto" not in self.spec.skip else []
        if box:
            parts += ["\n## First run\n"] + box
        parts += ["\n## Where things stand\n"]
        parts += _counts(rows) if rows else ["Status is not known. No status table was found."]
        if one:
            steps, risks = self.facts("step"), self.facts("risk")
            parts += ["\n## What comes next\n"] + ([f"{i}. {f.text}" for i, f in enumerate(steps[:10], 1)] or ["Next steps are not known."])
            if "risks" not in self.spec.skip:
                parts += ["\n## What could go wrong\n"] + ([f"- {f.text}" for f in risks[:10]] or ["No risks are recorded."])
            parts.append("\n" + _definitions())
        else:
            parts += ["\n## Read next\n"] + [f"- [{p.title}]({p.rel}): {p.summary}" for p in others]
        facts = purpose[:1] + results + (self.facts("howto") if box else [])
        body = "\n".join(parts)
        page = self._page(HOME, "result", self.brand, f"What {self.brand} is and where it stands, in plain words.", body + "\n\n" + _where(self._srcs(facts)),
                          facts, explain_key="overview", explain_facts="\n".join(f.text for f in facts))
        used = facts + (self.facts("step")[:10] + self.facts("risk")[:10] if one else [])
        page.source_hash_override = _facts_hash(used, "\n".join(f"{p.rel}|{p.title}|{p.summary}" for p in others))
        return page

    def _first_run(self):
        """Short numbered steps from Setup then How to run. Empty unless both sections exist and are CONFIRMED (a guess never reaches the home page)."""
        found = {f.section: f for f in self.facts("howto")}
        if not all(k in found and found[k].state == "CONFIRMED" for k in ("setup", "how-to-run")):
            return []
        lines = []
        for item in _howto_items(found["setup"].text)[1] + _howto_items(found["how-to-run"].text)[1]:
            action, expect = _expected(item)
            action = action if action.endswith((".", "!", "?")) else action + "."
            lines.append(f"{len(lines) + 1}. {action}" + (f" You should see: {expect}." if expect != "not known" else ""))
        return lines[:5]

    def steps(self):
        steps = self.facts("step")
        if not steps:
            return None
        body = ["Do these in order. Each step is one action.\n"] + [f"{i}. {f.text}" for i, f in enumerate(steps, 1)]
        body += ["\nAfter each step, check the status page to see what changed."]
        return self._page("1-start/next-steps.md", "how-to", "What comes next", "The next steps for the project, in order.", "\n".join(body) + "\n\n" + _where(self._srcs(steps)), steps)

    def status(self):
        results = self.facts("result")
        if not results:
            return None
        rows, extra = _capped(_status_rows(results))
        table = "| Item | Status | Detail |\n|---|---|---|\n" + "\n".join(f"| {_cell(i)} | {w} | {_cell(d)} |" for i, w, d in rows) + extra
        body = f"{len(results)} item{'s' if len(results) != 1 else ''} have a status.\n\n" + table + "\n\n" + _definitions()
        page = self._page("2-status/status.md", "result", "Status of each part", "Each part of the project with its status word and detail.",
                          body + "\n\n" + _where(self._srcs(results)), results, explain_key="status", explain_facts="\n".join(f.text for f in results))
        page.source_hash_override = _facts_hash(results)
        return page

    def decisions(self):
        ds = self.facts("decision")
        if not ds or "decisions" in self.spec.skip:
            return None
        lines, extra = _capped([f"- {f.text}" for f in ds])
        body = "These choices were made. Each line has the date, the choice, the reason and what was rejected.\n\n" + "\n".join(lines) + extra
        return self._page("3-decisions/decisions.md", "result", "Decisions made", "Choices the project made, with the date and the reason.", body + "\n\n" + _where(self._srcs(ds)), ds)

    def risks(self):
        rs = self.facts("risk")
        if not rs or "risks" in self.spec.skip:
            return None
        rows, extra = _capped(rs)
        table = "| What could go wrong | What to do |\n|---|---|\n" + "\n".join(f"| {_cell(f.text)} | not known |" for f in rows) + extra
        body = "These problems are written down in the project. The source does not say what to do about them, so that column says not known.\n\n" + table
        page = self._page("4-reference/risks.md", "troubleshooting", "Risks and gaps", "Problems the project records, and what is known about fixing them.", body + "\n\n" + _where(self._srcs(rs)), rs)
        page.source_hash_override = _facts_hash(rs)
        return page

    def terms(self):
        ts = self.facts("term")
        if not ts or "terms" in self.spec.skip:
            return None
        rows, extra = _capped(ts)
        body = "Words the project uses, with the meaning the project gives them.\n\n" + "\n".join(f"- **{f.text.split(': ', 1)[0]}**: {f.text.split(': ', 1)[-1]}" for f in rows) + extra
        return self._page("4-reference/terms.md", "term", "Words used here", "Terms the project uses and what they mean.", body + "\n\n" + _where(self._srcs(ts)), ts)

    def howto(self, section):
        """One page per PROJECT_STATUS.md section. A project without that heading gets no page; a section that says UNKNOWN gets a page that says so."""
        if self.spec.depth == "one-page" or "howto" in self.spec.skip:
            return None
        fact = next((f for f in self.facts("howto") if f.section == section), None)
        if fact is None:
            return None
        rel, shape, title, summary = HOWTO_PAGES[section]
        page = self._page(rel, shape, title, summary, howto_body(section, fact) + "\n\n" + _where(self._srcs([fact])), [fact],
                          explain_key=f"howto-{section}" if fact.state != "UNKNOWN" else "", explain_facts=fact.text)
        page.source_hash_override = fact.source_hash
        page.kind, page.howto_section = "howto", section
        return page

    def files(self):
        if self.spec.depth != "full" or "files" in self.spec.skip:
            return None
        scoped = [s for s in self.source_list if not self.spec.scope or any(s.path == p or s.path.startswith(p + "/") for p in self.spec.scope)]
        if not scoped:
            return None
        rows, extra = _capped(scoped)
        table = "| File | Kind |\n|---|---|\n" + "\n".join(f"| `{_cell(s.path)}` | {s.kind} |" for s in rows) + extra
        body = f"{len(scoped)} file{'s' if len(scoped) != 1 else ''} were read. Only names and kinds are listed.\n\n" + table
        page = self._page("4-reference/files.md", "result", "Files read", "The project files this guide was built from.", body + "\n\n" + _where([], "Names only; file contents are not copied."), (), srcs=[])
        page.source_hash_override = sources_hash({s.path: "" for s in scoped})
        return page

    # ---- assembly ---------------------------------------------------------
    def build(self, explainer=None, only=None):
        """Return [(rel, full page text)] for this version, overview first. The model's "In plain words" section goes on top when the explainer has one; `only` limits the explainer to those page rels."""
        def how(s):
            return lambda: self.howto(s)
        order = (self.steps, how("how-to-run"), how("setup"), self.status, self.decisions, self.risks, self.terms, self.files, how("data"), how("troubleshooting"))
        others = [] if self.spec.depth == "one-page" else [p for p in (fn() for fn in order) if p]
        out = []
        for page in [self.overview(others)] + others:
            shash = getattr(page, "source_hash_override", None) or sources_hash({s: self.store.source_hashes.get(s, "") for s in page.sources})
            body = page.body
            if explainer and page.explain_key and page.sources and (only is None or page.rel in only):
                text = explainer.explain(page.explain_key, page.explain_facts, page.sources, shash, self.spec)
                if text:
                    body = "## In plain words\n\n" + text + "\n\n" + body
            kw = [page.shape, self.spec.audience, self.brand.lower()]
            out.append((page.rel, make_page(page.title, page.summary, kw, self.spec.name, page.sources, shash, body, kind=page.kind, howto_section=page.howto_section)))
        return out
