"""Facts: deterministic extraction from collected sources into .guidebook/facts.json.
Every fact keeps its source files and a hash of them, so later phases can tell what went stale.
Claude-written explanations are NOT stored here (Phase 2 caches them separately)."""
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .hashing import normalize, sources_hash, text_hash
from .scrub import scrub

STATUS_WORDS = ("PASSED", "DOUBTFUL", "FAILED", "UNKNOWN", "UNTESTED")
EXTRACTOR_VERSION = "4"     # bump when extract() changes what it produces: cached facts are then rebuilt
KINDS = ("purpose", "step", "result", "decision", "term", "risk", "howto")
# PROJECT_STATUS.md sections that get their own guide page (heading, case-insensitive -> section key)
HOWTO_SECTIONS = {"how to run": "how-to-run", "setup": "setup", "data": "data", "troubleshooting": "troubleshooting"}


@dataclass
class Fact:
    id: str
    kind: str
    text: str
    sources: list
    source_hash: str
    status: str = ""
    confirmed: bool = True      # False when it comes from a loose README, not a kickoff file
    scrubbed: list = field(default_factory=list)
    section: str = ""           # howto facts: which PROJECT_STATUS.md section (how-to-run, setup, data, troubleshooting)
    state: str = ""             # howto facts: CONFIRMED, GUESSED or UNKNOWN


def _make(kind, text, src, status="", confirmed=True):
    clean, fired = scrub(" ".join(text.split()))
    fid = hashlib.sha1(f"{kind}|{src.path}|{clean}".encode("utf-8")).hexdigest()[:12]
    return Fact(fid, kind, clean, [src.path], sources_hash({src.path: src.hash}), status, confirmed, fired)


def _sections(text):
    """Yield (heading, lines) for each Markdown heading."""
    head, lines = "", []
    for ln in text.replace("\r\n", "\n").split("\n"):
        m = re.match(r"#{1,6}\s+(.*)", ln)
        if m:
            yield head, lines
            head, lines = m.group(1).strip(), []
        else:
            lines.append(ln)
    yield head, lines


def howto_state(body):
    """CONFIRMED, GUESSED or UNKNOWN for a PROJECT_STATUS.md section. The first word of the section says so; an empty section is UNKNOWN;
    a section with content and no marker is CONFIRMED (the kickoff wrap-up removes the GUESSED mark when it confirms a section)."""
    first = next((ln.strip().lstrip(">").strip() for ln in body.split("\n") if ln.strip()), "")
    if not first or first.startswith("UNKNOWN"):
        return "UNKNOWN"
    return "GUESSED" if first.startswith("GUESSED") else "CONFIRMED"


def _make_howto(section, body, src):
    """One fact per section. Its hash covers only the section text, so editing one section makes only its page stale."""
    clean, fired = scrub(normalize(body))
    fid = hashlib.sha1(f"howto|{src.path}|{section}|{clean}".encode("utf-8")).hexdigest()[:12]
    return Fact(fid, "howto", clean, [src.path], sources_hash({src.path: text_hash(clean)}), "", True, fired, section, howto_state(clean))


def _first_paragraph(lines):
    para = []
    for ln in lines:
        if ln.strip() and not ln.lstrip().startswith(("|", "```", "<!--", "---")):
            para.append(ln.strip())
        elif para:
            break
    return " ".join(para)


def _table_rows(lines):
    rows = []
    for ln in lines:
        if ln.strip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|\s*$", ln):
            rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return rows[1:] if rows else []     # drop the header row


WEAKEST_FIRST = ("FAILED", "DOUBTFUL", "UNTESTED", "UNKNOWN", "PASSED")


def _status_cell(row, status_map):
    """(cell, word) for the row's status cell. A cell is exactly one status word (or a mapped one), or it starts with one and
    adds a note, such as "PASSED (stub) / UNTESTED (real claude)": then the weakest word in it counts, so a mixed cell never reads as better than it is."""
    for c in row:
        if c in STATUS_WORDS or status_map.get(c) in STATUS_WORDS:
            return c, status_map.get(c, c)
    for c in row:
        if re.match(r"(?:%s)\b" % "|".join(STATUS_WORDS), c):
            found = set(re.findall(r"\b(%s)\b" % "|".join(STATUS_WORDS), c))
            return c, next(w for w in WEAKEST_FIRST if w in found)
    return "", ""


