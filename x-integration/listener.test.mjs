import { strict as assert } from 'node:assert';
import { classifyMention, newestId, adminOk } from './listener.mjs';
const mine = '10000', handle = 'jordan__chev';
function post(id, text, author_id='20000', mentions=[]) {
  return { id, text, author_id, entities: { mentions } };
}
assert.equal(classifyMention(post('123', 'Hi @jordan__chev can we play poker?', '20000', [{username:handle}]), handle, mine).request_type, 'poker');
assert.equal(classifyMention(post('124', 'Hello there'), handle, mine), null);
assert.equal(classifyMention(post('125', 'RT @jordan__chev start a game'), handle, mine), null);
assert.equal(classifyMention(post('126', '@jordan__chev start a game', mine), handle, mine), null);
assert.equal(classifyMention(post('127', '@jordan__chev please help me'), handle, mine), null);
assert.equal(classifyMention(post('128', '@different start a game'), handle, mine), null);
assert.equal(classifyMention(post('129', '@jordan__chev code drop', '20000'), handle, mine).request_type, 'code-drop');
assert.equal(newestId(['7','15','900','12']), '900');
console.log('X intake classifier tests passed');

assert.equal(adminOk('Bearer s3cret','s3cret'),true);
assert.equal(adminOk('Bearer wrong','s3cret'),false);
assert.equal(adminOk(undefined,'s3cret'),false);
assert.equal(adminOk('Bearer ','' ),false);
console.log('Admin token comparison tests passed');
