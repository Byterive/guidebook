"""Test helpers: build a throwaway project in a temp folder (no git unless asked)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BRIEF = """---
title: Brief
summary: x
keywords: [a]
status: draft
updated: 2026-10-25
---

# PROJECT_BRIEF

## 1. Goal
Track bike repairs so a shop owner sees what is late.
Second line of the goal.

## 8. Next steps wanted
1. Do a thing.
"""
STATUS = """# PROJECT_STATUS

## Modules
| Module | Purpose | Status | Tests |
|---|---|---|---|
| parser | reads orders | PASSED | 12 tests |
| exporter | writes csv | UNTESTED | none |

## Risks
- Orders file has no backup.
"""
DECISIONS = "# DECISIONS\n\n- 2026-10-01 | Use SQLite | simple | Postgres\n"
NEXT = "# NEXT\n\n**Next 3 steps:**\n1. Add export.\n2. Add tests.\n"
README = "# Bike shop\n\nA small tool for a bike shop.\n\n- **Order**: one repair job.\n"


def make_project(root: Path, extra=None):
    files = {"PROJECT_BRIEF.md": BRIEF, "PROJECT_STATUS.md": STATUS, "DECISIONS.md": DECISIONS, "NEXT.md": NEXT, "README.md": README,
             "app.py": "print('hi')\n", ".env": "API_KEY=abc123456789\n", "secrets/key.txt": "x\n", "server.pem": "x\n",
             ".gitignore": "ignored.md\n", "ignored.md": "# ignored\n", "__pycache__/x.pyc": "x\n"}
    files.update(extra or {})
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="")
    return root
