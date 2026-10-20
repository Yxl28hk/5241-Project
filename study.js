/* Fixed practice, account notebooks, and the current conversation for each lesson. */
let notebookState = null;
let exerciseState = null;
let studyConversation = null;
let focusedKey = "overview";
let failedTutorRequest = null;

function studyIsCurrent(courseId, userId, epoch) {
  return selectedLesson?.id === courseId && state.user?.id === userId && tutorEpoch === epoch;
}
function resetStudyConversation() {
  studyConversation = null; focusedKey = "overview"; failedTutorRequest = null;
  $("#tutor-focus-label").textContent = "提问范围：整节课";
}
function prepareStudyTools() {
  if (notebookState?.timer) clearTimeout(notebookState.timer);
  notebookState = {courseId:selectedLesson.id, userId:state.user.id, revision:0, notes:"", taskDraft:"", dirty:false, loaded:false, conflict:false, saving:null, timer:null};
  exerciseState = null;
  let tools = $("#study-tools");
  if (!tools) {
    tools = document.createElement("div"); tools.id = "study-tools";
    tools.innerHTML = `<section class="fixed-exercise" id="fixed-exercise"><span class="section-kicker">检查理解</span><h3>本节固定练习</h3><p class="supporting-copy">提交后查看解析，可重新作答；不计入成绩，也不会自动标记课时完成。</p><div id="exercise-body"></div><p id="exercise-error" class="form-error" role="alert"></p><button class="text-action" id="exercise-reload" type="button">重新加载练习</button></section>
      <section class="lesson-notebook"><span class="section-kicker">我的课时笔记</span><h3>留下你的理解与疑问</h3><label class="field">笔记（最多 12000 字）<textarea id="lesson-notes" maxlength="12000" rows="6" placeholder="记录本节要点，或将助手回答保存到这里。"></textarea></label><p id="notebook-status" class="supporting-copy" role="status"></p><div class="lesson-actions"><button class="button button-ghost" type="button" id="notebook-save">保存笔记与任务草稿</button><button class="text-action" type="button" id="notebook-reload">重新载入账号版本</button></div><div id="notebook-recovery" class="notebook-recovery hidden"><p>发现本机未同步草稿与账号版本不同。请选择保留哪份内容。</p><button class="button button-ghost" type="button" id="notebook-use-local">使用本机草稿并保存</button><button class="text-action" type="button" id="notebook-use-account">保留账号版本</button></div></section>`;
    $("#lesson-progress").before(tools);
  }
  $("#exercise-body").textContent = "正在加载练习…";
  $("#exercise-error").textContent = "";
  $("#fixed-exercise").classList.remove("hidden");
  $("#lesson-notes").value = "";
  $("#lesson-notes").disabled = true;
  if ($("#lesson-task-response")) $("#lesson-task-response").disabled = true;
  $("#notebook-status").textContent = "正在恢复账号笔记与任务草稿…";
  $("#notebook-recovery").classList.add("hidden");
  $("#notebook-save").disabled = true;
  $("#lesson-notes").oninput = captureNotebook;
  if ($("#lesson-task-response")) $("#lesson-task-response").oninput = captureNotebook;
  $("#notebook-save").onclick = flushNotebook;
  $("#notebook-reload").onclick = () => loadNotebook(notebookState, tutorEpoch);
  $("#exercise-reload").onclick = loadExercise;
}
function backupKey(n) { return `zhixing:study-backup:${n.userId}:${n.courseId}`; }
function writeBackup(n) {
  try { sessionStorage.setItem(backupKey(n),JSON.stringify({notes:n.notes,taskDraft:n.taskDraft,revision:n.revision})); } catch { /* Account save remains available. */ }
}
function removeBackup(n) { try { sessionStorage.removeItem(backupKey(n)); } catch {} }
function notebookStatus(n, text) {
  if (notebookState !== n || n.userId !== state.user?.id) return;
  $("#notebook-status").textContent = text;
  if ($("#lesson-draft-status")) $("#lesson-draft-status").textContent = text;
}
function applyNotebook(n) {
  $("#lesson-notes").value = n.notes;
  $("#lesson-notes").disabled = false;
  if ($("#lesson-task-response")) { $("#lesson-task-response").value = n.taskDraft; $("#lesson-task-response").disabled = false; }
  $("#notebook-save").disabled = false;
}
async function loadNotebook(n, epoch) {
  if (!n || n.userId !== state.user?.id) return;
  const loadVersion=(n.loadVersion || 0)+1;
  n.loadVersion=loadVersion;
  if (n.saving) await n.saving;
  if (n.loadVersion !== loadVersion) return;
  if (n.dirty) writeBackup(n);
  n.loaded=false;
  $("#notebook-save").disabled = true;
  $("#lesson-notes").disabled=true;
  if ($("#lesson-task-response")) $("#lesson-task-response").disabled=true;
  try {
    const result = await api(`/api/courses/${n.courseId}/notebook`);
    if (!studyIsCurrent(n.courseId,n.userId,epoch) || notebookState !== n || n.loadVersion !== loadVersion) return;
    const remote = result.notebook;
    n.revision = remote.revision; n.notes = remote.notes; n.taskDraft = remote.task_draft;
    n.dirty = false; n.conflict = false; n.loaded = true;
    applyNotebook(n);
    let backup = null;
    try { backup = JSON.parse(sessionStorage.getItem(backupKey(n))); } catch {}
    if (!backup && !n.taskDraft && n.revision === 0) {
      try {
        const legacy = sessionStorage.getItem(`zhixing:lesson-draft:${n.userId}:${n.courseId}`);
        if (legacy) backup = {notes:n.notes,taskDraft:legacy,revision:0};
      } catch {}
    }
    if (backup && (typeof backup.notes !== "string" || typeof backup.taskDraft !== "string" || backup.notes.length>12000 || backup.taskDraft.length>4000)) backup = null;
    if (backup && (backup.notes !== n.notes || backup.taskDraft !== n.taskDraft)) {
      if (backup.revision === n.revision) {
        n.notes=backup.notes; n.taskDraft=backup.taskDraft; n.dirty=true;
        applyNotebook(n); await flushNotebook();
      } else {
        n.conflict=true;
        $("#notebook-recovery").classList.remove("hidden");
        notebookStatus(n,"存在未同步的本机内容；请选择版本后继续编辑。");
        $("#lesson-notes").disabled=true;
        if ($("#lesson-task-response")) $("#lesson-task-response").disabled=true;
        $("#notebook-save").disabled=true;
        $("#notebook-use-local").onclick=async()=>{
          n.notes=backup.notes; n.taskDraft=backup.taskDraft; n.dirty=true; n.conflict=false;
          applyNotebook(n); $("#notebook-recovery").classList.add("hidden"); await flushNotebook();
        };
        $("#notebook-use-account").onclick=()=>{
          n.conflict=false; removeBackup(n); applyNotebook(n); $("#notebook-recovery").classList.add("hidden");
          notebookStatus(n,"已保留账号版本。");
        };
      }
    } else {
      removeBackup(n);
      notebookStatus(n,"已恢复账号笔记；输入后自动保存，支持重新登录后继续。");
    }
  } catch(error) {
    if (notebookState === n) notebookStatus(n,`笔记未载入：${error.message}。请点击重新载入账号版本。`);
  }
}
function captureNotebook() {
  const n=notebookState;
  if (!n?.loaded || n.conflict || n.userId !== state.user?.id) return;
  n.notes=$("#lesson-notes").value;
  n.taskDraft=$("#lesson-task-response")?.value || "";
  n.dirty=true; writeBackup(n);
  notebookStatus(n,"有修改，正在等待自动保存…");
  clearTimeout(n.timer); n.timer=setTimeout(()=>flushNotebook(),700);
}
async function flushNotebook() {
  const n=notebookState;
  if (!n || n.userId !== state.user?.id) return true;
  clearTimeout(n.timer);
  if (n.conflict) return false;
  if (n.saving) { const ok=await n.saving; return ok && n.dirty ? flushNotebook() : ok; }
  if (!n.dirty) return true;
  n.saving=(async()=>{
    while (n.dirty) {
      const sent={notes:n.notes,task_draft:n.taskDraft,revision:n.revision};
      notebookStatus(n,"正在保存到账号…");
      try {
        const result=await api(`/api/courses/${n.courseId}/notebook`,jsonRequest("PATCH",sent));
        n.revision=result.notebook.revision;
        n.dirty=n.notes!==sent.notes || n.taskDraft!==sent.task_draft;
        if (n.dirty) writeBackup(n); else removeBackup(n);
        notebookStatus(n,n.dirty ? "正在保存最新修改…" : "笔记与任务草稿已保存到账号。");
      } catch(error) {
        n.conflict=error.status===409; writeBackup(n);
        notebookStatus(n,`保存失败：${error.message}${n.conflict ? " 请重新载入账号版本，选择要保留的内容。" : " 请点击保存重试，本机草稿已保留。"}`);
        return false;
      }
    }
    return true;
  })();
  try { return await n.saving; } finally { n.saving=null; }
}
window.addEventListener("pagehide",()=>{
  const n=notebookState;
  if (!n?.dirty || n.conflict || n.userId !== state.user?.id) return;
  writeBackup(n);
  if (!n.saving) fetch(`/api/courses/${n.courseId}/notebook`,{...jsonRequest("PATCH",{notes:n.notes,task_draft:n.taskDraft,revision:n.revision}),credentials:"same-origin",keepalive:true}).catch(()=>{});
});

