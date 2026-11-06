(function buildCore() {
  'use strict';
  const D = typeof module !== 'undefined' ? require('./checklist-data.js') : globalThis.ChecklistData;
  const S = ['NOT TESTED', 'PASS', 'FAIL', 'BLOCKED'], MAX = 200000;
  const now = () => new Date().toISOString();
  function blank() {
    return { schemaVersion: 1, runStartedAt: now(), exportedAt: null, owner: '', acknowledged: false, signoffAt: null, results: Object.fromEntries(D.cases.map(c => [c.id, {status:S[0],notes:'',evidence:'',updatedAt:null}])) };
  }
  function checkText(v,n) {
    if (typeof v!=='string'||v.length>n||/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(v)) throw Error('Invalid or oversized text');
  }
  function isDate(v) {return typeof v==='string'&&/^\d{4}-\d\d-\d\dT/.test(v)&&Number.isFinite(Date.parse(v));}
  function keys(o,k) {
    if (!o || typeof o!=='object'||Array.isArray(o)||Object.keys(o).length!==k.length||k.some(x=>!Object.hasOwn(o,x))) throw Error('Unexpected schema fields');
  }
  function validate(s) {
    keys(s,['schemaVersion','runStartedAt','exportedAt','owner','acknowledged','signoffAt','results']);
    if(s.schemaVersion!==1||!isDate(s.runStartedAt)||(s.exportedAt!==null&&!isDate(s.exportedAt)))throw Error('Invalid schema or timestamp');
    checkText(s.owner,120);
    if(typeof s.acknowledged!=='boolean'||(s.signoffAt!==null&&!isDate(s.signoffAt)))throw Error('Invalid signoff');
    keys(s.results,D.cases.map(c=>c.id));
    for(const c of D.cases){
      const v=s.results[c.id];keys(v,['status','notes','evidence','updatedAt']);
      if(!S.includes(v.status))throw Error('Invalid status');
      checkText(v.notes,4000);checkText(v.evidence,240);
      if((v.updatedAt!==null&&!isDate(v.updatedAt))||(v.status!=='NOT TESTED'&&!isDate(v.updatedAt)))throw Error('Invalid check timestamp');
    }
    if((s.acknowledged&&(!s.owner.trim()||!s.signoffAt||!D.cases.every(c=>s.results[c.id].status==='PASS')))||(!s.acknowledged&&s.signoffAt!==null))throw Error('Invalid acknowledgement');
    return JSON.parse(JSON.stringify(s));
  }
  function parse(t) {
    if(typeof t!=='string'||new TextEncoder().encode(t).length>MAX)throw Error('Import exceeds 200 KB');
    return validate(JSON.parse(t));
  }
  // Imported files are untrusted evidence, even if a JSON payload claims prior signoff.
  // Preserve completed checks but require the operator to acknowledge them in this session.
  function importRecord(text) {
    const record = parse(text);
    revoke(record);
    return record;
  }
  function counts(s,g){
    const out={total:0,pass:0,fail:0,blocked:0,untested:0};
    for(const c of D.cases.filter(c=>!g||c.group===g)){out.total++;out[{PASS:'pass',FAIL:'fail',BLOCKED:'blocked','NOT TESTED':'untested'}[s.results[c.id].status]]++;}
    return out;
  }
  function ready(s){return counts(s).pass===D.cases.length&&s.acknowledged&&!!s.owner.trim()&&!!s.signoffAt;}
  function revoke(s){s.acknowledged=false;s.signoffAt=null;}
  function update(s,id,f,v){
    if(!Object.hasOwn(s.results,id)||!['status','notes','evidence'].includes(f))throw Error('Invalid edit');
    if(f==='status'){if(!S.includes(v))throw Error('Invalid status');}else checkText(v,f==='notes'?4000:240);
    s.results[id][f]=v;s.results[id].updatedAt=now();revoke(s);
  }
  function sign(s){
    if(!s.owner.trim()||counts(s).pass!==D.cases.length)throw Error('Named owner and all checks PASS required');
    s.acknowledged=true;s.signoffAt=now();return validate(s);
  }
  function snapshot(s){const v=validate(s);v.exportedAt=now();return v;}
  function escape(s){
    return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])).replace(/([\\`*_[\]{}()#!|~])/g,'\\$1');
  }
  function summary(s){
    const n=counts(s);return `${ready(s)?'READY — manual acceptance recorded':'NOT READY'}\n${n.pass}/${n.total} PASS; ${n.fail} FAIL; ${n.blocked} BLOCKED; ${n.untested} NOT TESTED\nOwner: ${s.owner||'not named'}; signoff: ${s.acknowledged?'YES':'NO'}\nHuman record only, not deployment authorization.`;
  }
  function markdown(s){
    const a=['# Gaming Network Launch Acceptance',escape(summary(s)),'Run started: '+s.runStartedAt,'Report generated: '+s.exportedAt,'Signoff: '+(s.signoffAt||'none'),'## Blocking reasons'];
    for(const c of D.cases)if(s.results[c.id].status!=='PASS')a.push(c.id+': '+s.results[c.id].status+' — '+escape(s.results[c.id].notes||'No reason recorded'));
    if(!s.acknowledged)a.push('Owner explicit signoff missing.');
    for(const g of D.groups){
      a.push('## '+g.title);
      for(const c of D.cases.filter(c=>c.group===g.id)){
        const v=s.results[c.id];a.push('### '+c.id+' '+c.title,'Action: '+c.action,'Expected: '+c.expected,'Status: '+v.status,'Updated: '+(v.updatedAt||'never'),'Notes: '+escape(v.notes),'Evidence reference: '+escape(v.evidence));
      }
    }
    a.push('## Responsible human acknowledgement','Owner: '+escape(s.owner),'Acknowledged: '+s.acknowledged,'Console self-tests and CI do NOT certify launch. No merge or deploy without owner approval.');
    return a.join('\n\n');
  }
  const C={D,S,MAX,blank,validate,parse,importRecord,counts,ready,revoke,update,sign,snapshot,summary,markdown};
  if(typeof module!=='undefined')module.exports=C;else globalThis.ConsoleCore=C;
})();
