"""Canonical serialisation and content hashing.

Everything that feeds a run identity or an output hash goes through these
helpers so that byte-identical inputs and configuration always give
byte-identical outputs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(obj: Any) -> str:
    """Stable JSON: sorted keys, no insignificant whitespace, UTF-8 safe."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_obj(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def short_id(prefix: str, *parts: Any, length: int = 12) -> str:
    return f"{prefix}-{sha256_obj(list(parts))[:length]}"