async function loadExercise() {
  const lessonId=selectedLesson?.id,userId=state.user?.id,epoch=tutorEpoch;
  if (!lessonId) return;
  try {
    const result=await api(`/api/courses/${lessonId}/exercise`);
    if (!studyIsCurrent(lessonId,userId,epoch)) return;
    exerciseState=result;
    $("#exercise-error").textContent="";
    $("#fixed-exercise").classList.toggle("hidden",!result.exercise);
    if (result.exercise) renderExercise();
  } catch(error) { if (studyIsCurrent(lessonId,userId,epoch)) $("#exercise-error").textContent=error.message; }
}
function renderExercise() {
  const {exercise,result}=exerciseState;
  $("#exercise-body").innerHTML=`<form id="exercise-form"><fieldset><legend>${escapeHTML(exercise.question)}</legend>${exercise.choices.map(c=>`<label class="exercise-choice"><input type="radio" name="exercise-choice" value="${escapeHTML(c.id)}" ${result?.choice_id===c.id?"checked":""}> <span>${escapeHTML(c.text)}</span></label>`).join("")}</fieldset><div class="lesson-actions"><button type="submit" class="button button-primary" id="exercise-submit">${result?"再次提交":"提交并查看解析"}</button><button class="button button-ghost" type="button" data-task-hint="exercise">给我提示</button></div></form><div id="exercise-result" class="exercise-result ${result?"":"hidden"}" role="status"></div>`;
  if (result) {
    const correct=exercise.choices.find(c=>c.id===result.correct_choice_id);
    $("#exercise-result").textContent=`${result.correct?"回答正确":"还需要巩固"} · 已提交 ${result.attempts} 次。\n${result.explanation}\n参考选择：${correct?.text || ""}`;
  }
  $("#exercise-form").onsubmit=async event=>{
    event.preventDefault();
    const choice=$("#exercise-form input:checked")?.value;
    if (!choice) { $("#exercise-error").textContent="请先选择一个选项。"; return; }
    const lessonId=selectedLesson.id,userId=state.user.id,epoch=tutorEpoch;
    $("#exercise-submit").disabled=true; $("#exercise-error").textContent="";
    try {
      const response=await api(`/api/courses/${lessonId}/exercise`,jsonRequest("POST",{version:exercise.version,choice_id:choice}));
      if (!studyIsCurrent(lessonId,userId,epoch)) return;
      exerciseState.result=response.result; renderExercise();
    } catch(error) { if (studyIsCurrent(lessonId,userId,epoch)) $("#exercise-error").textContent=error.message; }
    finally { if (studyIsCurrent(lessonId,userId,epoch)) $("#exercise-submit").disabled=false; }
  };
}

