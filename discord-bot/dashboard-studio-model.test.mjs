import assert from "node:assert/strict";
import {
  DEMO_SERVERS, PANE_COUNTS, PRESETS,
  defaultStudioState, sanitizeStudioState, studioTheme,
  updateStudioTheme, updateStudioPane, exportStudioConfig
} from "./dashboard-studio-model.mjs";

const initial = defaultStudioState();
assert.equal(initial.count, 4);
assert.equal(initial.panes.length, 8);
assert.deepEqual(PANE_COUNTS, [1, 2, 4, 8]);
assert.equal(new Set(initial.panes.slice(0, 4).map(x => x.serverId)).size, 4);

const invalid = sanitizeStudioState({
  count: 123, secret: "token-leak", messageHistory: [{ privateCode: "BAD" }],
  panes: [{ serverId: "admin-secret", channel: "private" }],
  themes: { arena: { accent: "url(https://attacker.test)", background: "#AABBCC", privateToken: "BAD" } },
});
assert.equal(invalid.count, 4);
assert.equal(invalid.panes[0].serverId, "arena");
assert.equal(invalid.themes.arena.accent, PRESETS.arena.accent);
assert.equal(invalid.themes.arena.background, "#aabbcc");
assert.ok(!exportStudioConfig(invalid).includes("secret"));
assert.ok(!exportStudioConfig(invalid).includes("messageHistory"));

const changed = updateStudioTheme(initial, "arena", "accent", "#123abc");
assert.equal(studioTheme(changed, "arena").accent, "#123abc");
assert.equal(studioTheme(changed, "markets").accent, PRESETS.markets.accent);
assert.equal(studioTheme(initial, "arena").accent, PRESETS.arena.accent);
assert.deepEqual(updateStudioTheme(initial, "unknown", "accent", "#123abc"), initial);

const pane = updateStudioPane(changed, 0, "markets", "market-watch");
assert.equal(pane.panes[0].serverId, "markets");
assert.equal(pane.panes[0].channel, "market-watch");
assert.deepEqual(updateStudioPane(pane, 99, "arena"), pane);
assert.equal(sanitizeStudioState({ count: 8 }).count, 8);
assert.equal(sanitizeStudioState({ count: 1 }).count, 1);

const allPresets = DEMO_SERVERS.map(server => studioTheme(initial, server.id));
assert.equal(new Set(allPresets.map(t => t.accent)).size, 6);
const fromJson = sanitizeStudioState(JSON.parse(exportStudioConfig(pane)));
assert.deepEqual(fromJson, pane);
console.log("Discord studio theme/layout model tests passed (mock configuration, no bot APIs).");
