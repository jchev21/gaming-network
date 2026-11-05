import assert from 'node:assert/strict';
import { createXAdapter, createPublicLifecycleEvent } from './bridge-contracts.mjs';

const disabled = createXAdapter();
assert.deepEqual(disabled.acceptMention({ mentionId: '123', authorId: '456' }), { accepted: false, reason: 'disabled' });
assert.deepEqual(disabled.queueApprovedReply({ mentionId: '123', text: 'Setup link', approved: true, expiresAt: Date.now() + 1000 }), { queued: false, reason: 'disabled' });

const adapter = createXAdapter({ enabled: true, verifyAuthor: (id) => id === '456' });
const mention = { mentionId: '123', authorId: '456', username: 'untrusted-handle' };
assert.equal(adapter.acceptMention(mention).accepted, true);
assert.equal(adapter.acceptMention(mention).reason, 'duplicate');
assert.equal(adapter.acceptMention({ mentionId: '124', authorId: '999' }).reason, 'unverified');
assert.equal(adapter.acceptMention({ mentionId: 'not-an-id', authorId: '456' }).reason, 'invalid');
assert.equal(adapter.queueApprovedReply({ mentionId: '123', text: 'setup', expiresAt: Date.now() + 1000 }).reason, 'approval_required');
assert.equal(adapter.queueApprovedReply({ mentionId: '123', text: 'setup', approved: true, expiresAt: Date.now() + 1000 }).queued, true);
assert.equal(adapter.queueApprovedReply({ mentionId: '123', text: 'again', approved: true, expiresAt: Date.now() + 1000 }).reason, 'duplicate');
assert.equal(adapter.listApprovedReplies(Date.now() + 2000).length, 0);

const privateLobby = {
  id: 'public-lobby-1', title: 'Sample game', game: 'fortnite', platform: 'pc', mode: 'first',
  status: 'ready', seats: 2, entryCount: 2, confirmedCount: 2, entryClosesAt: 12345,
  ownerXId: '998877', entries: [{ xId: '445566', name: 'SAMPLE player' }],
  waitlist: [{ xId: '334455', name: 'SAMPLE standby' }],
  joinSecrets: { data: 'ciphertext' }, inviteToken: 'secret-token',
};
const event = createPublicLifecycleEvent('ready', privateLobby, '2026-11-05T00:00:00.000Z');
assert.equal(event.type, 'ready');
assert.equal(event.lobby.status, 'ready');
assert.equal(event.eventId, createPublicLifecycleEvent('ready', privateLobby, '2026-11-06T00:00:00.000Z').eventId, 'event key is idempotent per lifecycle transition');
assert.equal(JSON.stringify(event).includes('998877'), false);
assert.equal(JSON.stringify(event).includes('445566'), false);
assert.equal(JSON.stringify(event).includes('ciphertext'), false);
assert.equal(JSON.stringify(event).includes('secret-token'), false);
assert.equal(JSON.stringify(event).includes('SAMPLE player'), false);
assert.throws(() => createPublicLifecycleEvent('unknown', privateLobby), /Unsupported/);
assert.throws(() => createPublicLifecycleEvent('created', {}), /incomplete/);

console.log('Bridge contract tests passed: disabled X, dedupe, approval, expiry, sanitized lifecycle events');
