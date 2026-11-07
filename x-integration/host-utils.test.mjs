import assert from 'node:assert/strict';
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
assert.equal(openJoinInstructions(sealed,secret),plaintext);
assert.ok(!JSON.stringify(sealed).includes('secret123'));
assert.notEqual(sealJoinInstructions(plaintext,secret).data,sealed.data);
assert.throws(() => openJoinInstructions(sealed,'wrong-encryption-secret'), /auth|authenticate|Unsupported/i);
const altered=Buffer.from(sealed.data,'base64url');altered[0]^=0x01;
const tampered={...sealed, data:altered.toString('base64url')};
assert.throws(() => openJoinInstructions(tampered,secret), /auth|authenticate/i);

const lobby={ownerXId:'123', status:'open', winners:[]};
assert.equal(joinDetailsRole(lobby,'123'),'host');
assert.equal(joinDetailsRole(lobby,'456'),null);
lobby.status='ready';lobby.winners=['456','789'];
assert.equal(joinDetailsRole(lobby,'456'),'selected');
assert.equal(joinDetailsRole(lobby,'111'),null);
console.log('Host metadata and encrypted join instructions tests passed');
