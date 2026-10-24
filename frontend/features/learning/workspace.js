const goalLabels = {collaboration:"协作开发入门", quality:"测试与发布", engineering:"软件工程实践"};
const levelLabels = {beginner:"零基础", intermediate:"入门", experienced:"有经验"};
const statusLabels = {not_started:"未开始", in_progress:"学习中", completed:"已完成"};

function lessonStatus(lesson) {
  if (lesson.progress === 100) return "completed";
  return lesson.enrolled || lesson.last_opened_at || lesson.progress > 0 ? "in_progress" : "not_started";
}

function renderWorkspace() {
  const profile = pathData?.profile || {};
  $("#workbench-greeting").textContent = state.user ? `${state.user.name}，按自己的节奏，把下一步学扎实。` : "选择一个目标，让每一次学习都有方向。";
  $("#profile-overview").innerHTML = `<div><dt>学习目标</dt><dd>${escapeHTML(goalLabels[profile.goal] || "尚未填写")}</dd></div><div><dt>基础水平</dt><dd>${escapeHTML(levelLabels[profile.level] || "待了解")}</dd></div><div><dt>每周投入</dt><dd>${profile.weekly_hours ? `${profile.weekly_hours} 小时` : "按自己的节奏"}</dd></div>`;
  $("#edit-learning-profile").textContent = profile.goal || profile.level ? "修改学习画像 ↗" : "完善学习画像 ↗";
  const active = pathData?.active_path;
  const resume = pathData?.modules.find(m => m.id === pathData.resume_course_id);
  const next = pathData?.modules.find(m => m.id === pathData.next_course_id);
  const complete = active && pathData.modules.length > 0 && !next;
  $("#resume-eyebrow").textContent = complete ? "READY TO PRACTICE" : active ? "CONTINUE LEARNING" : "YOUR NEXT STEP";
  $("#resume-title").textContent = complete ? "路径已完成，来一次实践挑战" : resume && active ? resume.title : "从一条适合你的路径开始";
  $("#resume-description").textContent = active ? `${pathData.completed} / ${pathData.modules.length} 节已完成 · 完成率 ${pathData.completion_percent}%${complete ? "。你可以挑战发布情境，或回顾课程。" : resume ? ` · ${pathData.has_resume ? "最近学习" : "建议开始"} · ${resume.duration}` : ""}` : "选择路径后，学习位置和完成状态会保存在你的账号中。";
  $("#resume-path-label").textContent = active ? `当前路径：${active.title}` : "建议先完善目标与基础，再查看路径目录；也可以直接选择。";
  $("#resume-learning").textContent = complete ? "开始实践挑战 →" : active ? pathData.has_resume ? "继续学习 →" : "开始学习 →" : "选择学习路径 →";
  $("#resume-view-path").classList.toggle("hidden", !active);
  $("#next-lesson-label").textContent = active ? next ? `下一节未完成：${next.title}` : "路径已完成！可以回顾课程，或挑战 Release Rescue。" : "支持切换路径，已完成的共同课时会复用进度。";
}

