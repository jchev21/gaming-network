import { strict as assert } from 'node:assert';
import { classifyMention, newestId, adminOk, requiredPublicOrigin } from './listener.mjs';
const mine = '10000', handle = '_xyzhub_';
function post(id, text, author_id='20000', mentions=[]) {
  return { id, text, author_id, entities: { mentions } };
}
assert.equal(classifyMention(post('123', 'Hi @_xyzhub_ can we play poker?', '20000', [{username:handle}]), handle, mine).request_type, 'poker');
assert.equal(classifyMention(post('124', 'Hello there'), handle, mine), null);
assert.equal(classifyMention(post('125', 'RT @_xyzhub_ start a game'), handle, mine), null);
assert.equal(classifyMention(post('126', '@_xyzhub_ start a game', mine), handle, mine), null);
assert.equal(classifyMention(post('127', '@_xyzhub_ please help me'), handle, mine), null);
assert.equal(classifyMention(post('128', '@different start a game'), handle, mine), null);
assert.equal(classifyMention(post('129', '@_xyzhub_ code drop', '20000'), handle, mine).request_type, 'code-drop');
assert.equal(newestId(['7','15','900','12']), '900');
assert.equal(adminOk('Bearer secret-admin-token','secret-admin-token'),true);
assert.equal(adminOk('Bearer wrong','secret-admin-token'),false);
assert.equal(adminOk(null,'secret-admin-token'),false);
assert.equal(adminOk('Bearer secret-admin-token',''),false);
assert.equal(requiredPublicOrigin({X_PUBLIC_ORIGIN:'https://x-game-intake-production.up.railway.app'}),'https://x-game-intake-production.up.railway.app');
assert.throws(()=>requiredPublicOrigin({}),/X_PUBLIC_ORIGIN/);
assert.throws(()=>requiredPublicOrigin({X_PUBLIC_ORIGIN:'http://example.com'}),/X_PUBLIC_ORIGIN/);
assert.throws(()=>requiredPublicOrigin({X_PUBLIC_ORIGIN:'https://example.com/evil'}),/X_PUBLIC_ORIGIN/);
assert.throws(()=>requiredPublicOrigin({X_PUBLIC_ORIGIN:'https://user:pass@example.com'}),/X_PUBLIC_ORIGIN/);
console.log('X intake classifier tests passed');
