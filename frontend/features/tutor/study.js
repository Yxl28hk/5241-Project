function focusTitle(key) {
  const guide=selectedLesson?.guide;
  const studio=selectedLesson?.studio;
  if (studio) {
    if (key.startsWith("section-")) return studio.sections?.[Number(key.slice(8))]?.title || "整节课";
    return key==="example" ? "课程示例" : key==="task" ? "动手任务" : "整节课";
  }
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
  $("#tutor-hint").disabled=tutorPending || !(selectedLesson?.guide || selectedLesson?.studio?.task) || step>=2;
  $("#tutor-reference").disabled=tutorPending || !(selectedLesson?.guide || (selectedLesson?.studio?.task && selectedLesson?.studio?.reference));
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
    const result=await zhixingApi.restoreConversation(lessonId);
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
  $("#tutor-status").textContent=payload.action==="reference" ? "正在读取已发布的参考思路…" : payload.mode==="guided-demo" ? "正在读取课程原文 / 知识卡…" : "正在读取本课资料并请求 AI，可能需要约 1–2 分钟…";
  $("#tutor-retry-actions").classList.add("hidden");
  tutorController=new AbortController();
  const controller=tutorController,timeout=setTimeout(()=>controller.abort(),180000);
  try {
    const result=await zhixingApi.askTutor(payload, {signal:controller.signal});
    if (!studyIsCurrent(lessonId,userId,epoch)) return;
    renderConversation(result.conversation);
    if ($("#tutor-question").value.trim()===question) $("#tutor-question").value="";
    failedTutorRequest=null;failedQuestion="";
    $("#tutor-status").textContent=result.mode==="live"?"回答与会话已保存，请结合课程核实。":"课程原文 / 预设提示已保存，未调用大模型。";
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
    const result=await zhixingApi.resetConversation(lessonId, {token:studyConversation.token,revision:studyConversation.revision});
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
