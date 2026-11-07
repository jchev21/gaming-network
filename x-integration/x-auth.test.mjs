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
 // User-supplied cookies may contain invalid URL escapes or invalid UTF-8.
 // They must not crash the server, invalidate another user's pending flow,
 // or create an authenticated session.
 for(const malformed of ['%ZZ','%E0%A4%A']){
  assert.equal(auth.authenticated({headers:{cookie:'gn_x_session='+malformed}}),null);
  const invalidSession=await fetch(base+'/api/me',{headers:{cookie:'gn_x_session='+malformed}});
  assert.equal(invalidSession.status,200);
  assert.equal((await invalidSession.json()).authenticated,false);
  const invalidState=await fetch(base+'/auth/x/callback?state='+encodeURIComponent(state)+'&code=c',{
   headers:{cookie:'gn_x_oauth_state='+malformed},redirect:'manual'
  });
  assert.equal(invalidState.status,400);
 }
 const cb=await fetch(base+'/auth/x/callback?state='+encodeURIComponent(state)+'&code=c',{headers:{cookie:csrf},redirect:'manual'});
 assert.equal(cb.status,302);
 const sid=cb.headers.get('set-cookie').split('gn_x_session=')[1].split(';')[0];
 const me=await fetch(base+'/api/me',{headers:{cookie:'gn_x_session='+sid}});assert.equal((await me.json()).user.id,'900001');
 const replay=await fetch(base+'/auth/x/callback?state='+encodeURIComponent(state)+'&code=c',{headers:{cookie:csrf},redirect:'manual'});assert.equal(replay.status,400);
 // The owner console return path must survive a verified X OAuth callback.
 const modStart=await fetch(base+'/auth/x/start?next=%2Fmoderation',{redirect:'manual'});
 assert.equal(modStart.status,302);
 const modCookie=modStart.headers.get('set-cookie').split(';')[0];
 const modState=new URL(modStart.headers.get('location')).searchParams.get('state');
 const modCallback=await fetch(base+'/auth/x/callback?state='+encodeURIComponent(modState)+'&code=c',{
   headers:{cookie:modCookie},redirect:'manual'
 });
 assert.equal(modCallback.status,302);
 assert.equal(modCallback.headers.get('location'),'/moderation');
 // Mobile web onboarding uses a same-origin, allowlisted X → Discord redirect.
 const linkStart=await fetch(base+'/auth/x/start?next=%2Fauth%2Fdiscord%2Fstart',{redirect:'manual'});
 assert.equal(linkStart.status,302);
 const linkCookie=linkStart.headers.get('set-cookie').split(';')[0];
 const linkState=new URL(linkStart.headers.get('location')).searchParams.get('state');
 const linkCallback=await fetch(base+'/auth/x/callback?state='+encodeURIComponent(linkState)+'&code=c',{
   headers:{cookie:linkCookie},redirect:'manual'
 });
 assert.equal(linkCallback.status,302);
 assert.equal(linkCallback.headers.get('location'),'/auth/discord/start');
 // External redirects and nearby path prefixes must NOT be accepted.
 const rejectedStart=await fetch(base+'/auth/x/start?next='+encodeURIComponent('/auth/discord/start-evil'),{redirect:'manual'});
 const rejectedCookie=rejectedStart.headers.get('set-cookie').split(';')[0];
 const rejectedState=new URL(rejectedStart.headers.get('location')).searchParams.get('state');
 const rejectedCallback=await fetch(base+'/auth/x/callback?state='+encodeURIComponent(rejectedState)+'&code=c',{
   headers:{cookie:rejectedCookie},redirect:'manual'
 });
 assert.equal(rejectedCallback.headers.get('location'),'/setup');
 assert.equal(requests,8);
 await fetch(base+'/auth/logout',{method:'POST',headers:{cookie:'gn_x_session='+sid}});
 const gone=await fetch(base+'/api/me',{headers:{cookie:'gn_x_session='+sid}});
 assert.equal((await gone.json()).authenticated,false);
 let blocked=0;
 for(let i=0;i<2003;i++){const r=await fetch(base+'/auth/x/start',{redirect:'manual'});if(r.status===429)blocked++}
 assert.ok(blocked>=1,'OAuth flow table must be capped');
 console.log('X OAuth tests passed');
}finally{server.close();await fs.rm(dir,{recursive:true,force:true})}