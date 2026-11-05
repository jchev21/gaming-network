/**
 * Pure, non-sensitive visual dashboard configuration.
 * Never handles Discord tokens, raw message history, private codes or user IDs.
 */
export const PRESETS = Object.freeze({
  arena: { name: "Esports Arena", accent: "#b79aff", secondary: "#f5c86a", background: "#19132a", icon: "🎮" },
  markets: { name: "Trading Desk", accent: "#62d9c3", secondary: "#a0c4ff", background: "#0c2225", icon: "📈" },
  academy: { name: "Education Academy", accent: "#7eacff", secondary: "#c9b4ff", background: "#101c35", icon: "🎓" },
  rewards: { name: "Rewards Studio", accent: "#f1c56b", secondary: "#ffa6b6", background: "#302219", icon: "🎁" },
  partners: { name: "Partner League", accent: "#f0a5e0", secondary: "#acb6ff", background: "#261429", icon: "🤝" },
  lounge: { name: "Community Lounge", accent: "#a4b0c5", secondary: "#88d8e4", background: "#171b27", icon: "💬" },
});
export const DEMO_SERVERS = Object.freeze([
  { id: "arena", name: "Neon Arena", channels: ["live-lobbies", "matchmaking", "tournaments", "general"] },
  { id: "markets", name: "Trading Floor", channels: ["market-watch", "trade-setups", "trading-chat", "calendar"] },
  { id: "academy", name: "Learning Lab", channels: ["start-here", "strategy-lessons", "academy-help", "progress"] },
  { id: "rewards", name: "Rewards Station", channels: ["giveaway-showcase", "rewards", "announcements", "general"] },
  { id: "partners", name: "Partner Network", channels: ["partner-events", "affiliate-studio", "leaderboard", "general"] },
  { id: "lounge", name: "Community Lounge", channels: ["introductions", "community-chat", "support", "general"] },
]);
export const PANE_COUNTS = Object.freeze([1, 2, 4, 8]);
const MAX_PANES = 8;
const isObj = value => value !== null && typeof value === "object" && !Array.isArray(value);
const safeColor = (value, fallback) => typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value) ? value.toLowerCase() : fallback;

export function defaultStudioState() {
  return {
    version: 1,
    count: 4,
    panes: Array.from({ length: MAX_PANES }, (_, i) => ({
      serverId: DEMO_SERVERS[i % DEMO_SERVERS.length].id,
      channel: DEMO_SERVERS[i % DEMO_SERVERS.length].channels[0],
    })),
    themes: {},
  };
}

/** Imports only documented, non-sensitive theme/layout fields, drops all extra keys. */
export function sanitizeStudioState(candidate) {
  const state = defaultStudioState();
  if (!isObj(candidate)) return state;
  if (PANE_COUNTS.includes(candidate.count)) state.count = candidate.count;
  if (Array.isArray(candidate.panes)) {
    for (let i = 0; i < Math.min(candidate.panes.length, MAX_PANES); i++) {
      const input = candidate.panes[i];
      if (!isObj(input)) continue;
      const server = DEMO_SERVERS.find(s => s.id === input.serverId);
      if (!server) continue;
      state.panes[i] = {
        serverId: server.id,
        channel: typeof input.channel === "string" && server.channels.includes(input.channel) ? input.channel : server.channels[0],
      };
    }
  }
  if (isObj(candidate.themes)) {
    for (const server of DEMO_SERVERS) {
      const custom = candidate.themes[server.id];
      if (!isObj(custom)) continue;
      const preset = PRESETS[server.id];
      state.themes[server.id] = {
        accent: safeColor(custom.accent, preset.accent),
        secondary: safeColor(custom.secondary, preset.secondary),
        background: safeColor(custom.background, preset.background),
      };
    }
  }
  return state;
}

export function studioTheme(state, serverId) {
  const base = PRESETS[serverId] ?? PRESETS.lounge;
  const custom = state.themes?.[serverId];
  return { ...base, ...(isObj(custom) ? custom : {}) };
}

export function updateStudioTheme(state, serverId, key, value) {
  if (!Object.hasOwn(PRESETS, serverId) || !["accent", "secondary", "background"].includes(key)) return state;
  const base = PRESETS[serverId];
  const safe = safeColor(value, base[key]);
  return sanitizeStudioState({
    ...state,
    themes: { ...state.themes, [serverId]: { ...state.themes?.[serverId], [key]: safe } },
  });
}

export function updateStudioPane(state, index, serverId, channel = null) {
  const original = sanitizeStudioState(state);
  const server = DEMO_SERVERS.find(s => s.id === serverId);
  if (!server || !Number.isSafeInteger(index) || index < 0 || index >= MAX_PANES) return original;
  original.panes[index] = {
    serverId: server.id,
    channel: server.channels.includes(channel) ? channel : server.channels[0],
  };
  return original;
}

/** JSON contains only mock IDs, pane count and theme RGB values; never message history. */
export function exportStudioConfig(state) {
  return JSON.stringify(sanitizeStudioState(state), null, 2);
}
