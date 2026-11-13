/* Upload first; generated content remains a candidate until explicitly adopted. */
let studioAIBusy=false,studioAIConfig=null,studioAIResult=null,studioAIJob=null,studioAITimer=null,studioAIEpoch=0,studioAISource=null,studioAIJobSource=null,studioAIObjectURL=null;
function aiURL(path){return path+(studioPreview?'?preview=1':'');}
function aiJobKey(){return 'zhixing:ai-job:'+(studioPreview?'preview':state.user?.id);}
function aiStatus(message,error=false){$('#studio-ai-status').textContent=message;$('#studio-ai-status').classList.toggle('ai-error',error);}
function aiControls(){
  $('#studio-ai-generate').disabled=studioAIBusy||!studioAIConfig?.configured;
  $('#studio-ai-file').disabled=studioAIBusy;$('#studio-ai-audience').disabled=studioAIBusy;
  $('#studio-ai-cancel').classList.toggle('hidden',!studioAIBusy);
  $('#studio-ai-generate').textContent=studioAIBusy?'正在整理资料…':'生成课程草稿与评价';
  $('#studio-ai-apply').disabled=studioAIBusy||!studioAIResult;
}
async function studioAIReset(){
  const epoch=++studioAIEpoch;clearTimeout(studioAITimer);studioAIJob=null;studioAIBusy=false;studioAIConfig=null;
  studioAIResult=null;studioAISource=null;studioAIJobSource=null;
  if(studioAIObjectURL){URL.revokeObjectURL(studioAIObjectURL);studioAIObjectURL=null;}
  $('#studio-ai-resume').classList.add('hidden');$$('.ai-stage').forEach(el=>el.classList.remove('is-done'));
  $('#studio-ai-file').value='';$('#studio-ai-filename').textContent='支持文字型 PDF / PPTX · 最多 20MB、60 页';
  $('#studio-ai-result').classList.add('hidden');aiStatus('正在检查 AI 服务配置…');aiControls();
  try{
    const config=await zhixingApi.request(aiURL('/api/studio/ai/config'));if(epoch!==studioAIEpoch)return;
    studioAIConfig=config;
    $('#studio-ai-model').textContent=config.configured?`云渡 · ${config.model}`:'AI 尚未配置';
    aiStatus(config.configured?'上传你已有的资料，其余内容交给 AI 先整理。':'后端尚未配置可用的云渡接口，可使用高级编辑。',!config.configured);aiControls();
    let saved;try{saved=JSON.parse(sessionStorage.getItem(aiJobKey())||'null');}catch{}
    if(saved?.id){studioAIJob=saved.id;studioAIBusy=true;aiControls();aiPoll(epoch);}
  }catch(error){if(epoch!==studioAIEpoch)return;aiStatus(error.message,true);aiControls();}
}
$('#studio-ai-file').onchange=()=>{
  const file=$('#studio-ai-file').files[0];
  $('#studio-ai-filename').textContent=file?`${file.name} · ${(file.size/1024/1024).toFixed(1)} MB`:'支持文字型 PDF / PPTX · 最多 20MB、60 页';
};
$('#studio-ai-generate').onclick=async()=>{
  if(studioAIBusy||!studioAIConfig?.configured)return;
  const file=$('#studio-ai-file').files[0];
  if(!file||! /\.(pdf|pptx)$/i.test(file.name)){aiStatus('请上传 PDF 或 PPTX；旧版 PPT 请先另存为 PPTX。',true);return;}
  if(!file.size||file.size>20*1024*1024){aiStatus('文件为空或超过 20MB，请拆分后上传。',true);return;}
  const epoch=++studioAIEpoch;studioAIBusy=true;$('#studio-ai-resume').classList.add('hidden');$$('.ai-stage').forEach(el=>el.classList.remove('is-done'));aiControls();aiStatus('正在上传资料，仅用于生成草稿…');
  const form=new FormData();form.append('file',file);form.append('audience',$('#studio-ai-audience').value);form.append('request_id',crypto.randomUUID());
  try{
    const response=await zhixingApi.request(aiURL('/api/studio/ai/jobs'),{method:'POST',headers:{'X-Studio-CSRF':studioAIConfig.csrf},body:form});
    if(epoch!==studioAIEpoch)return;studioAIJob=response.job_id;studioAIJobSource=file;
    try{sessionStorage.setItem(aiJobKey(),JSON.stringify({id:studioAIJob}));}catch{}
    aiPoll(epoch);
  }catch(error){if(epoch!==studioAIEpoch)return;studioAIBusy=false;aiStatus(error.message,true);aiControls();}
};
async function aiPoll(epoch){
  try{
    const job=await zhixingApi.request(aiURL('/api/studio/ai/jobs/'+studioAIJob));if(epoch!==studioAIEpoch)return;
    const prefix=job.state==='error'&&job.extraction?`资料解析已完成（${job.extraction.total_pages} 页）。`:'';
    aiStatus(prefix+job.message,job.state==='error');
    const stages=['queued','parsing','generating','done'];
    const current=stages.indexOf(job.state==='error'?(job.stage||'queued'):job.state);
    $$('.ai-stage').forEach((el,i)=>{el.classList.toggle('is-done',job.state==='done'||i<current);el.classList.toggle('ai-error',job.state==='error'&&i===current);});
    if(job.state==='done'){
      studioAIResult=job.result;studioAISource=studioAIJobSource;studioAIBusy=false;try{sessionStorage.removeItem(aiJobKey());}catch{}
      aiRenderResult();aiControls();return;
    }
    if(['error','cancelled'].includes(job.state)){studioAIBusy=false;try{sessionStorage.removeItem(aiJobKey());}catch{}aiControls();return;}
    studioAITimer=setTimeout(()=>aiPoll(epoch),1600);
  }catch(error){if(epoch!==studioAIEpoch)return;studioAIBusy=false;aiStatus('状态读取失败：'+error.message+' 可点击“恢复查询”，不会重复调用模型。',true);$('#studio-ai-resume').classList.remove('hidden');aiControls();}
}
$('#studio-ai-resume').onclick=()=>{if(!studioAIJob)return;$('#studio-ai-resume').classList.add('hidden');studioAIBusy=true;aiControls();aiPoll(++studioAIEpoch);};
$('#studio-ai-cancel').onclick=async()=>{
  if(!studioAIJob){aiStatus('正在上传，请稍候再停止等待。');return;}
  try{await zhixingApi.request(aiURL('/api/studio/ai/jobs/'+studioAIJob),{method:'DELETE',headers:{'X-Studio-CSRF':studioAIConfig.csrf}});++studioAIEpoch;clearTimeout(studioAITimer);studioAIBusy=false;try{sessionStorage.removeItem(aiJobKey());}catch{}aiStatus('已停止等待；已发出的模型请求仍可能产生费用。');aiControls();}
  catch(error){aiStatus(error.message,true);}
};
function aiRenderResult(){
  const data=studioAIResult;if(!data)return;
  $('#studio-ai-result').classList.remove('hidden');
  $('#studio-ai-summary').textContent=data.review.summary;
  $('#studio-ai-coverage').textContent=`${data.extraction.total_pages} 页资料 · ${data.extraction.readable_pages} 页提取到文字 · ${data.extraction.characters.toLocaleString()} 字符 · ${data.model||'Claude'}`;
  const list=items=>items.map(s=>`<li>${se(s)}</li>`).join('');
  $('#studio-ai-report').innerHTML=`<div class="ai-review-columns"><section><h4>资料的可用之处</h4><ul>${list(data.review.strengths)}</ul></section><section><h4>AI 补充内容</h4><ul>${list(data.supplements.length?data.supplements:['示例与任务为 AI 整理建议，请教师核对后使用。'])}</ul></section></div><h4>发布前需要确认</h4>${data.review.issues.length?data.review.issues.map(issue=>`<div class="ai-issue"><strong>${se(issue.title)}</strong><p>${se(issue.detail)}</p><small>${issue.source_pages.length?'涉及原资料第 '+issue.source_pages.join('、')+' 页':'整课建议'}</small></div>`).join(''):'<p>AI 未列出具体问题，仍需教师检查内容准确性。</p>'}<details><summary>资料读取限制与来源核对</summary><ul>${list(data.extraction.warnings)}</ul>${data.sources.map(source=>`<div class="ai-source"><b>${se(source.title)}</b><span>原资料第 ${source.pages.join('、')} 页 · ${source.quote_matched?'引文匹配':'引文待核对'}</span><blockquote>${se(source.quote)}</blockquote></div>`).join('')}<p class="supporting-copy">引文匹配只证明短句出现在来源文字中，不保证整节解释准确。图表内容需对照原文件。</p></details>`;
  if(studioAIObjectURL){URL.revokeObjectURL(studioAIObjectURL);studioAIObjectURL=null;}
  if(studioAISource&&studioAISource.name===data.source.filename)studioAIObjectURL=URL.createObjectURL(studioAISource);
  $('#studio-ai-original').classList.toggle('hidden',!studioAIObjectURL);$('#studio-ai-original').href=studioAIObjectURL||'#';
  $('#studio-ai-candidate').innerHTML=`<h2>${se(data.course.title)}</h2>`+studioLessonHTML(data.course,studioAIObjectURL,'file',true);
  $('#studio-ai-apply').disabled=false;
}
function studioAIRestoreReport(report){
  studioAIResult=report;studioAISource=null;
  if(studioAIObjectURL){URL.revokeObjectURL(studioAIObjectURL);studioAIObjectURL=null;}
  $('#studio-ai-result').classList.toggle('hidden',!report);
  if(report)aiRenderResult();
  aiControls();
}
$('#studio-ai-apply').onclick=()=>{
  if(!studioAIResult||studioAIBusy)return;
  if($('#studio-title').value.trim()&&!confirm('将 AI 草稿填入编辑器并替换当前文字？如需保留原稿，请先保存本机草稿。'))return;
  studioFill(studioAIResult.course);
  if(studioAISource&&studioAISource.name===studioAIResult.source.filename){const files=new DataTransfer();files.items.add(studioAISource);$('#course-file').files=files.files;}
  studioRefresh();studioTab('preview');
  $('#studio-draft-status').textContent='已采用 AI 草稿，尚未发布。难度、时长和补充任务仍需教师确认。';
  $('#studio-ai-review-note').classList.remove('hidden');
  showToast('草稿已填入，检查后再发布');
};
$('#studio-ai-export').onclick=()=>{
  if(!studioAIResult)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(studioAIResult,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='课程草稿与AI审阅.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
$('#studio-ai-edit').onclick=()=>studioTab('basics');
