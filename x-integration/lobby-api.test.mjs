import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {createLobbyApi} from './lobby-api.mjs';
const dir=await fs.mkdtemp(path.join(os.tmpdir(),'gn-lobbies-test-'));
const origin='https://example.test';
const auth={authenticated:req=>req.headers['x-test-user']?{id:req.headers['x-test-user'],username:req.headers['x-test-user']}:null};
const mentions={pending:[{post_id:'11111111',author_id:'10001',excerpt:'@jordan__chev start a game'}]};
let time=100000;
const api=await createLobbyApi({dataDir:dir,auth,mentions,adminToken:'secret',publicOrigin:origin,now:()=>time});
const server=http.createServer(async(req,res)=>{if(!(await api.handle(req,res,new URL(req.url,'http://localhost')))){res.writeHead(404);res.end()}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base='http://127.0.0.1:'+server.address().port;
async function req(route,method='GET',body,headers={}){const response=await fetch(base+route,{method,headers:{origin,'content-type':'application/json',...headers},body:body?JSON.stringify(body):undefined});return{code:response.status,body:await response.json()}}
try{
 const noadmin=await req('/admin/invites','POST',{post_id:'11111111'});assert.equal(noadmin.code,401);
 const approval=await req('/admin/invites','POST',{post_id:'11111111'},{authorization:'Bearer secret'});
 assert.equal(approval.code,201);
 const token=new URL(approval.body.setupUrl).searchParams.get('invite');assert.equal(token.length,43);
 const config={inviteToken:token,game:'arcade-runner',platform:'web',mode:'first',seats:2,roundSeconds:30,title:'X Challenge'};
 const missing=await req('/api/lobbies','POST',config);assert.equal(missing.code,401);
 const wrong=await req('/api/lobbies','POST',config,{'x-test-user':'10002'});assert.equal(wrong.code,403);
 const valid=await req('/api/lobbies','POST',config,{'x-test-user':'10001'});assert.equal(valid.code,201);
 const gameId=valid.body.game.id;assert.ok(gameId);
 const again=await req('/api/lobbies','POST',config,{'x-test-user':'10001'});assert.equal(again.code,403);
 const join1=await req('/api/lobbies/'+gameId+'/join','POST',{}, {'x-test-user':'10002'});assert.equal(join1.code,200);
 const duplicate=await req('/api/lobbies/'+gameId+'/join','POST',{}, {'x-test-user':'10002'});assert.equal(duplicate.code,409);
 const join2=await req('/api/lobbies/'+gameId+'/join','POST',{}, {'x-test-user':'10003'});assert.equal(join2.code,200);assert.equal(join2.body.game.status,'ready');
 const after=await req('/api/lobbies/'+gameId);assert.equal(after.body.game.confirmedCount,2);
 assert.ok(!JSON.stringify(after.body).includes('ownerXId'));
 const persisted=JSON.parse(await fs.readFile(path.join(dir,'x-lobbies.json'),'utf8'));assert.equal(Object.keys(persisted.lobbies).length,1);
 console.log('Lobby API tests passed');
}finally{server.close();await fs.rm(dir,{recursive:true,force:true})}