/** Bounded in-process abuse throttle. Each Railway replica needs edge/shared limits too. */
export class RateLimitError extends Error {
  constructor(retrySeconds) {
    super('Too many requests; retry shortly');
    this.code='RATE_LIMIT';
    this.status=429;
    this.retryAfter=Math.max(1,Math.ceil(retrySeconds));
  }
}

export function createRateLimiter({now=Date.now,maxKeys=5000}={}) {
  const entries=new Map();
  function check(key,{limit=12,windowMs=60_000}={}) {
    if(typeof key!=='string'||key.length<1||key.length>160)throw new Error('Invalid rate limit identity');
    if(!Number.isSafeInteger(limit)||limit<1||!Number.isSafeInteger(windowMs)||windowMs<1)throw new Error('Invalid rate limit policy');
    const current=now();
    if(!Number.isSafeInteger(current)||current<0)throw new Error('Invalid clock');
    const prior=entries.get(key)||[];
    const active=prior.filter(t=>current-t<windowMs && current>=t);
    if(active.length>=limit) {
      entries.delete(key);
      entries.set(key,active); // recently active key retained
      throw new RateLimitError((windowMs-(current-active[0]))/1000);
    }
    active.push(current);
    entries.delete(key);
    entries.set(key,active);
    if(entries.size>maxKeys) {
      // Eviction bounds memory; production must additionally rate-limit at edge.
      entries.delete(entries.keys().next().value);
    }
    return {remaining:limit-active.length};
  }
  return {check};
}
