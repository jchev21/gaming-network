"""Full Discord Hub implementation (production + /change-* registration).

Split across hub_core_part1.py / hub_core_part2.py for GitHub upload size limits.
Entrypoint remains bot.py which runpy-executes this module as __main__.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_src = (_ROOT / "hub_core_part1.py").read_text(encoding="utf-8") + (
    _ROOT / "hub_core_part2.py"
).read_text(encoding="utf-8")
exec(compile(_src, str(_ROOT / "hub_core_combined.py"), "exec"), globals())
