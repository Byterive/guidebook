"""status and update: compare what the project says now with what the guide was last built from.

A page is classified by its frontmatter: generated pages carry the hash of the sources they were written from.
  fresh    source_hash matches what the sources give now
  stale    source_hash differs (a source changed)
  missing  the page should exist but does not
  user     no generated:true, never touched
An edited generated page (body no longer matches page_hash) is additionally flagged `edited`: update will not overwrite it."""
from dataclasses import dataclass, field
from pathlib import Path

from . import state as st
from .build import build_guide
from .collect import collect
from .config import load_config
from .explain import ClaudeRunner, Explainer
from .facts import FactStore
from .frontmatter import edit_state, is_page_file, parse
from .pages import Builder
from .scrub import scrub
from .writer import stale_generated, write_pages


@dataclass
class PageStatus:
    version: str
    rel: str
    state: str                      # fresh | stale | missing | proposed (edited by you, new text waits in .proposed.md)
    edited: bool = False
    changed: list = field(default_factory=list)     # sources that changed since the last build (stale pages)


@dataclass
class StatusReport:
    pages: list = field(default_factory=list)
    orphans: list = field(default_factory=list)
    proposals: list = field(default_factory=list)
    html: str = "fresh"             # fresh | not built | out of date
    scrub_hits: list = field(default_factory=list)
    built_at: str = ""
    pages_at: str = ""
    commit: str = ""
    changed_sources: list = field(default_factory=list)

    @property
    def stale(self):
        return [p for p in self.pages if p.state in ("stale", "missing")]

    @property
    def ok(self):
        return not self.stale and self.html == "fresh" and not self.scrub_hits

    def lines(self):
        out = []
        for v in sorted({p.version for p in self.pages}):
            mine = [p for p in self.pages if p.version == v]
            bad = [p for p in mine if p.state in ("stale", "missing")]
            out.append(f"{v}: {'stale' if bad else 'fresh'} ({len([p for p in mine if p.state in ('fresh', 'proposed')])} of {len(mine)} pages up to date)")
            for p in bad:
                why = "page is missing" if p.state == "missing" else f"{len(p.changed)} source{'s' if len(p.changed) != 1 else ''} changed since the last build: {', '.join(p.changed) or 'not known'}"
                out.append(f"  {p.state:8} {p.rel} - {why}" + ("; you edited this page, update will write a .proposed.md" if p.edited else ""))
            for p in mine:
                if p.edited and p.state == "fresh":
                    out.append(f"  edited   {p.rel} - your edit is kept")
                if p.state == "proposed":
                    out.append(f"  proposal {p.rel} - sources changed after your edit; merge {p.rel[:-3]}.proposed.md or delete it")
        if self.changed_sources:
            out.append(f"{len(self.changed_sources)} source{'s' if len(self.changed_sources) != 1 else ''} used by pages changed since the last build")
        for o in self.orphans:
            out.append(f"  orphan   {o} - generated page the project no longer produces (kept)")
        for p in self.proposals:
            out.append(f"  proposal {p} - waiting for you to merge or delete")
        out.append({"fresh": "html: fresh", "not built": "html: not built (run `guidebook build`)", "out of date": "html: out of date (run `guidebook build`)"}[self.html])
        for s in self.scrub_hits:
            out.append(f"  scrub    {s} - text that looks sensitive (email, token, private path); edit or remove it")
        out.append(f"last pages written: {self.pages_at or 'never'}; last html built: {self.built_at or 'never'}; project commit: {self.commit or 'not known (not a git repo)'}")
        return out

    def as_dict(self):
        return {"ok": self.ok, "stale": [f"{p.version}/{p.rel}" for p in self.stale], "html": self.html, "proposals": self.proposals,
                "orphans": self.orphans, "scrub": self.scrub_hits, "built_at": self.built_at, "pages_at": self.pages_at, "commit": self.commit,
                "changed_sources": self.changed_sources, "lines": self.lines()}


def _store(root, cfg, sources):
    """Facts for the current sources, in memory only (status never writes)."""
    s = FactStore(root / ".guidebook" / "facts.json")
    s.update(sources, cfg.status_map)
    return s


def _expected(root, cfg, store, sources, versions, ex=None, only=None):
    return {spec.name: Builder(store, sources, spec, cfg.brand).build(ex, only) for spec in versions}