function renderPath() {
  renderWorkspace();
  if (!pathData) return;
  const recommended = pathData.recommendations[0]?.path_id;
  const ranking = new Map(pathData.recommendations.map((item, index) => [item.path_id, index]));
  const orderedCatalog = [...pathData.catalog].sort((a, b) => Number(b.id === pathData.active_path_id) - Number(a.id === pathData.active_path_id) || (ranking.get(a.id) ?? 99) - (ranking.get(b.id) ?? 99));
  $("#path-catalog").innerHTML = orderedCatalog.map(path => {
    const recommendation = pathData.recommendations.find(r => r.path_id === path.id);
    const active = path.id === pathData.active_path_id;
    return `<article class="catalog-card ${active ? "is-current" : ""}"><div class="catalog-tags"><span>${escapeHTML(path.level_label)}</span>${active ? '<span class="current-tag">当前路径</span>' : recommended === path.id && (pathData.profile.goal || pathData.profile.level) ? '<span class="current-tag">优先推荐</span>' : ""}</div><h3>${escapeHTML(path.title)}</h3><p>${escapeHTML(path.description)}</p><p class="path-focus">${escapeHTML(path.focus)}</p><p class="path-deliverable">学习成果：${escapeHTML(path.deliverable)}</p><p class="catalog-meta">${path.total} 节短课 · 阅读约 ${path.minutes} 分钟 · 含 ${path.total} 道固定自测</p><p class="recommendation-reason">${escapeHTML(recommendation?.reason || "部分课程暂不可用，请稍后再试。")}</p><button class="button ${active ? "button-primary" : "button-ghost"}" data-path-detail="${path.id}">${active ? "查看当前路径" : "查看目录与选择"} ↗</button></article>`;
  }).join("");
  $("#active-path-title").textContent = pathData.active_path?.title || "先选择一条学习路径";
  $("#path-summary").textContent = pathData.active_path ? `${pathData.completed} / ${pathData.modules.length} 节已完成 · 完成率 ${pathData.completion_percent}%（由你确认）` : "可以先查看目录再选择；填写画像后会更新推荐，不会自动替你选课。";
  $("#path-progress").value = pathData.active_path ? pathData.completion_percent : 0;
  $("#path-list").innerHTML = pathData.active_path ? pathData.modules.map((m, i) => `<button class="path-card ${m.progress === 100 ? "finished" : ""}" data-lesson="${m.id}"><span class="path-number">${m.progress === 100 ? "✓" : String(i + 1).padStart(2, "0")}</span><span><small>${escapeHTML(m.stage)} · ${escapeHTML(m.duration)}${m.id === pathData.next_course_id ? " · 下一节未完成" : ""}</small><strong>${escapeHTML(m.title)}</strong><span>${escapeHTML(m.description)}</span><small class="lesson-state state-${lessonStatus(m)}">${statusLabels[lessonStatus(m)]}</small></span><span>↗</span></button>`).join("") : '<div class="path-empty">先从上方选择一条路径。你也可以在下方发现课程中自由学习。</div>';
  $("#mission-best").textContent = pathData.mission.best_score === null ? "尚无完成成绩" : `历史最高 ${pathData.mission.best_score} / 100`;
}

async function refreshPath() {
  const requestVersion = ++pathRequestVersion;
  const userId = state.user?.id;
  $("#path-error").textContent = "";
  if (!state.user) {
    pathData = null;
    selectedLesson = null;
    lessonRequestVersion++;
    resetTutor();
    renderWorkspace();
    $("#path-summary").textContent = "登录后保存学习画像、学习进度和任务成绩。";
    $("#path-list").innerHTML = '<button class="button button-primary" id="path-login">登录 / 注册，开启学习</button>';
    $("#path-login").onclick = () => openModal("#auth-modal");
    $("#path-catalog").replaceChildren();
    $("#active-path-title").textContent = "开启你的学习路径";
    $("#path-progress").value = 0;
    $("#mission-best").textContent = "尚未开始";
    return false;
  }
  try {
    const result = await zhixingApi.getLearningPath();
    if (requestVersion !== pathRequestVersion || userId !== state.user?.id) return false;
    pathData = result;
    renderPath();
    return true;
  } catch (error) {
    if (requestVersion === pathRequestVersion && userId === state.user?.id) {
      $("#path-error").textContent = `${error.message}。可点击“刷新进度”重试；已保存的数据不会丢失。`;
      if (!pathData) $("#path-summary").textContent = "学习数据暂未加载。";
    }
    return false;
  }
}

async function openLearningProfile() {
  if (!requireLogin("设置学习画像")) return;
  if (!pathData && !await refreshPath()) return;
  const profile = pathData.profile;
  $("#learning-goal").value = profile.goal;
  $("#learning-level").value = profile.level;
  $("#learning-hours").value = profile.weekly_hours ?? "";
  $("#learning-profile-error").textContent = "";
  openModal("#learning-profile-modal");
}
$("#edit-learning-profile").onclick = openLearningProfile;
$("#view-enrolled-courses").onclick = () => openSpace("learning");
$("#learning-profile-form").onsubmit = async event => {
  event.preventDefault();
  const userId = state.user?.id;
  $("#learning-profile-save").disabled = true;
  $("#learning-profile-error").textContent = "";
  try {
    await zhixingApi.updateLearningProfile({goal:$("#learning-goal").value, level:$("#learning-level").value, weekly_hours:$("#learning-hours").value === "" ? null : Number($("#learning-hours").value)});
    if (userId !== state.user?.id) return;
    closeModals();
    await refreshPath();
    $("#learning-path").scrollIntoView({behavior:"smooth"});
    showToast("学习画像已保存，推荐已更新；当前路径保持不变");
  } catch (error) { $("#learning-profile-error").textContent = error.message; }
  finally { $("#learning-profile-save").disabled = false; }
};

