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
    const result = await zhixingApi.getNotebook(n.courseId);
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
        const result=await zhixingApi.saveNotebook(n.courseId, sent);
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
  if (!n.saving) zhixingApi.saveNotebook(n.courseId, {notes:n.notes,task_draft:n.taskDraft,revision:n.revision}, {keepalive:true}).catch(()=>{});
});

async function loadExercise() {
  const lessonId=selectedLesson?.id,userId=state.user?.id,epoch=tutorEpoch;
  if (!lessonId) return;
  try {
    const result=await zhixingApi.getExercise(lessonId);
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
      const response=await zhixingApi.submitExercise(lessonId, {version:exercise.version,choice_id:choice});
      if (!studyIsCurrent(lessonId,userId,epoch)) return;
      exerciseState.result=response.result; renderExercise();
    } catch(error) { if (studyIsCurrent(lessonId,userId,epoch)) $("#exercise-error").textContent=error.message; }
    finally { if (studyIsCurrent(lessonId,userId,epoch)) $("#exercise-submit").disabled=false; }
  };
}
