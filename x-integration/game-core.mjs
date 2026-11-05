/**
 * Gaming Network persistent lobby domain logic.
 * Independent of Discord, X, the web server and databases.
 * Caller MUST authenticate owner and player IDs with X OAuth (never trust request bodies).
 * Prizes, redeemable codes and verified arcade scores are deliberately out of scope.
 */
import { randomUUID, randomInt } from 'node:crypto';
import {normalizeHostDetails} from './host-utils.mjs';

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
  return { game, platform, mode, seats, roundSeconds, title, host: normalizeHostDetails(game, input.host) };
}
export function createLobby(input, ownerXId, now = Date.now(), id = randomUUID()) {
  assert(xId(ownerXId), 'AUTH_REQUIRED', 'X sign-in is required', 401);
  assert(Number.isSafeInteger(now) && now >= 0, 'INVALID_TIME', 'Invalid creation time');
  const opts = normalize(input);
  return {
    id, ...opts, ownerXId: String(ownerXId), createdAt: now,
    entryClosesAt: now + 300_000, // Five-minute lottery window.
    status: 'open', entries: [], winners: [], withdrawnXIds: [],
    waitlist: [], removedXIds: [], finalizedAt: null,
  };
}
export function finalizeLobby(lobby, now = Date.now(), random = randomInt) {
  assert(lobby && lobby.status, 'INVALID_LOBBY', 'Invalid lobby');
  if (lobby.status !== 'open') return lobby;
  if (lobby.mode === 'first') {
    if (lobby.entries.length >= lobby.seats) lobby.status = 'ready';
    else if (now >= lobby.entryClosesAt) lobby.status = 'closed';
    if (lobby.status !== 'open') {
      lobby.winners = lobby.status === 'ready' ? lobby.entries.slice(0, lobby.seats).map(e => e.xId) : [];
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
  assert(!(lobby.waitlist || []).some(e => e.xId === id), 'WAITLISTED', 'You are already on the waitlist', 409);
  assert(!(lobby.removedXIds || []).includes(id), 'REMOVED', 'You were removed from this game', 409);
  assert(!(lobby.withdrawnXIds || []).includes(id), 'WITHDRAWN', 'You previously withdrew from this game', 409);
  if (lobby.mode === 'first') {
    assert(lobby.entries.length < lobby.seats, 'FULL', 'All seats are filled', 409);
  } else assert(lobby.entries.length < 200, 'CAPACITY', 'Entry pool is full', 409);
  const name = maxName(displayName);
  assert(name.length >= 1, 'INVALID_NAME', 'Display name is required');
  lobby.entries.push({xId: id, name, joinedAt: now});
  if (lobby.mode === 'first') finalizeLobby(lobby, now);
  return lobby;
}

/** A full first-come lobby accepts a bounded FIFO standby list (not prize entry). */
export function joinWaitlist(lobby, actorXId, displayName, now = Date.now()) {
  assert(xId(actorXId), 'AUTH_REQUIRED', 'X sign-in is required', 401);
  assert(lobby && lobby.status, 'NOT_FOUND', 'Game not found', 404);
  finalizeLobby(lobby, now);
  assert(lobby.mode === 'first' && lobby.status === 'ready', 'NOT_FULL',
    'Waitlist is only available after a first-come game fills', 409);
  const id = String(actorXId);
  assert(!lobby.entries.some(e => e.xId === id), 'DUPLICATE', 'You already have a seat', 409);
  assert(!(lobby.waitlist || []).some(e => e.xId === id), 'WAITLISTED', 'Already on the waitlist', 409);
  assert(!(lobby.withdrawnXIds || []).includes(id), 'WITHDRAWN', 'You already withdrew', 409);
  assert(!(lobby.removedXIds || []).includes(id), 'REMOVED', 'You were removed from this game', 409);
  lobby.waitlist ||= [];
  assert(lobby.waitlist.length < 100, 'WAITLIST_FULL', 'Waitlist is full', 409);
  const name = maxName(displayName);
  assert(name.length >= 1, 'INVALID_NAME', 'Display name required');
  lobby.waitlist.push({ xId: id, name, joinedAt: now });
  return lobby;
}

/** Only the verified host can report a selected no-show and replace that seat. */
export function replaceNoShow(lobby, actorXId, seat, now = Date.now()) {
  assert(xId(actorXId), 'AUTH_REQUIRED', 'X sign-in is required', 401);
  assert(lobby && lobby.status, 'NOT_FOUND', 'Game not found', 404);
  assert(lobby.ownerXId === String(actorXId), 'HOST_ONLY', 'Only the host can replace seats', 403);
  assert(lobby.mode === 'first' && lobby.status === 'ready', 'NOT_READY',
    'Seat replacement requires a full first-come lobby', 409);
  assert(Number.isInteger(seat) && seat >= 0 && seat < lobby.winners.length,
    'INVALID_SEAT', 'Invalid selected seat', 400);
  const removedId = lobby.winners[seat];
  const idx = lobby.entries.findIndex(e => e.xId === removedId);
  assert(idx >= 0, 'MISSING_SEAT', 'Selected entrant no longer exists', 409);
  lobby.entries.splice(idx, 1);
  lobby.removedXIds ||= [];
  if (!lobby.removedXIds.includes(removedId)) lobby.removedXIds.push(removedId);
  const next = (lobby.waitlist || []).shift();
  if (next) {
    lobby.entries.push(next);
    lobby.winners[seat] = next.xId;
  } else {
    // Reopen for five minutes so a replacement can join normally.
    lobby.winners = [];
    lobby.status = 'open';
    lobby.entryClosesAt = now + 300_000;
    lobby.finalizedAt = null;
  }
  return lobby;
}

/** Hosts can cancel before or after a drawing; it removes all winning permissions. */
export function cancelLobby(lobby, actorXId, now = Date.now()) {
  assert(xId(actorXId), 'AUTH_REQUIRED', 'X sign-in is required', 401);
  assert(lobby && lobby.status, 'NOT_FOUND', 'Game not found', 404);
  assert(lobby.ownerXId === String(actorXId), 'HOST_ONLY', 'Only the host can cancel this game', 403);
  assert(lobby.status !== 'cancelled', 'CANCELLED', 'Game was already cancelled', 409);
  lobby.status = 'cancelled';
  lobby.winners = [];
  lobby.finalizedAt = now;
  lobby.cancelledAt = now;
  return lobby;
}

/** A player can withdraw before the signup window closes, not after selection. */
export function withdrawEntry(lobby, actorXId, now = Date.now()) {
  assert(xId(actorXId), 'AUTH_REQUIRED', 'X sign-in is required', 401);
  assert(lobby && lobby.status, 'NOT_FOUND', 'Game not found', 404);
  finalizeLobby(lobby, now);
  const id = String(actorXId);
  // A standby player may withdraw even after the first seats are confirmed.
  if (lobby.status === 'ready' && lobby.mode === 'first') {
    const wait = (lobby.waitlist || []).findIndex(e => e.xId === id);
    if (wait >= 0) {
      lobby.waitlist.splice(wait, 1);
      lobby.withdrawnXIds ||= [];
      if (!lobby.withdrawnXIds.includes(id)) lobby.withdrawnXIds.push(id);
      return lobby;
    }
  }
  assert(lobby.status === 'open', 'CLOSED', 'The signup window has already closed', 409);
  const idx = lobby.entries.findIndex(e => e.xId === id);
  assert(idx >= 0, 'NOT_ENTERED', 'You have not joined this lobby', 404);
  lobby.entries.splice(idx, 1);
  lobby.withdrawnXIds ||= [];
  if (!lobby.withdrawnXIds.includes(id)) lobby.withdrawnXIds.push(id);
  return lobby;
}

export function publicLobby(lobby, now = Date.now()) {
  if (!lobby) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
  finalizeLobby(lobby, now);
  const selected = new Set(lobby.winners);
  return {
    id: lobby.id, title: lobby.title, game: lobby.game,
    host: lobby.host || null, // validated public metadata only
    platform: lobby.platform, mode: lobby.mode, seats: lobby.seats,
    roundSeconds: lobby.roundSeconds,
    status: lobby.status, entryClosesAt: lobby.entryClosesAt,
    entryCount: lobby.entries.length,
    waitlistCount: lobby.status === 'cancelled' ? 0 : (lobby.waitlist || []).length,
    waitlist: lobby.status === 'cancelled' ? [] : (lobby.waitlist || []).map((e,i) => ({name:e.name,position:i+1})),
    confirmedCount: (lobby.status === 'cancelled' || lobby.status === 'closed') ? 0 : lobby.mode === 'lottery' ? selected.size : Math.min(lobby.entries.length, lobby.seats),
    // Never expose X IDs, internal keys, redeem codes, or random seeds.
    entries: lobby.entries.slice(0, 200).map(e => ({
      name: e.name, selected: lobby.status === 'open' ? null : selected.has(e.xId),
      seat: lobby.status === 'ready' && selected.has(e.xId) ? lobby.winners.indexOf(e.xId) : null,
    })),
  };
}