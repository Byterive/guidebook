"""Guide configuration and version specs.

Read order: .kickoff/guide.json (kickoff contract 1) wins for the fields it has; .guidebook/guide.json supplies the rest
(and guidebook-only fields such as status_map). Neither file is required: the default is one "layman" version."""
import json
from dataclasses import dataclass, field
from pathlib import Path

from .facts import STATUS_WORDS

SUPPORTED_CONTRACT = 1
DEPTHS = ("one-page", "standard", "full")

# Audience presets: who reads, tone, default depth, and which optional pages are left out.
AUDIENCES = {
    "layman": {"reader": "a smart adult with no background in the subject", "tone": "plain, friendly, no jargon", "depth": "standard", "skip": {"files", "decisions"}},
    "client-or-investor": {"reader": "a client or investor who wants to know progress, risk and what comes next", "tone": "plain and factual, no hype", "depth": "standard", "skip": {"files", "decisions", "terms"}},
    "teammate": {"reader": "a colleague joining the work who needs to find things", "tone": "direct and practical", "depth": "full", "skip": set()},
    "maintainer": {"reader": "the person who keeps this running and must know what was decided and why", "tone": "precise and technical", "depth": "full", "skip": set()},
    "quick-start": {"reader": "someone with two minutes who wants the point", "tone": "short and plain", "depth": "one-page", "skip": {"files", "decisions", "terms", "risks"}},
}
ALIASES = {"client": "client-or-investor", "investor": "client-or-investor"}


@dataclass
class VersionSpec:
    name: str
    audience: str
    depth: str
    scope: list = field(default_factory=list)   # path prefixes; empty = whole project
    reader: str = ""
    tone: str = ""
    skip: set = field(default_factory=set)


@dataclass
class Config:
    brand: str
    versions: list
    output: str = "docs/guide"
    publish: str = "local"
    hub: str = ""
    status_map: dict = field(default_factory=dict)
    enabled: bool = True
    contract: int = 1
    warnings: list = field(default_factory=list)


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def make_version(entry) -> VersionSpec:
    """A version from a name ("layman") or a dict (name, audience, depth, scope, reader, tone, skip)."""
    d = {"name": entry} if isinstance(entry, str) else dict(entry)
    name = d["name"]
    audience = ALIASES.get(d.get("audience", name), d.get("audience", name))
    preset = AUDIENCES.get(audience)
    base = preset or {"reader": "", "tone": "plain and clear", "depth": "standard", "skip": set()}
    depth = d.get("depth", base["depth"])
    if depth not in DEPTHS:
        raise ValueError(f"version {name}: depth must be one of {DEPTHS}, got {depth!r}")
    scope = d.get("scope") or []
    if isinstance(scope, str):
        scope = [scope]
    return VersionSpec(name=ALIASES.get(name, name), audience=audience, depth=depth, scope=[s.strip("/") for s in scope],
                       reader=d.get("reader", base["reader"]), tone=d.get("tone", base["tone"]), skip=set(d.get("skip", base["skip"])))


def validate_status_map(m: dict) -> dict:
    bad = {k: v for k, v in m.items() if v not in STATUS_WORDS}
    if bad:
        raise ValueError(f"status_map may only map onto {STATUS_WORDS}; got {bad}")
    return dict(m)


def load_config(root) -> Config:
    root = Path(root).resolve()
    own = _read(root / ".guidebook" / "guide.json")
    kick = _read(root / ".kickoff" / "guide.json")
    merged = {**own, **{k: v for k, v in kick.items() if v not in (None, "")}}
    versions = [make_version(v) for v in merged.get("versions") or ["layman"]]
    names = [v.name for v in versions]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate version names: {names}")
    contract = int(merged.get("contract", 1))
    warnings = [f"guide config says contract {contract}; this guidebook understands contract {SUPPORTED_CONTRACT}. Unknown fields are ignored."] if contract > SUPPORTED_CONTRACT else []
    return Config(brand=merged.get("brand") or root.name, versions=versions, output=merged.get("output") or "docs/guide",
                  publish=merged.get("publish") or "local", hub=merged.get("hub") or "",
                  status_map=validate_status_map(own.get("status_map", {})), enabled=merged.get("enabled", True) is not False,
                  contract=contract, warnings=warnings)
