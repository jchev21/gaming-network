"""Discord Hub entrypoint. Implementation is hub_core.py (prod + change-bridge)."""
from __future__ import annotations

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "hub_core.py"), run_name="__main__")
