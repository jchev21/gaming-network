/**
 * Optional, fail-closed Discord Member role gate for X-hosted games.
 * One X session + one authenticated Discord user + a fresh Member role check.
 * No bot tokens, role grants, Discord server edits, or X writes.
 *
 * Security: Discord access tokens are memory-only (relink on restart).
 * No authorization is derived from a typed username, public post, or client JSON.
 */
import crypto from 'node:crypto';

const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const random = () => crypto.randomBytes(32).toString('base64url');
const snowflake = value => typeof value === 'string' && /^[0-9]{15,24}$/.test(value);
const cookieLine = (key, value, seconds) =>
  key + '=' + encodeURIComponent(value) + '; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=' + seconds;
function cookie(req, name) {
  const header = String(req.headers?.cookie || '');
  if (header.length > 8192) return null;
  const fragment = header.split(';').map(x => x.trim()).find(x => x.startsWith(name + '='));
  if (!fragment) return null;
  const value = fragment.slice(name.length + 1);
  if (value.length > 256) return null;
  try { return decodeURIComponent(value); } catch { return null; }
}
function reply(res, status, body, headers={}) {
  res.writeHead(status, {
    'content-type':'application/json; charset=utf-8',
    'cache-control':'no-store',
    'x-content-type-options':'nosniff',
    ...headers,
  });
  res.end(JSON.stringify(body));
}
function deny(code, status=403) {
  const e = new Error(code);
  e.code = code;
  e.status = status;
  return e;
}
function authHash(req) {
  const raw = cookie(req, 'gn_x_session');
  return raw && /^[A-Za-z0-9_-]{43}$/.test(raw) ? sha(raw) : null;
}
export function validateMemberConfig({clientId, clientSecret, redirectUri, guildId, roleId}) {
  if (!snowflake(clientId) || !snowflake(guildId) || !snowflake(roleId) ||
      typeof clientSecret !== 'string' || !clientSecret ||
      typeof redirectUri !== 'string' ||
      !/^https:\/\/[^/?#]+\/auth\/discord\/callback$/.test(redirectUri)) {
    throw new Error('Discord Member gate configuration incomplete; denying game writes');
  }
  return true;
}
export function createDiscordMemberAuth({
  clientId, clientSecret, redirectUri, guildId, roleId, xAuth,
  fetchImpl=fetch, now=Date.now, discordBase='https://discord.com',
}={}) {
  validateMemberConfig({clientId, clientSecret, redirectUri, guildId, roleId});
  if (!xAuth || typeof xAuth.authenticated !== 'function') {
    throw new Error('An authenticated X session provider is required');
  }
  const flows = new Map();
  const sessions = new Map();
  const maxFlows=1000;
  function actor(req) {
    const user = xAuth.authenticated(req);
    const proof = authHash(req);
    if (!user || !snowflake(String(user.id || '')) || !proof) throw deny('X_SIGN_IN_REQUIRED',401);
    return {xId:String(user.id),xProof:proof};
  }
  async function getJSON(url, accessToken) {
    const response = await fetchImpl(url, {
      headers:{authorization:'Bearer '+accessToken},
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw deny('DISCORD_MEMBER_CHECK_FAILED',response.status===429?503:403);
    const value=await response.json();
    if (!value || typeof value!=='object' || Array.isArray(value)) throw deny('INVALID_DISCORD_RESPONSE',403);
    return value;
  }
  async function checkRole(accessToken, expectedDiscordId=null) {
    const discordUser=await getJSON(discordBase+'/api/v10/users/@me', accessToken);
    if (!snowflake(String(discordUser.id || '')) ||
        (expectedDiscordId && String(discordUser.id)!==expectedDiscordId)) throw deny('DISCORD_IDENTITY_MISMATCH');
    const member=await getJSON(discordBase+'/api/v10/users/@me/guilds/'+guildId+'/member',accessToken);
    if (member.user?.id && String(member.user.id)!==String(discordUser.id))
      throw deny('DISCORD_IDENTITY_MISMATCH');
    if (member.pending !== false) throw deny('DISCORD_RULES_NOT_ACCEPTED');
    if (!Array.isArray(member.roles) || !member.roles.includes(roleId))
      throw deny('DISCORD_MEMBER_ROLE_REQUIRED');
    return String(discordUser.id);
  }
  async function requireMember(req) {
    const owner=actor(req);
    const sessionCookie=cookie(req,'gn_discord_member');
    if (!sessionCookie || !/^[A-Za-z0-9_-]{43}$/.test(sessionCookie)) throw deny('DISCORD_MEMBER_SIGN_IN_REQUIRED');
    const hash=sha(sessionCookie),session=sessions.get(hash);
    if (!session || session.expires<=now() || session.xId!==owner.xId || session.xProof!==owner.xProof) {
      sessions.delete(hash);
      throw deny('DISCORD_MEMBER_SIGN_IN_REQUIRED');
    }
    try {
      await checkRole(session.accessToken,session.discordId);
    } catch(error) {
      sessions.delete(hash);
      throw error;
    }
    return {xUserId:owner.xId,discordUserId:session.discordId,member:true};
  }
  async function handle(req,res,url) {
    const pathname=url.pathname;
    if (req.method==='GET' && pathname==='/api/discord-member') {
      try {
        const verified=await requireMember(req);
        reply(res,200,{configured:true,authorized:true,discordUserId:verified.discordUserId});
      } catch(error) {
        reply(res,200,{configured:true,authorized:false,reason:error.code||'DISCORD_MEMBER_CHECK_FAILED'});
      }
      return true;
    }
    if (req.method==='GET' && pathname==='/auth/discord/start') {
      try {
        const owner=actor(req);
        for(const [k,v] of flows) if(v.expires<=now()) flows.delete(k);
        if(flows.size>=maxFlows) throw deny('TOO_MANY_AUTH_FLOWS',429);
        const state=random();
        flows.set(sha(state),{...owner,expires:now()+600000});
        const authorize=new URL(discordBase+'/oauth2/authorize');
        for (const [key,value] of Object.entries({
          client_id:clientId,redirect_uri:redirectUri,response_type:'code',
          scope:'identify guilds.members.read',state,prompt:'consent',
        })) authorize.searchParams.set(key,value);
        res.writeHead(302,{
          location:authorize.toString(),
          'cache-control':'no-store',
          'set-cookie':cookieLine('gn_discord_oauth_state',state,600),
        });
        res.end();
      } catch(error) { reply(res,error.status||403,{error:error.code||'AUTH_UNAVAILABLE'}); }
      return true;
    }
    if (req.method==='GET' && pathname==='/auth/discord/callback') {
      try {
        const owner=actor(req);
        const state=url.searchParams.get('state');
        const consent=cookie(req,'gn_discord_oauth_state');
        const code=url.searchParams.get('code');
        if (!state || state.length!==43 || !consent || state!==consent || !code)
          throw deny('INVALID_DISCORD_OAUTH_STATE',400);
        const key=sha(state),flow=flows.get(key);
        flows.delete(key);
        if (!flow || flow.expires<=now() || flow.xId!==owner.xId || flow.xProof!==owner.xProof)
          throw deny('INVALID_DISCORD_OAUTH_STATE',400);
        const form=new URLSearchParams({
          client_id:clientId,client_secret:clientSecret,grant_type:'authorization_code',
          code,redirect_uri:redirectUri,
        });
        const response=await fetchImpl(discordBase+'/api/v10/oauth2/token',{
          method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},
          body:form,signal:AbortSignal.timeout(15000),
        });
        if (!response.ok) throw deny('DISCORD_OAUTH_EXCHANGE_FAILED',502);
        const token=await response.json();
        if(typeof token.access_token!=='string' || !token.access_token ||
           !Number.isFinite(Number(token.expires_in)) || Number(token.expires_in)<=0)
          throw deny('INVALID_DISCORD_OAUTH_TOKEN',502);
        const discordId=await checkRole(token.access_token);
        // Do not allow two different X accounts to reuse one Discord role identity.
        for(const prior of sessions.values()) {
          if(prior.discordId===discordId && prior.xId!==owner.xId && prior.expires>now())
            throw deny('DISCORD_ALREADY_LINKED');
        }
        const sessionToken=random();
        sessions.set(sha(sessionToken),{
          ...owner,discordId,accessToken:token.access_token,
          expires:now()+Math.min(3600000,Number(token.expires_in)*1000),
        });
        res.writeHead(302,{
          location:'/setup?member=connected',
          'cache-control':'no-store',
          'set-cookie':[
            cookieLine('gn_discord_oauth_state','',0),
            cookieLine('gn_discord_member',sessionToken,3600),
          ],
        });
        res.end();
      } catch(error) {
        reply(res,error.status||403,{error:error.code||'DISCORD_AUTH_UNAVAILABLE'});
      }
      return true;
    }
    return false;
  }
  return {handle,requireMember};
}
