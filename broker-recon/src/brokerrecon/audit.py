"""Append-only, hash-chained event log.

Each event carries the hash of the previous event, so any edit, deletion or
re-ordering of the log is detectable by ``verify_chain``. Events contain no
wall-clock time (that lives in execution.json) so that a re-run on the same
inputs produces a byte-identical log.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hashing import canonical_json, sha256_text

GENESIS = "0" * 64


class EventLog:
    def __init__(self, path: Path, anchor: str = GENESIS):
        self.path = path
        self.prev = anchor
        self.seq = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "w", encoding="utf-8", newline="\n")

    def emit(self, event: str, **data: Any) -> str:
        self.seq += 1
        body = {"seq": self.seq, "event": event, "data": data, "prev": self.prev}
        h = sha256_text(canonical_json(body))
        self._fh.write(canonical_json(dict(body, hash=h)) + "\n")
        self.prev = h
        return h

    def close(self) -> str:
        self._fh.close()
        return self.prev


def append_events(path: Path, events: list[tuple[str, dict]], anchor: str) -> str:
    """Append to an existing chained log (used by human review); returns head hash."""
    prev, seq = anchor, 0
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        if lines:
            last = json.loads(lines[-1])
            prev, seq = last["hash"], last["seq"]
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        for event, data in events:
            seq += 1
            body = {"seq": seq, "event": event, "data": data, "prev": prev}
            h = sha256_text(canonical_json(body))
            fh.write(canonical_json(dict(body, hash=h)) + "\n")
            prev = h
    return prev


def verify_chain(path: Path, anchor: str = GENESIS) -> tuple[bool, str, int]:
    prev = anchor
    n = 0
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        ev = json.loads(line)
        h = ev.pop("hash")
        if ev["prev"] != prev:
            return False, f"event {n}: chain broken (prev hash mismatch)", n
        if sha256_text(canonical_json(ev)) != h:
            return False, f"event {n}: content altered (hash mismatch)", n
        prev = h
    return True, prev, n
