/**
 * Public multiplayer-host metadata and encrypted private joining instructions.
 * No integration with third-party matchmaking APIs is implied.
 */
import crypto from 'node:crypto';

export const HOSTED_GAMES = Object.freeze([
  'fortnite', 'warzone', 'apex-legends', 'rocket-league',
  'minecraft', 'roblox', 'valorant', 'custom-multiplayer',
]);
export const REGIONS = Object.freeze([
  'any', 'na-east', 'na-central', 'na-west', 'europe',
  'asia', 'oceania', 'south-america', 'middle-east',
]);
export const CROSSPLAY = Object.freeze(['any', 'on', 'off']);

export class HostDetailsError extends Error {
  constructor(code, message) { super(message); this.code = code; this.status = 400; }
}

export function normalizeHostDetails(game, input) {
  if (!HOSTED_GAMES.includes(game)) return null;
  const data = input == null ? {} : input;
  if (typeof data !== 'object' || Array.isArray(data)) {
    throw new HostDetailsError('INVALID_HOST_DETAILS', 'Invalid host settings');
  }
  const mode = String(data.mode || '').trim();
  if (mode.length > 50 || /[\x00-\x1f\x7f<>]/.test(mode)) {
    throw new HostDetailsError('INVALID_GAME_MODE', 'Invalid game mode');
  }
  const region = String(data.region || 'any');
  if (!REGIONS.includes(region)) throw new HostDetailsError('INVALID_REGION', 'Unsupported region');
  const crossplay = String(data.crossplay || 'any');
  if (!CROSSPLAY.includes(crossplay)) throw new HostDetailsError('INVALID_CROSSPLAY', 'Unsupported crossplay setting');
  const islandCode = String(data.islandCode || '').trim();
  if (islandCode && (game !== 'fortnite' || !/^\d{4}-\d{4}-\d{4}$/.test(islandCode))) {
    throw new HostDetailsError('INVALID_ISLAND', 'Use a public 12-digit Fortnite island code (0000-0000-0000)');
  }
  // Public details never contain lobby passwords, custom-match keys or private URLs.
  return { mode, region, crossplay, islandCode };
}

export function validateJoinInstructions(value) {
  if (typeof value !== 'string') {
    throw new HostDetailsError('INVALID_INSTRUCTIONS', 'Joining instructions must be text');
  }
  const message = value.trim();
  if (message.length < 5 || message.length > 700 ||
      /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(message)) {
    throw new HostDetailsError('INVALID_INSTRUCTIONS', 'Enter 5–700 characters of joining instructions');
  }
  return message;
}

function requireDedicatedSecret(secret) {
  if(typeof secret!=='string'||Buffer.byteLength(secret,'utf8')<32)
    throw new Error('X_JOIN_SECRET_KEY must contain at least 32 bytes and must not be the admin token');
  return secret;
}
function v2Key(secret){
  return Buffer.from(crypto.hkdfSync('sha256',
    Buffer.from(requireDedicatedSecret(secret),'utf8'),
    Buffer.from('gaming-network-join-instructions','utf8'),
    Buffer.from('aes-256-gcm-v2','utf8'),32));
}
function legacyV1Key(secret){
  if(typeof secret!=='string'||secret.length<6)
    throw new Error('Legacy join instruction decryption key is not configured');
  return crypto.createHash('sha256').update('gaming-network-host-join-v1:').update(secret).digest();
}
/** Writes always use the dedicated v2 key; records carry a format/key version. */
export function sealJoinInstructions(plainText, secret){
  const message=validateJoinInstructions(plainText);
  const nonce=crypto.randomBytes(12);
  const cipher=crypto.createCipheriv('aes-256-gcm',v2Key(secret),nonce);
  const payload=Buffer.concat([cipher.update(message,'utf8'),cipher.final()]);
  return {v:2,keyVersion:2,iv:nonce.toString('base64url'),
    tag:cipher.getAuthTag().toString('base64url'),data:payload.toString('base64url')};
}
/** Optional legacy key is for explicit migration only, never a fallback for new writes. */
export function openJoinInstructions(record,secret,legacyKey=''){
  if(!record)return null;
  if(!record.iv||!record.tag||!record.data)
    throw new Error('Invalid encrypted joining instructions');
  let key;
  if(record.v===2&&record.keyVersion===2)key=v2Key(secret);
  else if(record.v===1)key=legacyV1Key(legacyKey);
  else throw new Error('Unsupported encrypted join instruction key version');
  const decipher=crypto.createDecipheriv('aes-256-gcm',key,Buffer.from(record.iv,'base64url'));
  decipher.setAuthTag(Buffer.from(record.tag,'base64url'));
  return Buffer.concat([decipher.update(Buffer.from(record.data,'base64url')),decipher.final()]).toString('utf8');
}

/** Only owners, or selected players after the lobby is ready, can access secrets. */
export function joinDetailsRole(lobby, authenticatedXId) {
  if (!lobby || !authenticatedXId) return null;
  const actor = String(authenticatedXId);
  if (lobby.ownerXId === actor) return 'host';
  if (lobby.status === 'ready' && Array.isArray(lobby.winners) && lobby.winners.includes(actor)) return 'selected';
  return null;
}
