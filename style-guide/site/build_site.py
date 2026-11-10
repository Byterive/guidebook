"""
title: build_site
purpose: Turn a folder of Markdown pages into a static, offline documentation website with the guide's look: sticky header with one drop-down per top-level folder, search box
         (press /), light/dark toggle, section landing pages with cards, breadcrumb, "on this page" list, previous/next links, status words shown as colour badges, and links to other
         pages that carry the target's one-line summary as hover text. Opens from the file system (no server).
inputs:  --src folder of .md files. Each page starts with a frontmatter block (title, summary, keywords: [a, b]). Top-level sub-folders become the menu sections
         (a leading "1-" style number sets the order and is not shown). An optional index.md in the folder root is the home page text. Files starting with "_" are skipped.
         Templates come from ./templates and the stylesheet and search script from this folder (style.css, search.template.js).
outputs: --out folder with index.html, <section>/index.html, every page as .html, style.css, search.js
usage:   pip install markdown
         python build_site.py --src sample-content --out ../preview/site --brand "Acme"
         optional: --sections "1-start=Start here,2-guides=Guides" (titles), --status-words PASSED FAILED DOUBTFUL UNTESTED UNKNOWN
"""
import argparse
import html as htmllib
import json
import posixpath
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_STATUS_WORDS = ("PASSED", "FAILED", "DOUBTFUL", "UNTESTED", "UNKNOWN")


@dataclass
class Page:
    rel: str            # path inside the source folder, forward slashes
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
        return self.rel[:-3] + ".html"


def parse_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith((" ", "#")):
            key, val = line.split(":", 1)
            val = val.strip()
            meta[key.strip()] = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()] if val.startswith("[") else val.strip("'\"")
    return meta, text[m.end():]


def load_pages(src):
    pages = []
    for p in sorted(Path(src).rglob("*.md")):
        if p.name.startswith("_"):
            continue
        meta, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        pages.append(Page(p.relative_to(src).as_posix(), meta, body))
    return pages


def fill(template, **values):
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def section_title(folder, titles):
    return titles.get(folder) or re.sub(r"^\d+-", "", folder).replace("-", " ").capitalize()


def fix_links(html, from_rel, by_rel):
    """.md links become .html; links to other pages in the folder carry that page's summary as hover text."""
    def swap(m):
        path, anchor = m.group(1), m.group(2) or ""
        page = by_rel.get(posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), path + ".md")))
        if page is None:
            return m.group(0)
        return f'href="{path}.html{anchor}" title="{htmllib.escape(page.summary, quote=True)}"'
    return re.sub(r'href="([^"#:]+)\.md(#[^"]*)?"', swap, html)


def badges(html, words):
    """Wrap the status words in colour badges, outside tags, <code> and <pre>."""
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


