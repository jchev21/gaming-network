import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { checkLaunchConfiguration, formatLaunchPreflight } from './launch-preflight.mjs';

const fixture = {
  X_PUBLIC_ORIGIN: 'https://x-game-intake-production.up.railway.app',
  X_CALLBACK_URL: 'https://x-game-intake-production.up.railway.app/auth/x/callback',
  X_CLIENT_ID: 'test-public-client-id',
  X_CLIENT_SECRET: 'local-dummy-client-secret',
  X_ADMIN_TOKEN: 'admin-dummy-'.repeat(5),
  X_JOIN_SECRET_KEY: 'join-dummy-'.repeat(5),
  X_POLL_ENABLED: 'false',
  X_HANDLE: 'jordan__chev',
  X_MODERATOR_USER_ID: '123456789',
  X_API_BEARER_TOKEN: 'dummy-read-only-token',
  DATA_DIR: '/data',
};

{
  const report = checkLaunchConfiguration(fixture);
  assert.equal(report.readyForManualTests, true, 'valid dummy config should pass format checks');
  assert.equal(report.checks.every(c => c.passed), true);
  const text = formatLaunchPreflight(report);
  assert.ok(text.includes('Real-account tests'));
  assert.ok(text.includes('[OK]'));
  assert.ok(text.includes(String.fromCharCode(10)), 'real newline expected');
  for (const secret of [fixture.X_ADMIN_TOKEN, fixture.X_JOIN_SECRET_KEY,
    fixture.X_CLIENT_SECRET, fixture.X_API_BEARER_TOKEN]) {
    assert.ok(!JSON.stringify(report).includes(secret), 'never return secret values');
    assert.ok(!text.includes(secret), 'never print secrets');
  }
  console.log('✓ full dummy configuration passes format-only preflight without secret disclosure');
}

{
  const empty = checkLaunchConfiguration({});
  assert.equal(empty.readyForManualTests, false);
  assert.ok(empty.checks.some(c => c.required && !c.passed));
  assert.ok(formatLaunchPreflight(empty).includes('BLOCKED'));
  console.log('✓ absent credentials fail closed');
}

{
  const wrongCallback = checkLaunchConfiguration({
    ...fixture, X_CALLBACK_URL: 'https://other.example/auth/x/callback',
  });
  assert.equal(wrongCallback.readyForManualTests, false);
  assert.equal(wrongCallback.checks.find(c => c.id === 'oauth-callback')?.passed, false);
  console.log('✓ callback URL must exactly match the public origin');
}

{
  const invalid = checkLaunchConfiguration({
    ...fixture,
    X_PUBLIC_ORIGIN: 'https://admin:SECRET_NEVER_ECHO@evil.example',
  });
  assert.equal(invalid.readyForManualTests, false);
  assert.ok(!JSON.stringify(invalid).includes('SECRET_NEVER_ECHO'));
  console.log('✓ malformed origins never echo URL-embedded credentials');
}

{
  for (const unsafe of [
    { X_JOIN_SECRET_KEY: 'too-short' },
    { X_JOIN_SECRET_KEY: fixture.X_ADMIN_TOKEN },
    { X_ADMIN_TOKEN: 'too-short' },
    { X_POLL_ENABLED: 'true' },
    { X_POLL_ENABLED: 'once' },
    { DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED: 'true' },
  ]) {
    const result = checkLaunchConfiguration({ ...fixture, ...unsafe });
    assert.equal(result.readyForManualTests, false, 'unsafe go-live flag or weak secret');
  }
  console.log('✓ dangerous polling, posting or weak/reused secrets block manual-test readiness');
}

{
  const optionalMissing = { ...fixture };
  delete optionalMissing.X_CLIENT_SECRET;
  delete optionalMissing.X_API_BEARER_TOKEN;
  delete optionalMissing.X_MODERATOR_USER_ID;
  delete optionalMissing.X_HANDLE;
  delete optionalMissing.DATA_DIR;
  const report = checkLaunchConfiguration(optionalMissing);
  assert.equal(report.readyForManualTests, true);
  assert.ok(report.checks.some(c => !c.required && !c.passed));
  assert.ok(formatLaunchPreflight(report).includes('OPTIONAL'));
  console.log('✓ optional developer app settings are not falsely marked as verified');
}

{
  const child = spawnSync(process.execPath, ['launch-preflight.mjs'], {
    cwd: new URL('.', import.meta.url),
    env: { ...process.env, ...fixture },
    encoding: 'utf8',
  });
  assert.equal(child.status, 0, child.stderr);
  assert.ok(child.stdout.includes('secret-safe preflight'));
  for (const sensitive of ['admin-dummy-', 'join-dummy-', 'local-dummy-', 'dummy-read-only-token']) {
    assert.ok(!child.stdout.includes(sensitive), 'CLI stdout must not reveal secret material');
    assert.ok(!child.stderr.includes(sensitive), 'CLI stderr must not reveal secret material');
  }
  console.log('✓ command-line preflight reports only fixed safe descriptions');
}

console.log('All credential preflight tests passed.');
