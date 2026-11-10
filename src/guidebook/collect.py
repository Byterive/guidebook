"""Collector: read a project, never write to it. Skips secrets, caches and git-ignored files."""
import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .hashing import text_hash

KICKOFF = ("PROJECT_BRIEF.md", "PROJECT_STATUS.md", "DECISIONS.md", "NEXT.md", "INDEX.md")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode", ".guidebook", "docs/guide", "docs/guide-src", "dist", "build"}
SKIP_NAMES = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "*.sqlite", "*.db", "*.pyc", "secrets.*")
TEXT_EXT = {".md", ".txt", ".rst", ".py", ".toml", ".json", ".yaml", ".yml", ".cfg", ".ini", ".go", ".js", ".ts", ".cs", ".sh", ".ps1", ".html", ".css"}
MAX_BYTES = 1_000_000


@dataclass
class Source:
    path: str       # relative, forward slashes
    kind: str       # kickoff | readme | doc | code | test | config | other
    text: str
    hash: str


def _kind(rel: str) -> str:
    name, low = rel.rsplit("/", 1)[-1], rel.lower()
    if "/" not in rel and name in KICKOFF:
        return "kickoff"
    if name.lower().startswith("readme"):
        return "readme"
    if low.startswith("tests/") or low.startswith("test/") or name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if low.startswith(("docs/", "doc/")) or low.endswith((".md", ".rst", ".txt")):
        return "doc"
    if name.endswith((".toml", ".json", ".yaml", ".yml", ".cfg", ".ini")):
        return "config"
    return "code" if "." in name else "other"


def _ignore_list(root: Path):
    f = root / ".guidebook" / "ignore"
    if not f.is_file():
        return []
    return [ln.strip() for ln in f.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip() and not ln.startswith("#")]


def _git_listing(root: Path):
    """Tracked + untracked-but-not-ignored files, or None when git is missing or this is not a repo."""
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return [p for p in r.stdout.decode("utf-8", errors="replace").split("\0") if p]


def _walk_listing(root: Path):
    gi_file = root / ".gitignore"
    gi = [ln.strip().strip("/") for ln in gi_file.read_text(encoding="utf-8", errors="replace").splitlines()] if gi_file.is_file() else []
    gi = [g for g in gi if g and not g.startswith("#")]
    out = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(part, g) or fnmatch.fnmatch(rel, g) for g in gi for part in rel.split("/")):
            continue
        out.append(rel)
    return out


def _blocked(rel: str, extra) -> bool:
    parts = rel.split("/")
    if any("/".join(parts[:i]) in SKIP_DIRS or parts[i - 1] in SKIP_DIRS for i in range(1, len(parts))):
        return True
    if any(part.lower() in ("secrets", "credentials") for part in parts[:-1]):
        return True
    name = parts[-1]
    if any(fnmatch.fnmatch(name.lower(), pat) for pat in SKIP_NAMES):
        return True
    return any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat) or rel.startswith(pat.rstrip("/") + "/") for pat in extra)


def collect(root) -> list:
    """Return Sources, kickoff files first. Reads only; the project is never modified."""
    root = Path(root).resolve()
    listing = _git_listing(root)
    if listing is None:
        listing = _walk_listing(root)
    extra = _ignore_list(root)
    out = []
    for rel in sorted(set(p.replace("\\", "/") for p in listing)):
        f = root / rel
        if _blocked(rel, extra) or f.suffix.lower() not in TEXT_EXT or not f.is_file():
            continue
        try:
            if f.stat().st_size > MAX_BYTES:
                continue
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out.append(Source(rel, _kind(rel), text, text_hash(text)))
    order = {"kickoff": 0, "readme": 1, "doc": 2, "config": 3, "code": 4, "test": 5, "other": 6}
    return sorted(out, key=lambda s: (order[s.kind], s.path))
