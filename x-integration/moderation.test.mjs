import { strict as assert } from 'node:assert';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createLobbyApi } from './lobby-api.mjs';

const dir=await fs.mkdtemp(path.join(os.tmpdir(),'gn-moderation-test-'));
const origin='https://example.test';
const auth={authenticated:req=>req.headers['x-test-user']
  ? {id:req.headers['x-test-user'],username:'owner'} : null};
const mentions={pending:[{post_id:'99123',author_id:'1001',status:'awaiting_review',
  created_at:'2026-11-06T00:00:00Z',request_type:'game',
  excerpt:'@jordan__chev start a game'}]};
const api=await createLobbyApi({dataDir:dir,auth,mentions,moderatorXId:'700',
  publicOrigin:origin,now:()=>1700000000000});
const server=http.createServer(async(req,res)=>{
  const handled=await api.handle(req,res,new URL(req.url,'http://localhost'));
  if(!handled){res.writeHead(404);res.end()}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base='http://127.0.0.1:'+server.address().port;
async function request(endpoint,method='GET',payload=null,headers={}){
  const opts={method,headers:{origin,'content-type':'application/json',...headers}};
  if(payload!==null)opts.body=JSON.stringify(payload);
  const res=await fetch(base+endpoint,opts);
  return {status:res.status,data:await res.json()};
}
try{
  assert.equal((await request('/api/moderation/mentions')).status,403);
  assert.equal((await request('/api/moderation/mentions','GET',null,{'x-test-user':'701'})).status,403);
  const before=await request('/api/moderation/mentions','GET',null,{'x-test-user':'700'});
  assert.equal(before.status,200);
  assert.equal(before.data.requests.length,1);
  assert.equal(before.data.requests[0].invitation_active,false);
  assert.equal((await request('/api/moderation/approve','POST',{post_id:'99123'})).status,403);
  assert.equal((await request('/api/moderation/approve','POST',{post_id:'99123'},{'x-test-user':'701'})).status,403);
  assert.equal((await request('/api/moderation/approve','POST',{post_id:'99123'},
    {'x-test-user':'700',origin:'https://evil.example'})).status,403);
  const owner=await request('/api/moderation/approve','POST',{post_id:'99123'},{'x-test-user':'700'});
  assert.equal(owner.status,201);
  assert.match(owner.data.setupUrl,/^https:\/\/example\.test\/setup\?invite=[A-Za-z0-9_-]{43}$/);
  const token=new URL(owner.data.setupUrl).searchParams.get('invite');
  const after=await request('/api/moderation/mentions','GET',null,{'x-test-user':'700'});
  assert.equal(after.data.requests[0].invitation_active,true);
  assert.equal(after.data.requests[0].game_created,false);
  const noAuth=await request('/api/lobbies','POST',{inviteToken:token});
  assert.equal(noAuth.status,401);
  const mismatch=await request('/api/lobbies','POST',{inviteToken:token},
    {'x-test-user':'701'});assert.equal(mismatch.status,403);
  const good=await request('/api/lobbies','POST',{
    inviteToken:token,game:'fortnite',platform:'pc',title:'Community match',
    mode:'first',seats:2,roundSeconds:60
  },{'x-test-user':'1001'});
  assert.equal(good.status,201);
  const final=await request('/api/moderation/mentions','GET',null,{'x-test-user':'700'});
  assert.equal(final.data.requests[0].game_created,true);
  assert.equal(final.data.requests[0].invitation_active,false);
  const publicList=await request('/api/lobbies');
  assert.equal(publicList.status,200);
  assert.ok(!JSON.stringify(publicList.data).includes(token));
  assert.ok(!JSON.stringify(publicList.data).includes('1001'));
  const html=await fs.readFile(new URL('./moderation.html',import.meta.url),'utf8');
  assert.ok(html.includes('/api/moderation/mentions'));
  assert.ok(html.includes('/api/moderation/approve'));
  assert.ok(html.includes('X_MODERATOR_USER_ID'));
  assert.ok(html.includes('navigator.clipboard.writeText'));
  assert.ok(html.includes('textContent'));
  assert.ok(!html.includes('X_ADMIN_TOKEN'));
  console.log('X moderation console checks passed: owner-only, origin, private invite, replay and live lobby');
} finally {
  server.close();
  await fs.rm(dir,{recursive:true,force:true});
}
