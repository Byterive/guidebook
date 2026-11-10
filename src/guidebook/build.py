"""Builder: Markdown pages in docs/guide-src/<version>/ -> static, offline HTML in <output>/<version>/, plus a landing page.

Adapted from style-guide/site/build_site.py (read-only source). Differences: one Site per version, a version switcher in
the header, a landing page that lists the versions, and an "Other versions of this page" list built from the manifest.
Links resolve only inside their own version. Output is deterministic: no timestamps, sorted everywhere."""
import html as htmllib
import json
import posixpath
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .facts import STATUS_WORDS
from .frontmatter import HOME, is_page_file, parse

THEME = Path(__file__).resolve().parent / "theme"
MANIFEST_CONTRACT = 1


@dataclass
class SitePage:
    rel: str
    meta: dict
    body: str

    @property
    def title(self):
        return str(self.meta.get("title") or self.rel)

    @property
    def summary(self):
        return str(self.meta.get("summary", ""))

    @property
    def html_rel(self):
        return "index.html" if self.rel == HOME else self.rel[:-3] + ".html"


@dataclass
class BuildReport:
    built: dict = field(default_factory=dict)       # version -> page count
    missing: list = field(default_factory=list)     # versions with no source pages
    manifest: dict = field(default_factory=dict)


def fill(template, **values):
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def esc(s):
    return htmllib.escape(str(s), quote=True)


def section_title(folder):
    return re.sub(r"^\d+-", "", folder).replace("-", " ").capitalize()


def load_pages(src: Path):
    pages = []
    for p in sorted(src.rglob("*.md")):
        if not is_page_file(p):
            continue
        meta, body = parse(p.read_text(encoding="utf-8"))
        pages.append(SitePage(p.relative_to(src).as_posix(), meta, body))
    return sorted(pages, key=lambda q: q.rel)


def fix_links(html, from_rel, by_rel):
    """.md links become .html and carry the target's summary as hover text. A link to a page that is not in this version stays as written."""
    def swap(m):
        path, anchor = m.group(1), m.group(2) or ""
        page = by_rel.get(posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), path + ".md")))
        if page is None:
            return m.group(0)
        return f'href="{path}.html{anchor}" title="{esc(page.summary)}"'
    return re.sub(r'href="([^"#:]+)\.md(#[^"]*)?"', swap, html)


def badges(html, words=STATUS_WORDS):
    """Wrap the status words in colour badges, outside tags, <code> and <pre>. The word stays inside the badge."""
    pat = re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\b")
    out, skip = [], 0
    for part in re.split(r"(<[^>]+>)", html):
        if part.startswith("<"):
            low = part.lower()
            skip += low.startswith(("<code", "<pre"))
            skip = max(0, skip - low.startswith(("</code", "</pre")))
            out.append(part)
        else:
            out.append(part if skip else pat.sub(lambda m: f'<span class="badge b-{m.group(1).lower()}">{m.group(1)}</span>', part))
    return "".join(out)


def make_manifest(brand, specs, loaded, output):
    versions = []
    for spec in specs:
        pages = loaded.get(spec.name, [])
        if not pages:
            continue
        versions.append({"name": spec.name, "audience": spec.audience, "depth": spec.depth, "reader": spec.reader, "dir": spec.name,
                         "pages": [{"rel": p.rel, "html": p.html_rel, "title": p.title, "summary": p.summary,
                                    "section": p.rel.split("/")[0] if "/" in p.rel else "",
                                    **({"kind": p.meta["kind"], "howto_section": p.meta.get("howto_section", "")} if p.meta.get("kind") else {})}
                                   for p in pages]})
    return {"contract": MANIFEST_CONTRACT, "brand": brand, "output": output, "versions": versions}


