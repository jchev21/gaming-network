import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {
  HOSTED_GAMES, normalizeHostDetails, sealJoinInstructions,
  openJoinInstructions, validateJoinInstructions, joinDetailsRole,
} from './host-utils.mjs';

for (const game of HOSTED_GAMES) {
  const host = normalizeHostDetails(game, {mode:'Duos', region:'na-east', crossplay:'on'});
  assert.equal(host.mode, 'Duos');
  assert.equal(host.region, 'na-east');
  assert.equal(host.crossplay, 'on');
}
assert.deepEqual(normalizeHostDetails('fortnite', {islandCode:'1234-5678-9012'}),
  {mode:'',region:'any',crossplay:'any',islandCode:'1234-5678-9012'});
assert.equal(normalizeHostDetails('arcade-runner', {mode:'casual'}), null);
assert.throws(() => normalizeHostDetails('warzone', {islandCode:'1234-5678-9012'}), e => e.code==='INVALID_ISLAND');
assert.throws(() => normalizeHostDetails('fortnite', {islandCode:'secret-room'}), e => e.code==='INVALID_ISLAND');
assert.throws(() => normalizeHostDetails('warzone', {region:'moon'}), e => e.code==='INVALID_REGION');
assert.throws(() => normalizeHostDetails('fortnite', {mode:'<script>'}), e => e.code==='INVALID_GAME_MODE');
assert.throws(() => validateJoinInstructions('x'), e => e.code==='INVALID_INSTRUCTIONS');

const secret='a-private-admin-secret-with-high-entropy';
const plaintext='Join my party using private key "secret123" after you are selected.';
const sealed=sealJoinInstructions(plaintext,secret);
assert.equal(sealed.v,2);assert.equal(sealed.keyVersion,2);
assert.equal(openJoinInstructions(sealed,secret),plaintext);
assert.throws(()=>sealJoinInstructions(plaintext,'short'),/X_JOIN_SECRET_KEY/);
assert.ok(!JSON.stringify(sealed).includes('secret123'));
assert.notEqual(sealJoinInstructions(plaintext,secret).data,sealed.data);
assert.throws(() => openJoinInstructions(sealed,'wrong-encryption-secret-of-sufficient-length'), /auth|authenticate|Unsupported/i);
const altered=Buffer.from(sealed.data,'base64url');altered[0]^=0x01;
const tampered={...sealed, data:altered.toString('base64url')};
assert.throws(() => openJoinInstructions(tampered,secret), /auth|authenticate/i);

const oldKey='legacy-admin-token-example-for-test';
const iv=crypto.randomBytes(12),legacyDerived=crypto.createHash('sha256')
  .update('gaming-network-host-join-v1:').update(oldKey).digest();
const legacyCipher=crypto.createCipheriv('aes-256-gcm',legacyDerived,iv);
const data=Buffer.concat([legacyCipher.update(plaintext,'utf8'),legacyCipher.final()]);
const legacyRecord={v:1,iv:iv.toString('base64url'),tag:legacyCipher.getAuthTag().toString('base64url'),data:data.toString('base64url')};
assert.throws(()=>openJoinInstructions(legacyRecord,secret),/Legacy/);
assert.equal(openJoinInstructions(legacyRecord,secret,oldKey),plaintext);
assert.throws(()=>openJoinInstructions({...sealed,keyVersion:77},secret),/Unsupported/);
const lobby={ownerXId:'123', status:'open', winners:[]};
assert.equal(joinDetailsRole(lobby,'123'),'host');
assert.equal(joinDetailsRole(lobby,'456'),null);
lobby.status='ready';lobby.winners=['456','789'];
assert.equal(joinDetailsRole(lobby,'456'),'selected');
assert.equal(joinDetailsRole(lobby,'111'),null);
console.log('Host metadata and encrypted join instructions tests passed');
