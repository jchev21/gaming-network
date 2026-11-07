import { strict as assert } from 'node:assert';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pollX } from './listener.mjs';

const handle = 'jordan__chev';
const makeState = () => ({ since_id: '100', initialized: true, target_user_id: '999',
  target_handle: handle, pending: [], scan: null, budget: null, pause_until: null,
  blocked_reason: null, last_checked: null, last_error: null });
const config = (overrides={}) => ({ bearer: 'synthetic-not-a-secret', userId: '999',
  handle, once: true, maxReadsPerDay: 8, maxPagesPerPoll: 2, ...overrides });
const mention = (id) => ({ id: String(id), author_id: '555', text: '@jordan__chev start a game',
  entities: { mentions: [{ username: handle }] } });
const response = (data, next) => new Response(JSON.stringify({ data, meta: next ? { next_token: next } : {} }),
  { status: 200, headers: {'content-type':'application/json'} });
const withTemp = async (fn) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-poll-guard-'));
  const file = path.join(dir,'state.json');
  try { await fn(file); } finally { await fs.rm(dir,{recursive:true,force:true}); }
};
async function capture(mock, fn) {
  const original = globalThis.fetch; globalThis.fetch = mock;
  try { await fn(); } finally { globalThis.fetch = original; }
}
function persisted(file){return fs.readFile(file,'utf8').then(JSON.parse);}

await withTemp(async file => {
  const state=makeState();
  let calls=0;
  await capture(async (url) => {
    calls++;
    const u=new URL(url);
    assert.equal(u.searchParams.get('since_id'),'100');
    if(calls===1){assert.equal(u.searchParams.get('pagination_token'),null);
      return response([mention(220),mention(215),mention(211),mention(210),mention(205)],'NEXT');}
    assert.equal(u.searchParams.get('pagination_token'),'NEXT');
    return response([mention(201),mention(200)],null);
  },async()=>{
    const first=await pollX(config(),state,file);
    assert.equal(first.partial,true);
    assert.equal(first.scanned,5);
    assert.equal(state.since_id,'100','incomplete scan must not advance since_id');
    assert.equal(state.scan.next_token,'NEXT');
    assert.equal(state.pending.length,5);
    const restarted=await persisted(file);
    const finish=await pollX(config(),restarted,file);
    assert.equal(finish.partial,false);
    assert.equal(restarted.since_id,'220','finish must promote first page HIGH-WATER, not last');
    assert.equal(restarted.scan,null);
    assert.equal(restarted.pending.length,7);
    assert.equal(restarted.budget.used,2);
  });
  assert.equal(calls,2);
});

await withTemp(async file => {
  const state=makeState();
  let calls=0;
  await capture(async () => { calls++; return response([mention(121)],'PAGE2'); },async()=>{
    await pollX(config({maxReadsPerDay:1}),state,file);
    assert.equal(state.scan.next_token,'PAGE2');
    await assert.rejects(pollX(config({maxReadsPerDay:1}),state,file),/daily API read-call cap/);
    assert.equal(state.since_id,'100');
    assert.equal((await persisted(file)).budget.used,1);
  });
  assert.equal(calls,1,'hard cap must prevent extra outbound calls');
});

await withTemp(async file => {
  const state=makeState();
  let calls=0;
  await capture(async()=>{calls++;return new Response('{}',{status:402});},async()=>{
    await assert.rejects(pollX(config(),state,file),/HTTP 402/);
    assert.match(state.blocked_reason,/HTTP 402/);
    await assert.rejects(pollX(config(),state,file),/blocked/);
  });
  assert.equal(calls,1);
  assert.equal((await persisted(file)).budget.used,1);
});

await withTemp(async file => {
  const state=makeState();
  let calls=0;
  await capture(async()=>{calls++;return new Response('{}',{status:429,headers:{'retry-after':'120'}});},async()=>{
    await assert.rejects(pollX(config(),state,file),/HTTP 429/);
    assert.ok(Date.parse(state.pause_until)>Date.now());
    const restarted = await persisted(file);
    assert.equal(restarted.pause_until, state.pause_until);
    await assert.rejects(pollX(config(),restarted,file),/paused/);
  });
  assert.equal(calls,1);
});

