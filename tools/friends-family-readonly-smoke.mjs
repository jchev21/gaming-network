#!/usr/bin/env node
/**
 * Read-only public smoke test for a limited friends-and-family preview.
 * Does not authenticate, redeem codes, enter lobbies, post Discord messages,
 * enable paid X polling, or follow an OAuth redirect.
 */
import fs from 'node:fs';
const WEB = 'https://gaming-network-web-production.up.railway.app';
const X = 'https://x-game-intake-production.up.railway.app';
const checks = [];
const context = { revision: 'friends-family-1105', checkedAt: new Date().toISOString(),
  mode: 'READ_ONLY', checks };
async function probe(name, base, route, validate) {
  try {
    const result = await fetch(base + route, {
      method: 'GET', redirect: 'manual',
      headers: { accept: 'application/json,text/html;q=0.9' },
      cache: 'no-store', signal: AbortSignal.timeout(12000)
    });
    // Never persist OAuth locations, cookies, headers, session IDs or JSON payloads.
    const body = await result.text();
    const reason = validate(result, body);
    checks.push({ name, status: reason ? 'FAIL' : 'PASS', code: result.status,
      details: reason || 'HTTP and expected shape verified' });
  } catch (err) {
    checks.push({ name, status: 'BLOCKED', details: err?.name === 'TimeoutError' ? 'Timeout' : 'Network/parse error' });
  }
}
const http200 = (r) => r.status === 200 ? '' : 'Expected HTTP 200';
const html = (r,b) => r.status !== 200 ? 'Expected HTTP 200' : (!b.includes('Gaming Network') ? 'Page missing Gaming Network title' : '');
const json = (body) => { try { return JSON.parse(body); } catch { return null; } };
for (const route of ['/', '/welcome', '/games', '/live-games', '/discord', '/activity', '/high-scores']) {
  await probe('Website ' + route, WEB, route, html);
}
await probe('Public X readiness gateway', WEB, '/api/x-status', (r,b) => {
  if (![200,503].includes(r.status)) return 'Gateway unavailable (not a supported readiness HTTP status)';
  const j=json(b);
  return j && typeof j.reachable === 'boolean' && typeof j.signInReady === 'boolean' && typeof j.mentionsEnabled === 'boolean'
   ? '' : 'Readiness JSON does not have three expected booleans';
});
await probe('Safe public lobby gateway', WEB, '/api/public-lobbies', (r,b) => {
  if (![200,503].includes(r.status)) return 'Unexpected gateway HTTP status';
  if (r.status === 503) return ''; // transparent unavailable is an honest response
  const j=json(b);
  return j && typeof j === 'object' && !Array.isArray(j) ? '' : 'Public feed is not an object';
});
await probe('X service health and polling disabled', X, '/health', (r,b) => {
  if(r.status !== 200) return 'Health endpoint not HTTP 200';
  const j=json(b);
  return !j || j.service !== 'x-game-intake' || j.running !== true || j.auto_poll !== false
    ? 'Unexpected X health or automatic polling is enabled' : '';
});
await probe('X anonymous identity', X, '/api/me', (r,b) => {
  const j=json(b);
  return r.status===200 && j?.authenticated===false ? '' : 'Anonymous identity was not explicitly false';
});
await probe('X public lobby list privacy', X, '/api/lobbies?limit=5', (r,b) => {
  if(r.status !== 200) return 'Public lobby endpoint not HTTP 200';
  const j=json(b);
  if(!j || j.source !== 'live' || !Array.isArray(j.games)) return 'Unexpected live feed format';
  const forbidden=['join_code','joinCode','joinSecret','joinInstructions','access_token','sessionToken','secretKey','rawMention','xUserId','adminToken'];
  const raw=JSON.stringify(j);
  return forbidden.some(key=>raw.includes('"'+key+'"')) ? 'Forbidden private field in public feed' : '';
});
await probe('X private admin denies anonymous visitor', X, '/admin/mentions', r =>
  r.status === 401 ? '' : 'Admin data did not return HTTP 401'
);
await probe('X My Games requires authentication', X, '/api/my-games', r =>
  [401,403].includes(r.status) ? '' : 'Unauthenticated My Games not denied'
);
await probe('X invalid OAuth callback rejected', X, '/auth/x/callback', r =>
  r.status === 400 ? '' : 'Invalid OAuth callback not rejected with HTTP 400'
);
await probe('X OAuth sign-in start redirect and secure state cookie', X,
 '/auth/x/start?next=%2Fmy-games', (r) => {
  if (r.status !== 302) return 'X OAuth sign-in start is not HTTP 302 (redirect)';
  const location=r.headers.get('location') || '';
  let url;
  try { url = new URL(location); } catch { return 'OAuth redirect location is invalid'; }
  if (url.protocol !== 'https:' || !['x.com','twitter.com','api.x.com'].includes(url.hostname))
    return 'OAuth redirect host not trusted X domain';
  const cookie=r.headers.get('set-cookie')||'';
  if (!/HttpOnly/i.test(cookie) || !/Secure/i.test(cookie) || !/SameSite/i.test(cookie))
    return 'OAuth state cookie missing key security flags';
  return '';
});
const ok=checks.filter(x=>x.status==='PASS').length, failed=checks.filter(x=>x.status==='FAIL').length,
 blocked=checks.filter(x=>x.status==='BLOCKED').length;
context.summary={ pass:ok, fail:failed, blocked, total:checks.length };
const textReport=[
 '# Gaming Network — Friends & Family Read-only Preflight',
 'Mode: READ_ONLY. The test did NOT join or create games, contact Discord, complete X callback, or approve a launch.',
 'Checked: '+context.checkedAt,
 'Result: '+ok+' PASS / '+failed+' FAIL / '+blocked+' BLOCKED',
 ...checks.map(x => '- '+x.status+' '+x.name+(x.code ? ' (HTTP '+x.code+')':'')+(x.details ? ' — '+x.details:''))
].join('\n')+'\n';
console.log(textReport);
fs.writeFileSync(process.env.GITHUB_STEP_SUMMARY||'/tmp/gn-friends-family-summary.md',textReport);
fs.writeFileSync('/tmp/gn-friends-family-smoke.json',JSON.stringify(context,null,2)+'\n');
if(failed || blocked) process.exitCode=1;
