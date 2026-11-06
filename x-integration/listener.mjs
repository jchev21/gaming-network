import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
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
export function requiredPublicOrigin(env = process.env) {
  const value=env.X_PUBLIC_ORIGIN;
  if(typeof value!=='string' || !/^https:\/\/[^/?#\s:@]+(?::\d{1,5})?$/.test(value))
    throw new Error('X_PUBLIC_ORIGIN must explicitly be set to a single secure HTTPS origin');
  const parsed=new URL(value);
  if(parsed.origin!==value||!parsed.hostname)
    throw new Error('X_PUBLIC_ORIGIN must have no path, query, fragment or trailing slash');
  return value;
}
export function adminOk(given, token) {
  if (!token || typeof given !== 'string') return false;
  const provided=crypto.createHash('sha256').update(given).digest();
  const expected=crypto.createHash('sha256').update('Bearer '+token).digest();
  return crypto.timingSafeEqual(provided,expected);
}
export function newestId(ids) {
  return ids.map(String).filter(x => /^\d+$/.test(x)).reduce(
    (best, x) => !best || BigInt(x) > BigInt(best) ? x : best, null);
}
function cappedInt(raw, defaultValue, max, label) {
  if (raw === undefined || raw === '') return defaultValue;
  const n = Number(raw);
  if (!Number.isSafeInteger(n) || n < 1 || n > max) throw new Error(label + ' must be 1–' + max);
  return n;
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
    maxReadsPerDay: cappedInt(env.X_MAX_READS_PER_DAY, 8, 40, 'X_MAX_READS_PER_DAY'),
    maxPagesPerPoll: cappedInt(env.X_MAX_PAGES_PER_POLL, 2, 5, 'X_MAX_PAGES_PER_POLL'),
    dataDir: env.DATA_DIR || './runtime',
    port: Number(env.PORT || 8080),
  };
}
async function readState(file) {
  try {
    const d = JSON.parse(await fs.readFile(file, 'utf8'));
    if (typeof d !== 'object' || !d || Array.isArray(d)) throw new Error('Invalid state root');
    if (d.since_id !== null && d.since_id !== undefined && !/^\d+$/.test(String(d.since_id)))
      throw new Error('Invalid saved since_id');
    const scan = d.scan || null;
    if (scan && (!/^\d+$/.test(String(scan.base_since_id || '')) && scan.base_since_id !== null ||
      (scan.next_token !== null && (typeof scan.next_token !== 'string' || scan.next_token.length > 4096)) ||
      (scan.highest_id !== null && !/^\d+$/.test(String(scan.highest_id))) ||
      !Number.isSafeInteger(scan.scanned) || scan.scanned < 0))
      throw new Error('Invalid saved scan cursor');
    const budget = d.budget || null;
    if (budget && (!/^\d{4}-\d\d-\d\d$/.test(String(budget.day)) ||
      !Number.isSafeInteger(budget.used) || budget.used < 0))
      throw new Error('Invalid saved budget');
    if (d.pending !== undefined && (!Array.isArray(d.pending) || d.pending.length > maxStateItems))
      throw new Error('Invalid saved pending queue');
    return { since_id: d.since_id || null, initialized: !!d.initialized,
      target_user_id: d.target_user_id || null, target_handle: d.target_handle || null,
      pending: d.pending || [], scan, budget,
      pause_until: d.pause_until || null, blocked_reason: d.blocked_reason || null,
      last_checked: d.last_checked || null, last_error: d.last_error || null };
  } catch (e) {
    if (e.code !== 'ENOENT')
      throw new Error('Stored X mention state unreadable; refusing cursor reset: ' + e.message);
    return { since_id: null, initialized: false, pending: [], scan: null, budget: null,
      pause_until: null, blocked_reason: null, last_checked: null, last_error: null,
      target_user_id: null, target_handle: null };
  }
}
async function persist(file, state) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const temp = file + '.tmp';
  await fs.writeFile(temp, JSON.stringify(state, null, 2), { mode: 0o600 });
  await fs.rename(temp, file);
}
export async function pollX(s, state, file) {
  if (!s.bearer) throw new Error('X_API_BEARER_TOKEN required');
  if (state.blocked_reason) throw new Error('X reads blocked: ' + state.blocked_reason);
  if (state.pause_until && Date.now() < Date.parse(state.pause_until))
    throw new Error('X reads paused until ' + state.pause_until);
  if (state.target_handle && state.target_handle !== s.handle)
    throw new Error('X_HANDLE changed; operator must migrate the cursor safely');
  const maxReads = s.maxReadsPerDay || 8;
  const pagesPerPoll = s.once ? 1 : (s.maxPagesPerPoll || 2);
  const day = new Date().toISOString().slice(0, 10);
  if (!state.budget || state.budget.day !== day) {
    state.budget = { day, used: 0 };
    await persist(file, state);
  }
  async function request(url) {
    // Reserve before the outbound request: crashes/errors still count toward the cap.
    const today = new Date().toISOString().slice(0, 10);
    if (state.budget.day !== today) state.budget = { day: today, used: 0 };
    if (state.budget.used >= maxReads) throw new Error('X daily API read-call cap reached');
    state.budget.used++;
    await persist(file, state);
    const response = await fetch(url, { headers: { Authorization: 'Bearer ' + s.bearer },
      signal: AbortSignal.timeout(15000) });
    if (!response.ok) {
      const status = response.status;
      if ([401, 402, 403].includes(status)) state.blocked_reason = 'HTTP ' + status + ': operator review required';
      else {
        const retry = Number(response.headers.get('retry-after'));
        const delaySeconds = status === 429
          ? (Number.isFinite(retry) && retry > 0 ? Math.min(86400, Math.max(60, retry)) : 3600)
          : 300;
        state.pause_until = new Date(Date.now() + delaySeconds * 1000).toISOString();
      }
      await persist(file, state);
      throw new Error('X API returned HTTP ' + status);
    }
    return response;
  }
  // Cache the known account ID across restarts; do not pay for repeated profile lookups.
  if (!s.userId && state.target_handle === s.handle && /^\d+$/.test(String(state.target_user_id || ''))) {
    s.userId = state.target_user_id;
  }
  if (!s.userId) {
    const lookup = await request('https://api.x.com/2/users/by/username/' +
      encodeURIComponent(s.handle.replace(/^@/, '')));
    const profile = await lookup.json();
    if (!/^\d+$/.test(String(profile.data?.id || '')) ||
        String(profile.data?.username || '').toLowerCase() !== s.handle.replace(/^@/, '').toLowerCase())
      throw new Error('X account lookup returned unexpected profile');
    s.userId = String(profile.data.id);
  }
  if (!/^\d+$/.test(String(s.userId))) throw new Error('X_USER_ID must be numeric');
  state.target_user_id = s.userId;
  state.target_handle = s.handle;
  if (state.pending.length >= maxStateItems) throw new Error('X pending review queue full; no cursor advanced');
  if (!state.scan) {
    state.scan = { base_since_id: state.since_id, next_token: null, highest_id: null, scanned: 0 };
    await persist(file, state);
  }
  let scanned = 0, added = 0, pages = 0;
  for (let page = 0; page < pagesPerPoll; page++) {
    const scan = state.scan;
    const url = new URL('https://api.x.com/2/users/' + s.userId + '/mentions');
    url.searchParams.set('max_results', s.once ? '5' : '100');
    url.searchParams.set('tweet.fields', 'author_id,created_at,entities');
    if (scan.base_since_id) url.searchParams.set('since_id', scan.base_since_id);
    if (scan.next_token) url.searchParams.set('pagination_token', scan.next_token);
    const response = await request(url);
    const parsed = await response.json();
    if (!parsed || typeof parsed !== 'object' || (parsed.data !== undefined && !Array.isArray(parsed.data)) ||
        (parsed.meta !== undefined && (typeof parsed.meta !== 'object' || parsed.meta === null)))
      throw new Error('Invalid X mentions response; cursor not advanced');
    const posts = parsed.data || [];
    const next = parsed.meta?.next_token || null;
    if (next !== null && (typeof next !== 'string' || next.length > 4096))
      throw new Error('Invalid X pagination token; cursor not advanced');
    const newest = newestId(posts.map(p => p?.id));
    const found = new Set(state.pending.map(p => p.post_id));
    const fresh = [];
    if (state.initialized) {
      for (const post of posts) {
        const item = classifyMention(post, s.handle, s.userId);
        if (item && !found.has(item.post_id)) { fresh.push(item); found.add(item.post_id); }
      }
      if (state.pending.length + fresh.length > maxStateItems)
        throw new Error('X review queue capacity exceeded; no cursor advanced');
    }
    if (newest && (!scan.highest_id || BigInt(newest) > BigInt(scan.highest_id)))
      scan.highest_id = newest;
    state.pending.unshift(...fresh.reverse());
    scan.next_token = next;
    scan.scanned += posts.length;
    scanned += posts.length; added += fresh.length; pages++;
    state.last_checked = new Date().toISOString();
    state.last_error = null;
    // First-run baseline deliberately ignores historical mentions, one page is sufficient.
    if (!state.initialized || !next) {
      if (scan.highest_id && (!state.since_id || BigInt(scan.highest_id) > BigInt(state.since_id)))
        state.since_id = scan.highest_id;
      const initialized = !state.initialized;
      state.initialized = true;
      state.scan = null;
      await persist(file, state);
      return { initialized, scanned, added, pages, partial: false,
        daily_reads_used: state.budget.used, daily_reads_limit: maxReads };
    }
    // Preserve the continuation token and all pending results atomically on /data.
    await persist(file, state);
  }
  return { initialized: false, scanned, added, pages, partial: true,
    daily_reads_used: state.budget.used, daily_reads_limit: maxReads };
}
export async function start(env = process.env) {
  const s = settings(env);
  const stateFile = path.join(s.dataDir, 'x-mentions-state.json');
  const state = await readState(stateFile);
  const auth = await createXAuth({dataDir:s.dataDir,clientId:env.X_CLIENT_ID||'',clientSecret:env.X_CLIENT_SECRET||'',redirectUri:env.X_CALLBACK_URL||''});
  const lobbyApi = await createLobbyApi({dataDir:s.dataDir,auth,mentions:state,adminToken:s.admin,publicOrigin:requiredPublicOrigin(env)});
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
        credentials_configured: !!s.bearer, oauth_ready: auth.enabled, last_checked: state.last_checked, scan_in_progress: !!state.scan,
        daily_reads_used: state.budget?.used || 0, daily_reads_limit: s.maxReadsPerDay });
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
    const staticPages = { '/': 'demo.html', '/setup': 'demo.html', '/high-scores': 'high-scores.html', '/lobby': 'lobby.html', '/my-games': 'my-games.html' };
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
        last_checked: state.last_checked, last_error: state.last_error, pending: state.pending,
        scan_in_progress: !!state.scan, daily_reads_used: state.budget?.used || 0,
        daily_reads_limit: s.maxReadsPerDay, pause_until: state.pause_until,
        blocked_reason: state.blocked_reason }); return;
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