function showPathDetail(pathId) {
  const path = pathData?.catalog.find(p => p.id === pathId);
  if (!path) return;
  detailPathId = path.id;
  $("#path-detail-title").textContent = path.title;
  $("#path-detail-description").textContent = path.description;
  $("#path-detail-outcome").textContent = `学习产出：${path.outcome} 具体成果：${path.deliverable}`;
  $("#path-detail-fit").textContent = `适合${path.level_label} · ${path.total} 节 · 约 ${path.minutes} 分钟。${pathData.profile.level === "beginner" && path.level !== "beginner" ? "你填写的是零基础，建议先学协作入门，也可以继续选择。" : ""}${pathData.active_path_id && pathData.active_path_id !== path.id ? "选择后将切换当前路径，保留已有学习记录。" : "可以自由浏览课时，不强制锁定顺序。"}`;
  $("#path-detail-lessons").innerHTML = path.modules.map((m,index) => `<li><small>第 ${index + 1} 节 · ${escapeHTML(m.stage)}</small><strong>${escapeHTML(m.title)}</strong><p>${escapeHTML(m.description)}</p><span>${escapeHTML(m.duration)} · ${m.progress === 100 ? "已完成，可复用" : statusLabels[lessonStatus(m)]}</span></li>`).join("");
  $("#path-select-confirm").textContent = path.id === pathData.active_path_id ? "继续学习当前路径 →" : "确认选择这条路径 →";
  $("#path-select-confirm").disabled = !path.available;
  $("#path-detail-error").textContent = path.available ? "" : "部分课程已下架，暂时无法选择。";
  openModal("#path-detail-modal");
}
$("#path-catalog").onclick = event => {
  const button = event.target.closest("[data-path-detail]");
  if (button) showPathDetail(button.dataset.pathDetail);
};
$("#path-select-confirm").onclick = async () => {
  const pathId = detailPathId;
  $("#path-select-confirm").disabled = true;
  try {
    if (pathId !== pathData.active_path_id) await zhixingApi.selectLearningPath(pathId);
    if (!await refreshPath()) throw new Error("路径已选择，学习列表加载失败，请刷新重试");
    closeModals();
    if (pathData.resume_course_id) await openLesson(pathData.resume_course_id);
  } catch (error) { $("#path-detail-error").textContent = error.message; }
  finally { $("#path-select-confirm").disabled = false; }
};

function lessonSiblings() {
  const modules = pathData?.active_path?.modules || pathData?.modules || [];
  return modules.some(m => m.id === selectedLesson?.id) ? modules : selectedLesson ? [selectedLesson] : [];
}

