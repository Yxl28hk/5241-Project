let analyticsRequest = 0;
function analyticsStatus(learner) {
  if (Number(learner.progress) >= 100) return "completed";
  return learner.last_opened_at || Number(learner.progress) > 0 ? "in_progress" : "not_started";
}
function analyticsEscape(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function analyticsDate(value) {
  if (!value) return "暂无记录";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "暂无记录" : date.toLocaleString("zh-CN", {month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"});
}
function renderAnalytics(learners, courseId, preview=false) {
  closeLearnerDetail(false);
  const complete = learners.filter(l => analyticsStatus(l) === "completed").length;
  const started = learners.filter(l => analyticsStatus(l) !== "not_started").length;
  const stats = [["当前加入",learners.length,"课程当前学习者"],["已开始",started,"包含已完成者"],["已完成",complete,"进度达到 100%"],["完成率",learners.length ? Math.round(complete/learners.length*100)+"%" : "—",learners.length ? "已完成 / 当前加入" : "暂无加入者"]];
  $("#analytics-stats").innerHTML=stats.map(([label,value,note])=>`<div class="analytics-stat"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join("");
  $("#analytics-preview-note").classList.toggle("hidden",!preview);
  $("#learners-description").textContent="了解学生参与和完成情况，找到需要跟进的学习者。";
  const renderRows=()=>{
    const query=$("#analytics-search").value.trim().toLocaleLowerCase();
    const status=$("#analytics-filter").value;
    const visible=learners.filter(l=>String(l.name).toLocaleLowerCase().includes(query)&&(status==="all"||analyticsStatus(l)===status));
    $("#analytics-result-count").textContent=`显示 ${visible.length} / ${learners.length} 位学习者 · 上方统计不受筛选影响`;
    $("#learners-list").innerHTML=visible.length ? visible.map(l=>{
      const progress=Math.max(0,Math.min(100,Number(l.progress)||0));
      const label={completed:"已完成",in_progress:"学习中",not_started:"未开始"}[analyticsStatus(l)];
      return `<article class="analytics-row"><button type="button" class="analytics-person learner-detail-trigger" data-learner-id="${Number(l.id)}" aria-label="查看${analyticsEscape(l.name)}的学习详情"><span class="author-avatar">${analyticsEscape(String(l.name).slice(0,1))}</span><div><strong>${analyticsEscape(l.name)}</strong><small>加入 ${analyticsEscape(analyticsDate(l.enrolled_at))} · 查看详情 →</small></div></button><div class="analytics-progress"><div><span class="analytics-status ${analyticsStatus(l)}">${label}</span><b>${progress}%</b></div><progress value="${progress}" max="100" aria-label="${analyticsEscape(l.name)}的学习进度">${progress}%</progress></div><div class="analytics-visit"><small>最近打开课时</small><span>${analyticsEscape(analyticsDate(l.last_opened_at))}</span></div>${preview ? "" : `<button class="delete-course" data-remove-learner-id="${Number(l.id)}" type="button">移除</button>`}</article>`;
    }).join("") : `<div class="space-empty">${learners.length ? "没有符合条件的学生，试试其他昵称或状态。" : "还没有学生加入这门课程。学生加入后，学习记录会显示在这里。"}</div>`;
    $$("#learners-list [data-learner-id]").forEach(button=>button.onclick=()=>{
      const learner=learners.find(l=>String(l.id)===button.dataset.learnerId);
      if(learner)openLearnerDetail(learner,courseId,preview,button);
    });
    $$("#learners-list [data-remove-learner-id]").forEach(button=>button.onclick=async()=>{
      const learner=learners.find(l=>String(l.id)===button.dataset.removeLearnerId);
      if(!learner||!confirm(`确定将 ${learner.name} 移出这门课程吗？`))return;
      button.disabled=true;
      try{await zhixingApi.request(`/api/courses/${courseId}/learners/${learner.id}`,{method:"DELETE"});await openLearners(courseId);}
      catch(error){showToast(error.message);button.disabled=false;}
    });
  };
  $("#analytics-search").oninput=renderRows;$("#analytics-filter").onchange=renderRows;
  $("#analytics-refresh").disabled=false;
  $("#analytics-refresh").onclick=()=>preview ? renderAnalytics(learners,courseId,true) : openLearners(courseId);
  renderRows();
}
async function openLearners(courseId) {
  closeLearnerDetail(false);
  const request=++analyticsRequest;
  const course=state.courses.find(c=>String(c.id)===String(courseId));
  $("#learners-title").textContent=`${course?.title || "课程"} · 学习情况`;
  $("#analytics-search").value="";$("#analytics-filter").value="all";
  $("#analytics-stats").replaceChildren();$("#analytics-result-count").textContent="";
  $("#analytics-preview-note").classList.add("hidden");
  $("#analytics-search").oninput=null;$("#analytics-filter").onchange=null;
  $("#learners-description").textContent="正在加载课程数据…";
  $("#learners-list").textContent="正在获取学习记录…";
  $("#analytics-refresh").disabled=true;openModal("#learners-modal");
  try {
    const result=await zhixingApi.request(`/api/courses/${courseId}/learners`);
    if(request!==analyticsRequest)return;
    renderAnalytics(result.learners,courseId);
  } catch(error) {
    if(request!==analyticsRequest)return;
    $("#learners-description").textContent="暂时无法加载学习情况";
    $("#learners-list").textContent=error.message;
    $("#analytics-refresh").disabled=false;$("#analytics-refresh").onclick=()=>openLearners(courseId);
  }
}
function openAnalyticsPreview() {
  ++analyticsRequest;
  $("#learners-title").textContent="Git 与团队协作 · 学习情况";
  $("#analytics-search").value="";$("#analytics-filter").value="all";
  const examples=[
    {id:1,name:"示例学生 · 小林",progress:100,last_opened_at:"2026-10-22T09:10:00+08:00"},
    {id:2,name:"示例学生 · 小陈",progress:50,last_opened_at:"2026-10-22T08:30:00+08:00"},
    {id:3,name:"示例学生 · 小周",progress:0,last_opened_at:null},
    {id:4,name:"示例学生 · 小许",progress:100,last_opened_at:"2026-10-21T17:20:00+08:00"},
    {id:5,name:"示例学生 · 小吴",progress:0,last_opened_at:"2026-10-22T10:00:00+08:00"}
  ].map(l=>({...l,enrolled_at:"2026-10-20T14:00:00+08:00"}));
  renderAnalytics(examples,null,true);openModal("#learners-modal");
}
let learnerDetailRequest=0, learnerDetailTrigger=null;
function closeLearnerDetail(restoreFocus=true){
  ++learnerDetailRequest;
  $("#learner-detail").classList.add("hidden");$("#analytics-overview").classList.remove("hidden");
  $("#learner-detail-content").replaceChildren();
  if(restoreFocus&&learnerDetailTrigger?.isConnected)learnerDetailTrigger.focus();
}
$("#learner-back").onclick=()=>closeLearnerDetail();
function renderLearnerDetail(data,preview){
  const l=data.learner, rows=data.exercises;
  const status={not_started:"未开始",in_progress:"学习中",completed:"已完成"}[analyticsStatus(l)];
  const count=rows.reduce((total,row)=>total+Number(row.attempts||0),0);
  const progress=Math.max(0,Math.min(100,Number(l.progress)||0));
  $("#learner-detail-content").innerHTML=`
    ${preview?'<div class="analytics-notice">示例学习档案 · 仅供本地界面预览</div>':''}
    <div class="learner-heading"><span class="learner-avatar">${analyticsEscape(String(l.name).slice(0,1))}</span><div><span class="section-kicker">LEARNER OVERVIEW</span><h2>${analyticsEscape(l.name)}</h2><p>${analyticsEscape(data.course.title)} · 仅显示本课程记录</p></div></div>
    <div class="analytics-stats learner-stats"><div class="analytics-stat"><span>课程进度</span><strong>${progress}%</strong><small>${status}</small></div><div class="analytics-stat"><span>练习提交次数</span><strong>${count}</strong><small>各题目版本提交次数合计</small></div><div class="analytics-stat"><span>最近一次练习</span><strong class="result-word">${rows.length?(rows[0].correct?'答对':'待巩固'):'暂无记录'}</strong><small>${rows.length?analyticsEscape(analyticsDate(rows[0].updated_at)):'尚无练习提交'}</small></div></div>
    <section class="learner-section"><h3>学习时间记录</h3><dl class="learner-dates"><div><dt>加入课程</dt><dd>${analyticsEscape(analyticsDate(l.enrolled_at))}</dd></div><div><dt>最近打开课时</dt><dd>${analyticsEscape(analyticsDate(l.last_opened_at))}</dd></div><div><dt>学习记录最近更新</dt><dd>${analyticsEscape(analyticsDate(l.updated_at))}</dd></div></dl><p class="analytics-definition">当前未记录有效学习时长，以上时间不能用于推算学习时长或完成时间。</p></section>
    <section class="learner-section"><h3>练习表现</h3><p class="analytics-definition">展示每个题目版本最后一次提交及累计次数，不是完整答题历史。</p>${rows.length?rows.map(row=>`<article class="learner-exercise"><div><span class="analytics-status ${row.correct?'completed':'in_progress'}">${row.correct?'最近回答正确':'建议复习'}</span><small>累计提交 ${Number(row.attempts)||0} 次</small></div><h4>${analyticsEscape(row.question)}</h4><p><b>最近选择：</b>${analyticsEscape(row.answer)}</p><small>提交时间：${analyticsEscape(analyticsDate(row.updated_at))}</small></article>`).join(''):'<div class="space-empty">暂无练习提交记录。未提交不代表答错，也不代表未阅读。</div>'}</section>
    <p class="learner-boundary">此处用于查看课程参与和练习情况；私人笔记、任务草稿和 AI 对话内容不在教师详情中展示。</p>`;
}
async function openLearnerDetail(learner,courseId,preview,trigger){
  const request=++learnerDetailRequest;learnerDetailTrigger=trigger;
  $("#analytics-overview").classList.add("hidden");$("#learner-detail").classList.remove("hidden");
  $("#learner-detail-content").textContent="正在加载学习详情…";
  $("#learners-modal .modal").scrollTop=0;$("#learner-back").focus();
  try{
    let data;
    if(preview){
      const practiced=Number(learner.progress)>0;
      data={learner:{...learner,updated_at:learner.last_opened_at||learner.enrolled_at},course:{title:"Git 与团队协作"},exercises:practiced?[{question:"完成一次页面修改后，PR 说明应该包含哪些内容？",answer:learner.progress===100?"说明修改内容、已验证范围，以及尚未验证的情况。":"说明修改内容即可，不需要写验证方法。",correct:learner.progress===100,attempts:learner.id===1?2:1,updated_at:learner.last_opened_at}]:[]};
    }else data=await zhixingApi.request(`/api/courses/${courseId}/learners/${learner.id}`);
    if(request!==learnerDetailRequest)return;
    renderLearnerDetail(data,preview);
  }catch(error){
    if(request!==learnerDetailRequest)return;
    $("#learner-detail-content").replaceChildren();
    const message=document.createElement('p');message.textContent=error.message;
    const retry=document.createElement('button');retry.className='detail-back';retry.textContent='重新加载';retry.onclick=()=>openLearnerDetail(learner,courseId,preview,trigger);
    $("#learner-detail-content").append(message,retry);
  }
}

if(new URLSearchParams(location.search).get("preview")==="analytics")window.addEventListener("load",openAnalyticsPreview,{once:true});
