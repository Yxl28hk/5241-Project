/* Teacher authoring and student rendering share one course-content schema. */
const studioModes={resource:['资料阅读','以 PDF、Word 或 PPT 等资料为主'],video:['视频学习','上传视频，配上目标和学习提示'],guided:['分步讲解','用短小节、示例循序渐进地讲清概念'],practice:['动手实践','布置具体任务，明确产出与自查标准'],blended:['混合课程','附件与分步正文组合，按需添加任务']};
const studioLevels={beginner:'零基础',intermediate:'有一定基础',advanced:'进阶'};
let studioPreview=false,studioId=null,studioRevision=0,studioExistingFile=null,studioFileURL=null,studioBusy=false,studioEpoch=0;
const se=value=>analyticsEscape(value);
function studioKey(){return `zhixing:course-draft:${studioPreview?'preview':state.user?.id}:${studioId||'new'}`;}
function studioBlank(){return {title:'',category:'技术',mode:'guided',level:'beginner',minutes:15,audience:'',objectives:'',description:'',sections:[{title:'',body:''}],example:'',task:'',checklist:'',reference:''};}
function studioRead(){const data={revision:studioRevision};for(const key of ['title','category','mode','level','minutes','audience','objectives','description','example','task','checklist','reference','source_notes'])data[key]=$(`#studio-${key}`).value.trim();data.minutes=Number(data.minutes);data.sections=$$('#studio-sections .studio-section-editor').map(el=>({title:el.querySelector('input').value.trim(),body:el.querySelector('textarea').value.trim()})).filter(s=>s.title||s.body);return data;}
function studioSection(value={title:'',body:''}){
  if($$('#studio-sections .studio-section-editor').length>=8){showToast('最多添加 8 个小节');return;}
  const el=document.createElement('div');el.className='studio-section-editor';
  el.innerHTML=`<div class="studio-section-toolbar"><b>正文小节</b><div><button type="button" data-up aria-label="上移小节">↑</button><button type="button" data-down aria-label="下移小节">↓</button><button type="button" data-remove>删除</button></div></div><label class="field">小节标题<input maxlength="120" value="${se(value.title)}" placeholder="例如：为什么修改需要先审查？"></label><label class="field">小节正文<textarea maxlength="6000" rows="4" placeholder="先描述情境，再解释概念。">${se(value.body)}</textarea></label>`;
  el.querySelector('[data-remove]').onclick=()=>{el.remove();studioRefresh();};
  el.querySelector('[data-up]').onclick=()=>{if(el.previousElementSibling)el.before(el.previousElementSibling);studioRefresh();};
  el.querySelector('[data-down]').onclick=()=>{if(el.nextElementSibling)el.after(el.nextElementSibling);studioRefresh();};
  $('#studio-sections').append(el);
}
function studioFill(data){for(const key of ['title','category','mode','level','minutes','audience','objectives','description','example','task','checklist','reference','source_notes'])$(`#studio-${key}`).value=data[key]??'';$('#studio-sections').replaceChildren();(data.sections||[]).forEach(studioSection);studioRefresh();}
function studioLines(text){return String(text||'').split('\n').map(s=>s.trim()).filter(Boolean);}
function studioLessonHTML(c,fileURL=null,fileType=null,preview=false){
  const lines=text=>studioLines(text).map(t=>`<li>${se(t)}</li>`).join('');
  return `<div class="studio-lesson-meta"><span>${se(studioModes[c.mode]?.[0]||'课程')}</span><span>${se(studioLevels[c.level]||'')}</span><span>约 ${Number(c.minutes)||0} 分钟</span></div><section class="lesson-objectives"><span class="section-kicker">学习目标</span><h3>完成后，你能够…</h3><ul>${lines(c.objectives)}</ul><p class="supporting-copy">适合：${se(c.audience)}</p></section>${fileURL ? fileType==='video'?`<section class="studio-media"><h3>课程视频</h3><video controls preload="metadata" src="${se(fileURL)}"></video><p class="supporting-copy">若浏览器不支持此编码，可打开附件查看。</p><a href="${se(fileURL)}" target="_blank" rel="noopener">打开视频附件 ↗</a></section>`:`<section class="studio-media"><h3>课程资料</h3><a class="button button-ghost" href="${se(fileURL)}" target="_blank" rel="noopener">打开课程附件 ↗</a></section>`:''}${(c.sections||[]).map((s,i)=>`<section class="studio-reading-block"><span class="section-kicker">第 ${i+1} 步</span><h3>${se(s.title)}</h3><p>${se(s.body)}</p></section>`).join('')}${c.example?`<section class="lesson-example"><span class="section-kicker">具体例子</span><h3>先看一个示范</h3><pre><code>${se(c.example)}</code></pre></section>`:''}${c.source_notes?`<details class="ai-source-notes"><summary>资料来源与 AI 补充说明</summary><p class="studio-prewrap">${se(c.source_notes)}</p></details>`:''}${c.task?`<section class="lesson-task"><span class="section-kicker">轮到你了</span><h3>动手任务</h3><p class="studio-prewrap">${se(c.task)}</p>${c.checklist?`<h4>完成前自查</h4><ul>${lines(c.checklist)}</ul>`:''}<label class="field">我的思路<textarea ${preview?'disabled':'id="lesson-task-response"'} maxlength="4000" rows="4" placeholder="写下你的方案或操作结果…"></textarea></label><p ${preview?'':'id="lesson-draft-status"'} class="supporting-copy">${preview?'预览中不保存学生回答。':'任务草稿保存到账号，不自动评分。'}</p>${c.reference?`<details class="lesson-reference"><summary>完成后查看参考思路</summary><p class="studio-prewrap">${se(c.reference)}</p></details>`:''}</section>`:''}`;
}
function studioRefresh(){
  const c=studioRead(),mode=c.mode;
  $$('.studio-mode').forEach(el=>{el.classList.toggle('selected',el.dataset.mode===mode);el.setAttribute('aria-pressed',String(el.dataset.mode===mode));});
  $('#studio-mode-help').textContent=studioModes[mode]?.[1]||'';
  $('#studio-attachment-help').textContent=['resource','video','blended'].includes(mode)?'此模式必须提供附件；其他文字内容可补充说明。':'附件可选，可以只发布结构化文字内容。';
  $('#course-file').accept=mode==='video'?'.mp4,.mov':'.pdf,.doc,.docx,.ppt,.pptx,.mp4,.mov';
  const file=$('#course-file').files[0];$('#studio-file-label').textContent=file?`${file.name} · ${(file.size/1024/1024).toFixed(1)} MB`:studioExistingFile?'保留已有附件（选择新文件可替换）':'尚未选择附件';
  $('#studio-outline').innerHTML=`<strong>${se(c.title||'未命名课程')}</strong><p>${se(studioModes[mode]?.[0])} · ${se(studioLevels[c.level])} · ${c.minutes||'—'} 分钟</p><ol><li>学习目标：${studioLines(c.objectives).length} 项</li>${file||studioExistingFile?'<li>课程附件</li>':''}${c.sections.map(s=>`<li>${se(s.title||'未命名小节')}</li>`).join('')}${c.example?'<li>示例演示</li>':''}${c.task?'<li>动手任务与自查</li>':''}</ol><small>课程完成由学生手动确认；阅读、播放视频均不会自动判定掌握。</small>`;
  $('#studio-submit').textContent=studioPreview?'预览模式 · 不发布':studioId?'保存课程修改':'发布课程';
  $('#studio-submit').disabled=studioPreview||studioBusy;
}
function studioValidate(c){
  if(!c.title||!c.description||!c.audience||!c.objectives)return '请填写课程名称、简介、适合人群和学习目标。';
  if(!Number.isInteger(c.minutes)||c.minutes<1||c.minutes>600)return '预计时长应为 1–600 分钟。';
  if(c.sections.some(s=>!s.title||!s.body))return '请补全每个正文小节的标题与内容，或删除空小节。';
  if(['guided','blended'].includes(c.mode)&&!c.sections.length)return '此模式至少需要一个正文小节。';
  if(c.mode==='practice'&&(!c.task||!c.checklist))return '动手实践需要任务说明和完成标准。';
  const file=$('#course-file').files[0];
  if(['resource','video','blended'].includes(c.mode)&&!file&&!studioExistingFile)return '此模式需要上传附件。';
  if(file&&file.size>500*1024*1024)return '附件不能超过 500MB。';
  if(file&&!/\.(pdf|docx?|pptx?|mp4|mov)$/i.test(file.name))return '附件格式不支持。';
  if(c.mode==='video'&&((file&&!/\.(mp4|mov)$/i.test(file.name))||(!file&&studioExistingFile?.type!=='video')))return '视频模式需要 MP4 或 MOV 文件。';
  return '';
}
function studioTab(tab){
  if(studioBusy)return;
  $('#upload-modal .studio-layout').classList.toggle('ai-focused',tab==='ai');
  $('#upload-modal .studio-footer').classList.toggle('hidden',tab==='ai');
  $$('.studio-pane').forEach(el=>el.classList.toggle('hidden',el.dataset.pane!==tab));
  $$('.studio-step').forEach(el=>{el.classList.toggle('active',el.dataset.tab===tab);el.setAttribute('aria-selected',String(el.dataset.tab===tab));});
  if(tab==='preview'){
    const c=studioRead(),error=studioValidate(c);$('#studio-preview-warning').textContent=error?`发布前待完善：${error}`:'内容已齐全，可以检查学生视角后发布。';
    $('#studio-preview-title').textContent=c.title||'未命名课程';
    if(studioFileURL){URL.revokeObjectURL(studioFileURL);studioFileURL=null;}
    const file=$('#course-file').files[0];if(file)studioFileURL=URL.createObjectURL(file);
    $('#studio-preview-body').innerHTML=studioLessonHTML(c,studioFileURL||studioExistingFile?.url,file?/\.(mp4|mov)$/i.test(file.name)?'video':'file':studioExistingFile?.type,true);
  }
}
async function openStudio(courseId=null,preview=false){
  if(studioBusy || (typeof studioAIBusy!=='undefined' && studioAIBusy)){showToast('请先停止等待或完成当前保存');return;}
  if(!preview&&!requireUploadPermission())return;
  const epoch=++studioEpoch;studioPreview=preview;studioId=courseId;studioRevision=0;studioExistingFile=null;
  $('#course-file').value='';$('#studio-error').textContent='';$('#studio-draft-status').textContent='草稿仅保存在本浏览器；附件需要重新选择。';
  $('#studio-preview-banner').classList.toggle('hidden',!preview);$('#studio-heading').textContent=courseId?'编辑课程':'创建课程';
  studioFill(studioBlank());studioTab(courseId?'basics':'ai');openModal('#upload-modal');
  $('#studio-ai-review-note').classList.add('hidden');
  if(typeof studioAIReset==='function')studioAIReset();
  if(courseId){
    $('#studio-fieldset').disabled=true;$('#studio-error').textContent='正在读取课程…';
    try{
      const result=await zhixingApi.request(`/api/studio/courses/${courseId}`);if(epoch!==studioEpoch)return;
      const course=result.course;studioRevision=result.content?.revision||0;
      studioExistingFile=course.file_url?{url:course.file_url,type:course.type}:null;
      studioFill(result.content||{...studioBlank(),title:course.title,category:course.category,description:course.description,mode:course.type==='video'?'video':'resource',sections:[]});
      $('#studio-error').textContent='';$('#studio-fieldset').disabled=false;
    }catch(error){if(epoch===studioEpoch){$('#studio-error').textContent=error.message;$('#studio-submit').disabled=true;}}
  }else $('#studio-fieldset').disabled=false;
}
function studioSample(){studioFill({...studioBlank(),title:'第一次提交 PR：把修改说清楚',description:'从一处按钮修改出发，练习检查变更并写出清楚的 PR 说明。',audience:'没用过 Git、第一次参与团队项目的同学',objectives:'能识别需求之外的改动\n能写出修改内容与验证方法',sections:[{title:'先明确要改什么',body:'需求：把按钮“开始”改成“开始学习”，点击后仍然进入课程页面。检查时既要看文字，也要实际点击。'},{title:'把修改交给队友检查',body:'PR（Pull Request）可以理解为一份修改申请。你要说明改了什么、为什么改、做过哪些验证，让队友决定是否合并。'}],example:'修改前：开始 → 课程页面\n修改后：开始学习 → 课程页面\n验证：打开首页，检查文字，再点击按钮确认去向。',task:'写一份三句话的 PR 说明：问题是什么、改了什么、怎样验证。',checklist:'明确指出修改的位置\n只描述实际完成的验证\n列出还没有检查的情况',reference:'把首页按钮文案从“开始”改为“开始学习”。点击去向仍为课程页面。已检查桌面端文字与跳转，手机端待验证。'});}
$$('.studio-mode').forEach(b=>b.onclick=()=>{$('#studio-mode').value=b.dataset.mode;studioRefresh();});
$$('.studio-step').forEach(b=>b.onclick=()=>studioTab(b.dataset.tab));
$('#studio-form').oninput=studioRefresh;$('#studio-add-section').onclick=()=>{studioSection();studioRefresh();};
$('#course-file').onchange=studioRefresh;$('#studio-remove-file').onclick=()=>{$('#course-file').value='';studioRefresh();};
$('#studio-sample').onclick=()=>{if(confirm('用示例内容替换当前填写的文字？'))studioSample();};
$('#studio-save-draft').onclick=()=>{try{localStorage.setItem(studioKey(),JSON.stringify({content:studioRead(),savedAt:new Date().toISOString(),aiReport:typeof studioAIResult!=='undefined'?studioAIResult:null}));$('#studio-draft-status').textContent='本机文字草稿已保存 · '+new Date().toLocaleTimeString('zh-CN')+' · 附件不保存';}catch{$('#studio-error').textContent='浏览器无法保存草稿，请复制内容后重试。';}};
$('#studio-restore-draft').onclick=()=>{try{const saved=JSON.parse(localStorage.getItem(studioKey())||'null');if(!saved){$('#studio-draft-status').textContent='当前课程还没有本机草稿。';return;}if(confirm('恢复本机草稿并替换当前文字？')){studioFill(saved.content);if(typeof studioAIRestoreReport==='function')studioAIRestoreReport(saved.aiReport||null);$('#studio-draft-status').textContent='已恢复文字草稿；请确认附件和当前课程版本。';}}catch{$('#studio-error').textContent='草稿无法读取。';}};
$('#studio-form').onsubmit=async event=>{
  event.preventDefault();if(studioPreview||studioBusy)return;if(!requireUploadPermission())return;
  const content=studioRead(),error=studioValidate(content);$('#studio-error').textContent=error;if(error){studioTab('content');return;}
  const form=new FormData();form.append('content',JSON.stringify(content));const file=$('#course-file').files[0];if(file)form.append('file',file);
  const draftKey=studioKey();studioBusy=true;$('#studio-fieldset').disabled=true;$('#studio-error').textContent='正在保存，请勿关闭窗口…';studioRefresh();
  try{
    const result=await zhixingApi.request(studioId?`/api/studio/courses/${studioId}`:'/api/studio/courses',{method:studioId?'PATCH':'POST',body:form});
    studioId=result.course.id;studioRevision=result.content.revision;studioExistingFile=result.course.file_url?{url:result.course.file_url,type:result.course.type}:null;
    try{localStorage.removeItem(draftKey);}catch{}
    $('#course-file').value='';$('#studio-heading').textContent='编辑课程';$('#studio-error').textContent='';$('#studio-draft-status').textContent='课程已保存到账号；学生可在发现课程中查看。';
    showToast('课程保存成功');await loadCourses().catch(()=>showToast('课程已保存，课程列表刷新失败，请稍后刷新页面'));
  }catch(error){$('#studio-error').textContent=error.message;}
  finally{studioBusy=false;$('#studio-fieldset').disabled=false;studioRefresh();}
};
if(new URLSearchParams(location.search).get('preview')==='studio')window.addEventListener('load',()=>openStudio(null,true),{once:true});
