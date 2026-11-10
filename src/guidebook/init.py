"""`guidebook init`: read the project, PROPOSE a set of versions with reasons, and write nothing until the user approves.

Approval = `--yes` (or `--versions a,b --yes`). Without it the command only prints the proposal and the exact command to approve it.
`--dry-run` lists every file that would be created. Existing guide settings are never overwritten."""
import json
from dataclasses import dataclass, field
from pathlib import Path

from .build import html_paths
from .collect import collect
from .config import AUDIENCES, load_config, make_version
from .facts import FactStore
from .pages import Builder

IGNORE_STARTER = """# Paths guidebook must not read, one per line (folders end with /). Secrets, .env files and git-ignored files are skipped already.
# examples:
# private-notes/
# *.draft.md
"""


@dataclass
class Proposal:
    name: str
    reason: str


@dataclass
class Plan:
    proposals: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    brand: str = ""
    already: bool = False
    disabled: bool = False
    empty: bool = False
    files: list = field(default_factory=list)


def _counts(store, sources):
    k = lambda kind: len(store.by_kind(kind))  # noqa: E731
    kinds = {}
    for s in sources:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1
    return {"purpose": k("purpose"), "results": k("result"), "decisions": k("decision"), "risks": k("risk"), "steps": k("step"),
            "terms": k("term"), "kinds": kinds, "confirmed_purpose": any(f.confirmed for f in store.by_kind("purpose"))}


def propose(counts) -> list:
    """Versions worth building for this project, each with the reason. Deterministic."""
    c, kinds = counts, counts["kinds"]
    if not (c["purpose"] or c["results"] or c["steps"] or c["decisions"] or kinds.get("readme") or kinds.get("doc")):
        return []
    out = [Proposal("layman", "a plain-language overview: the project has a purpose or README text to explain")]
    if c["results"] or c["risks"] or c["steps"]:
        out.append(Proposal("client-or-investor", f"the project records progress to report ({c['results']} status items, {c['risks']} risks, {c['steps']} next steps)"))
    if c["decisions"] or kinds.get("code", 0) + kinds.get("test", 0) >= 3:
        out.append(Proposal("maintainer", f"there is history to explain ({c['decisions']} decisions, {kinds.get('code', 0)} code files)"))
    others = kinds.get("code", 0) + kinds.get("test", 0) + kinds.get("doc", 0) + kinds.get("config", 0)
    if others >= 6:
        out.append(Proposal("teammate", f"{others} files beyond the kickoff files: a newcomer needs a map"))
    out.append(Proposal("quick-start", "a one-page version for someone with two minutes"))
    return out


def make_plan(project, versions=None) -> Plan:
    root = Path(project).resolve()
    cfg = load_config(root)
    plan = Plan(brand=cfg.brand)
    if not cfg.enabled:
        plan.disabled = True
        return plan
    own = root / ".guidebook" / "guide.json"
    kick = root / ".kickoff" / "guide.json"
    plan.already = own.is_file()
    sources = collect(root)
    store = FactStore(root / ".guidebook" / "facts.json")
    store.update(sources, cfg.status_map)
    counts = _counts(store, sources)
    if versions:
        plan.proposals = [Proposal(v, "chosen by you") for v in versions]
    elif kick.is_file():
        plan.proposals = [Proposal(v.name, "listed in .kickoff/guide.json") for v in cfg.versions]
        plan.notes.append("Versions come from .kickoff/guide.json; kickoff owns that file and it is not changed.")
    else:
        plan.proposals = propose(counts)
    plan.empty = not plan.proposals
    if not counts["confirmed_purpose"] and not plan.empty:
        plan.notes.append("No project brief states the purpose: it will come from the README and be marked unconfirmed (or \"not known\").")
    if not counts["kinds"].get("kickoff"):
        plan.notes.append("No kickoff files (PROJECT_BRIEF, PROJECT_STATUS, DECISIONS, NEXT): the guide will be thinner. Facts are taken from README, docs and file names only.")
    if (root / "tools" / "build_index.py").is_file() and not plan.empty:
        plan.notes.append("This project has tools/build_index.py: the guide ignores INDEX.md files, but add \"guide-src\" and \"guide\" to skip_dirs in tools/budgets.json to keep indexes out of the guide folders.")
    if not plan.empty:
        plan.files = planned_files(root, cfg, store, sources, [make_version(p.name) for p in plan.proposals], write_config=not kick.is_file() or not own.is_file())
    return plan


def planned_files(root, cfg, store, sources, specs, write_config=True) -> list:
    """Every file init would create (project-relative), excluding files that already exist."""
    out = []
    if write_config and not (root / ".guidebook" / "guide.json").is_file():
        out.append(".guidebook/guide.json")
    if not (root / ".guidebook" / "ignore").is_file():
        out.append(".guidebook/ignore")
    out += [".guidebook/facts.json", ".guidebook/state.json", ".guidebook/manifest.json"]
    per_version = {}
    for spec in specs:
        pages = [rel for rel, _ in Builder(store, sources, spec, cfg.brand).build(None)]
        per_version[spec.name] = pages
        out += [f"docs/guide-src/{spec.name}/{rel}" for rel in pages]
    out += [f"{cfg.output}/{p}" for p in html_paths(per_version)]
    return sorted(set(out) - {p for p in out if (root / p).exists()})


def write_config(root, brand, versions):
    f = Path(root) / ".guidebook" / "guide.json"
    if f.is_file():
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    data = {"brand": brand, "versions": versions, "output": "docs/guide", "publish": "local", "status_map": {}}
    f.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    ig = f.with_name("ignore")
    if not ig.is_file():
        ig.write_text(IGNORE_STARTER, encoding="utf-8", newline="\n")
    return True


def describe(plan: Plan, preset_names=tuple(AUDIENCES)) -> list:
    lines = []
    if plan.disabled:
        return ["guide is disabled in .kickoff/guide.json (enabled: false); nothing to do"]
    if plan.empty:
        return ["nothing to read: no README, docs or kickoff files found, so there is nothing to write a guide from"]
    lines.append(f"proposed versions for \"{plan.brand}\":")
    for p in plan.proposals:
        lines.append(f"  {p.name:20} {p.reason}")
    lines += [f"note: {n}" for n in plan.notes]
    if plan.already:
        lines.append("already set up (.guidebook/guide.json exists): init will not change it; use `guidebook update`")
    return lines
