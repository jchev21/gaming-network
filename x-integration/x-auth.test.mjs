import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {createXAuth,createPKCE,authorizeUrl} from './x-auth.mjs';
const pkce=createPKCE();assert.equal(pkce.challenge.length,43);
const url=authorizeUrl({clientId:'client',redirectUri:'https://example.com/auth/x/callback',state:'s',challenge:pkce.challenge});
assert.equal(new URL(url).searchParams.get('scope'),'tweet.read users.read');
const dir=await fs.mkdtemp(path.join(os.tmpdir(),'gn-x-test-'));
let requests=0;
const fetchImpl=async(u,o)=>{requests++;if(u.includes('/token'))return{ok:true,json:async()=>({access_token:'test-access'})};if(u.includes('/me'))return{ok:true,json:async()=>({data:{id:'900001',username:'sample'}})};throw Error('unknown endpoint')};
const auth=await createXAuth({clientId:'client',redirectUri:'https://example.com/auth/x/callback',dataDir:dir,fetchImpl,now:()=>100000});
const server=http.createServer(async(req,res)=>{if(!(await auth.handle(req,res,new URL(req.url,'http://localhost')))){res.writeHead(404);res.end()}});
await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
const base='http://127.0.0.1:'+server.address().port;
try{
 const start=await fetch(base+'/auth/x/start',{redirect:'manual'});
 assert.equal(start.status,302);
 const csrf=start.headers.get('set-cookie').split(';')[0];
 const state=new URL(start.headers.get('location')).searchParams.get('state');
 const bad=await fetch(base+'/auth/x/callback?state=bad&code=c',{headers:{cookie:csrf},redirect:'manual'});assert.equal(bad.status,400);
 const cb=await fetch(base+'/auth/x/callback?state='+encodeURIComponent(state)+'&code=c',{headers:{cookie:csrf},redirect:'manual'});
 assert.equal(cb.status,302);
 const sid=cb.headers.get('set-cookie').split('gn_x_session=')[1].split(';')[0];
 const me=await fetch(base+'/api/me',{headers:{cookie:'gn_x_session='+sid}});assert.equal((await me.json()).user.id,'900001');
 const replay=await fetch(base+'/auth/x/callback?state='+encodeURIComponent(state)+'&code=c',{headers:{cookie:csrf},redirect:'manual'});assert.equal(replay.status,400);
 assert.equal(requests,2);
 await fetch(base+'/auth/logout',{method:'POST',headers:{cookie:'gn_x_session='+sid}});
 const gone=await fetch(base+'/api/me',{headers:{cookie:'gn_x_session='+sid}});
 assert.equal((await gone.json()).authenticated,false);
 let blocked=0;
 for(let i=0;i<2003;i++){const r=await fetch(base+'/auth/x/start',{redirect:'manual'});if(r.status===429)blocked++}
 assert.ok(blocked>=1,'OAuth flow table must be capped');
 console.log('X OAuth tests passed');
}finally{server.close();await fs.rm(dir,{recursive:true,force:true})}