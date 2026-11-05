/** Persistent invite-to-lobby API; all writes require verified X identity or admin approval. */
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createLobby,joinLobby,publicLobby,LobbyError,cancelLobby,withdrawEntry,joinWaitlist,replaceNoShow} from './game-core.mjs';
import {sealJoinInstructions,openJoinInstructions,joinDetailsRole} from './host-utils.mjs';
import {createRateLimiter} from './rate-limit.mjs';
const sha=s=>crypto.createHash('sha256').update(String(s)).digest('hex');
const send=(res,status,body)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'});res.end(JSON.stringify(body))};
const err=(code,message,status=400)=>new LobbyError(code,message,status);
async function readBody(req){let bytes=0,chunks=[];for await(const c of req){bytes+=c.length;if(bytes>8192)throw err('TOO_LARGE','Request body too large',413);chunks.push(c)}try{return JSON.parse(Buffer.concat(chunks).toString('utf8'))}catch{throw err('INVALID_JSON','Invalid JSON')}}
async function load(file){try{const d=JSON.parse(await fs.readFile(file,'utf8'));return{invites:d.invites||{},lobbies:d.lobbies||{},joinSecrets:d.joinSecrets||{}}}catch(e){if(e.code!=='ENOENT')throw e;return{invites:{},lobbies:{},joinSecrets:{}}}}
async function save(file,db){await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file+'.tmp',JSON.stringify(db),{mode:0o600});await fs.rename(file+'.tmp',file)}
export async function createLobbyApi({dataDir='./runtime',auth,mentions,adminToken='',moderatorXId=process.env.X_MODERATOR_USER_ID||'',publicOrigin,now=Date.now,joinSecretKey=process.env.X_JOIN_SECRET_KEY||adminToken}={}){
 if(!auth||typeof auth.authenticated!=='function')throw Error('X auth required');
 if(!publicOrigin||!/^https:\/\/[^/?#]+$/.test(publicOrigin))throw Error('A secure public origin is required');
 const file=path.join(dataDir,'x-lobbies.json'),db=await load(file);
 let queue=Promise.resolve();
 const limiter=createRateLimiter({now});
 const guard=(key,limit=20)=>limiter.check(key,{limit,windowMs:60_000});
 async function serial(fn,write=true){const task=queue.then(async()=>{let touched=false;const result=await fn(()=>{touched=true});if(write===true||(write==='on-touch'&&touched))await save(file,db);return result});queue=task.catch(()=>{});return task}
 function admin(req){const given=req.headers.authorization||'';if(!adminToken||!given.startsWith('Bearer '))return false;const a=Buffer.from(given.slice(7)),b=Buffer.from(adminToken);return a.length===b.length&&crypto.timingSafeEqual(a,b)}
 function origin(req){if(req.headers.origin!==publicOrigin)throw err('FORBIDDEN_ORIGIN','Same-origin request required',403)}
 function who(req){const user=auth.authenticated(req);if(!user)throw err('AUTH_REQUIRED','Sign in with X first',401);return user}
 function isModerator(req){const u=auth.authenticated(req);return /^\d+$/.test(String(moderatorXId||'')) && u && u.id===String(moderatorXId)}
 async function handle(req,res,url){
  const method=req.method||'GET',pathname=url.pathname;
  // Viewer-scoped list: never expose other players' account IDs or private instructions.
  if(method==='GET'&&pathname==='/api/my-games'){
   try{
    const actor=who(req);
    const result=await serial(()=>{
     const all=Object.values(db.lobbies).filter(g=>g.ownerXId===actor.id ||
      g.entries.some(e=>e.xId===actor.id) || (g.waitlist||[]).some(e=>e.xId===actor.id) || (g.withdrawnXIds||[]).includes(actor.id) || (g.removedXIds||[]).includes(actor.id));
     all.sort((a,b)=>b.createdAt-a.createdAt||b.id.localeCompare(a.id));
     return {games:all.slice(0,50).map(g=>{
      const game=publicLobby(g,now());
      const role=g.ownerXId===actor.id?'host':(g.withdrawnXIds||[]).includes(actor.id)?'withdrawn':(g.removedXIds||[]).includes(actor.id)?'removed':(g.waitlist||[]).some(e=>e.xId===actor.id)?'waitlisted':'player';
      return {...game,viewerRole:role,viewerSelected:game.status==='ready'&&g.winners.includes(actor.id)};
     })};
    });send(res,200,result)
   }catch(e){send(res,e.status||500,{error:e.code||'FAILED',message:e.status?e.message:'Server temporarily unavailable'})}
   return true;
  }
  if(method==='GET'&&pathname==='/api/moderation/mentions'){
   if(!isModerator(req)){send(res,403,{error:'Moderator X sign-in required'});return true}
   const requests=(mentions.pending||[]).slice(0,100).map(p=>({
     post_id:p.post_id,created_at:p.created_at,request_type:p.request_type,
     excerpt:p.excerpt,status:p.status,
     game_created:Object.values(db.lobbies).some(g=>g.sourcePostId===p.post_id)
   }));
   send(res,200,{requests});return true;
  }
  if(method==='POST'&&(pathname==='/admin/invites'||pathname==='/api/moderation/approve')){
   const viaSession=pathname==='/api/moderation/approve';
   if(viaSession&&!isModerator(req)){send(res,403,{error:'Moderator X sign-in required'});return true}
   if(!viaSession&&!admin(req)){send(res,401,{error:'Unauthorized'});return true}
   try{
    if(viaSession)origin(req);
    guard(viaSession?'mod:'+String(auth.authenticated(req)?.id):'admin:invites',12);
    const body=await readBody(req);
    const result=await serial(()=>{
     const post=(mentions.pending||[]).find(p=>p.post_id===String(body.post_id||''));
     if(!post||!/^\d+$/.test(post.author_id))throw err('MENTION_NOT_FOUND','Recognized mention not found',404);
     if(Object.values(db.lobbies).some(g=>g.sourcePostId===post.post_id))throw err('ALREADY_USED','Mention already has a game',409);
     const raw=crypto.randomBytes(32).toString('base64url'),key=sha(raw);
     for(const [k,v]of Object.entries(db.invites))if(v.postId===post.post_id&&!v.usedAt)delete db.invites[k];
     db.invites[key]={postId:post.post_id,ownerXId:post.author_id,createdAt:now(),expiresAt:now()+86400000,usedAt:null};
     return{setupUrl:publicOrigin+'/setup?invite='+encodeURIComponent(raw),expiresAt:db.invites[key].expiresAt};
    });send(res,201,result);
   }catch(e){send(res,e.status||500,{error:e.code||'FAILED',message:e.message})}
   return true;
  }
  if(method==='POST'&&pathname==='/api/lobbies'){
   try{origin(req);const user=who(req);guard('create:'+user.id,10);const body=await readBody(req);
    const result=await serial(()=>{
     const token=String(body.inviteToken||'');
     if(!/^[A-Za-z0-9_-]{43}$/.test(token))throw err('INVITE_REQUIRED','Valid invitation required',403);
     const invite=db.invites[sha(token)];
     if(!invite||invite.usedAt||invite.expiresAt<=now()||invite.ownerXId!==user.id)throw err('INVITE_INVALID','Invite expired or not for this X account',403);
     const recent=Object.values(db.lobbies).filter(g=>g.ownerXId===user.id&&g.createdAt>=now()-86400000).length;
     if(recent>=10)throw err('RATE_LIMIT','Daily game limit reached',429);
     const g=createLobby(body,user.id,now());g.sourcePostId=invite.postId;db.lobbies[g.id]=g;invite.usedAt=now();
     return{game:publicLobby(g,now()),lobbyUrl:publicOrigin+'/lobby?id='+g.id};
    });send(res,201,result)
   }catch(e){send(res,e.status||500,{error:e.code||'FAILED',message:e.message})}return true;
  }
  const manage=pathname.match(/^\/api\/lobbies\/([a-zA-Z0-9-]+)\/(me|cancel|withdraw|waitlist|replace)$/);
  if(manage && ((manage[2]==='me' && method==='GET') || (method==='POST' && manage[2]!=='me'))) {
   try {
    const actor=who(req);
    if(method==='POST'){origin(req);guard('manage:'+manage[2]+':'+actor.id,20);}
    const body=manage[2]==='replace'&&method==='POST'?await readBody(req):null;
    const result=await serial(()=>{
     const game=db.lobbies[manage[1]];
     if(!game)throw err('NOT_FOUND','Game not found',404);
     publicLobby(game,now());
     if(manage[2]==='waitlist') {
      joinWaitlist(game,actor.id,'@'+actor.username,now());
      return {game:publicLobby(game,now())};
     }
     if(manage[2]==='replace') {
      replaceNoShow(game,actor.id,body?.seat,now());
      return {game:publicLobby(game,now())};
     }
     if(manage[2]==='cancel') {
      cancelLobby(game,actor.id,now());
      delete db.joinSecrets[game.id]; // revoke private instructions for former selected players
      return {game:publicLobby(game,now())};
     }
     if(manage[2]==='withdraw') {
      withdrawEntry(game,actor.id,now());
      return {game:publicLobby(game,now())};
     }
     const joined=game.entries.some(p=>p.xId===actor.id);
     const queuePosition=(game.waitlist||[]).findIndex(p=>p.xId===actor.id);
     const isHost=game.ownerXId===actor.id;
     const withdrawn=(game.withdrawnXIds||[]).includes(actor.id);
     const removed=(game.removedXIds||[]).includes(actor.id);
     return {isHost,joined,selected:game.status==='ready'&&game.winners.includes(actor.id),
      waitlistPosition:queuePosition<0?null:queuePosition+1,withdrawn,removed,
      canCancel:isHost&&game.status!=='cancelled',
      canReplace:isHost&&game.mode==='first'&&game.status==='ready',
      canWaitlist:!isHost&&game.mode==='first'&&game.status==='ready'&&!joined&&queuePosition<0&&!withdrawn&&!removed&&(game.waitlist||[]).length<100,
      canWithdraw:(joined&&game.status==='open')||queuePosition>=0};
    });
    send(res,200,result);
   }catch(e){send(res,e.status||500,{error:e.code||'FAILED',message:e.status?e.message:'Server temporarily unavailable'})}
   return true;
  }
  // Only hosts can write; hosts and selected players may read after the selection.
  const privateMatch=pathname.match(/^\/api\/lobbies\/([a-zA-Z0-9-]+)\/join-details$/);
  if(privateMatch&&(method==='GET'||method==='POST')){
   try{
    const actor=who(req);
    if(!joinSecretKey)throw err('NOT_CONFIGURED','Host joining instructions are unavailable',503);
    let body=null;
    if(method==='POST'){origin(req);guard('join-details:'+actor.id,10);body=await readBody(req)}
    const result=await serial(touch=>{
     const g=db.lobbies[privateMatch[1]];
     if(!g)throw err('NOT_FOUND','Game not found',404);
     const previous=g.status;publicLobby(g,now());if(g.status!==previous)touch();
     if(method==='POST'&&g.status==='cancelled')throw err('CANCELLED','Cannot edit a cancelled game',409);
     const role=joinDetailsRole(g,actor.id);
     if(!role)throw err('NOT_SELECTED','Joining details are only available to the host or selected players',403);
     if(method==='POST'){
      if(role!=='host')throw err('HOST_ONLY','Only the host may change instructions',403);
      db.joinSecrets[g.id]=sealJoinInstructions(body.instructions,joinSecretKey);touch();
     }
     return {role,ready:g.status==='ready',instructions:openJoinInstructions(db.joinSecrets[g.id],joinSecretKey)};
    },'on-touch');
    send(res,200,result);
   }catch(e){send(res,e.status||500,{error:e.code||'FAILED',message:e.status?e.message:'Server temporarily unavailable'})}
   return true;
  }
  const match=pathname.match(/^\/api\/lobbies\/([a-zA-Z0-9-]+)(\/join)?$/);
  if(match&&method==='GET'&&!match[2]){
   try{const result=await serial(touch=>{const g=db.lobbies[match[1]];const prev=g?.status;const view=publicLobby(g,now());if(g.status!==prev)touch();return view},'on-touch');send(res,200,{game:result})}
   catch(e){send(res,e.status||500,{error:e.code||'FAILED',message:e.message})}return true;
  }
  if(match&&match[2]&&method==='POST'){
   try{origin(req);const user=who(req);guard('join:'+user.id,20);const result=await serial(()=>{
    const g=db.lobbies[match[1]];if(!g)throw err('NOT_FOUND','Game not found',404);
    joinLobby(g,user.id,'@'+user.username,now());return publicLobby(g,now());
   });send(res,200,{game:result})
   }catch(e){send(res,e.status||500,{error:e.code||'FAILED',message:e.message})}return true;
  }
  return false;
 }
 return{handle};
}