/** Read-only X OAuth PKCE authentication: no X write scopes or stored access tokens. */
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
const sha = s => crypto.createHash('sha256').update(String(s)).digest('hex');
const rnd = () => crypto.randomBytes(32).toString('base64url');
const cookie = (req,k) => {
 const part=String(req.headers.cookie||'').split(';').map(s=>s.trim()).find(s=>s.startsWith(k+'='));
 return part ? decodeURIComponent(part.slice(k.length+1)) : null;
};
const send=(res,status,obj,headers={})=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store',...headers});res.end(JSON.stringify(obj))};
const setCookie=(key,val,age)=>key+'='+encodeURIComponent(val)+'; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age='+age;
const safeReturn=next=>{
 const s=String(next||'/setup');
 return /^\/(setup|high-scores|lobby)(?:\?|\/|$)/.test(s)&&!s.startsWith('//')&&!s.includes('\\')?s.slice(0,300):'/setup';
};
export function createPKCE(){
 const verifier=rnd();
 return {verifier,challenge:crypto.createHash('sha256').update(verifier).digest('base64url')};
}
export function authorizeUrl({clientId,redirectUri,state,challenge,base='https://x.com/i/oauth2/authorize'}){
 const url=new URL(base);
 for(const [k,v] of Object.entries({response_type:'code',client_id:clientId,redirect_uri:redirectUri,scope:'tweet.read users.read',state,code_challenge:challenge,code_challenge_method:'S256'}))url.searchParams.set(k,v);
 return url.toString();
}
async function readDb(file){
 try{const d=JSON.parse(await fs.readFile(file,'utf8'));return {flows:d.flows||{},sessions:d.sessions||{}}}
 catch(e){if(e.code!=='ENOENT')throw e;return {flows:{},sessions:{}}}
}
async function persist(file,data){
 await fs.mkdir(path.dirname(file),{recursive:true});
 await fs.writeFile(file+'.tmp',JSON.stringify(data),{mode:0o600});
 await fs.rename(file+'.tmp',file);
}
export async function createXAuth({clientId=process.env.X_CLIENT_ID||'',clientSecret=process.env.X_CLIENT_SECRET||'',redirectUri=process.env.X_CALLBACK_URL||'',dataDir=process.env.DATA_DIR||'./runtime',fetchImpl=fetch,now=Date.now,authorizationBase='https://x.com/i/oauth2/authorize',tokenUrl='https://api.x.com/2/oauth2/token',meUrl='https://api.x.com/2/users/me'}={}){
 const file=path.join(dataDir,'x-auth-sessions.json'),db=await readDb(file);
 const enabled=Boolean(clientId&&redirectUri&&/^https:\/\//.test(redirectUri));
 const cleanup=()=>{const t=now();for(const [k,v] of Object.entries(db.flows))if(v.expires<=t)delete db.flows[k];for(const[k,v]of Object.entries(db.sessions))if(v.expires<=t)delete db.sessions[k]};
 function authenticated(req){
  const raw=cookie(req,'gn_x_session');if(!raw||raw.length!==43)return null;
  const s=db.sessions[sha(raw)];if(!s||s.expires<=now())return null;
  return {id:s.xId,username:s.username};
 }
 async function handle(req,res,url){
  if(req.method==='GET'&&url.pathname==='/api/me'){
   const user=authenticated(req);send(res,200,{authenticated:!!user,user});return true;
  }
  if(req.method==='POST'&&url.pathname==='/auth/logout'){
   const raw=cookie(req,'gn_x_session');if(raw)delete db.sessions[sha(raw)];
   await persist(file,db);send(res,200,{ok:true},{'set-cookie':setCookie('gn_x_session','',0)});return true;
  }
  if(req.method==='GET'&&url.pathname==='/auth/x/start'){
   if(!enabled){send(res,503,{error:'X sign-in not configured'});return true;}
   cleanup();if(Object.keys(db.flows).length>=2000){send(res,429,{error:'Too many sign-in attempts; retry shortly'},{'retry-after':'60'});return true;}
   const {verifier,challenge}=createPKCE(),state=rnd();
   db.flows[sha(state)]={verifier,expires:now()+600000,next:safeReturn(url.searchParams.get('next'))};
   await persist(file,db);
   res.writeHead(302,{location:authorizeUrl({clientId,redirectUri,state,challenge,base:authorizationBase}),'cache-control':'no-store','set-cookie':setCookie('gn_x_oauth_state',state,600)});res.end();
   return true;
  }
  if(req.method==='GET'&&url.pathname==='/auth/x/callback'){
   if(!enabled){send(res,503,{error:'X sign-in not configured'});return true;}
   const state=url.searchParams.get('state'),code=url.searchParams.get('code'),csrf=cookie(req,'gn_x_oauth_state');
   if(!state||!csrf||state!==csrf||!code){send(res,400,{error:'Invalid OAuth state'});return true;}
   const key=sha(state),flow=db.flows[key];
   if(!flow||flow.expires<=now()){send(res,400,{error:'Expired OAuth state'});return true;}
   delete db.flows[key];await persist(file,db);
   const body=new URLSearchParams({grant_type:'authorization_code',code,redirect_uri:redirectUri,client_id:clientId,code_verifier:flow.verifier});
   const headers={'content-type':'application/x-www-form-urlencoded'};
   if(clientSecret)headers.authorization='Basic '+Buffer.from(clientId+':'+clientSecret).toString('base64');
   try{
    const tok=await fetchImpl(tokenUrl,{method:'POST',headers,body,signal:AbortSignal.timeout(15000)});
    if(!tok.ok){send(res,502,{error:'X token exchange failed',status:tok.status});return true;}
    const token=await tok.json();if(!token.access_token){send(res,502,{error:'Missing X access token'});return true;}
    const me=await fetchImpl(meUrl,{headers:{authorization:'Bearer '+token.access_token},signal:AbortSignal.timeout(15000)});
    if(!me.ok){send(res,502,{error:'X identity request failed',status:me.status});return true;}
    const info=(await me.json()).data||{};
    if(!/^\d{1,24}$/.test(String(info.id||''))||!info.username){send(res,502,{error:'Unverified X identity'});return true;}
    cleanup();const raw=rnd();db.sessions[sha(raw)]={xId:String(info.id),username:String(info.username).slice(0,40),expires:now()+86400000};
    await persist(file,db);
    res.writeHead(302,{location:flow.next,'cache-control':'no-store','set-cookie':[setCookie('gn_x_session',raw,86400),setCookie('gn_x_oauth_state','',0)]});res.end();return true;
   }catch(e){send(res,502,{error:'X sign-in temporarily unavailable'});return true;}
  }
  return false;
 }
 return {handle,authenticated,enabled};
}