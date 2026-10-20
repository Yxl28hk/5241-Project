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
  if (typeof flushNotebook === "function" && !await flushNotebook()) {
    showToast("请先保存笔记或处理版本冲突，再进入挑战");
    return;
  }
  try {
    const result = await zhixingApi.startMission();
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
    const result = await zhixingApi.answerMission(missionAttempt.id, {step:missionAttempt.step, choice_id:button.dataset.choice});
    renderMission(result.attempt);
  } catch (error) { showToast(error.message); $$("[data-choice]").forEach(b => b.disabled = false); }
};
