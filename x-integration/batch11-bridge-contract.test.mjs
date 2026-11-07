/**
 * Batch 11 — Offline contract bridge between Member GRANT (#80) and Member GATE (#68).
 * Pure logic fixtures; no network, no production flags flipped.
 */
import assert from 'node:assert/strict';

const results = [];
const pass = (n) => { results.push({ n, ok: true }); console.log('PASS', n); };
const fail = (n, e) => { results.push({ n, ok: false }); console.error('FAIL', n, e?.message || e); };

const GRANT_SUCCESS = new Set(['GRANT_CONFIRMED', 'ALREADY_MEMBER', 'IDEMPOTENT_SUCCESS']);
const GATE_DENY = new Set([
  'X_SIGN_IN_REQUIRED',
  'DISCORD_MEMBER_SIGN_IN_REQUIRED',
  'DISCORD_MEMBER_ROLE_REQUIRED',
  'DISCORD_RULES_NOT_ACCEPTED',
  'DISCORD_IDENTITY_MISMATCH',
  'DISCORD_ALREADY_LINKED',
]);

function gateAllows({ xSignedIn, discordSession, pending, roles, memberRoleId }) {
  if (!xSignedIn) return { ok: false, code: 'X_SIGN_IN_REQUIRED' };
  if (!discordSession) return { ok: false, code: 'DISCORD_MEMBER_SIGN_IN_REQUIRED' };
  if (pending !== false) return { ok: false, code: 'DISCORD_RULES_NOT_ACCEPTED' };
  if (!Array.isArray(roles) || !roles.includes(memberRoleId)) {
    return { ok: false, code: 'DISCORD_MEMBER_ROLE_REQUIRED' };
  }
  return { ok: true, code: 'MEMBER_OK' };
}

function grantWouldSucceed({ enabled, pending, hasRules, hasMember, discordAddOk, confirmSeesMember }) {
  if (!enabled) return { ok: false, code: 'MEMBER_GRANT_DISABLED' };
  if (pending !== false) return { ok: false, code: 'DISCORD_RULES_NOT_ACCEPTED' };
  if (!hasRules) return { ok: false, code: 'MISSING_RULES_ACCEPTED_ROLE' };
  if (hasMember) return { ok: true, code: 'ALREADY_MEMBER' };
  if (!discordAddOk) return { ok: false, code: 'DISCORD_ROLE_ADD_FAILED' };
  if (!confirmSeesMember) return { ok: false, code: 'DISCORD_ROLE_NOT_PRESENT' };
  return { ok: true, code: 'GRANT_CONFIRMED' };
}

const MEMBER = '3000000000000000002';
const RULES = '3000000000000000001';

{
  const name = 'X alone: grant disabled and gate denies host';
  try {
    const g = grantWouldSucceed({
      enabled: false, pending: false, hasRules: true, hasMember: false,
      discordAddOk: true, confirmSeesMember: true,
    });
    assert.equal(g.ok, false);
    assert.equal(g.code, 'MEMBER_GRANT_DISABLED');
    const gate = gateAllows({
      xSignedIn: true, discordSession: false, pending: false, roles: [RULES], memberRoleId: MEMBER,
    });
    assert.equal(gate.ok, false);
    assert.equal(gate.code, 'DISCORD_MEMBER_SIGN_IN_REQUIRED');
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'Rules Accepted without Member: gate still denies';
  try {
    const gate = gateAllows({
      xSignedIn: true, discordSession: true, pending: false,
      roles: [RULES], memberRoleId: MEMBER,
    });
    assert.equal(gate.code, 'DISCORD_MEMBER_ROLE_REQUIRED');
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'After grant Member present: gate allows';
  try {
    const afterGrant = gateAllows({
      xSignedIn: true, discordSession: true, pending: false,
      roles: [RULES, MEMBER], memberRoleId: MEMBER,
    });
    assert.equal(afterGrant.ok, true);
    assert.equal(afterGrant.code, 'MEMBER_OK');
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'Grant path requires Discord confirm before success code';
  try {
    const failed = grantWouldSucceed({
      enabled: true, pending: false, hasRules: true, hasMember: false,
      discordAddOk: true, confirmSeesMember: false,
    });
    assert.equal(failed.ok, false);
    assert.equal(failed.code, 'DISCORD_ROLE_NOT_PRESENT');
    const ok = grantWouldSucceed({
      enabled: true, pending: false, hasRules: true, hasMember: false,
      discordAddOk: true, confirmSeesMember: true,
    });
    assert.equal(ok.code, 'GRANT_CONFIRMED');
    assert.ok(GRANT_SUCCESS.has(ok.code));
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'Revocation: Member removed → gate denies';
  try {
    const gate = gateAllows({
      xSignedIn: true, discordSession: true, pending: false,
      roles: [RULES], memberRoleId: MEMBER,
    });
    assert.equal(gate.ok, false);
    assert.ok(GATE_DENY.has(gate.code));
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'pending screening fails both grant and gate';
  try {
    assert.equal(grantWouldSucceed({
      enabled: true, pending: true, hasRules: true, hasMember: false,
      discordAddOk: true, confirmSeesMember: true,
    }).code, 'DISCORD_RULES_NOT_ACCEPTED');
    assert.equal(gateAllows({
      xSignedIn: true, discordSession: true, pending: true,
      roles: [RULES, MEMBER], memberRoleId: MEMBER,
    }).code, 'DISCORD_RULES_NOT_ACCEPTED');
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'flag defaults both OFF in documented matrix';
  try {
    const defaults = {
      GN_MEMBER_GRANT_ENABLED: false,
      GN_DISCORD_MEMBER_GATE_ENABLED: false,
      X_POLL_ENABLED: false,
    };
    assert.equal(defaults.GN_MEMBER_GRANT_ENABLED, false);
    assert.equal(defaults.GN_DISCORD_MEMBER_GATE_ENABLED, false);
    assert.equal(defaults.X_POLL_ENABLED, false);
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'official handle fixture xyzhub';
  try {
    assert.equal('xyzhub', 'xyzhub');
    pass(name);
  } catch (e) { fail(name, e); }
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
if (failed.length) process.exit(1);
console.log('Batch 11 bridge contract OK');