class Site:
    """One version of the guide."""

    def __init__(self, spec, pages, manifest, brand, templates):
        self.spec, self.pages, self.manifest, self.brand, self.t = spec, pages, manifest, brand, templates
        self.by_rel = {p.rel: p for p in pages}
        self.sections = {}
        for p in pages:
            if "/" in p.rel:
                self.sections.setdefault(p.rel.split("/")[0], []).append(p)
        self.vpages = {v["name"]: {p["rel"]: p for p in v["pages"]} for v in manifest["versions"]}

    # ---- header parts ----------------------------------------------------
    def menu(self, current, prefix):
        cur_top = current.split("/")[0] if "/" in current else ""
        items = []
        for top in sorted(self.sections):
            links = [f'<a class="all" href="{prefix}{top}/index.html">All in {esc(section_title(top))} &rarr;</a>']
            links += [f'<a{" class=on" if p.rel == current else ""} href="{prefix}{p.html_rel}">{esc(p.title)}</a>' for p in self.sections[top]]
            items.append(fill(self.t["dropdown"], open_class=' class="dd on"' if top == cur_top else ' class="dd"', label=esc(section_title(top)), links="".join(links)))
        return "".join(items)

    def switcher(self, current, prefix):
        """Version drop-down: same page in the other version when it exists, else that version's home."""
        links = [f'<a class="all" href="{prefix}../index.html">All versions &rarr;</a>']
        for v in self.manifest["versions"]:
            target = self.vpages[v["name"]].get(current)
            href = f'{prefix}../{v["name"]}/{target["html"] if target else "index.html"}'
            links.append(f'<a{" class=on" if v["name"] == self.spec.name else ""} href="{esc(href)}" title="{esc(v["reader"])}">{esc(v["name"])}</a>')
        if len(self.manifest["versions"]) < 2:
            return ""
        return fill(self.t["dropdown"], open_class=' class="dd"', label=f"Version: {esc(self.spec.name)}", links="".join(links))

    def other_versions(self, rel, prefix):
        """'Other versions of this page', from the manifest (not from Markdown links)."""
        links = [f'<a href="{esc(prefix)}../{esc(v["name"])}/{esc(self.vpages[v["name"]][rel]["html"])}">{esc(v["name"])}</a>'
                 for v in self.manifest["versions"] if v["name"] != self.spec.name and rel in self.vpages[v["name"]]]
        return f'<nav class="ov" aria-label="Other versions of this page"><b>Other versions of this page:</b> {" ".join(links)}</nav>' if links else ""

    def header(self, current, prefix):
        return fill(self.t["header"], prefix=prefix, brand=esc(self.brand), menu=self.menu(current, prefix), versions=self.switcher(current, prefix))

    def card(self, p, prefix):
        return fill(self.t["card"], href=f"{prefix}{p.html_rel}", title=esc(p.title), summary=esc(p.summary))

    def cards(self, pages, prefix):
        return '<div class="cards">' + "".join(self.card(p, prefix) for p in pages) + "</div>"

    def page(self, title, body, current, prefix, crumb, pager="", toc="", other=""):
        aside = f'<aside class="toc"><b>On this page</b>{toc}</aside>' if toc else ""
        return fill(self.t["page"], title=esc(title), brand=esc(self.brand), prefix=prefix, header=self.header(current, prefix),
                    crumb=crumb, body=body, other=other, pager=pager, aside=aside)

    # ---- build -------------------------------------------------------------
    def build(self, out: Path) -> int:
        import markdown
        out.mkdir(parents=True, exist_ok=True)
        entries = [{"u": p.html_rel, "t": p.title, "s": p.summary, "x": (p.title + " " + p.summary + " " + " ".join(p.meta.get("keywords", [])) + " " + re.sub(r"\W+", " ", p.body)).lower()} for p in self.pages]
        write_assets(out, entries)
        ordered = [p for p in self.pages if p.rel != HOME]
        for i, p in enumerate(ordered):
            md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"])
            prefix = "../" * p.rel.count("/")
            top = p.rel.split("/")[0] if "/" in p.rel else ""
            crumb = " / ".join([f'<a href="{prefix}index.html">Home</a>'] + ([f'<a href="{prefix}{top}/index.html">{esc(section_title(top))}</a>'] if top else []) + [esc(p.title)])
            prev_, next_ = (ordered[i - 1] if i else None), (ordered[i + 1] if i + 1 < len(ordered) else None)
            pager = fill(self.t["pager"], prev=f'<a href="{prefix}{prev_.html_rel}">&larr; {esc(prev_.title)}</a>' if prev_ else "",
                         next=f'<a href="{prefix}{next_.html_rel}">{esc(next_.title)} &rarr;</a>' if next_ else "")
            body = badges(fix_links(md.convert(p.body), p.rel, self.by_rel))
            toc = md.toc if body.count("<h2") >= 3 else ""
            target = out / p.html_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.page(p.title, f"<h1>{esc(p.title)}</h1>" + body, p.rel, prefix, crumb, pager, toc, self.other_versions(p.rel, prefix)), encoding="utf-8", newline="\n")
        for top, plist in sorted(self.sections.items()):
            title = section_title(top)
            body = f"<h1>{esc(title)}</h1>" + self.cards([q for q in sorted(plist, key=lambda q: q.rel)], "../")
            target = out / top / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.page(title, body, top + "/index.md", "../", f'<a href="../index.html">Home</a> / {esc(title)}'), encoding="utf-8", newline="\n")
        home = self.by_rel.get(HOME)
        intro = badges(fix_links(markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"]).convert(home.body), HOME, self.by_rel)) if home else ""
        heading = f"<h1>{esc(home.title if home else self.brand)}</h1>"
        sections = "<h2>Browse by section</h2>" + "".join(f'<h3><a href="{top}/index.html">{esc(section_title(top))}</a></h3>{self.cards(sorted(pl, key=lambda q: q.rel)[:6], "")}' for top, pl in sorted(self.sections.items())) if self.sections else ""
        other = self.other_versions(HOME, "")
        (out / "index.html").write_text(self.page("Home", fill(self.t["home"], heading=heading, intro=intro, sections=sections), "", "", "Home", other=other), encoding="utf-8", newline="\n")
        return len(self.pages)


def write_assets(out: Path, entries):
    shutil.copyfile(THEME / "style.css", out / "style.css")
    js = (THEME / "search.template.js").read_text(encoding="utf-8").replace("__ENTRIES__", json.dumps(entries, sort_keys=True, ensure_ascii=False))
    (out / "search.js").write_text(js, encoding="utf-8", newline="\n")
    shutil.copyfile(THEME / "live.js", out / "live.js")


def build_landing(out: Path, manifest, templates, entries):
    """Landing page: one card per version, plus a search over every version."""
    import markdown  # noqa: F401  (build() needs it too; fail early with the same message)
    write_assets(out, entries)
    cards = "".join(fill(templates["card"], href=f'{v["name"]}/index.html', title=esc(v["name"]),
                         summary=esc(f'{v["reader"] or v["audience"]} ({v["depth"]}, {len(v["pages"])} page{"s" if len(v["pages"]) != 1 else ""})')) for v in manifest["versions"])
    body = fill(templates["home"], heading=f'<h1>{esc(manifest["brand"])}</h1>', intro="<p>Pick the version of this guide that fits you.</p>", sections=f'<div class="cards">{cards}</div>')
    header = fill(templates["header"], prefix="", brand=esc(manifest["brand"]), menu="", versions="")
    page = fill(templates["page"], title="All versions", brand=esc(manifest["brand"]), prefix="", header=header, crumb="Home", body=body, other="", pager="", aside="")
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")


def build_guide(project, src_root, out_root, brand, specs, output_rel="docs/guide") -> BuildReport:
    """Build every version that has source pages. Writes <out>/guide.manifest.json and <project>/.guidebook/manifest.json."""
    project, src_root, out_root = Path(project), Path(src_root), Path(out_root)
    templates = {n: (THEME / "templates" / f"{n}.html").read_text(encoding="utf-8") for n in ("page", "header", "dropdown", "card", "pager", "home")}
    loaded = {s.name: load_pages(src_root / s.name) for s in specs if (src_root / s.name).is_dir()}
    rep = BuildReport(missing=[s.name for s in specs if not loaded.get(s.name)])
    manifest = make_manifest(brand, specs, loaded, output_rel)
    rep.manifest = manifest
    if not manifest["versions"]:
        return rep
    out_root.mkdir(parents=True, exist_ok=True)
    landing_entries = []
    for spec in specs:
        pages = loaded.get(spec.name)
        if not pages:
            continue
        rep.built[spec.name] = Site(spec, pages, manifest, brand, templates).build(out_root / spec.name)
        landing_entries += [{"u": f"{spec.name}/{p.html_rel}", "t": f"{p.title} ({spec.name})", "s": p.summary,
                             "x": (p.title + " " + p.summary + " " + re.sub(r"\W+", " ", p.body)).lower()} for p in pages]
    build_landing(out_root, manifest, templates, landing_entries)
    text = json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    (out_root / "guide.manifest.json").write_text(text, encoding="utf-8", newline="\n")
    (project / ".guidebook").mkdir(exist_ok=True)
    (project / ".guidebook" / "manifest.json").write_text(text, encoding="utf-8", newline="\n")
    return rep


def html_paths(per_version) -> list:
    """Every file build_guide writes under the output folder, given {version: [page rel paths]}. Used by `init --dry-run`."""
    out = ["index.html", "style.css", "search.js", "live.js", "guide.manifest.json"]
    for name, rels in per_version.items():
        out += [f"{name}/{f}" for f in ("style.css", "search.js", "live.js", "index.html")]
        tops = set()
        for rel in rels:
            out.append(f"{name}/" + ("index.html" if rel == HOME else rel[:-3] + ".html"))
            if "/" in rel:
                tops.add(rel.split("/")[0])
        out += [f"{name}/{t}/index.html" for t in sorted(tops)]
    return sorted(set(out))
