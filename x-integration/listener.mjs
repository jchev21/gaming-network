import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createXAuth } from './x-auth.mjs';
import { createLobbyApi } from './lobby-api.mjs';

/**
 * Isolated Gaming Network X mention intake.
 * Read-only on X. It NEVER publishes posts or modifies the Discord bot.
 * An operator must explicitly enable polling after configuring credentials.
 */
const words = /\b(game|poker|play|challenge|lobby|giveaway|code[ -]?drop|start a game)\b/i;
const maxStateItems = 300;
export function classifyMention(post, handle, ownUserId) {
  if (!post || !/^\d+$/.test(String(post.id || ''))) return null;
  if (!post.author_id || String(post.author_id) === String(ownUserId)) return null;
  const body = String(post.text || '');
  if (/^RT\s+@/i.test(body)) return null;
  const normalized = handle.replace(/^@/, '').toLowerCase();
  const mentions = (post.entities?.mentions || []).some(m =>
    String(m.username || '').toLowerCase() === normalized ||
    (ownUserId && String(m.id || '') === String(ownUserId)));
  const escaped = normalized.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const literal = new RegExp('(^|[^\\w])@' + escaped + '(?![\\w])', 'i').test(body);
  if (!(mentions || literal) || !words.test(body)) return null;
  return {
    post_id: String(post.id),
    author_id: String(post.author_id),
    created_at: String(post.created_at || ''),
    status: 'awaiting_review',
    request_type: /poker/i.test(body) ? 'poker' : /giveaway/i.test(body) ? 'giveaway' : /code[ -]?drop/i.test(body) ? 'code-drop' : 'game',
    excerpt: body.slice(0, 240),
  };
}
export function adminOk(given, token) {
  if (!token || typeof given !== 'string') return false;
  const a = crypto.createHash('sha256').update(given).digest();
  const b = crypto.createHash('sha256').update('Bearer ' + token).digest();
  return crypto.timingSafeEqual(a, b);
}
export function newestId(ids) {
  return ids.map(String).filter(x => /^\d+$/.test(x)).reduce(
    (best, x) => !best || BigInt(x) > BigInt(best) ? x : best, null);
}
function settings(env = process.env) {
  const interval = Number(env.X_POLL_SECONDS || 120);
  return {
    handle: env.X_HANDLE || 'jordan__chev',
    userId: env.X_USER_ID || '',
    bearer: env.X_API_BEARER_TOKEN || '',
    admin: env.X_ADMIN_TOKEN || '',
    enabled: env.X_POLL_ENABLED === 'true',
    once: env.X_POLL_ENABLED === 'once',
    pollSeconds: Number.isFinite(interval) ? Math.min(3600, Math.max(90, interval)) : 120,
    dataDir: env.DATA_DIR || './runtime',
    port: Number(env.PORT || 8080),
  };
}
async function readState(file) {
  try {
    const d = JSON.parse(await fs.readFile(file, 'utf8'));
    return { since_id: d.since_id || null, initialized: !!d.initialized,
      target_user_id: d.target_user_id || null, target_handle: d.target_handle || null,
      pending: Array.isArray(d.pending) ? d.pending.slice(0, maxStateItems) : [],
      last_checked: d.last_checked || null, last_error: d.last_error || null };
  } catch (e) {
    if (e.code !== 'ENOENT') console.error('Invalid X state; starting empty', e.message);
    return { since_id: null, initialized: false, pending: [], last_checked: null, last_error: null, target_user_id: null, target_handle: null };
  }
}
async function persist(file, state) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const temp = file + '.tmp';
  await fs.writeFile(temp, JSON.stringify(state, null, 2), { mode: 0o600 });
  await fs.rename(temp, file);
}
async function pollX(s, state, file) {
  if (!s.bearer) throw new Error('X_API_BEARER_TOKEN required');
  // Reuse the verified numeric account ID for the unchanged handle to avoid a paid lookup on each restart.
  if (!s.userId && state.target_handle === s.handle && /^\d+$/.test(String(state.target_user_id || ''))) {
    s.userId = state.target_user_id;
  }
  if (!s.userId) {
    const lookup = await fetch('https://api.x.com/2/users/by/username/' +
      encodeURIComponent(s.handle.replace(/^@/, '')), {
      headers: { Authorization: 'Bearer ' + s.bearer },
      signal: AbortSignal.timeout(15000),
    });
    if (!lookup.ok) throw new Error('X username lookup HTTP ' + lookup.status);
    const profile = await lookup.json();
    if (!/^\d+$/.test(String(profile.data?.id || '')) ||
        String(profile.data?.username || '').toLowerCase() !== s.handle.replace(/^@/, '').toLowerCase())
      throw new Error('X account lookup returned unexpected profile');
    s.userId = String(profile.data.id);
  }
  if (!/^\d+$/.test(s.userId)) throw new Error('X_USER_ID must be numeric');
  state.target_user_id = s.userId;
  state.target_handle = s.handle;
  let nextToken;
  let posts = [];
  // Bounded pagination, read only. Does not call POST /2/tweets.
  for (let page = 0; page < (s.once ? 1 : 5); page++) {
    const url = new URL('https://api.x.com/2/users/' + s.userId + '/mentions');
    url.searchParams.set('max_results', s.once ? '5' : '100');
    url.searchParams.set('tweet.fields', 'author_id,created_at,entities');
    if (state.since_id) url.searchParams.set('since_id', state.since_id);
    if (nextToken) url.searchParams.set('pagination_token', nextToken);
    const response = await fetch(url, { headers: { Authorization: 'Bearer ' + s.bearer },
      signal: AbortSignal.timeout(15000) });
    if (!response.ok) {
      throw new Error('X API returned HTTP ' + response.status +
        (response.status === 429 ? ' (rate limit)' : ''));
    }
    const parsed = await response.json();
    posts.push(...(parsed.data || []));
    nextToken = parsed.meta?.next_token;
    if (!nextToken) break;
  }
  // Fail closed if rate limit/volume exceeds our safe scan window.
  if (nextToken && state.initialized) throw new Error('Too many mentions for scan window; no cursor advanced');
  const newest = newestId(posts.map(p => p.id));
  if (!state.initialized) {
    // First request establishes a baseline: never reply to older mentions.
    if (newest) state.since_id = newest;
    state.initialized = true;
    state.last_checked = new Date().toISOString();
    state.last_error = null;
    await persist(file, state);
    return { initialized: true, scanned: posts.length, added: 0 };
  }
  const found = new Set(state.pending.map(p => p.post_id));
  let added = 0;
  for (const post of posts.reverse()) {
    const p = classifyMention(post, s.handle, s.userId);
    if (!p || found.has(p.post_id)) continue;
    state.pending.unshift(p); found.add(p.post_id); added++;
  }
  state.pending = state.pending.slice(0, maxStateItems);
  if (newest && (!state.since_id || BigInt(newest) > BigInt(state.since_id))) state.since_id = newest;
  state.last_checked = new Date().toISOString();
  state.last_error = null;
  await persist(file, state);
  return { initialized: false, scanned: posts.length, added };
}
export async function start(env = process.env) {
  const s = settings(env);
  const stateFile = path.join(s.dataDir, 'x-mentions-state.json');
  const state = await readState(stateFile);
  const auth = await createXAuth({dataDir:s.dataDir,clientId:env.X_CLIENT_ID||'',clientSecret:env.X_CLIENT_SECRET||'',redirectUri:env.X_CALLBACK_URL||''});
  const lobbyApi = await createLobbyApi({dataDir:s.dataDir,auth,mentions:state,adminToken:s.admin,publicOrigin:env.X_PUBLIC_ORIGIN||'https://x-game-intake-production.up.railway.app'});
  let busy = false;
  async function doPoll() {
    if (busy) return { error: 'poll already running' };
    busy = true;
    try { return await pollX(s, state, stateFile); }
    catch (e) {
      state.last_error = e.message;
      await persist(stateFile, state);
      return { error: e.message };
    } finally { busy = false; }
  }
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', 'http://localhost');
    const send = (code, body) => { res.writeHead(code, {'content-type':'application/json','cache-control':'no-store'});
      res.end(JSON.stringify(body)); };
    if (req.method === 'GET' && url.pathname === '/health') {
      send(200, { service: 'x-game-intake', running: true, auto_poll: s.enabled,
        credentials_configured: !!s.bearer, oauth_ready: auth.enabled, last_checked: state.last_checked });
      return;
    }
    // OAuth and lobbies are independent of the X mention polling schedule.
    try {
      if (await auth.handle(req, res, url)) return;
      if (await lobbyApi.handle(req, res, url)) return;
    } catch (err) {
      console.error('X auth/lobby handler failed:', err.code||err.message);
      if (!res.headersSent) send(503, {error:'Service temporarily unavailable'});
      else res.end();
      return;
    }
    // Static, local-browser previews only. The X API is not called here.
    const staticPages = { '/': 'demo.html', '/setup': 'demo.html', '/high-scores': 'high-scores.html', '/lobby': 'lobby.html' };
    if (req.method === 'GET' && Object.prototype.hasOwnProperty.call(staticPages, url.pathname)) {
      try {
        const html = await fs.readFile(new URL('./' + staticPages[url.pathname], import.meta.url));
        res.writeHead(200, {
          'content-type': 'text/html; charset=utf-8',
          'cache-control': 'no-store',
          'x-robots-tag': 'noindex, nofollow',
          'referrer-policy': 'no-referrer',
          'x-content-type-options': 'nosniff',
          'content-security-policy': "default-src 'none'; connect-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        });
        res.end(html);
      } catch (err) {
        console.error('Could not load game preview:', err.code || err.message);
        send(503, { error: 'Preview unavailable' });
      }
      return;
    }
    if (!url.pathname.startsWith('/admin/')) { send(404, { error: 'Not found' }); return; }
    if (!adminOk(req.headers.authorization, s.admin)) {
      send(401, { error: 'Unauthorized' }); return;
    }
    if (req.method === 'GET' && url.pathname === '/admin/mentions') {
      send(200, { handle: s.handle, since_id: state.since_id, initialized: state.initialized,
        last_checked: state.last_checked, last_error: state.last_error, pending: state.pending }); return;
    }
    if (req.method === 'POST' && url.pathname === '/admin/poll') {
      const result = await doPoll(); send(result.error ? 503 : 200, result); return;
    }
    send(404, { error: 'Not found' });
  });
  server.listen(s.port, '0.0.0.0', () =>
    console.log('X intake ready on port ' + s.port + '; read-only, auto-poll=' + s.enabled));
  if (s.once) {
    console.log('X one-shot read-only test; at most one page of five mentions, no X posts');
    const result = await doPoll();
    console.log('X one-shot result:', JSON.stringify(result));
  } else if (s.enabled) {
    console.log('X polling enabled (no automatic replies or game creation)');
    await doPoll();
    setInterval(doPoll, s.pollSeconds * 1000);
  } else console.log('X polling disabled; no billable API calls will occur');
  return server;
}
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  start().catch(e => { console.error(e.message); process.exitCode = 1; });
}
