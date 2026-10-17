/* Week 8 enhancement; existing account and resource management remain in app.js. */
let pathData = null;
let selectedLesson = null;
let missionAttempt = null;
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const jsonRequest = (method, data) => ({method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});

async function refreshPath() {
  if (!state.user) {
    pathData = null;
    $("#path-summary").textContent = "登录后保存学习进度和任务成绩。";
    $("#path-list").innerHTML = '<button class="button button-primary" id="path-login">登录 / 注册，开启学习</button>';
    $("#path-login").onclick = () => openModal("#auth-modal");
    $("#path-progress").value = 0;
    $("#mission-best").textContent = "尚未开始";
    return;
  }
  try {
    pathData = await api("/api/learning-path");
    $("#path-summary").textContent = `${pathData.completed} / ${pathData.modules.length} 节已完成 · 总进度 ${pathData.progress}%（自评记录）`;
    $("#path-progress").value = pathData.progress;
    $("#path-list").innerHTML = pathData.modules.map((m, i) => `<button class="path-card ${m.progress === 100 ? "finished" : ""}" data-lesson="${m.id}"><span class="path-number">${m.progress === 100 ? "✓" : String(i + 1).padStart(2, "0")}</span><span><small>${escapeHTML(m.duration)} · ${m.id === pathData.next_course_id ? "推荐下一步" : m.progress === 100 ? "已完成" : "可自由探索"}</small><strong>${escapeHTML(m.title)}</strong><span>${escapeHTML(m.description)}</span><progress max="100" value="${m.progress}" aria-label="课程进度"></progress><small>${m.progress}%</small></span><span>↗</span></button>`).join("");
    $("#mission-best").textContent = pathData.mission.best_score === null ? "尚无完成成绩" : `历史最高 ${pathData.mission.best_score} / 100`;
  } catch (error) { $("#path-summary").textContent = error.message; }
}

async function openLesson(courseId) {
  if (!requireLogin("学习课程")) return;
  try {
    await api(`/api/courses/${courseId}/learn`, {method:"POST"});
    await refreshPath();
    selectedLesson = pathData?.modules.find(m => m.id === Number(courseId));
    if (!selectedLesson) {
      const data = await api("/api/profile/learning");
      selectedLesson = data.courses.find(c => c.id === Number(courseId));
    }
    if (!selectedLesson) throw new Error("课程已不存在，请刷新页面");
    $("#lesson-title").textContent = selectedLesson.title;
    $("#lesson-copy").textContent = selectedLesson.lesson || selectedLesson.description;
    $("#lesson-question").textContent = selectedLesson.question || "学习后，请用自己的话总结一个关键概念。";
    $("#lesson-progress").textContent = `当前进度 ${selectedLesson.progress}% · 由你确认完成情况`;
    $("#lesson-resource").classList.toggle("hidden", !selectedLesson.file_url);
    $("#lesson-resource").href = selectedLesson.file_url || "#";
    $("#tutor-messages").replaceChildren();
    $("#tutor-question").value = "";
    $("#tutor-context").textContent = `正在讨论：${selectedLesson.title}`;
    openModal("#lesson-modal");
  } catch (error) { showToast(error.message); }
}

$("#path-list").addEventListener("click", event => {
  const button = event.target.closest("[data-lesson]");
  if (button) openLesson(Number(button.dataset.lesson));
});
$("#path-refresh").onclick = refreshPath;
$("#path-nav").onclick = () => $("#learning-path").scrollIntoView({behavior:"smooth"});
$$("[data-save-progress]").forEach(button => button.onclick = async () => {
  button.disabled = true;
  try {
    const value = Number(button.dataset.saveProgress);
    await api(`/api/courses/${selectedLesson.id}/progress`, jsonRequest("PATCH", {progress:value}));
    selectedLesson.progress = value;
    $("#lesson-progress").textContent = `当前进度 ${value}% · 已保存`;
    await refreshPath(); showToast("学习进度已保存");
  } catch(error) { showToast(error.message); }
  finally { button.disabled = false; }
});