function renderLessonContent(lesson) {
  if(lesson.studio){
    $("#lesson-content").classList.remove("hidden");$("#lesson-copy").classList.add("hidden");$("#lesson-reflection").classList.add("hidden");
    const fileType=lesson.file_url && /\.(mp4|mov)$/i.test(lesson.file_url) ? "video" : "file";
    $("#lesson-content").innerHTML=studioLessonHTML(lesson.studio,lesson.file_url,fileType,false);
    return;
  }

  const guide = lesson.guide;
  $("#lesson-content").classList.toggle("hidden", !guide);
  $("#lesson-copy").classList.toggle("hidden", Boolean(guide));
  $("#lesson-reflection").classList.toggle("hidden", Boolean(guide));
  if (!guide) {
    $("#lesson-content").replaceChildren();
    $("#lesson-copy").textContent = lesson.lesson || lesson.description;
    return;
  }
  const list = items => items.map(item => `<li>${escapeHTML(item)}</li>`).join("");
  $("#lesson-content").innerHTML = `
    <section class="lesson-objectives"><span class="section-kicker">本节目标</span><h3>这节课，你将练习什么？</h3><ul>${list(guide.objectives)}</ul></section>
    <section class="lesson-scenario"><span class="section-kicker">真实情境</span><h3>先看一个团队里的问题</h3><p>${escapeHTML(guide.scenario)}</p></section>
    <section class="lesson-explanation"><span class="section-kicker">核心讲解</span>${guide.sections.map((section,index) => `<div class="explanation-part"><h3>${escapeHTML(section.title)}</h3><p>${escapeHTML(section.body)}</p><button class="text-action context-action" type="button" data-ask-context="section-${index}">解释这一段 ↗</button></div>`).join("")}</section>
    <section class="lesson-example"><span class="section-kicker">操作示例</span><h3>${escapeHTML(guide.example.title)}</h3><pre><code>${escapeHTML(guide.example.code)}</code></pre><p class="supporting-copy">${escapeHTML(guide.example.note)}</p><button class="text-action context-action" type="button" data-ask-context="example">解释这个示例 ↗</button></section>
    <section class="lesson-task"><span class="section-kicker">动手任务</span><h3>${escapeHTML(guide.task.title)}</h3><p>${escapeHTML(guide.task.instruction)}</p><label class="field">我的思路（可选）<textarea id="lesson-task-response" maxlength="4000" rows="5" placeholder="试着写下你的方案，再展开参考思路进行对照。"></textarea></label><p id="lesson-draft-status" class="supporting-copy" role="status">草稿仅保存在当前浏览器标签页，刷新可恢复；不提交评分。</p><h4>完成前自查</h4><ul>${list(guide.task.checklist)}</ul><details class="lesson-reference"><summary>写好后，展开参考思路</summary><p>${escapeHTML(guide.task.reference)}</p></details><div class="ai-review"><h4>检查 AI 的建议</h4><p>${escapeHTML(guide.task.ai_suggestion)}</p><details class="lesson-reference"><summary>这条建议缺少什么？</summary><p>${escapeHTML(guide.task.ai_feedback)}</p></details></div></section>
    <section class="lesson-recap"><span class="section-kicker">本节回顾</span><ul>${list(guide.takeaways)}</ul></section>`;
  $("#lesson-draft-status").textContent = "任务草稿将与本课笔记一起保存到账号，不提交评分。";
  $("#lesson-content .lesson-task").insertAdjacentHTML("beforeend", '<div class="lesson-actions"><button type="button" class="button button-ghost" data-task-hint="task">给我分步提示</button></div>');
}

function renderLessonState() {
  if (!selectedLesson) return;
  const done = selectedLesson.progress === 100;
  for (const selector of ["#complete-lesson", "#restart-lesson", "#completion-next"]) $(selector).disabled = progressSaving || lessonOpening;
  $("#lesson-progress").textContent = progressSaving ? "正在保存，请稍候…" : `${statusLabels[lessonStatus(selectedLesson)]} · 学习位置已保存${done ? " · 完成状态已保存" : ""}`;
  $("#complete-lesson").classList.toggle("hidden", done);
  $("#restart-lesson").classList.toggle("hidden", !done);
  $("#completion-feedback").classList.toggle("hidden", !done);
  completionTarget = null;
  if (!done) return;
  const siblings = lessonSiblings();
  const index = siblings.findIndex(m => m.id === selectedLesson.id);
  const next = [...siblings.slice(index + 1), ...siblings.slice(0, index)].find(m => m.progress < 100);
  const inPath = pathData?.active_path?.modules.some(m => m.id === selectedLesson.id);
  const pathComplete = inPath && siblings.length > 0 && siblings.every(m => m.id === selectedLesson.id || m.progress === 100);
  $("#completion-title").textContent = pathComplete ? "本节已完成，路径也已完成！" : "本节已完成";
  $("#completion-summary").textContent = "完成状态已保存。回顾本节要点，再选择下一步。";
  $("#completion-takeaways").innerHTML = (selectedLesson.guide?.takeaways || [selectedLesson.description]).map(item => `<li>${escapeHTML(item)}</li>`).join("");
  if (next) {
    completionTarget = {type:"lesson", id:next.id};
    const isFollowing = siblings.indexOf(next) > index;
    $("#completion-next-label").textContent = `${isFollowing ? "下一节" : "还有未完成课时"}：${next.title} · ${next.duration}`;
    $("#completion-next").textContent = isFollowing ? "继续下一节 →" : "继续未完成课时 →";
  } else if (pathComplete) {
    completionTarget = {type:"mission"};
    $("#completion-next-label").textContent = "把课程内容用于四个发布决策。Release Rescue · 约 3 分钟。";
    $("#completion-next").textContent = "开始实践挑战 →";
  } else {
    completionTarget = {type:"workspace"};
    $("#completion-next-label").textContent = "本课已完成，可以回到工作台选择下一项学习内容。";
    $("#completion-next").textContent = "返回学习工作台 →";
  }
}