def _classify(root, cfg, store, sources, versions):
    src_root = root / "docs" / "guide-src"
    now = {s.path: s.hash for s in sources}
    old = st.load(root).get("sources", {})
    rep = StatusReport()
    expected = _expected(root, cfg, store, sources, versions)
    changed_all = set()
    for spec in versions:
        for rel, text in expected[spec.name]:
            meta, _ = parse(text)
            f = src_root / spec.name / rel
            if not f.is_file():
                rep.pages.append(PageStatus(spec.name, rel, "missing"))
                continue
            kind = edit_state(f.read_text(encoding="utf-8"))
            if kind == "user":
                continue
            have, _ = parse(f.read_text(encoding="utf-8"))
            if have.get("source_hash") == meta["source_hash"]:
                rep.pages.append(PageStatus(spec.name, rel, "fresh", kind == "edited"))
            else:
                prop = f.with_name(f.stem + ".proposed.md")
                if kind == "edited" and prop.is_file() and parse(prop.read_text(encoding="utf-8"))[0].get("source_hash") == meta["source_hash"]:
                    rep.pages.append(PageStatus(spec.name, rel, "proposed", True))      # you have not merged it yet; not counted as stale
                    continue
                changed = sorted(s for s in set(meta["sources"]) | set(have.get("sources", [])) if old.get(s) != now.get(s))
                changed_all.update(changed)
                rep.pages.append(PageStatus(spec.name, rel, "stale", kind == "edited", changed))
        rep.orphans += stale_generated(src_root, spec.name, {rel for rel, _ in expected[spec.name]})
        base = src_root / spec.name
        rep.proposals += sorted(f"{spec.name}/{p.relative_to(base).as_posix()}" for p in base.rglob("*.proposed.md")) if base.is_dir() else []
    rep.changed_sources = sorted(changed_all)
    return rep, expected


def status(project) -> StatusReport:
    root = Path(project).resolve()
    cfg = load_config(root)
    sources = collect(root)
    rep, _ = _classify(root, cfg, _store(root, cfg, sources), sources, cfg.versions)
    s = st.load(root)
    rep.built_at, rep.pages_at, rep.commit = s.get("built_at", ""), s.get("pages_at", ""), s.get("commit", "")
    out = root / cfg.output
    src_root = root / "docs" / "guide-src"
    if not (out / "guide.manifest.json").is_file():
        rep.html = "not built"
    elif s.get("pages_digest") != st.pages_digest(src_root):
        rep.html = "out of date"
    for f in sorted(src_root.rglob("*.md")) if src_root.is_dir() else []:
        if not is_page_file(f):
            continue
        if scrub(f.read_text(encoding="utf-8"))[1]:
            rep.scrub_hits.append(f.relative_to(root).as_posix())
    return rep


@dataclass
class UpdateReport:
    written: list = field(default_factory=list)
    proposed: list = field(default_factory=list)
    skipped_edited: list = field(default_factory=list)
    nothing_to_do: bool = False
    built: dict = field(default_factory=dict)
    calls: int = 0
    hits: int = 0
    capped: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    changed_sources: list = field(default_factory=list)
    dry_run: bool = False


def update(project, version=None, dry_run=False, no_model=False, max_calls=20, runner=None) -> UpdateReport:
    """Re-extract facts for changed sources, rewrite only affected pages, rebuild the HTML. Edited pages become .proposed.md."""
    root = Path(project).resolve()
    cfg = load_config(root)
    versions = [v for v in cfg.versions if not version or v.name == version]
    if version and not versions:
        raise ValueError(f"no version named {version!r}; configured: {', '.join(v.name for v in cfg.versions)}")
    sources = collect(root)
    store = FactStore(root / ".guidebook" / "facts.json")
    store.update(sources, cfg.status_map)
    rep = UpdateReport(dry_run=dry_run)
    cls, expected = _classify(root, cfg, store, sources, versions)
    rep.changed_sources = cls.changed_sources
    todo = {}                                   # version -> {rel}
    for p in cls.stale:
        todo.setdefault(p.version, set()).add(p.rel)
    ex = Explainer(root / ".guidebook" / "cache", None if no_model else (runner or ClaudeRunner()), max_calls=max_calls)
    src_root = root / "docs" / "guide-src"
    for spec in versions:
        rels = todo.get(spec.name)
        if not rels:
            continue
        pages = Builder(store, sources, spec, cfg.brand).build(None if no_model else ex, only=rels)
        wr = write_pages(src_root, spec.name, [(r, t) for r, t in pages if r in rels], dry_run)
        rep.written += wr.created + wr.updated
        rep.proposed += wr.proposed
    rep.calls, rep.hits, rep.capped, rep.errors = ex.calls, ex.hits, ex.capped, ex.errors
    rep.skipped_edited = [f"{p.version}/{p.rel}" for p in cls.pages if p.edited and p.state == "fresh"]
    out = root / cfg.output
    html_old = st.load(root).get("pages_digest") != st.pages_digest(src_root) or not (out / "guide.manifest.json").is_file()
    rep.nothing_to_do = not rep.written and not rep.proposed and not html_old
    if dry_run:
        return rep
    store.save()
    st.record_pages(root, sources)
    if rep.written or html_old:
        b = build_guide(root, src_root, out, cfg.brand, cfg.versions, cfg.output)
        rep.built = b.built
        st.record_build(root, src_root)
    return rep
