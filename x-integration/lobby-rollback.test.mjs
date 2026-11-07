/** Regression: failed persistence must not later resurrect an unauthorized or rejected join. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {createLobby} from './game-core.mjs';
import {createLobbyApi} from './lobby-api.mjs';

const dir=await fs.mkdtemp(path.join(os.tmpdir(),'gn-lobby-rollback-'));
const store=path.join(dir,'x-lobbies.json');
const lobby=createLobby({
  game:'fortnite',platform:'pc',mode:'first',seats:2,
  roundSeconds:30,title:'Persistence rollback smoke'
},'10001',1000);
await fs.writeFile(store,JSON.stringify({
  invites:{},lobbies:{[lobby.id]:lobby},joinSecrets:{}
}));
let writes=0;
const saveState=async (file,data)=>{
  writes++;
  if(writes===1)throw new Error('injected private storage failure');
  await fs.writeFile(file+'.tmp',JSON.stringify(data),{mode:0o600});
  await fs.rename(file+'.tmp',file);
};
const auth={authenticated(req){
  const id=req.headers['x-test-user'];
  return id ? {id,username:'player'+id} : null;
}};
const api=await createLobbyApi({
  dataDir:dir,auth,mentions:{pending:[]},publicOrigin:'https://example.test',
  joinSecretKey:'test-secret-32-chars-safe',now:()=>1002,saveState
});
const server=http.createServer(async (req,res)=>{
  if(!(await api.handle(req,res,new URL(req.url,'http://localhost')))){
    res.writeHead(404);res.end();
  }
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base='http://127.0.0.1:'+server.address().port;
async function request(route,method='GET',user){
  const headers={origin:'https://example.test'};
  if(user)headers['x-test-user']=user;
  const response=await fetch(base+route,{method,headers});
  return {status:response.status,body:await response.json()};
}
try{
  const route='/api/lobbies/'+lobby.id+'/join';
  const failed=await request(route,'POST','10002');
  assert.equal(failed.status,500);
  assert.equal(failed.body.error,'FAILED');
  assert.ok(!JSON.stringify(failed.body).includes('injected private storage failure'));
  assert.equal(writes,1);
  const afterFailure=await request('/api/lobbies/'+lobby.id);
  assert.equal(afterFailure.status,200);
  assert.equal(afterFailure.body.game.entryCount,0,
    'Failed join must not linger in memory');
  let saved=JSON.parse(await fs.readFile(store,'utf8'));
  assert.equal(saved.lobbies[lobby.id].entries.length,0,
    'Failed join must not change durable state');
  const retry=await request(route,'POST','10002');
  assert.equal(retry.status,200,
    'The same player should be allowed to retry a failed join');
  assert.equal(retry.body.game.entryCount,1);
  const next=await request(route,'POST','10003');
  assert.equal(next.status,200);
  assert.equal(next.body.game.status,'ready');
  saved=JSON.parse(await fs.readFile(store,'utf8'));
  assert.deepEqual(saved.lobbies[lobby.id].entries.map(x=>x.xId),['10002','10003']);
  assert.equal(saved.lobbies[lobby.id].status,'ready');
  const publicFeed=await request('/api/lobbies');
  assert.equal(publicFeed.status,200);
  assert.equal(publicFeed.body.games[0].confirmedCount,2);
  assert.ok(!JSON.stringify(publicFeed.body).includes('10002'));
  console.log('Lobby persistence rollback regression passed (mock disk, no production I/O)');
}finally{
  server.close();
  await fs.rm(dir,{recursive:true,force:true});
}
