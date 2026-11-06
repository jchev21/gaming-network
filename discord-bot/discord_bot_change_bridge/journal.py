"""Atomic proposal/approval/operation journal under /data (no tokens)."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class JournalError(ValueError):
    pass


@dataclass
class JournalEntry:
    kind: str
    at_unix: int
    guild_id: int
    proposal_id: str
    plan_hash: str
    detail: dict[str, Any] = field(default_factory=dict)


class Journal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._atomic_write({"entries": [], "consumed_approvals": [], "applied_idempotency": []})

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise JournalError(f"journal unreadable: {e}") from e

    def _atomic_write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".journal-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def append(self, entry: JournalEntry) -> None:
        data = self._read()
        data.setdefault("entries", []).append(asdict(entry))
        self._atomic_write(data)

    def mark_approval_consumed(self, approval_id: str) -> None:
        data = self._read()
        consumed = set(data.get("consumed_approvals") or [])
        consumed.add(approval_id)
        data["consumed_approvals"] = sorted(consumed)
        self._atomic_write(data)

    def is_approval_consumed(self, approval_id: str) -> bool:
        data = self._read()
        return approval_id in set(data.get("consumed_approvals") or [])

    def mark_idempotency_applied(self, token: str) -> None:
        data = self._read()
        applied = set(data.get("applied_idempotency") or [])
        applied.add(token)
        data["applied_idempotency"] = sorted(applied)
        self._atomic_write(data)

    def is_idempotency_applied(self, token: str) -> bool:
        data = self._read()
        return token in set(data.get("applied_idempotency") or [])

    def entries(self) -> list:
        return list(self._read().get("entries") or [])