function focusTitle(key) {
  const guide=selectedLesson?.guide;
  if (key.startsWith("section-")) return guide?.sections[Number(key.slice(8))]?.title || "整节课";
  return key==="example" ? guide?.example.title : key==="task" ? guide?.task.title : key==="exercise" ? "本节固定练习" : "整节课";
}
function setStudyFocus(key) {
  focusedKey=key;
  $("#tutor-focus-label").textContent=`提问范围：${focusTitle(key)}`;
  renderHintButtons();
}
function renderHintButtons() {
  const key=focusedKey==="exercise"?"exercise":"task";
  const steps=(studyConversation?.messages || []).filter(m=>m.role==="assistant" && m.context_key===key && m.action==="hint").map(m=>m.hint_step || 0);
  const step=steps.length?Math.max(...steps):0;
  $("#tutor-hint").textContent=step>=2?"两步提示已提供":`任务提示 ${step+1}`;
  $("#tutor-hint").disabled=tutorPending || !selectedLesson?.guide || step>=2;
  $("#tutor-reference").disabled=tutorPending || !selectedLesson?.guide;
}
function renderConversation(conversation) {
  studyConversation=conversation;
  $("#tutor-messages").replaceChildren();
  conversation.messages.forEach((message,index)=>{
    tutorMessage(message.role==="user"?"你":message.label || "学习助手",message.content);
    if (message.role==="assistant") {
      const button=document.createElement("button"); button.type="button";button.className="text-action save-answer";
      button.textContent="保存到本课笔记";button.dataset.saveAnswer=String(index);
      $("#tutor-messages").lastElementChild.append(button);
    }
  });
  if (!conversation.messages.length) $("#tutor-messages").innerHTML='<p class="supporting-copy">从当前课时提问，也可以在段落旁选择“解释这一段”。</p>';
  renderHintButtons();
}
async function restoreStudyConversation() {
  if (!selectedLesson || tutorPending) return;
  const lessonId=selectedLesson.id,userId=state.user.id,epoch=tutorEpoch;
  setTutorBusy(true);
  try {
    const result=await api(`/api/courses/${lessonId}/conversation`,{method:"POST"});
    if (!studyIsCurrent(lessonId,userId,epoch)) return;
    renderConversation(result.conversation);
    $("#tutor-status").textContent=result.conversation.messages.length ? "已恢复本课最近会话，可继续追问。" : "本课会话按账号保存。";
    failedTutorRequest=null;
    $("#tutor-retry-actions").classList.add("hidden");
  } catch(error) { if (studyIsCurrent(lessonId,userId,epoch)) $("#tutor-status").textContent=`会话恢复失败：${error.message}。可点击恢复账号会话重试。`; }
  finally { if (studyIsCurrent(lessonId,userId,epoch)) {setTutorBusy(false);renderHintButtons();} }
}
async function loadStudyTools() {
  await Promise.allSettled([loadNotebook(notebookState,tutorEpoch),loadExercise(),restoreStudyConversation()]);
}
async function sendStudyTutor(question,{retry=false,mode="auto",action="answer",hintStep=null,contextKey=null}={}) {
  if (!selectedLesson || tutorPending || !question.trim()) return;
  const origin={courseId:selectedLesson.id,userId:state.user.id,epoch:tutorEpoch};
  if (!studyConversation) await restoreStudyConversation();
  if (!studyConversation || !studyIsCurrent(origin.courseId,origin.userId,origin.epoch)) return;
  const epoch=tutorEpoch,lessonId=selectedLesson.id,userId=state.user.id;
  let payload;
  if (retry && failedTutorRequest && mode==="auto") payload=failedTutorRequest;
  else payload={course_id:lessonId,message:question,token:studyConversation.token,revision:studyConversation.revision,request_id:crypto.randomUUID(),context_key:contextKey || focusedKey,action,hint_step:hintStep,mode};
  if (retry && mode==="guided-demo" && failedTutorRequest) payload={...failedTutorRequest,mode,request_id:crypto.randomUUID()};
  if (!retry) tutorMessage("你",question);
  setTutorBusy(true);
  $("#tutor-status").textContent="正在结合所选内容整理回答…";
  $("#tutor-retry-actions").classList.add("hidden");
  tutorController=new AbortController();
  const controller=tutorController,timeout=setTimeout(()=>controller.abort(),30000);
  try {
    const result=await api("/api/tutor",{...jsonRequest("POST",payload),signal:controller.signal});
    if (!studyIsCurrent(lessonId,userId,epoch)) return;
    renderConversation(result.conversation);
    if ($("#tutor-question").value.trim()===question) $("#tutor-question").value="";
    failedTutorRequest=null;failedQuestion="";
    $("#tutor-status").textContent=result.mode==="live"?"回答与会话已保存，请结合课程核实。":"预设知识卡 / 提示已保存，未调用大模型。";
  } catch(error) {
    if (!studyIsCurrent(lessonId,userId,epoch)) return;
    failedTutorRequest=payload;failedQuestion=question;
    $("#tutor-question").value=question;
    $("#tutor-status").textContent=error.name==="AbortError"?"回答超时，可重试；相同请求不会重复写入。":error.message;
    $("#tutor-retry-actions").classList.remove("hidden");
  } finally {
    clearTimeout(timeout);
    if (studyIsCurrent(lessonId,userId,epoch)) {setTutorBusy(false);tutorController=null;renderHintButtons();}
  }
}
async function newStudyConversation() {
  if (!studyConversation || tutorPending) return;
  const lessonId=selectedLesson.id,userId=state.user.id,epoch=tutorEpoch;
  let ownEpoch=epoch;
  setTutorBusy(true);
  try {
    const result=await api(`/api/courses/${lessonId}/conversation`,jsonRequest("DELETE",{token:studyConversation.token,revision:studyConversation.revision}));
    if (!studyIsCurrent(lessonId,userId,epoch)) return;
    resetTutor(); renderConversation(result.conversation);
    ownEpoch=tutorEpoch;
    $("#tutor-status").textContent="已开启新对话。本课笔记和练习记录保留。";
    if (!notebookState?.loaded) await loadNotebook(notebookState,tutorEpoch);
    if (!exerciseState) await loadExercise();
  } catch(error) { if (studyIsCurrent(lessonId,userId,epoch)) $("#tutor-status").textContent=error.message; }
  finally {if(studyIsCurrent(lessonId,userId,ownEpoch)){setTutorBusy(false);renderHintButtons();}}
}
function showStudyTutor() {
  if ($("#tutor-panel").classList.contains("hidden")) $("#toggle-tutor").click();
  $("#tutor-panel").scrollIntoView({block:"nearest",behavior:"smooth"});
}
document.addEventListener("click",event=>{
  const context=event.target.closest("[data-ask-context]");
  const hint=event.target.closest("[data-task-hint]");
  if (context && !tutorPending) {
    setStudyFocus(context.dataset.askContext);showStudyTutor();
    sendStudyTutor("请解释当前选中的内容");
  } else if (hint && !tutorPending) {
    setStudyFocus(hint.dataset.taskHint);showStudyTutor();$("#tutor-hint").click();
  }
});
$("#clear-tutor-focus").onclick=()=>setStudyFocus("overview");
$("#tutor-restore").onclick=restoreStudyConversation;
$("#tutor-hint").onclick=()=>{
  const key=focusedKey==="exercise"?"exercise":"task";
  const steps=(studyConversation?.messages || []).filter(m=>m.action==="hint" && m.context_key===key).map(m=>m.hint_step || 0);
  const next=Math.min(2,(steps.length?Math.max(...steps):0)+1);
  setStudyFocus(key);sendStudyTutor(`给我第 ${next} 步提示`,{action:"hint",hintStep:next,contextKey:key});
};
$("#tutor-reference").onclick=()=>{
  const key=focusedKey==="exercise"?"exercise":"task";
  setStudyFocus(key);sendStudyTutor("查看参考思路",{action:"reference",contextKey:key});
};
$("#tutor-messages").addEventListener("click",async event=>{
  const button=event.target.closest("[data-save-answer]");
  if (!button) return;
  const message=studyConversation?.messages[Number(button.dataset.saveAnswer)],n=notebookState;
  if (!message || !n?.loaded || n.conflict || n.userId!==state.user?.id) {showToast("请先载入笔记或处理版本冲突");return;}
  const text=`${n.notes}${n.notes?"\n\n":""}【助手摘录 · ${focusTitle(message.context_key || "overview")}】\n${message.content}`;
  if (text.length>12000) {showToast("笔记超过 12000 字，请先精简内容");return;}
  $("#lesson-notes").value=text;captureNotebook();
  if (await flushNotebook()) showToast("回答已保存到本课笔记");
});
// The auth request can finish before this optional script is downloaded.
if (state.user && !pathData) refreshPath();