await withTemp(async file => {
  const state=makeState();
  let calls=0;
  await capture(async()=>{calls++;return new Response('{"data":false}',{status:200});},async()=>{
    await assert.rejects(pollX(config(),state,file),/Invalid X mentions response/);
    assert.equal(state.since_id,'100');
    assert.equal(state.scan?.highest_id,null);
    assert.equal((await persisted(file)).budget.used,1);
  });
  assert.equal(calls,1);
});

await withTemp(async file => {
  const state=makeState();
  state.pending=Array.from({length:300},(_,i)=>({post_id:String(i+1)}));
  let calls=0;
  await capture(async()=>{calls++;return response([],null);},async()=>{
    await assert.rejects(pollX(config(),state,file),/queue full/);
  });
  assert.equal(calls,0);
});

await withTemp(async file => {
  const state=makeState(); state.initialized=false; state.since_id=null;
  let calls=0;
  await capture(async()=>{calls++;return response([mention(450),mention(444)],'MORE');},async()=>{
    const result=await pollX(config(),state,file);
    assert.equal(result.initialized,true);
    assert.equal(result.partial,false,'baseline must not drain historical pages');
    assert.equal(result.added,0);
    assert.equal(state.since_id,'450');
    assert.equal(state.scan,null);
  });
  assert.equal(calls,1);
});

await withTemp(async file => {
  const state=makeState();
  state.scan={base_since_id:'100',next_token:'RESUME',highest_id:'300',scanned:5};
  let calls=0;
  await capture(async (url)=>{calls++;assert.equal(new URL(url).searchParams.get('pagination_token'),'RESUME');
    return response([mention(255)],null);},async()=>{
    await pollX(config(),state,file);
    assert.equal(state.since_id,'300');
    assert.equal(state.scan,null);
  });
  assert.equal(calls,1);
});

await withTemp(async file => {
  const state=makeState();
  state.budget={day:new Date().toISOString().slice(0,10),used:8};
  let calls=0;
  await capture(async()=>{calls++;return response([],null);},async()=>{
    await assert.rejects(pollX(config(),state,file),/daily API read-call cap/);
  });
  assert.equal(calls,0);
});

await withTemp(async file => {
  const state=makeState();
  const observed=[];
  await capture(async (url) => {
    const u=new URL(url);
    observed.push(u.searchParams.get('max_results'));
    return response([mention(302)],null);
  },async()=>{
    const result=await pollX(config({once:false,maxResultsPerPage:5,maxPagesPerPoll:1}),state,file);
    assert.equal(result.partial,false);
    assert.equal(result.added,1);
    assert.equal(result.daily_reads_used,1);
  });
  assert.deepEqual(observed,['5'],'Paid recurring reads must request at most five posts by default');
});
await withTemp(async file => {
  const state=makeState();
  const before=state.since_id;
  let called=0;
  await capture(async (url)=>{
    called++;
    assert.equal(new URL(url).searchParams.get('max_results'),'5');
    return response([mention(201),mention(202),mention(203),mention(204),mention(205),mention(206)],null);
  },async()=>{
    await assert.rejects(
      pollX(config({once:false,maxResultsPerPage:5,maxPagesPerPoll:1}),state,file),
      /oversized mentions page/
    );
  });
  assert.equal(called,1);
  assert.equal(state.since_id,before);
  assert.equal((await persisted(file)).budget.used,1);
});

await withTemp(async file => {
  const state = makeState();
  const settings = config({ maxReadsPerHour: 1 });
  let calls = 0;
  await capture(async () => {
    calls++;
    return response([mention(121)], 'PAGE2');
  }, async () => {
    await pollX(settings, state, file);
    const restarted = await persisted(file);
    assert.equal(restarted.budget.hourUsed, 1);
    await assert.rejects(pollX(settings, restarted, file), /hourly API read-call cap/);
    const saved = await persisted(file);
    assert.equal(saved.budget.used, 1);
    assert.equal(saved.scan.next_token, 'PAGE2');
    assert.equal(saved.since_id, '100');
  });
  assert.equal(calls, 1);
});

console.log('X poll guard tests passed: restart-safe pages, high-water, cost cap, 402, 429, baseline and queue safety');
