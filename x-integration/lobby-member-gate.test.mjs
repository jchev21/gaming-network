import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {createLobbyApi} from './lobby-api.mjs';

const dir=await fs.mkdtemp(path.join(os.tmpdir(),'gn-member-gate-'));
const origin='https://example.test';
const allow=new Set(['10001','10002']);
const auth={authenticated:req=>req.headers['x-test-user']?{id:req.headers['x-test-user'],username:req.headers['x-test-user']}:null};
const memberAuthorized=async(req)=>{
 const id=req.headers['x-test-user'];
 if(!allow.has(id))throw Object.assign(new Error('Role required'),{code:'DISCORD_MEMBER_ROLE_REQUIRED',status:403});
 return {xUserId:id,discordUserId:'2222222222222222222',member:true};
};
const api=await createLobbyApi({
 dataDir:dir,auth,mentions:{pending:[]},publicOrigin:origin,now:()=>100000,
 joinSecretKey:'test-secret-key-with-strong-length',
 memberAuthorized,
});
const server=http.createServer(async(req,res)=>{
 if(!(await api.handle(req,res,new URL(req.url,'http://localhost')))){
  res.writeHead(404);res.end();
 }
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base='http://127.0.0.1:'+server.address().port;
async function req(url,method='GET',body,user){
 const response=await fetch(base+url,{method,
  headers:{origin,'content-type':'application/json',...(user?{'x-test-user':user}:{})},
  body:body?JSON.stringify(body):undefined,
 });
 return {status:response.status,json:await response.json()};
}
try {
 const game={game:'arcade-runner',platform:'web',mode:'first',seats:2,roundSeconds:30,title:'Member-hosted game'};
 assert.equal((await req('/api/lobbies','POST',game)).status,401,'X identity required');
 assert.equal((await req('/api/lobbies','POST',game,'10099')).status,403,'Member role required');
 const created=await req('/api/lobbies','POST',game,'10001');
 assert.equal(created.status,201,'No moderator invitation required for verified Member');
 assert.ok(!created.json.game.sourcePostId);
 const id=created.json.game.id;
 assert.equal((await req('/api/lobbies/'+id,'GET')).status,200,'public read stays public');
 assert.equal((await req('/api/lobbies/'+id+'/join','POST',{},'10099')).status,403);
 assert.equal((await req('/api/lobbies/'+id+'/join','POST',{},'10002')).status,200);
 assert.equal((await req('/api/my-games','GET',undefined,'10099')).status,403);
 assert.equal((await req('/api/my-games','GET',undefined,'10002')).status,200);
 allow.delete('10002');
 assert.equal((await req('/api/lobbies/'+id+'/me','GET',undefined,'10002')).status,403,'role revocation denies viewer');
 assert.equal((await req('/api/lobbies/'+id+'/join-details','GET',undefined,'10002')).status,403,'role revocation denies secrets');
 assert.equal((await req('/api/lobbies/'+id+'/withdraw','POST',{},'10002')).status,403);
 assert.equal((await req('/api/lobbies/'+id,'GET')).status,200);
 const saved=JSON.parse(await fs.readFile(path.join(dir,'x-lobbies.json'),'utf8'));
 assert.equal(Object.keys(saved.lobbies).length,1,'real server-side lobby persisted');
 console.log('Discord Member-gated lobby tests passed');
} finally {
 await new Promise(resolve=>server.close(resolve));
 await fs.rm(dir,{recursive:true,force:true});
}
