const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../frontend/features/courses/studio-ai.js'),'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function fixture(request){
  const elements=new Map(),storage=new Map(),timers=new Map(),calls=[];let next=0;
  const $=key=>{if(!elements.has(key)){const classes=new Set();elements.set(key,{value:'',files:[],textContent:'',disabled:false,
    classList:{add:k=>classes.add(k),remove:k=>classes.delete(k),contains:k=>classes.has(k),toggle:(k,on)=>{if(on??!classes.has(k))classes.add(k);else classes.delete(k);}}});}return elements.get(key);};
  const context=vm.createContext({$, $$:()=>[0,1,2,3].map(i=>$('stage'+i)),studioPreview:false,state:{user:{id:16}},
    zhixingApi:{request:async(url,options)=>{calls.push({url,options});return request(url,options);}},
    sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    setTimeout:fn=>{timers.set(++next,fn);return next;},clearTimeout:id=>timers.delete(id),
    FormData,Blob,URL,Date,crypto:{randomUUID:()=> 'unique-request-id'},studioRefresh:()=>{},
    se:String,studioLessonHTML:()=>'',studioTab:()=>{},studioFill:()=>{},showToast:()=>{},confirm:()=>true});
  vm.runInContext(source,context);
  return {$,calls,context,reset:()=>vm.runInContext('studioAIReset()',context),
    file:()=>{$('#studio-ai-file').files=[Object.assign(new Blob(['test']),{name:'new-file.pptx'})];},
    timer:async()=>{const [id,fn]=timers.entries().next().value||[];assert.ok(fn,'scheduled progress query');timers.delete(id);await fn();await tick();}};
}
const config={configured:true,request_bound:true,max_mb:3,csrf:'test',model:'test'};
const done={id:'existing',state:'done',message:'done',result:{course:{title:'Original'},source:{filename:'original.pptx'},
  review:{summary:'Ready',strengths:[],issues:[]},extraction:{total_pages:1,readable_pages:1,characters:100,warnings:[]},sources:[],supplements:[]}};

test('opening editor recovers the owner task without a saved browser token',async()=>{
  const f=fixture(async url=>url.endsWith('/config')?{...config,active_job_id:'existing'}:{id:'existing',state:'generating',message:'working'});
  await f.reset();await tick();
  assert.equal(f.$('#studio-ai-generate').disabled,true);
  assert.equal(f.$('#studio-ai-status').textContent,'working');
  assert.equal(f.calls.filter(c=>c.options?.method==='POST').length,0);
});

test('409 resumes existing generation and never attaches the new file to its result',async()=>{
  const f=fixture(async(url,options)=>{if(url.endsWith('/config'))return config;if(options?.method==='POST')throw Object.assign(new Error('busy'),{status:409,body:{job_id:'existing'}});return done;});
  await f.reset();f.file();await f.$('#studio-ai-generate').onclick();await tick();
  assert.equal(f.$('#studio-ai-summary').textContent,'Ready');
  assert.equal(f.$('#studio-ai-generate').disabled,false);
  assert.equal(vm.runInContext('studioAISource',f.context),null);
  assert.equal(f.calls.filter(c=>c.options?.method==='POST').length,1);
});

test('cancelled invocation stays visible until drained, then releases generate',async()=>{
  let cancelled=false,drained=false;
  const f=fixture(async(url,options)=>{if(url.endsWith('/config'))return {...config,active_job_id:'existing'};
    if(options?.method==='DELETE'){cancelled=true;return {in_flight:true};}
    return {id:'existing',state:cancelled?'cancelled':'generating',in_flight:cancelled&&!drained,message:'Waiting'};});
  await f.reset();await tick();await f.$('#studio-ai-cancel').onclick();await tick();
  assert.equal(f.$('#studio-ai-generate').disabled,true);assert.equal(f.$('#studio-ai-cancel').disabled,true);
  drained=true;await f.timer();assert.equal(f.$('#studio-ai-generate').disabled,false);
  assert.equal(f.calls.filter(c=>c.options?.method==='POST').length,0);
});

test('hosted progress is queried while upload request is still pending',async()=>{
  const upload=deferred();let registered=false;
  const f=fixture(async(url,options)=>{if(url.endsWith('/config'))return config;if(options?.method==='POST')return upload.promise;
    if(!registered)throw Object.assign(new Error('not registered yet'),{status:404});
    return {id:'existing',state:'parsing',message:'Extracting pages'};});
  await f.reset();f.file();const posting=f.$('#studio-ai-generate').onclick();
  await f.timer();assert.equal(f.$('#studio-ai-generate').disabled,true);
  assert.equal(f.$('#studio-ai-resume').classList.contains('hidden'),true);
  registered=true;await f.timer();assert.equal(f.$('#studio-ai-status').textContent,'Extracting pages');
  upload.resolve({job_id:'existing'});await posting;await tick();
  assert.equal(f.calls.filter(c=>c.options?.method==='POST').length,1);
});

test('late poll of a rejected request cannot hide recovery of the existing job',async()=>{
  const upload=deferred(),oldPoll=deferred();
  const f=fixture(async(url,options)=>{if(url.endsWith('/config'))return config;if(options?.method==='POST')return upload.promise;
    if(url.includes('request-unique'))return oldPoll.promise;return done;});
  await f.reset();f.file();const posting=f.$('#studio-ai-generate').onclick();const polling=f.timer();
  upload.reject(Object.assign(new Error('busy'),{status:409,body:{job_id:'existing'}}));await posting;
  oldPoll.reject(Object.assign(new Error('not found'),{status:404}));await polling;await f.timer();
  assert.equal(f.$('#studio-ai-summary').textContent,'Ready');
  assert.equal(f.$('#studio-ai-generate').disabled,false);
});