function renderLessonNavigation() {
  if (!selectedLesson) return;
  const siblings = lessonSiblings();
  const index = siblings.findIndex(m => m.id === selectedLesson.id);
  $("#lesson-directory").innerHTML = siblings.map((m,index) => `<button class="directory-item ${m.id === selectedLesson.id ? "is-selected" : ""}" data-lesson="${m.id}" ${m.id === selectedLesson.id ? 'aria-current="page"' : ""}><span>${m.progress === 100 ? "✓" : lessonStatus(m) === "in_progress" ? "◐" : "○"}</span><span>第 ${index + 1} 节 · ${escapeHTML(m.title)}<small>${statusLabels[lessonStatus(m)]}</small></span></button>`).join("");
  $("#previous-lesson").disabled = index <= 0 || progressSaving || lessonOpening;
  $("#next-lesson").disabled = index < 0 || index >= siblings.length - 1 || progressSaving || lessonOpening;
}

async function openLesson(courseId) {
  if (!requireLogin("学习课程") || progressSaving || lessonOpening) return;
  const userId = state.user.id;
  lessonOpening = true;
  if (typeof flushNotebook === "function" && !await flushNotebook()) {
    lessonOpening = false;
    showToast("请先保存笔记或处理版本冲突，再切换课时");
    renderLessonState(); renderLessonNavigation();
    return;
  }
  if (state.user?.id !== userId) { lessonOpening=false; return; }
  const requestVersion = ++lessonRequestVersion;
  lessonOpening = true;
  renderLessonState();
  renderLessonNavigation();
  try {
    // Save visit first. Completion is never inferred from opening a page.
    await zhixingApi.startLearning(courseId);
    const result = await zhixingApi.getLesson(courseId);
    if (requestVersion !== lessonRequestVersion || userId !== state.user?.id) return;
    selectedLesson = result.lesson;
    resetTutor();
    $("#lesson-title").textContent = selectedLesson.title;
    $("#lesson-duration").textContent = `阅读参考：${selectedLesson.duration} · 动手时间按个人节奏 · 学习位置随账号保存`;
    renderLessonContent(selectedLesson);
    prepareStudyTools();
    $("#lesson-question").textContent = selectedLesson.question || "学习后，请用自己的话总结一个关键概念。";
    pendingProgressValue = null;
    $("#progress-error").textContent = "";
    $("#progress-retry").classList.add("hidden");
    $("#completion-refresh-note").textContent = "";
    $("#lesson-resource").classList.toggle("hidden", !selectedLesson.file_url);
    $("#lesson-resource").href = selectedLesson.file_url || "#";
    $("#tutor-context").textContent = `当前课时：${selectedLesson.title}`;
    $("#tutor-panel").classList.remove("hidden");
    $("#toggle-tutor").setAttribute("aria-expanded", "true");
    $("#toggle-tutor").textContent = "收起学习助手";
    $(".lesson-layout").classList.remove("tutor-collapsed");
    renderLessonNavigation();
    renderLessonState();
    openModal("#lesson-modal");
    $(".lesson-modal").scrollTop = 0;
    await Promise.allSettled([refreshPath(), loadStudyTools()]);
  } catch (error) { showToast(error.message); }
  finally {
    lessonOpening = false;
    renderLessonNavigation();
    renderLessonState();
  }
}
$("#resume-learning").onclick = () => {
  if (!requireLogin("开始学习")) return;
  if (pathData?.active_path && pathData.modules.length && pathData.next_course_id === null) startMission();
  else if (pathData?.active_path && pathData.resume_course_id) openLesson(pathData.resume_course_id);
  else $("#learning-path").scrollIntoView({behavior:"smooth"});
};
$("#resume-view-path").onclick = () => { if (pathData?.active_path_id) showPathDetail(pathData.active_path_id); };
for (const selector of ["#path-list", "#lesson-directory"]) $(selector).onclick = event => {
  const button = event.target.closest("[data-lesson]");
  if (button) openLesson(Number(button.dataset.lesson));
};
for (const [selector, delta] of [["#previous-lesson", -1], ["#next-lesson", 1]]) $(selector).onclick = () => {
  const siblings = lessonSiblings();
  const index = siblings.findIndex(m => m.id === selectedLesson?.id);
  if (siblings[index + delta]) openLesson(siblings[index + delta].id);
};
$("#path-refresh").onclick = refreshPath;
$("#path-nav").onclick = () => { if (state.user) $("#learning-path").scrollIntoView({behavior:"smooth"}); };
$("#toggle-tutor").onclick = () => {
  const collapsed = $("#tutor-panel").classList.toggle("hidden");
  $(".lesson-layout").classList.toggle("tutor-collapsed", collapsed);
  $("#toggle-tutor").setAttribute("aria-expanded", String(!collapsed));
  $("#toggle-tutor").textContent = collapsed ? "打开学习助手" : "收起学习助手";
};

