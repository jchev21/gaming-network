/**
 * Gaming Network — Discord Embedded App SDK bootstrap (Batch 2).
 * Client ID must match the Discord application used for Activities.
 * Scopes: identify only until owner approves broader scopes.
 * Never fetches private channel messages or redemption codes.
 */
import { DiscordSDK } from "/sdk/@discord/embedded-app-sdk@2.5.0";

export const CLIENT_ID = "1566288861259108424";

/** @typedef {"idle"|"connecting"|"ready"|"authorized"|"browser"|"error"} ConnectionState */

const discordSdk = new DiscordSDK(CLIENT_ID);

/**
 * @param {ConnectionState} state
 * @param {string} detail
 */
function setStatus(state, detail) {
  const el = document.getElementById("discord-status");
  const badge = document.getElementById("connection-badge");
  if (el) el.textContent = detail;
  if (badge) {
    badge.dataset.state = state;
    badge.textContent = stateLabel(state);
  }
  document.documentElement.dataset.activityState = state;
  window.dispatchEvent(
    new CustomEvent("gn-activity-state", { detail: { state, detail } }),
  );
}

function stateLabel(state) {
  switch (state) {
    case "connecting":
      return "Connecting";
    case "ready":
      return "SDK ready";
    case "authorized":
      return "Discord Activity connected";
    case "browser":
      return "Browser preview";
    case "error":
      return "Connection error";
    default:
      return "Idle";
  }
}

/**
 * Detect whether we are likely inside Discord's iframe.
 * Outside Discord, RPC parent is missing — treat as browser preview.
 */
function isLikelyEmbedded() {
  try {
    return window.parent !== window;
  } catch {
    return true;
  }
}

/**
 * Bootstrap: ready → authorize(identify) → update UI.
 * Failures are explicit; UI remains interactive for public/local controls.
 */
export async function connectActivity() {
  setStatus("connecting", "Connecting to Discord…");

  if (!isLikelyEmbedded()) {
    setStatus(
      "browser",
      "Browser preview — open via Talk → Activity → Hub inside Discord for full connection",
    );
    return { mode: "browser", sdk: discordSdk };
  }

  try {
    await discordSdk.ready();
    setStatus("ready", "SDK ready — authorizing…");

    const auth = await discordSdk.commands.authorize({
      client_id: CLIENT_ID,
      response_type: "code",
      state: "",
      prompt: "none",
      scope: ["identify"],
    });

    setStatus("authorized", "Discord Activity connected");
    console.info("[GN Activity] authorized", { hasCode: Boolean(auth?.code) });
    return { mode: "embedded", sdk: discordSdk, auth };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown Discord SDK error";
    setStatus("error", `Discord connection failed: ${message}`);
    console.error("[GN Activity] connection failed", error);
    return { mode: "error", sdk: discordSdk, error };
  }
}

// Auto-start when loaded as module from index.html
connectActivity();
