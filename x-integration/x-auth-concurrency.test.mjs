/** Concurrent real-world login regression. No network access to X is required. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createXAuth } from './x-auth.mjs';

const dir=await fs.mkdtemp(path.join(os.tmpdir(),'gn-concurrent-oauth-'));
const config={
  dataDir:dir,clientId:'test-app',
  redirectUri:'https://example.test/auth/x/callback',
  fetchImpl:async url=>{
    if(String(url).includes('/token'))return {ok:true,json:async()=>({access_token:'local-test-token'})};
    if(String(url).includes('/users/me'))return {ok:true,json:async()=>({data:{id:'12345678901',username:'localtestuser'}})};
    throw Error('Unexpected external OAuth endpoint');
  },
  now:()=>1_000_000
};
const servers=[];
async function serve(auth){
  const server=http.createServer(async (req,res)=>{
    if(!(await auth.handle(req,res,new URL(req.url,'http://localhost')))){
      res.writeHead(404);res.end();
    }
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  servers.push(server);
  return 'http://127.0.0.1:'+server.address().port;
}

try{
  const first=await serve(await createXAuth(config));
  const count=32;
  const starts=await Promise.all(Array.from({length:count},()=>fetch(first+'/auth/x/start?next=%2Fmy-games',{redirect:'manual'})));
  assert.equal(starts.length,count);
  const callbacks=starts.map(response=>{
    assert.equal(response.status,302,'Concurrent OAuth starts must not overwrite shared temporary state');
    const location=new URL(response.headers.get('location'));
    assert.equal(location.origin,'https://x.com');
    const state=location.searchParams.get('state');
    assert.equal(state.length,43);
    return {state,cookie:response.headers.get('set-cookie').split(';')[0]};
  });
  assert.equal(new Set(callbacks.map(x=>x.state)).size,count);
  // Reload persisted flows to verify durability, not just the in-memory object.
  const second=await serve(await createXAuth(config));
  const authorized=await Promise.all(callbacks.map(({state,cookie})=>fetch(
    second+'/auth/x/callback?state='+encodeURIComponent(state)+'&code=fake-authorization-code',
    {redirect:'manual',headers:{cookie}}
  )));
  const sessions=authorized.map(response=>{
    assert.equal(response.status,302,'Every persisted PKCE flow must complete once');
    assert.equal(response.headers.get('location'),'/my-games',
      'Real signed-in players must return to their My Games view');
    const match=response.headers.get('set-cookie').match(/gn_x_session=([^;]+)/);
    assert.ok(match);
    return match[1];
  });
  assert.equal(new Set(sessions).size,count);
  const third=await serve(await createXAuth(config));
  const verified=await Promise.all(sessions.map(token=>fetch(third+'/api/me',{
    headers:{cookie:'gn_x_session='+token}
  }).then(r=>r.json())));
  assert.ok(verified.every(item=>item.authenticated&&item.user.id==='12345678901'),
    'Concurrent session writes must all survive a restart');

  // Never redirect to third-party domains or internal admin routes from OAuth input.
  for(const next of ['https://evil.example/','//evil.example/','/admin/mentions']){
    const begin=await fetch(first+'/auth/x/start?next='+encodeURIComponent(next),{redirect:'manual'});
    assert.equal(begin.status,302);
    const loc=new URL(begin.headers.get('location'));
    const state=loc.searchParams.get('state');
    const csrf=begin.headers.get('set-cookie').split(';')[0];
    const end=await fetch(first+'/auth/x/callback?state='+encodeURIComponent(state)+'&code=fixture',{
      redirect:'manual',headers:{cookie:csrf}
    });
    assert.equal(end.status,302);
    assert.equal(end.headers.get('location'),'/setup');
  }
  console.log('X concurrent sign-in, session durability, safe return tests passed');
}finally{
  await Promise.all(servers.map(server=>new Promise(resolve=>server.close(resolve))));
  await fs.rm(dir,{recursive:true,force:true});
}