async function saveLessonProgress(value) {
  if (!selectedLesson || progressSaving || lessonOpening) return;
  const lesson = selectedLesson;
  const userId = state.user?.id;
  progressSaving = true;
  pendingProgressValue = value;
  $$("[data-save-progress]").forEach(b => b.disabled = true);
  $("#progress-retry").disabled = true;
  $("#completion-next").disabled = true;
  renderLessonNavigation();
  $("#progress-error").textContent = "";
  $("#lesson-progress").textContent = "正在保存，请稍候…";
  try {
    await zhixingApi.updateProgress(lesson.id, value);
    if (userId !== state.user?.id || selectedLesson?.id !== lesson.id) return;
    selectedLesson.progress = value;
    selectedLesson.status = value === 100 ? "completed" : "in_progress";
    selectedLesson.enrolled = true;
    for (const group of [pathData?.modules, ...((pathData?.catalog || []).map(p => p.modules)), pathData?.active_path?.modules]) {
      const cached = group?.find(m => m.id === lesson.id);
      if (cached) { cached.progress = value; cached.status = selectedLesson.status; cached.enrolled = true; }
    }
    pendingProgressValue = null;
    $("#progress-retry").classList.add("hidden");
    const refreshed = await refreshPath();
    if (userId !== state.user?.id || selectedLesson?.id !== lesson.id) return;
    $("#completion-refresh-note").textContent = refreshed ? "" : "完成状态已保存，首页刷新暂时失败；可稍后点击刷新进度。";
    showToast(value === 100 ? "本节已完成，查看回顾和下一步" : "已恢复为学习中，原位置保留");
  } catch(error) {
    if (userId !== state.user?.id || selectedLesson?.id !== lesson.id) return;
    $("#progress-error").textContent = `保存失败：${error.message}。完成状态尚未更改，请重试。`;
    $("#progress-retry").classList.remove("hidden");
  } finally {
    progressSaving = false;
    $$("[data-save-progress]").forEach(b => b.disabled = false);
    $("#progress-retry").disabled = false;
    $("#completion-next").disabled = false;
    renderLessonNavigation();
    renderLessonState();
    if (pendingProgressValue === null && value === 100 && userId === state.user?.id && selectedLesson?.id === lesson.id) {
      $("#completion-feedback").focus({preventScroll:true});
      $("#completion-feedback").scrollIntoView({block:"nearest", behavior:"smooth"});
    }
  }
}
$$("[data-save-progress]").forEach(button => button.onclick = () => saveLessonProgress(Number(button.dataset.saveProgress)));
$("#progress-retry").onclick = () => { if (pendingProgressValue !== null) saveLessonProgress(pendingProgressValue); };
$("#postpone-lesson").onclick = async () => {
  if (!await closeModals()) return;
  $("#student-workbench").scrollIntoView({behavior:"smooth"});
  showToast("学习位置已保存，下次可从工作台继续");
};
$("#completion-next").onclick = async () => {
  if (progressSaving || lessonOpening || !completionTarget) return;
  if (completionTarget.type === "lesson") openLesson(completionTarget.id);
  else if (completionTarget.type === "mission") startMission();
  else { if (await closeModals()) $("#student-workbench").scrollIntoView({behavior:"smooth"}); }
};