function tutorMessage(label, text) {
  const message = document.createElement("div"); message.className = "tutor-message";
  const heading = document.createElement("strong"); heading.textContent = label;
  const body = document.createElement("p"); body.textContent = text;
  message.append(heading, body); $("#tutor-messages").append(message);
  message.scrollIntoView({block:"nearest"});
}
$("#tutor-form").onsubmit = async event => {
  event.preventDefault();
  const question = $("#tutor-question").value.trim();
  if (!question) return;
  const lessonId = selectedLesson.id;
  $("#tutor-send").disabled = true;
  tutorMessage("你", question);
  try {
    const result = await api("/api/tutor", jsonRequest("POST", {course_id:lessonId, message:question}));
    if (selectedLesson.id === lessonId) tutorMessage("学习助手 · 演示", result.answer);
    $("#tutor-question").value = "";
  } catch (error) { tutorMessage("暂时无法回答", error.message); }
  finally { $("#tutor-send").disabled = false; }
};
$$("[data-tutor-prompt]").forEach(button => button.onclick = () => {
  $("#tutor-question").value = button.dataset.tutorPrompt;
  $("#tutor-form").requestSubmit();
});

function renderMission(attempt) {
  missionAttempt = attempt;
  $("#mission-status").textContent = `${attempt.step} / ${attempt.total} 个决策已完成 · ${attempt.score} 分`;
  $("#mission-progress").value = attempt.step;
  $("#mission-history").innerHTML = attempt.history.map(h => `<div class="decision-feedback"><strong>${escapeHTML(h.title)} · +${h.points} 分</strong><p>你的选择：${escapeHTML(h.text)}</p><p>${escapeHTML(h.feedback)}</p></div>`).join("");
  $("#mission-retry").classList.toggle("hidden", !attempt.complete);
  if (attempt.complete) {
    $("#mission-scene-title").textContent = attempt.passed ? "任务通过 · 发布守护者" : "任务完成 · 再练习一次";
    $("#mission-scenario").textContent = `最终成绩 ${attempt.score} / 100。${attempt.passed ? "你已掌握基本发布决策。" : "75 分通过。回看反馈，再次挑战。"} 真实项目仍需结合团队流程与实际风险判断。`;
    $("#mission-choices").replaceChildren();
    refreshPath();
  } else {
    $("#mission-scene-title").textContent = attempt.current.title;
    $("#mission-scenario").textContent = attempt.current.scenario;
    $("#mission-choices").innerHTML = attempt.current.choices.map(c => `<button class="choice-button" data-choice="${c.id}">${escapeHTML(c.text)} <span>→</span></button>`).join("");
  }
}
async function startMission() {
  if (!requireLogin("挑战任务")) return;
  try {
    const result = await api("/api/missions/release-rescue/start", {method:"POST"});
    renderMission(result.attempt); openModal("#mission-modal");
  } catch (error) { showToast(error.message); }
}
$("#mission-start").onclick = startMission;
$("#mission-retry").onclick = startMission;
$("#mission-choices").onclick = async event => {
  const button = event.target.closest("[data-choice]");
  if (!button) return;
  $$("[data-choice]").forEach(b => b.disabled = true);
  try {
    const result = await api(`/api/missions/attempts/${missionAttempt.id}/answer`, jsonRequest("POST", {step:missionAttempt.step, choice_id:button.dataset.choice}));
    renderMission(result.attempt);
  } catch (error) { showToast(error.message); $$("[data-choice]").forEach(b => b.disabled = false); }
};
document.addEventListener("keydown", event => { if (event.key === "Escape") closeModals(); });
api("/api/prototype/config").then(config => {
  $("#learning-environment").textContent = "学习数据存储：PostgreSQL";
}).catch(() => { $("#learning-environment").textContent = "服务暂不可用"; });
