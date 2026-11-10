"""Content hashing. Text is normalized (LF, no trailing spaces, no outer blank lines) so editors do not cause false changes."""
import hashlib


def normalize(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def sources_hash(hashes: dict) -> str:
    """One hash for a set of sources: {relative path: file hash}. Order does not matter."""
    joined = "\n".join(f"{p}:{h}" for p, h in sorted(hashes.items()))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