class Site:
    def __init__(self, src, out, brand, titles, words):
        self.src, self.out, self.brand, self.titles, self.words = Path(src), Path(out), brand, titles, words
        self.t = {n: (HERE / "templates" / f"{n}.html").read_text(encoding="utf-8") for n in ("page", "header", "dropdown", "card", "pager", "home")}
        self.pages = load_pages(src)
        self.by_rel = {p.rel: p for p in self.pages}
        self.sections = {}
        for p in self.pages:
            if "/" in p.rel:
                self.sections.setdefault(p.rel.split("/")[0], []).append(p)

    def header(self, current, prefix):
        cur_top = current.split("/")[0] if "/" in current else ""
        items = []
        for top in sorted(self.sections):
            here = self.sections[top]
            links = [f'<a class="all" href="{prefix}{top}/index.html">All in {htmllib.escape(section_title(top, self.titles))} &rarr;</a>']
            links += [f'<a{" class=on" if p.rel == current else ""} href="{prefix}{p.html_rel}">{htmllib.escape(p.title)}</a>' for p in here]
            items.append(fill(self.t["dropdown"], open_class=' class="dd on"' if top == cur_top else ' class="dd"', label=htmllib.escape(section_title(top, self.titles)), links="".join(links)))
        return fill(self.t["header"], prefix=prefix, brand=htmllib.escape(self.brand), menu="".join(items))

    def card(self, p, prefix):
        return fill(self.t["card"], href=f"{prefix}{p.html_rel}", title=htmllib.escape(p.title), summary=htmllib.escape(p.summary))

    def cards(self, pages, prefix):
        return '<div class="cards">' + "".join(self.card(p, prefix) for p in pages) + "</div>"

    def page(self, title, body, current, prefix, crumb, pager="", toc=""):
        aside = f'<aside class="toc"><b>On this page</b>{toc}</aside>' if toc else ""
        return fill(self.t["page"], title=htmllib.escape(title), brand=htmllib.escape(self.brand), prefix=prefix, header=self.header(current, prefix), crumb=crumb, body=body, pager=pager, aside=aside)

    def build(self):
        import markdown
        self.out.mkdir(parents=True, exist_ok=True)
        entries = [{"u": p.html_rel, "t": p.title, "s": p.summary,
                    "x": (p.title + " " + p.summary + " " + " ".join(p.meta.get("keywords", [])) + " " + re.sub(r"\W+", " ", p.body)).lower()} for p in self.pages]
        shutil.copyfile(HERE / "style.css", self.out / "style.css")
        (self.out / "search.js").write_text((HERE / "search.template.js").read_text(encoding="utf-8").replace("__ENTRIES__", json.dumps(entries)), encoding="utf-8")
        ordered = [p for p in self.pages if p.rel != "index.md"]
        for i, p in enumerate(ordered):
            md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"])
            prefix = "../" * p.rel.count("/")
            top = p.rel.split("/")[0] if "/" in p.rel else ""
            crumb = " / ".join([f'<a href="{prefix}index.html">Home</a>'] + ([f'<a href="{prefix}{top}/index.html">{htmllib.escape(section_title(top, self.titles))}</a>'] if top else []) + [htmllib.escape(p.title)])
            prev_, next_ = (ordered[i - 1] if i else None), (ordered[i + 1] if i + 1 < len(ordered) else None)
            pager = fill(self.t["pager"], prev=f'<a href="{prefix}{prev_.html_rel}">&larr; {htmllib.escape(prev_.title)}</a>' if prev_ else "",
                         next=f'<a href="{prefix}{next_.html_rel}">{htmllib.escape(next_.title)} &rarr;</a>' if next_ else "")
            body = badges(fix_links(md.convert(p.body), p.rel, self.by_rel), self.words)
            toc = md.toc if body.count("<h2") >= 3 else ""
            target = self.out / p.html_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.page(p.title, f"<h1>{htmllib.escape(p.title)}</h1>" + body, p.rel, prefix, crumb, pager, toc), encoding="utf-8")
        for top, plist in self.sections.items():
            title = section_title(top, self.titles)
            body = f"<h1>{htmllib.escape(title)}</h1>" + self.cards(sorted(plist, key=lambda q: q.rel), "../")
            target = self.out / top / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.page(title, body, top + "/index.md", "../", f'<a href="../index.html">Home</a> / {htmllib.escape(title)}'), encoding="utf-8")
        home = self.by_rel.get("index.md")
        intro = badges(markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"]).convert(home.body), self.words) if home else ""
        heading = f"<h1>{htmllib.escape(home.title if home else self.brand)}</h1>"
        sections = "<h2>Browse by section</h2>" + "".join(
            f'<h3><a href="{top}/index.html">{htmllib.escape(section_title(top, self.titles))}</a></h3>{self.cards(sorted(pl, key=lambda q: q.rel)[:6], "")}' for top, pl in sorted(self.sections.items()))
        (self.out / "index.html").write_text(self.page("Home", fill(self.t["home"], heading=heading, intro=intro, sections=sections), "", "", "Home"), encoding="utf-8")
        return len(ordered)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2].strip())
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand", default="Docs")
    ap.add_argument("--sections", default="", help='titles for folders, e.g. "1-start=Start here,2-guides=Guides"')
    ap.add_argument("--status-words", nargs="+", default=list(DEFAULT_STATUS_WORDS))
    args = ap.parse_args(argv)
    titles = dict(x.split("=", 1) for x in args.sections.split(",") if "=" in x)
    n = Site(args.src, args.out, args.brand, titles, args.status_words).build()
    print(f"{n} pages written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
