/**
 * Discord announcement bridge tests (mock transport only — never hits Discord).
 * Run: node discord-announce.test.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  resolveAnnounceConfig,
  buildAnnouncementPayload,
  formatDiscordContent,
  announcementKey,
  createDiscordAnnounceBridge,
  discordWebhookTransport,
  AnnounceConfigError,
  DISCORD_WEBHOOK_RE,
} from './discord-announce.mjs';
import { createLobby, joinLobby } from './game-core.mjs';

const VALID_WEBHOOK =
  'https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyzABCDEF';

{
  // A successful response from a redirected destination must never count as
  // an accepted Discord webhook delivery. This test makes NO network calls.
  let requests = 0;
  const accepted = await discordWebhookTransport(VALID_WEBHOOK,
    { content: 'public lobby', allowed_mentions: { parse: [] } },
    { fetchImpl: async (url, init) => {
      requests++;
      assert.equal(url, VALID_WEBHOOK);
      assert.equal(init.method, 'POST');
      assert.equal(init.redirect, 'error', 'webhook fetch must refuse HTTP redirects');
      return { ok: true, status: 204, redirected: false, url: VALID_WEBHOOK };
    } });
  assert.equal(accepted.status, 204);
  assert.equal(requests, 1);

  await assert.rejects(
    discordWebhookTransport(VALID_WEBHOOK, { content: 'public lobby' },
      { fetchImpl: async (_url, init) => {
        assert.equal(init.redirect, 'error');
        return { ok: true, status: 200, redirected: true, url: 'https://other.example/hook' };
      } }),
    e => e instanceof AnnounceConfigError && e.retryable === false && /redirect refused/.test(e.message),
    'followed redirects must fail closed even with HTTP 200'
  );

  await assert.rejects(
    discordWebhookTransport(VALID_WEBHOOK, { content: 'public lobby' },
      { fetchImpl: async () => ({ ok: true, status: 204, redirected: false,
        url: 'https://other.example/hook' }) }),
    /redirect refused/,
    'a mismatched response URL must fail closed'
  );

  await assert.rejects(
    discordWebhookTransport(VALID_WEBHOOK, { content: 'public lobby' },
      { fetchImpl: async (_url, init) => {
        assert.equal(init.redirect, 'error');
        throw new TypeError('fetch redirect disallowed');
      } }),
    /redirect disallowed/,
    'a redirect that Fetch rejects must not be retried by Fetch itself'
  );
  console.log('✓ webhook request blocks redirects and rejects suspicious responses');
}

{
  assert.equal(resolveAnnounceConfig({}).enabled, false);
  assert.equal(
    resolveAnnounceConfig({ DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED: 'true' }).enabled,
    false
  );
  assert.equal(
    resolveAnnounceConfig({
      DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED: 'true',
      DISCORD_LOBBY_WEBHOOK_URL: 'https://evil.example/hooks/1',
      X_PUBLIC_ORIGIN: 'https://games.example',
    }).enabled,
    false
  );
  assert.ok(DISCORD_WEBHOOK_RE.test(VALID_WEBHOOK));
  const ok = resolveAnnounceConfig({
    DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED: 'true',
    DISCORD_LOBBY_WEBHOOK_URL: VALID_WEBHOOK,
    X_PUBLIC_ORIGIN: 'https://games.example',
  });
  assert.equal(ok.enabled, true);
  console.log('\u2713 config disabled by default; invalid webhook rejected');
}

{
  const lobby = createLobby(
    { game: 'fortnite', title: 'Squad Up', seats: 2, mode: 'first', platform: 'pc' },
    '1001',
    1_700_000_000_000
  );
  joinLobby(lobby, '2002', '@alice', 1_700_000_000_100);
  joinLobby(lobby, '2003', '@bob', 1_700_000_000_200);
  const payload = buildAnnouncementPayload(lobby, {
    publicOrigin: 'https://games.example',
    hostDisplayName: '@host',
    event: 'ready',
  });
  assert.equal(payload.event, 'ready');
  assert.equal(payload.status, 'ready');
  assert.equal(payload.game, 'fortnite');
  assert.equal(payload.confirmedCount, 2);
  assert.equal(payload.lobbyUrl, `https://games.example/lobby?id=${lobby.id}`);
  assert.equal(payload.host, '@host');
  const json = JSON.stringify(payload);
  for (const leak of ['ownerXId', 'xId', 'joinSecrets', 'invite', '1001', '2002', 'instructions', 'ciphertext']) {
    assert.ok(!json.includes(leak), `must not leak ${leak}`);
  }
  const content = formatDiscordContent(payload);
  assert.match(content, /Lobby ready/);
  assert.match(content, /fortnite/);
  assert.ok(!content.includes('1001'));
  console.log('\u2713 sanitized payload and Discord content');
}

{
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-ann-'));
  const calls = [];
  const bridge = createDiscordAnnounceBridge({
    enabled: false,
    dataDir: dir,
    publicOrigin: 'https://games.example',
    transport: async (...args) => { calls.push(args); },
  });
  const lobby = createLobby({ game: 'warzone', title: 'Off', seats: 2, mode: 'first' }, '9', Date.now());
  const r = await bridge.enqueue(lobby, { event: 'ready' });
  assert.equal(r.queued, false);
  assert.equal(r.reason, 'disabled');
  assert.equal(calls.length, 0);
  await fs.rm(dir, { recursive: true, force: true });
  console.log('\u2713 disabled mode never queues or posts');
}

{
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-ann-'));
  const calls = [];
  let clock = 1000;
  const bridge = createDiscordAnnounceBridge({
    enabled: true,
    webhookUrl: VALID_WEBHOOK,
    publicOrigin: 'https://games.example',
    dataDir: dir,
    now: () => clock,
    transport: async (url, body) => {
      calls.push({ url, body });
      return { status: 204 };
    },
  });

  const lobby = createLobby(
    { game: 'valorant', title: 'Ranked', seats: 2, mode: 'first', platform: 'pc' },
    '1001',
    clock
  );
  joinLobby(lobby, '2002', '@p2', clock + 1);

  const first = await bridge.enqueue(lobby, { event: 'ready', hostDisplayName: '@host' });
  assert.equal(first.queued, true);
  assert.equal(first.key, announcementKey(lobby.id, 'ready'));

  const dup = await bridge.enqueue(lobby, { event: 'ready' });
  assert.equal(dup.queued, false);
  assert.equal(dup.reason, 'already_pending');

  const flushed = await bridge.flush();
  assert.equal(flushed.sent, 1);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, VALID_WEBHOOK);
  assert.match(calls[0].body.content, /Lobby ready/);
  assert.match(calls[0].body.content, /valorant/);
  assert.ok(!JSON.stringify(calls[0].body).includes('1001'));

  const bridge2 = createDiscordAnnounceBridge({
    enabled: true,
    webhookUrl: VALID_WEBHOOK,
    publicOrigin: 'https://games.example',
    dataDir: dir,
    now: () => clock,
    transport: async (...a) => { calls.push(a); return { status: 204 }; },
  });
  const again = await bridge2.enqueue(lobby, { event: 'ready' });
  assert.equal(again.queued, false);
  assert.equal(again.reason, 'already_sent');
  await bridge2.flush();
  assert.equal(calls.length, 1);

  await fs.rm(dir, { recursive: true, force: true });
  console.log('\u2713 enqueue once, dedupe pending+sent, survives restart');
}

{
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-ann-'));
  let clock = 5000;
  let attempts = 0;
  const bridge = createDiscordAnnounceBridge({
    enabled: true,
    webhookUrl: VALID_WEBHOOK,
    publicOrigin: 'https://games.example',
    dataDir: dir,
    now: () => clock,
    maxAttempts: 3,
    transport: async () => {
      attempts++;
      if (attempts < 2) {
        const e = new Error('Discord webhook HTTP 503');
        e.status = 503;
        e.retryable = true;
        throw e;
      }
      return { status: 204 };
    },
  });
  const lobby = createLobby({ game: 'minecraft', title: 'Retry', seats: 2, mode: 'first' }, '1', clock);
  joinLobby(lobby, '2', '@b', clock + 1);
  await bridge.enqueue(lobby, { event: 'ready' });
  const f1 = await bridge.flush();
  assert.equal(f1.sent, 0);
  assert.equal(attempts, 1);
  clock += 10_000;
  const f2 = await bridge.flush();
  assert.equal(f2.sent, 1);
  assert.equal(attempts, 2);
  await fs.rm(dir, { recursive: true, force: true });
  console.log('\u2713 retryable failure then success');
}

{
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-ann-'));
  const bridge = createDiscordAnnounceBridge({
    enabled: true,
    webhookUrl: 'https://example.com/not-discord',
    publicOrigin: 'https://games.example',
    dataDir: dir,
  });
  assert.equal(bridge.config.enabled, false);
  await fs.rm(dir, { recursive: true, force: true });
  console.log('\u2713 non-Discord webhook URL disables bridge');
}

{
  const rendered = formatDiscordContent({
    event: 'ready', title: '@everyone **fake link https://evil.test**',
    host: '@here', game: 'fortnite', platform: 'pc', mode: 'first',
    seats: 2, confirmedCount: 2, waitlistCount: 0,
    lobbyUrl: 'https://games.example/lobby?id=safe',
  });
  assert.ok(!rendered.includes('@everyone'));
  assert.ok(!rendered.includes('@here'));
  assert.ok(!rendered.includes('https://evil.test'));
  assert.ok(rendered.includes('https://games.example/lobby?id=safe'));
  console.log('✓ untrusted titles and display names cannot inject pings or hyperlinks');
}

{
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-ann-drain-'));
  let clock = 1000, attempts = 0;
  const bridge = createDiscordAnnounceBridge({
    enabled: true,
    webhookUrl: VALID_WEBHOOK,
    publicOrigin: 'https://games.example',
    dataDir: dir,
    now: () => clock,
    retryIntervalMs: 100,
    transport: async () => {
      attempts++;
      if (attempts === 1) {
        const error = new Error('synthetic HTTP 503');
        error.retryable = true;
        throw error;
      }
      return { status: 204 };
    },
  });
  try {
    const lobby = createLobby({ game: 'minecraft', title: 'Timer recovery', seats: 2, mode: 'first' }, '1001', clock);
    joinLobby(lobby, '2002', '@player', clock + 1);
    await bridge.enqueue(lobby);
    assert.equal(bridge.start(), true);
    assert.equal(bridge.start(), false, 'must not create duplicate drain timers');
    // First scheduled drain fails. Advance the mocked clock past the retry deadline.
    for (let i = 0; i < 40 && attempts < 1; i++) {
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    assert.equal(attempts, 1);
    clock += 2500;
    for (let i = 0; i < 40 && attempts < 2; i++) {
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    assert.equal(attempts, 2, 'retry timer should drain without an unrelated lobby event');
    // The mock transport can finish before the flush saves the sent marker.
    // Wait for the durable outbox state, not just a transport invocation.
    let stored;
    for (let i = 0; i < 40; i++) {
      stored = JSON.parse(await fs.readFile(bridge.outboxFile, 'utf8'));
      if (stored.sent[announcementKey(lobby.id, 'ready')]) break;
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    assert.ok(stored.sent[announcementKey(lobby.id, 'ready')]);
    console.log('✓ opt-in retry timer drains pending work after a transient failure');
  } finally {
    bridge.stop();
    await fs.rm(dir, { recursive: true, force: true });
  }
}

console.log('\nAll discord-announce tests passed.');
