import assert from 'node:assert/strict';
import {createDiscordMemberAuth,validateMemberConfig} from './discord-member-auth.mjs';

const guildId='1566290427366080612',roleId='1566290427366080613';
const xId='1111111111111111111',discordId='2222222222222222222';
const clientId='3333333333333333333';
let now=1000, memberRoles=[roleId], pending=false, exchangeCount=0, requests=[];
const xCookie='gn_x_session='+'x'.repeat(43);
const xAuth={authenticated:req=>String(req.headers.cookie||'').includes(xCookie)?{id:xId,username:'host'}:null};
const fetchImpl=async(url,opts={})=>{
 requests.push({url,method:opts.method||'GET'});
 const route=new URL(url).pathname;
 if(route==='/api/v10/oauth2/token'){exchangeCount++;return {ok:true,json:async()=>({access_token:'confidential-discord-access-token',expires_in:3600})};}
 if(route==='/api/v10/users/@me')return{ok:true,json:async()=>({id:discordId})};
 if(route==='/api/v10/users/@me/guilds/'+guildId+'/member')
  return{ok:true,json:async()=>({user:{id:discordId},roles:memberRoles,pending})};
 throw Error('Unexpected URL '+url);
};
function response(){
 const r={status:0,headers:null,body:'',writeHead(code,headers){this.status=code;this.headers=headers;},end(text=''){this.body=String(text)}};
 return r;
}
const req=(cookies='')=>({method:'GET',headers:{cookie:cookies}});
function cookieValue(setCookie,name){
 const all=Array.isArray(setCookie)?setCookie:[setCookie];
 const line=all.find(c=>c.startsWith(name+'='));
 return line?.split(';')[0]||'';
}
assert.throws(()=>validateMemberConfig({clientId,clientSecret:'x',redirectUri:'https://example.test/auth/discord/callback',guildId,roleId:'Member'}),/incomplete/);
const auth=createDiscordMemberAuth({
 clientId,clientSecret:'test-secret',redirectUri:'https://example.test/auth/discord/callback',
 guildId,roleId,xAuth,fetchImpl,now:()=>now,discordBase:'https://discord.test',
});
const missingStart=response();
assert.equal(await auth.handle(req(),missingStart,new URL('https://example.test/auth/discord/start')),true);
assert.equal(missingStart.status,401);
let startRes=response();
await auth.handle(req(xCookie),startRes,new URL('https://example.test/auth/discord/start'));
assert.equal(startRes.status,302);
const redirect=new URL(startRes.headers.location);
assert.equal(redirect.searchParams.get('scope'),'identify guilds.members.read');
const state=redirect.searchParams.get('state');
const stateCookie=cookieValue(startRes.headers['set-cookie'],'gn_discord_oauth_state');
assert.equal(stateCookie.split('=')[1],state);
const callbackCookie=xCookie+'; '+stateCookie;
let callback=response();
await auth.handle(req(callbackCookie),callback,new URL('https://example.test/auth/discord/callback?state='+state+'&code=test'));
assert.equal(callback.status,302);
assert.equal(exchangeCount,1);
assert.equal(callback.headers.location,'/setup?member=connected');
const memberCookie=cookieValue(callback.headers['set-cookie'],'gn_discord_member');
assert.ok(memberCookie);
const memberReq=req(xCookie+'; '+memberCookie);
assert.equal((await auth.requireMember(memberReq)).discordUserId,discordId);
const status=response();
await auth.handle(memberReq,status,new URL('https://example.test/api/discord-member'));
assert.equal(JSON.parse(status.body).authorized,true);
assert.equal(JSON.stringify(status.body).includes('confidential-discord-access-token'),false);
const replay=response();
await auth.handle(req(callbackCookie),replay,new URL('https://example.test/auth/discord/callback?state='+state+'&code=test'));
assert.equal(replay.status,400);
assert.equal(exchangeCount,1);
let denied=false;
try{await auth.requireMember(req('gn_x_session='+'y'.repeat(43)+'; '+memberCookie))}catch(e){denied=e.code==='X_SIGN_IN_REQUIRED'||e.code==='DISCORD_MEMBER_SIGN_IN_REQUIRED'}
assert.ok(denied,'cross-X-cookie replay denied');
memberRoles=[];
await assert.rejects(()=>auth.requireMember(memberReq),{code:'DISCORD_MEMBER_ROLE_REQUIRED'});
memberRoles=[roleId];
await assert.rejects(()=>auth.requireMember(memberReq),{code:'DISCORD_MEMBER_SIGN_IN_REQUIRED'});
const statusAfter=response();
await auth.handle(memberReq,statusAfter,new URL('https://example.test/api/discord-member'));
assert.equal(JSON.parse(statusAfter.body).authorized,false);
const secondStart=response();
await auth.handle(req(xCookie),secondStart,new URL('https://example.test/auth/discord/start'));
const secondState=new URL(secondStart.headers.location).searchParams.get('state');
pending=true;
const secondCb=response();
await auth.handle(req(xCookie+'; '+cookieValue(secondStart.headers['set-cookie'],'gn_discord_oauth_state')),secondCb,
 new URL('https://example.test/auth/discord/callback?state='+secondState+'&code=again'));
assert.equal(secondCb.status,403,'rules screening pending must deny');
assert.equal(JSON.parse(secondCb.body).error,'DISCORD_RULES_NOT_ACCEPTED');
assert.ok(requests.some(x=>x.url.endsWith('/users/@me/guilds/'+guildId+'/member')));
console.log('Discord Member OAuth role-gate tests passed');