def extract(src, status_map=None) -> list:
    """Facts for one source. Unknown file kinds give no facts (they are still listed as sources).
    status_map maps a project's own status words onto the five (e.g. {"DONE": "PASSED"}); no new colours."""
    status_map = status_map or {}
    name = src.path.rsplit("/", 1)[-1]
    out = []
    if src.kind not in ("kickoff", "readme", "doc"):
        return out
    confirmed = src.kind == "kickoff"
    text = src.text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        text = text[end + 4:] if end > 0 else text
    for head, lines in _sections(text):
        low = head.lower()
        if name == "PROJECT_BRIEF.md" and re.match(r"(\d+\.\s*)?goal", low):
            p = _first_paragraph(lines)
            if p:
                out.append(_make("purpose", p, src))
        elif src.kind == "readme" and head and not any(f.kind == "purpose" for f in out) and _first_paragraph(lines):
            out.append(_make("purpose", _first_paragraph(lines), src, confirmed=False))
        if name == "PROJECT_STATUS.md" and low in HOWTO_SECTIONS:
            out.append(_make_howto(HOWTO_SECTIONS[low], "\n".join(lines), src))
        if name == "NEXT.md":
            for ln in lines:
                m = re.match(r"\s*\d+\.\s+(\S.*)", ln)
                if m:
                    out.append(_make("step", m.group(1), src))
        if name == "DECISIONS.md":
            for ln in lines:
                m = re.match(r"-\s+(\d{4}-\d{2}-\d{2})\s*\|\s*(.*)", ln)
                if m:
                    parts = [x.strip() for x in m.group(2).split("|")]
                    text = f"{m.group(1)}: {parts[0]}"
                    if len(parts) > 1 and parts[1] not in ("", "-"):
                        text += f". Why: {parts[1]}"
                    if len(parts) > 2 and parts[2] not in ("", "-"):
                        text += f". Rejected: {parts[2]}"
                    out.append(_make("decision", text, src))
        for row in _table_rows(lines):
            cell, word = _status_cell(row, status_map)
            if word and name == "PROJECT_STATUS.md":
                rest = [c for c in row if c and c != cell]
                if cell != word and cell.upper() != word:
                    rest.insert(1, cell)
                out.append(_make("result", f"{rest[0]}: {word}" + (f" ({'; '.join(rest[1:])})" if len(rest) > 1 else ""), src, word, confirmed))
        if re.search(r"risk|gap", low):
            for ln in lines:
                m = re.match(r"\s*(?:[-*]|\d+\.)\s+(\S.*)", ln)
                if m:
                    out.append(_make("risk", m.group(1), src, confirmed=confirmed))
        for ln in lines:
            m = re.match(r"\s*[-*]\s+\*\*(.+?)\*\*\s*[:–-]\s+(\S.*)", ln)
            if m and src.kind != "kickoff":
                out.append(_make("term", f"{m.group(1)}: {m.group(2)}", src, confirmed=confirmed))
    return out


class FactStore:
    """Facts cache on disk. update() re-extracts only sources whose hash changed."""

    def __init__(self, path):
        self.path = Path(path)
        self.source_hashes, self.facts, self.status_map, self.version = {}, [], {}, ""
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.source_hashes = data.get("source_hashes", {})
            self.status_map = data.get("status_map", {})
            self.version = data.get("extractor_version", "")
            self.facts = [Fact(**f) for f in data.get("facts", [])]

    def update(self, sources, status_map=None):
        """Return (changed, removed): paths re-extracted (new or edited) and paths that no longer exist.
        A different status_map re-extracts everything."""
        status_map = status_map or {}
        now = {s.path: s for s in sources}
        redo_all = status_map != self.status_map or self.version != EXTRACTOR_VERSION
        changed = sorted(p for p, s in now.items() if redo_all or self.source_hashes.get(p) != s.hash)
        removed = sorted(p for p in self.source_hashes if p not in now)
        drop = set(changed) | set(removed)
        self.facts = [f for f in self.facts if not (set(f.sources) & drop)]
        for p in changed:
            self.facts.extend(extract(now[p], status_map))
        self.source_hashes = {p: s.hash for p, s in now.items()}
        self.status_map, self.version = status_map, EXTRACTOR_VERSION
        return changed, removed

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"extractor_version": self.version, "source_hashes": self.source_hashes, "status_map": self.status_map, "facts": [asdict(f) for f in sorted(self.facts, key=lambda f: (f.sources, f.kind))]}
        self.path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def by_kind(self, kind):
        return [f for f in self.facts if f.kind == kind]
