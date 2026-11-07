"""Batch G: owner-approved scheduled publish. No unreviewed auto-post."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ScheduledPost:
    schedule_id: str
    guild_id: int
    proposal_id: str
    plan_hash: str
    approval_id: str
    execute_after_unix: int
    execute_before_unix: int
    status: str = "pending"
    message_id: int | None = None


class ScheduleStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            self._write({"items": []})

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def add(self, item: ScheduledPost) -> None:
        data = self._read()
        data.setdefault("items", []).append(asdict(item))
        self._write(data)

    def cancel(self, schedule_id: str) -> bool:
        data = self._read()
        found = False
        for it in data.get("items") or []:
            if it.get("schedule_id") == schedule_id and it.get("status") == "pending":
                it["status"] = "cancelled"
                found = True
        if found:
            self._write(data)
        return found

    def due(self, now_unix: int | None = None) -> list:
        now = int(now_unix if now_unix is not None else time.time())
        out = []
        data = self._read()
        changed = False
        for it in data.get("items") or []:
            if it.get("status") != "pending":
                continue
            if now > int(it.get("execute_before_unix", 0)):
                it["status"] = "expired"
                changed = True
                continue
            if now >= int(it.get("execute_after_unix", 0)):
                out.append(it)
        if changed:
            self._write(data)
        return out

    def mark_posted(self, schedule_id: str, message_id: int) -> None:
        data = self._read()
        for it in data.get("items") or []:
            if it.get("schedule_id") == schedule_id:
                it["status"] = "posted"
                it["message_id"] = message_id
        self._write(data)
