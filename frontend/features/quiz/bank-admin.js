/** Admin-only question bank maintenance. Mirrors openAdminUsers() in account.js. */
const kindLabels = { single: "单选", multi: "多选", order: "排序" };
const sourceLabels = { seed: "预置", admin: "管理员", teacher: "教师", ai: "AI 生成" };

const quizBank = { questions: [], levels: [], topics: [], editing: null };

function parseChoiceLines(text) {
  return String(text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const matched = line.match(/^([A-Za-z0-9]+)\s*[.、:：]\s*(.+)$/);
      return matched ? { id: matched[1], text: matched[2] } : null;
    })
    .filter(Boolean);
}

function serializeChoices(choices) {
  return (choices || []).map((choice) => `${choice.id}. ${choice.text}`).join("\n");
}

function quizBankRows() {
  const level = $("#quiz-filter-level").value;
  const topic = $("#quiz-filter-topic").value;
  const active = $("#quiz-filter-active").value;
  return quizBank.questions.filter((question) => {
    if (level !== "all" && String(question.level) !== level) return false;
    if (topic !== "all" && question.topic !== topic) return false;
    if (active === "active" && !question.active) return false;
    if (active === "inactive" && question.active) return false;
    return true;
  });
}

function renderQuizBank() {
  const rows = quizBankRows();
  $("#admin-quiz-stats").textContent = `共 ${quizBank.questions.length} 题 · 启用 ${quizBank.questions.filter((q) => q.active).length} 题`;
  const list = $("#admin-quiz-list");
  if (!rows.length) {
    list.innerHTML = '<div class="space-empty">没有符合条件的题目。</div>';
    return;
  }
  list.innerHTML = rows.map((question) => `
    <section class="admin-quiz-row${question.active ? "" : " is-inactive"}">
      <div class="admin-quiz-main">
        <p class="admin-quiz-stem">${escapeHTML(question.stem)}</p>
        <p class="admin-quiz-meta"><span class="admin-quiz-code">${escapeHTML(question.code)}</span><span>第 ${question.level} 关</span><span>${escapeHTML(question.topic_label)}</span><span>${escapeHTML(kindLabels[question.kind] || question.kind)}</span>${question.boss ? '<span class="admin-quiz-boss">Boss 题</span>' : ""}<span>${escapeHTML(question.source_label || sourceLabels[question.source] || question.source)}</span></p>
      </div>
      <div class="admin-quiz-side">
        <span class="admin-quiz-state">${question.active ? "启用" : "停用"}</span>
        <div class="admin-quiz-row-actions">
          <button class="admin-quiz-btn" data-quiz-edit="${escapeHTML(question.code)}">编辑</button>
          <button class="admin-quiz-btn" data-quiz-toggle="${escapeHTML(question.code)}" data-active="${question.active}">${question.active ? "停用" : "启用"}</button>
          <button class="admin-quiz-btn is-danger" data-quiz-delete="${escapeHTML(question.code)}">删除</button>
        </div>
      </div>
    </section>`).join("");
}

function fillQuizFilters() {
  const level = $("#quiz-filter-level");
  const topic = $("#quiz-filter-topic");
  const formLevel = $("#quiz-form-level");
  const formTopic = $("#quiz-form-topic");
  const levelOptions = quizBank.levels
    .map((item) => `<option value="${item.id}">第 ${item.id} 关 · ${escapeHTML(item.name)}</option>`).join("");
  const topicOptions = quizBank.topics
    .map((item) => `<option value="${escapeHTML(item.id)}">${escapeHTML(item.label)}</option>`).join("");
  if (level.options.length <= 1 && quizBank.levels.length) level.insertAdjacentHTML("beforeend", levelOptions);
  if (topic.options.length <= 1 && quizBank.topics.length) topic.insertAdjacentHTML("beforeend", topicOptions);
  if (formLevel.options.length <= 1 && quizBank.levels.length) formLevel.insertAdjacentHTML("beforeend", levelOptions);
  if (formTopic.options.length <= 1 && quizBank.topics.length) formTopic.insertAdjacentHTML("beforeend", topicOptions);
}

