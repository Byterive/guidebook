"""Build state in .guidebook/state.json: which source hashes the pages were last written from, and which pages the HTML was built from.
Timestamps and the commit live only here, never in the guide HTML (the HTML must be deterministic)."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .frontmatter import is_page_file
from .hashing import text_hash


def _file(root) -> Path:
    return Path(root) / ".guidebook" / "state.json"


def load(root) -> dict:
    try:
        data = json.loads(_file(root).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(root, data: dict):
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def commit(root) -> str:
    """Short git commit of the project, or '' when git is missing or the folder is not a repo."""
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def pages_digest(src_root) -> str:
    """One hash over every page the builder would read (not drafts, not proposals)."""
    import hashlib
    h = hashlib.sha256()
    for p in sorted(Path(src_root).rglob("*.md")):
        if not is_page_file(p):
            continue
        h.update(f"{p.relative_to(src_root).as_posix()}:{text_hash(p.read_text(encoding='utf-8'))}\n".encode("utf-8"))
    return h.hexdigest()


def record_pages(root, sources):
    """Remember the source hashes the pages were just written from."""
    s = load(root)
    s["sources"] = {x.path: x.hash for x in sources}
    s["pages_at"] = now()
    s["commit"] = commit(root)
    save(root, s)


def record_build(root, src_root):
    s = load(root)
    s["pages_digest"] = pages_digest(src_root)
    s["built_at"] = now()
    save(root, s)
