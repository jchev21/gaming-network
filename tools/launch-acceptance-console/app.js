(function launchConsoleApp() {
  'use strict';
  const C=globalThis.ConsoleCore;
  const $=id=>document.getElementById(id);
  const KEY='gaming-network-launch-v1';
  let state=C.blank();
  function msg(s){$('message').textContent=s;}
  function node(t,s){const n=document.createElement(t);if(s!==undefined)n.textContent=s;return n;}
  try{const stored=localStorage.getItem(KEY);if(stored)state=C.parse(stored);}
  catch(e){msg('Saved state unavailable/invalid: '+e.message);}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(C.validate(state)));}catch(e){msg('Storage failed; export now: '+e.message);}}
  function progress(){
    const n=C.counts(state);
    $('ready').textContent=C.ready(state)?'READY — manual acceptance recorded':'NOT READY';
    $('overall').max=n.total;$('overall').value=n.pass;
    $('count').textContent=C.summary(state);$('ack').checked=state.acknowledged;
    for(const g of C.D.groups){
      const n=C.counts(state,g.id);
      $('p-'+g.id).value=n.pass;
      $('n-'+g.id).textContent=`${n.pass}/${n.total} PASS; ${n.fail} FAIL; ${n.blocked} BLOCKED; ${n.untested} NOT TESTED`;
    }
  }
  function render(){
    $('checks').replaceChildren();
    for(const g of C.D.groups){
      const section=node('section');
      section.append(node('h2',g.title));
      const p=node('progress');p.id='p-'+g.id;p.max=C.counts(state,g.id).total;p.setAttribute('aria-label',g.title+' passed checks');
      const n=node('p');n.id='n-'+g.id;section.append(p,n);
      for(const c of C.D.cases.filter(c=>c.group===g.id)){
        const a=node('article'),time=node('small','Updated: '+(state.results[c.id].updatedAt||'never'));
        a.append(node('h3',c.id+' · '+c.title),node('p','Human action: '+c.action),node('p','PASS means: '+c.expected));
        for(const f of ['status','notes','evidence']){
          const label=node('label',f==='status'?'Human-entered status':f==='notes'?'Notes / blocking reason (no secrets)':'Safe evidence reference or filename');
          const input=node(f==='status'?'select':f==='notes'?'textarea':'input');
          input.id=c.id+'-'+f;label.htmlFor=input.id;
          if(f==='status')for(const s of C.S){const option=node('option',s);option.value=s;input.append(option);}
          else input.maxLength=f==='notes'?4000:240;
          input.value=state.results[c.id][f];
          input.addEventListener(f==='status'?'change':'input',()=>{
            try{C.update(state,c.id,f,input.value);save();progress();time.textContent='Updated: '+state.results[c.id].updatedAt;}
            catch(e){msg(e.message);}
          });
          a.append(label,input);
        }
        a.append(time);section.append(a);
      }
      $('checks').append(section);
    }
    $('owner').value=state.owner;progress();
  }
  function download(name,data,type){
    const url=URL.createObjectURL(new Blob([data],{type})),a=node('a');a.href=url;a.download=name;
    document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
  }
  $('owner').addEventListener('input',()=>{state.owner=$('owner').value;C.revoke(state);save();progress();});
  $('ack').addEventListener('change',()=>{if(!$('ack').checked){C.revoke(state);save();progress();}});
  $('sign').onclick=()=>{
    try{
      if(!$('ack').checked)throw Error('Check the personal acknowledgement first.');
      state=C.sign(state);save();progress();msg('Manual signoff recorded; no deployment authorized.');
    }catch(e){$('ack').checked=state.acknowledged;msg(e.message);}
  };
  $('export').onclick=()=>{
    try{
      const s=C.snapshot(state),name='gaming-network-acceptance-'+s.exportedAt.replace(/[:.]/g,'-');
      download(name+'.json',JSON.stringify(s,null,2),'application/json');
      download(name+'.md',C.markdown(s),'text/markdown');
      msg('Both downloads requested. Allow multiple downloads if prompted and verify both files. Review for secrets before sharing.');
    }catch(e){msg(e.message);}
  };
  $('import').onchange=async event=>{
    const file=event.target.files[0];if(!file)return;
    try{
      if(file.size>C.MAX)throw Error('Import exceeds 200 KB');
      const candidate=C.importRecord(await file.text());
      if(!confirm('Replace current run with this validated prior human record? Imported PASS values are not independently verified.'))return;
      state=candidate;save();render();msg('Imported statuses and notes only; any previous signoff has been REVOKED. Review evidence in person and sign again. No live checks performed.');
    }catch(e){msg('Import rejected; current run unchanged: '+e.message);}
    finally{$('import').value='';}
  };
  $('reset').onclick=()=>{
    if(confirm('Permanently clear ALL results, notes, evidence and owner signoff? Export first if needed.')){
      state=C.blank();save();render();msg('Reset complete; all NOT TESTED.');
    }
  };
  $('copy').onclick=async()=>{
    const s=C.summary(state);
    try{if(!navigator.clipboard?.writeText)throw Error();await navigator.clipboard.writeText(s);msg('Summary copied.');}
    catch(e){$('fallback').hidden=false;$('fallback').value=s;$('fallback').focus();$('fallback').select();msg('Use your keyboard copy command on the selected summary.');}
  };
  render();
})();