function quizFormPayload(mode) {
  const choices = parseChoiceLines($("#quiz-form-choices").value);
  if (choices.length < 2) {
    showToast("至少要有两个选项，格式：a. 选项内容");
    return null;
  }
  const payload = {
    code: $("#quiz-form-code").value.trim(),
    level: Number($("#quiz-form-level").value),
    topic: $("#quiz-form-topic").value,
    difficulty: Number($("#quiz-form-difficulty").value),
    kind: $("#quiz-form-kind").value,
    boss: $("#quiz-form-boss").checked,
    stem: $("#quiz-form-stem").value.trim(),
    snippet: $("#quiz-form-snippet").value.trim(),
    choices,
    correct_choice_id: $("#quiz-form-correct").value.trim(),
    explanation: $("#quiz-form-explanation").value.trim(),
  };
  if (mode === "edit") delete payload.code;
  return payload;
}

function openQuizForm(question) {
  quizBank.editing = question ? question.code : null;
  $("#quiz-form-title").textContent = question ? `编辑题目 · ${question.code}` : "新增题目";
  $("#quiz-form-code").value = question ? question.code : "";
  $("#quiz-form-code").readOnly = Boolean(question);
  $("#quiz-form-level").value = question ? question.level : 1;
  $("#quiz-form-topic").value = question ? question.topic : quizBank.topics[0]?.id || "concepts";
  $("#quiz-form-difficulty").value = question ? question.difficulty : 2;
  $("#quiz-form-kind").value = question ? question.kind : "single";
  $("#quiz-form-boss").checked = question ? question.boss : false;
  $("#quiz-form-stem").value = question ? question.stem : "";
  $("#quiz-form-snippet").value = question ? question.snippet || "" : "";
  $("#quiz-form-choices").value = question ? serializeChoices(question.choices) : "";
  $("#quiz-form-correct").value = question ? question.correct_choice_id : "";
  $("#quiz-form-explanation").value = question ? question.explanation : "";
  $("#admin-quiz-form").classList.remove("hidden");
  $("#quiz-form-stem").focus();
}

function closeQuizForm() {
  quizBank.editing = null;
  $("#admin-quiz-form").classList.add("hidden");
}

async function loadQuizBank() {
  const result = await zhixingApi.listQuizQuestions();
  quizBank.questions = result.questions || [];
  quizBank.levels = result.levels || [];
  quizBank.topics = result.topics || [];
  fillQuizFilters();
  renderQuizBank();
}

async function openAdminQuiz() {
  if (!state.user?.is_admin) { showToast("需要管理员权限"); return; }
  try {
    await loadQuizBank();
    openModal("#admin-quiz-modal");
  } catch (error) { showToast(error.message); }
}

async function submitQuizForm() {
  const editing = quizBank.editing;
  const payload = quizFormPayload(editing ? "edit" : "create");
  if (!payload) return;
  try {
    const result = editing
      ? await zhixingApi.updateQuizQuestion(editing, payload)
      : await zhixingApi.createQuizQuestion(payload);
    showToast(result.message);
    closeQuizForm();
    await loadQuizBank();
  } catch (error) { showToast(error.message); }
}

async function toggleQuizQuestion(code, active) {
  try {
    const result = await zhixingApi.setQuizQuestionActive(code, !active);
    showToast(result.message);
    await loadQuizBank();
  } catch (error) { showToast(error.message); }
}

async function removeQuizQuestion(code) {
  if (!window.confirm(`确定删除题目 ${code} 吗？\n\n已有作答记录的题目无法删除（只能停用）。此操作不可恢复。`)) return;
  try {
    const result = await zhixingApi.deleteQuizQuestion(code);
    showToast(result.message);
    closeQuizForm();
    await loadQuizBank();
  } catch (error) { showToast(error.message); }
}

$("#quiz-bank-create").addEventListener("click", () => openQuizForm(null));
$("#quiz-form-cancel").addEventListener("click", closeQuizForm);
$("#quiz-form-submit").addEventListener("click", submitQuizForm);
["quiz-filter-level", "quiz-filter-topic", "quiz-filter-active"].forEach((id) => {
  $("#" + id).addEventListener("change", renderQuizBank);
});
$("#admin-quiz-list").addEventListener("click", (event) => {
  const target = event.target.closest("[data-quiz-edit],[data-quiz-toggle],[data-quiz-delete]");
  if (!target) return;
  if (target.dataset.quizEdit) {
    const question = quizBank.questions.find((item) => item.code === target.dataset.quizEdit);
    if (question) openQuizForm(question);
  } else if (target.dataset.quizToggle) {
    toggleQuizQuestion(target.dataset.quizToggle, target.dataset.active === "true");
  } else if (target.dataset.quizDelete) {
    removeQuizQuestion(target.dataset.quizDelete);
  }
});
