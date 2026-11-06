"""Batch H: process-local operation lock."""
from __future__ import annotations

import time
from pathlib import Path


class OperationLock:
    def __init__(self, path: Path, *, ttl_seconds: int = 300):
        self.path = Path(path)
        self.ttl = ttl_seconds

    def acquire(self, key: str) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        if self.path.exists():
            try:
                held_key, ts = self.path.read_text(encoding="utf-8").split("|", 1)
                if now - float(ts) < self.ttl:
                    return False
            except Exception:
                pass
        self.path.write_text(f"{key}|{now}", encoding="utf-8")
        return True

    def release(self, key: str) -> None:
        if not self.path.exists():
            return
        try:
            held_key, _ = self.path.read_text(encoding="utf-8").split("|", 1)
            if held_key == key:
                self.path.unlink(missing_ok=True)
        except Exception:
            pass
