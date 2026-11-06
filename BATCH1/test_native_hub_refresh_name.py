"""Offline check that NativeChannelHubView no longer collides with LayoutView._refresh."""
import ast
import pathlib
import sys

candidates = [
    pathlib.Path("discord-bot/bot.py"),
    pathlib.Path("../discord-bot/bot.py"),
    pathlib.Path("/home/workdir/artifacts/bot_fixed_clean.py"),
    pathlib.Path(__file__).resolve().parents[1] / "discord-bot" / "bot.py",
]
BOT = None
for c in candidates:
    if c.exists():
        BOT = c
        break
if BOT is None:
    print("FAIL: bot.py not found in candidates")
    sys.exit(1)

src = BOT.read_text(encoding="utf-8")
tree = ast.parse(src)

class_methods = {}
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "NativeChannelHubView":
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_methods[item.name] = item

if not class_methods:
    print("FAIL: NativeChannelHubView class not found")
    sys.exit(1)

if "_refresh" in class_methods:
    print("FAIL: NativeChannelHubView still defines _refresh — collides with discord.ui.LayoutView._refresh")
    sys.exit(1)

if "_on_refresh_feed" not in class_methods:
    print("FAIL: NativeChannelHubView missing _on_refresh_feed after rename")
    sys.exit(1)

print("PASS: NativeChannelHubView has _on_refresh_feed and no _refresh")
