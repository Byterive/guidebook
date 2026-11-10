"""Frontmatter contract of generated pages: parse, write, and the edit-protection rule."""
from .hashing import text_hash

KEYS = ("title", "summary", "keywords", "generated", "version", "sources", "source_hash", "page_hash", "kind", "howto_section")
_LISTS = ("keywords", "sources")


def _value(key, raw):
    raw = raw.strip()
    if key in _LISTS:
        inner = raw[1:-1] if raw.startswith("[") and raw.endswith("]") else raw
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw


def parse(text: str):
    """Return (meta dict, body). No frontmatter block -> ({}, text)."""
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[4:end].split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = _value(k.strip(), v)
    body = text[end + 4:].lstrip("\n")
    return meta, body


def render(meta: dict, body: str) -> str:
    lines = []
    for k in KEYS:
        if k not in meta:
            continue
        v = meta[k]
        if isinstance(v, list):
            v = "[" + ", ".join(v) + "]"
        elif isinstance(v, bool):
            v = "true" if v else "false"
        lines.append(f"{k}: {v}")
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body.strip("\n") + "\n"


def make_page(title, summary, keywords, version, sources, source_hash, body, **extra) -> str:
    """A generated page with page_hash computed from its body. `extra` (kind, howto_section) is written after page_hash."""
    meta = {"title": title, "summary": summary, "keywords": list(keywords), "generated": True, "version": version,
            "sources": list(sources), "source_hash": source_hash, "page_hash": text_hash(body)}
    meta.update({k: v for k, v in extra.items() if v})
    return render(meta, body)


def edit_state(text: str) -> str:
    """'user' (not generated: never touch), 'edited' (generated but body changed: write .proposed.md), or 'pristine' (safe to overwrite)."""
    meta, body = parse(text)
    if meta.get("generated") is not True:
        return "user"
    return "pristine" if meta.get("page_hash") == text_hash(body) else "edited"


HOME = "home.md"  # never index.md: a project indexer writes INDEX.md, the same file name on Windows and macOS


def is_page_file(path) -> bool:
    """True for a Markdown file the builder reads: not a draft, not a proposal, not an index file."""
    name = path.name
    return not (name.startswith("_") or name.endswith(".proposed.md") or name.lower() == "index.md")
