"""Scrub secrets, tokens, private absolute paths, emails and account IDs from text before it is stored or written to a page.
A safety net, not a guarantee: it catches common shapes only."""
import re

RULES = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"), "[removed: private key]"),
    ("token", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})\b"), "[removed: token]"),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"), "Bearer [removed]"),
    ("assignment", re.compile(r"(?i)\b((?:password|passwd|secret|api[_-]?key|token|access[_-]?key)\s*[:=]\s*)(?!\[removed)[^\s'\",;]{4,}"), r"\1[removed]"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[email removed]"),
    ("path", re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+|/Users/|/home/)[^\\/\s'\"]+"), "[user folder]"),
    ("account-id", re.compile(r"(?i)\b(account(?:[ _-]?id)?\s*[:=#]?\s*)\d{10,}\b"), r"\1[removed]"),
]


def scrub(text: str):
    """Return (clean text, sorted list of rule names that fired)."""
    fired = set()
    for name, rx, repl in RULES:
        text, n = rx.subn(repl, text)
        if n:
            fired.add(name)
    return text, sorted(fired)


def has_secret(text: str) -> bool:
    return bool(scrub(text)[1])
