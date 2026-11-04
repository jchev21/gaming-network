import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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
    pollSeconds: Number.isFinite(interval) ? Math.min(3600, Math.max(90, interval)) : 120,
    dataDir: env.DATA_DIR || './runtime',
    port: Number(env.PORT || 8080),
  };
}
async function readState(file) {
  try {
    const d = JSON.parse(await fs.readFile(file, 'utf8'));
    return { since_id: d.since_id || null, initialized: !!d.initialized,
      pending: Array.isArray(d.pending) ? d.pending.slice(0, maxStateItems) : [],
      last_checked: d.last_checked || null, last_error: d.last_error || null };
  } catch (e) {
    if (e.code !== 'ENOENT') console.error('Invalid X state; starting empty', e.message);
    return { since_id: null, initialized: false, pending: [], last_checked: null, last_error: null };
  }
}
async function persist(file, state) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const temp = file + '.tmp';
  await fs.writeFile(temp, JSON.stringify(state, null, 2), { mode: 0o600 });
  await fs.rename(temp, file);
}
async function pollX(s, state, file) {
  if (!s.userId || !s.bearer) throw new Error('X_USER_ID and X_API_BEARER_TOKEN required');
  if (!/^\d+$/.test(s.userId)) throw new Error('X_USER_ID must be numeric');
  let nextToken;
  let posts = [];
  // Bounded pagination, read only. Does not call POST /2/tweets.
  for (let page = 0; page < 5; page++) {
    const url = new URL('https://api.x.com/2/users/' + s.userId + '/mentions');
    url.searchParams.set('max_results', '100');
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
  if (nextToken) throw new Error('More than 500 mentions pending; manual pagination needed');
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
        credentials_configured: !!(s.userId && s.bearer), last_checked: state.last_checked });
      return;
    }
    if (!url.pathname.startsWith('/admin/')) { send(404, { error: 'Not found' }); return; }
    if (!s.admin || req.headers.authorization !== 'Bearer ' + s.admin) {
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
  if (s.enabled) {
    console.log('X polling enabled (no automatic replies or game creation)');
    await doPoll();
    setInterval(doPoll, s.pollSeconds * 1000);
  } else console.log('X polling disabled; no billable API calls will occur');
  return server;
}
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  start().catch(e => { console.error(e.message); process.exitCode = 1; });
}
