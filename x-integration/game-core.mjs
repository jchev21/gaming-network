/**
 * Gaming Network persistent lobby domain logic.
 * Independent of Discord, X, the web server and databases.
 * Caller MUST authenticate owner and player IDs with X OAuth (never trust request bodies).
 * Prizes, redeemable codes and verified arcade scores are deliberately out of scope.
 */
import { randomUUID, randomInt } from 'node:crypto';

export const ENTRY_MODES = Object.freeze(['first', 'lottery']);
export const GAME_TYPES = Object.freeze(['arcade-runner', 'arcade-targets', 'poker', 'trivia', 'code-drop', 'giveaway', 'fortnite', 'warzone', 'apex-legends', 'rocket-league', 'minecraft', 'roblox', 'valorant', 'custom-multiplayer']);
export const PLATFORMS = Object.freeze(['web', 'discord', 'pc', 'playstation', 'xbox', 'mobile']);
export const ROUND_SECONDS = Object.freeze([30, 60, 120, 300]);
export class LobbyError extends Error {
  constructor(code, message, status = 400) { super(message); this.code = code; this.status = status; }
}
const xId = value => /^\d{1,24}$/.test(String(value || ''));
const assert = (ok, code, msg, status) => { if (!ok) throw new LobbyError(code, msg, status); };
const maxName = input => String(input || '').trim().replace(/[\x00-\x1f\x7f]/g, '').slice(0, 48);
function normalize(input = {}) {
  const game = String(input.game || 'arcade-runner');
  const platform = String(input.platform || 'web');
  const mode = String(input.mode || 'first');
  const roundSeconds = Number(input.roundSeconds ?? 60);
  const seats = Number(input.seats ?? 5);
  assert(GAME_TYPES.includes(game), 'INVALID_GAME', 'Unsupported game type');
  assert(PLATFORMS.includes(platform), 'INVALID_PLATFORM', 'Unsupported platform');
  assert(ENTRY_MODES.includes(mode), 'INVALID_MODE', 'Unsupported entry mode');
  assert(ROUND_SECONDS.includes(roundSeconds), 'INVALID_ROUND', 'Unsupported round duration');
  assert(Number.isSafeInteger(seats) && seats >= 2 && seats <= 8, 'INVALID_SEATS', 'Choose between 2 and 8 players');
  const title = maxName(input.title || 'Gaming Network Challenge');
  assert(title.length >= 3, 'INVALID_TITLE', 'Give the game a title');
  return { game, platform, mode, seats, roundSeconds, title };
}
export function createLobby(input, ownerXId, now = Date.now(), id = randomUUID()) {
  assert(xId(ownerXId), 'AUTH_REQUIRED', 'X sign-in is required', 401);
  assert(Number.isSafeInteger(now) && now >= 0, 'INVALID_TIME', 'Invalid creation time');
  const opts = normalize(input);
  return {
    id, ...opts, ownerXId: String(ownerXId), createdAt: now,
    entryClosesAt: now + 300_000, // Five-minute lottery window.
    status: 'open', entries: [], winners: [], finalizedAt: null,
  };
}
export function finalizeLobby(lobby, now = Date.now(), random = randomInt) {
  assert(lobby && lobby.status, 'INVALID_LOBBY', 'Invalid lobby');
  if (lobby.status !== 'open') return lobby;
  if (lobby.mode === 'first') {
    if (lobby.entries.length >= lobby.seats) lobby.status = 'ready';
    else if (now >= lobby.entryClosesAt) lobby.status = 'closed';
    if (lobby.status !== 'open') {
      lobby.winners = lobby.entries.slice(0, lobby.seats).map(e => e.xId);
      lobby.finalizedAt = now;
    }
  } else if (now >= lobby.entryClosesAt) {
    const indices = lobby.entries.map((_, i) => i);
    for (let i = indices.length - 1; i > 0; i--) {
      const j = random(i + 1);
      assert(Number.isInteger(j) && j >= 0 && j <= i, 'INVALID_RANDOM', 'Invalid random index');
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    lobby.winners = indices.slice(0, lobby.seats).map(i => lobby.entries[i].xId);
    lobby.status = lobby.winners.length ? 'ready' : 'closed';
    lobby.finalizedAt = now;
  }
  return lobby;
}
export function joinLobby(lobby, actorXId, displayName, now = Date.now()) {
  assert(xId(actorXId), 'AUTH_REQUIRED', 'X sign-in is required', 401);
  assert(lobby && lobby.status, 'NOT_FOUND', 'Game not found', 404);
  finalizeLobby(lobby, now);
  assert(lobby.status === 'open', 'CLOSED', 'Entries are closed', 409);
  const id = String(actorXId);
  assert(!lobby.entries.some(e => e.xId === id), 'DUPLICATE', 'You already entered', 409);
  if (lobby.mode === 'first') {
    assert(lobby.entries.length < lobby.seats, 'FULL', 'All seats are filled', 409);
  } else assert(lobby.entries.length < 200, 'CAPACITY', 'Entry pool is full', 409);
  const name = maxName(displayName);
  assert(name.length >= 1, 'INVALID_NAME', 'Display name is required');
  lobby.entries.push({xId: id, name, joinedAt: now});
  if (lobby.mode === 'first') finalizeLobby(lobby, now);
  return lobby;
}
export function publicLobby(lobby, now = Date.now()) {
  if (!lobby) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
  finalizeLobby(lobby, now);
  const selected = new Set(lobby.winners);
  return {
    id: lobby.id, title: lobby.title, game: lobby.game,
    platform: lobby.platform, mode: lobby.mode, seats: lobby.seats,
    roundSeconds: lobby.roundSeconds,
    status: lobby.status, entryClosesAt: lobby.entryClosesAt,
    entryCount: lobby.entries.length,
    confirmedCount: lobby.mode === 'lottery' ? selected.size : Math.min(lobby.entries.length, lobby.seats),
    // Never expose X IDs, internal keys, redeem codes, or random seeds.
    entries: lobby.entries.slice(0, 200).map(e => ({ name: e.name, selected: lobby.status === 'open' ? null : selected.has(e.xId) })),
  };
}