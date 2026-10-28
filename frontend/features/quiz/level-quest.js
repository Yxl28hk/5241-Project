let questRun = null;
let questMode = "quest";
let questPick = [];
let questMissStreak = 0;
let questLastBoss = false;
// Snapshot of the level states as last rendered, so an unlock plays its
// animation once instead of on every refresh. Null until the first render.
let questLevelStates = null;

// [v3 A1] combo is pure presentation: it never adds score.
const COMBO_TIERS = [
  {min: 8, text: "🔥 连击 ×{n} · 手感滚烫"},
  {min: 5, text: "🔥 连击 ×{n} · 势不可挡"},
  {min: 3, text: "🔥 连击 ×{n} · 渐入佳境"},
  {min: 2, text: "🔥 连击 ×{n}"},
];
// [v3 A2] empathy lines, indexed by consecutive misses (capped at the last one).
const COMFORT_LINES = [
  "这题有点绕，很多人第一次都会选这个。",
  "连着两题没顺，很正常 —— 看一眼解析就过去了。",
  "先歇口气。连续卡住不代表你不适合，这几题确实是分水岭。",
];
const BOSS_COMFORT = "Boss 本来就不是一次能过的。";

// [v3+] AI companion banter. Pure presentation: no score, no storage, no API.
const COMPANION_LINES = {
  correct: [
    "这题你拿得很稳。",
    "嗯，思路是对的。",
    "不错，保持这个节奏。",
  ],
  streak: [
    "连着对了 —— 手感来了。",
    "这个连击我记下了。",
    "稳得有点过分了。",
  ],
  wrong: [
    "这题我也差点选错，选项长得太像了。",
    "别急，这题本身就带坑。",
    "错了也没关系，看一眼解析就值回票价。",
  ],
  bossWrong: [
    "Boss 嘛，第一次交手很正常。",
    "这题我承认有点狠，下次再收拾它。",
  ],
  bossCorrect: [
    "Boss 一击拿下，这波我服。",
    "压轴题都稳了，剩下的不在话下。",
  ],
};
let companionLastLine = "";

// [v3+] Hidden egg lines. Each entry owns its trigger; nothing is persisted.
const EASTER_EGGS = [
  {
    id: "perfect",
    when: (result, mode) => mode !== "revenge" && result.total > 0 && result.score === result.total,
    lines: [
      "全对 —— 这套题我出的时候没想到有人能一遍过。",
      "满分。我把这条写进你的隐藏档案了。",
    ],
  },
  {
    id: "revenge-clear",
    when: (result, mode) => mode === "revenge" && result.total > 0 && !result.wrong_items.length,
    lines: [
      "错题清零。复仇这事儿，你比我狠。",
      "全部拿下 —— 这个错题池空了。",
    ],
  },
  {
    id: "april-fools",
    when: () => { const now = new Date(); return now.getMonth() === 3 && now.getDate() === 1; },
    lines: ["今天是愚人节，但你的成绩是真的。"],
  },
];

const questLevelMarks = {cleared: "✓", unlocked: "▶", locked: "🔒"};
const questModeLabels = {quest: "完整闯关", quick: "8 题速测", revenge: "错题复仇"};
const HEART_SLOTS = 3;

function renderQuestCard() {
  const quest = pathData?.quest;
  const levels = $("#quest-levels");
  const best = $("#quest-best");
  const quick = $("#quest-quick");
  const revenge = $("#quest-revenge");
  if (!quest || quest.available === false) {
    levels.replaceChildren();
    questLevelStates = null;
    $("#quest-progress").value = 0;
    best.textContent = "尚未开始";
    $("#quest-start").textContent = "开始闯关 →";
    quick.classList.add("hidden");
    revenge.classList.add("hidden");
    return;
  }
  // A level that was locked on the previous render just opened up — flag it so
  // the map plays the unlock animation once, not on every refresh.
  const freshlyUnlocked = questLevelStates === null ? [] : quest.levels
    .filter((level, index) => questLevelStates[index] === "locked" && level.state !== "locked")
    .map(level => level.level);
  questLevelStates = quest.levels.map(level => level.state);
  levels.innerHTML = quest.levels.map(level => `<li class="quest-level ${level.state}${freshlyUnlocked.includes(level.level) ? " just-unlocked" : ""}"><span class="quest-level-mark">${questLevelMarks[level.state] || "▶"}</span><span>第 ${level.level} 关 · ${escapeHTML(level.name)}</span><small>${level.state === "cleared" ? `历史通过 · 最佳 ${level.best_correct} / ${level.total}` : level.state === "locked" ? `需在同一局内通过第 ${level.level - 1} 关` : escapeHTML(level.hint)}</small></li>`).join("");
  $("#quest-progress").max = quest.total;
  $("#quest-progress").value = quest.best_score || 0;
  best.textContent = quest.best_score === null || quest.best_score === undefined
    ? "尚无完成成绩"
    : `历史最佳 ${quest.best_score} / ${quest.total}` + (quest.badge ? ` · ${quest.badge.icon} ${escapeHTML(quest.badge.label)}` : "");
  const cleared = quest.levels.filter(level => level.state === "cleared").length;
  $("#quest-start").textContent = quest.has_unfinished ? "继续闯关 →" : cleared ? "再挑战一次 ↗" : "开始闯关 →";
  quick.classList.remove("hidden");
  if (quest.revenge_count > 0) {
    revenge.classList.remove("hidden");
    revenge.textContent = `错题复仇 ${quest.revenge_count} ⚔️`;
  } else {
    revenge.classList.add("hidden");
  }
}

function renderHearts(run) {
  const box = $("#quest-hearts");
  if (!run || !run.hearts_enabled) {
    box.classList.add("hidden");
    return;
  }
  const left = Math.max(0, Math.min(HEART_SLOTS, run.hearts || 0));
  box.classList.remove("hidden");
  box.innerHTML = `<span class="quest-heart-full">${"♥".repeat(left)}</span><span class="quest-heart-empty">${"♡".repeat(HEART_SLOTS - left)}</span><small>本关剩余机会</small>`;
}

function renderChoices(question) {
  questPick = [];
  const kind = question.kind || "single";
  $("#quest-choices").innerHTML = question.choices.map(choice => `<button class="choice-button" data-choice="${escapeHTML(choice.id)}"><span class="order-badge hidden"></span>${escapeHTML(choice.text)}<span class="choice-mark">${kind === "single" ? "→" : ""}</span></button>`).join("");
  $$("#quest-choices [data-choice]").forEach(button => button.disabled = false);
  const confirm = $("#quest-confirm");
  if (kind === "single") {
    confirm.classList.add("hidden");
  } else {
    confirm.classList.remove("hidden");
    confirm.disabled = true;
    confirm.textContent = kind === "multi" ? `请选择 ${question.pick_count} 项` : "请按顺序排列";
  }
}

function renderQuestion() {
  const run = questRun;
  for (const selector of ["#quest-feedback", "#quest-summary", "#quest-next", "#quest-retry", "#quest-to-path"]) $(selector).classList.add("hidden");
  renderHearts(null);
  $("#quest-boss").classList.add("hidden");
  $("#quest-snippet").classList.add("hidden");
  $("#quest-modal .modal").classList.remove("is-boss");
  if (!run) return;
  if (run.finished) { showQuestSummary(); return; }
  $("#quest-run-progress").max = run.total;
  $("#quest-run-progress").value = run.step;
  const question = run.question;
  const level = run.level;
  const levelText = level.position
    ? `第 ${level.level} 关「${escapeHTML(level.name)}」本关 ${level.position} / ${level.per_level}`
    : `第 ${level.level} 关「${escapeHTML(level.name)}」`;
  $("#quest-status").textContent = `${questModeLabels[run.mode] || ""} · ${levelText} · 总进度 ${run.step + 1} / ${run.total} 题 · 已答对 ${run.score} 题`;
  $("#quest-title").textContent = `第 ${run.step + 1} 题`;
  $("#quest-topic").textContent = question.topic_label ? `本题维度：${escapeHTML(question.topic_label)}` : "";
  if (question.snippet) {
    $("#quest-snippet").textContent = question.snippet;
    $("#quest-snippet").classList.remove("hidden");
  }
  $("#quest-stem").textContent = question.stem;
  if (question.boss) {
    $("#quest-boss").classList.remove("hidden");
    $("#quest-modal .modal").classList.add("is-boss");
  }
  renderHearts(run);
  renderChoices(question);
}

function togglePick(button, question) {
  const id = button.dataset.choice;
  const at = questPick.indexOf(id);
  if (at >= 0) questPick.splice(at, 1);
  else questPick.push(id);
  $$("#quest-choices [data-choice]").forEach(item => {
    const position = questPick.indexOf(item.dataset.choice);
    const badge = item.querySelector(".order-badge");
    item.classList.toggle("picked", position >= 0);
    badge.textContent = position >= 0 ? position + 1 : "";
    badge.classList.toggle("hidden", position < 0);
  });
  const confirm = $("#quest-confirm");
  confirm.disabled = questPick.length !== question.pick_count;
  confirm.textContent = questPick.length === question.pick_count
    ? "确认提交 ✓"
    : (question.kind === "multi" ? `请选择 ${question.pick_count} 项` : "请按顺序排列");
}

function serializePick(question) {
  if (question.kind === "multi") {
    return question.choices.filter(choice => questPick.includes(choice.id)).map(choice => choice.id).join(",");
  }
  return questPick.join(",");
}

function comboText(streak) {
  const tier = COMBO_TIERS.find(item => streak >= item.min);
  return tier ? tier.text.replace("{n}", streak) : "";
}

function comfortFor(missStreak, isBoss) {
  const line = COMFORT_LINES[Math.min(missStreak, COMFORT_LINES.length) - 1];
  return isBoss ? `${BOSS_COMFORT} ${line}` : line;
}

function companionLine(result, streak) {
  const pool = result.correct
    ? (questLastBoss ? COMPANION_LINES.bossCorrect : streak >= 3 ? COMPANION_LINES.streak : COMPANION_LINES.correct)
    : (questLastBoss ? COMPANION_LINES.bossWrong : COMPANION_LINES.wrong);
  // Skip the line just shown so it does not repeat back to back.
  const fresh = pool.filter(line => line !== companionLastLine);
  const choices = fresh.length ? fresh : pool;
  companionLastLine = choices[Math.floor(Math.random() * choices.length)];
  return companionLastLine;
}

function easterEggLine(result, mode) {
  const egg = EASTER_EGGS.find(item => item.when(result, mode));
  if (!egg) return "";
  return egg.lines[Math.floor(Math.random() * egg.lines.length)];
}

async function submitAnswer(question, choiceId) {
  $$("#quest-choices [data-choice]").forEach(button => button.disabled = true);
  const confirm = $("#quest-confirm");
  confirm.disabled = true;
  try {
    const result = await zhixingApi.answerQuiz(questRun.id, {
      step: questRun.step, question_code: question.code, choice_id: choiceId
    });
    questRun = result.run;
    questLastBoss = Boolean(question.boss);
    questMissStreak = result.correct ? 0 : questMissStreak + 1;
    renderQuestFeedback(result);
  } catch (error) {
    showToast(error.message);
    if (questRun && questRun.question && questRun.question.kind !== "single") {
      $$("#quest-choices [data-choice]").forEach(button => button.disabled = false);
      confirm.disabled = questPick.length !== questRun.question.pick_count;
    } else {
      $$("#quest-choices [data-choice]").forEach(button => button.disabled = false);
    }
  }
}

function renderQuestFeedback(result) {
  const box = $("#quest-feedback");
  box.classList.remove("hidden");
  const streak = result.run.streak || 0;
  const combo = result.correct ? comboText(streak) : "";
  const comfort = result.correct ? "" : comfortFor(questMissStreak, questLastBoss);
  const banter = companionLine(result, streak);
  box.innerHTML = `${combo ? `<span class="quest-combo${streak >= 5 ? " is-hot" : ""}">${escapeHTML(combo)}</span>` : ""}
    <strong class="${result.correct ? "is-correct" : "is-wrong"}">${result.correct ? "回答正确" : "再想想"}</strong>
    ${comfort ? `<p class="quest-comfort">${escapeHTML(comfort)}</p>` : ""}
    <p class="quest-companion"><span class="quest-companion-avatar">🤖</span><span>${escapeHTML(banter)}</span></p>
    <p>${escapeHTML(result.explanation)}</p>`;
  if (result.level_result) {
    box.innerHTML += `<p class="quest-level-note">${escapeHTML(result.level_result.message)}</p>`;
  }
  $("#quest-next").textContent = result.finished ? "查看结果 →" : "下一题 →";
  $("#quest-next").classList.remove("hidden");
}

async function showQuestSummary() {
  try {
    const data = await zhixingApi.getQuizResult(questMode);
    const result = data.result;
    const box = $("#quest-summary");
    box.classList.remove("hidden");
    if (!result) {
      box.innerHTML = `<h3>还没有完成记录</h3><p class="supporting-copy">完整答完一局后才能看到成绩与徽章。</p>`;
    } else if (questMode === "revenge") {
      box.innerHTML = `<h3>${result.wrong_items.length ? "复仇继续 ⚔️" : "复仇成功 🎉"}</h3>
        <p>本局答对 ${result.score} / ${result.total} 题。答对的题目已从错题池移除，剩下的下次再来。</p>
        ${result.wrong_items.length ? `<div class="quest-wrong"><strong>还没拿下</strong>${result.wrong_items.map(item => `<p>${escapeHTML(item.stem)}<br>${escapeHTML(item.explanation)}</p>`).join("")}</div>` : ""}`;
    } else if (questMode === "quick") {
      box.innerHTML = `<h3>速测完成 ⚡</h3>
        <p>答对 ${result.score} / ${result.total} 题。速测只用来让你试试题目长什么样，<strong>不计入历史最佳</strong>。</p>
        <ul class="quest-topic-list">${(result.topics || []).map(topic => `<li><span>${escapeHTML(topic.label)}</span><span class="progress-track"><span style="width:${Math.round(topic.correct * 100 / topic.total)}%"></span></span><small>${topic.correct} / ${topic.total}</small></li>`).join("")}</ul>
        <p class="supporting-copy">想要更稳的起点建议，做一次完整的 18 题闯关。</p>`;
    } else {
      box.innerHTML = `<h3>${result.badge ? `${result.badge.icon} ${escapeHTML(result.badge.label)}` : "闯关结束"}</h3>
        <p>本局答对 ${result.score} / ${result.total} 题（${result.percent}%）。历史最佳 ${data.best_score} / ${result.total}。</p>
        ${result.persona ? `<div class="quest-persona"><span class="quest-persona-icon">${result.persona.icon}</span><div><strong>${escapeHTML(result.persona.label)}</strong><small>${escapeHTML(result.persona.note)}</small></div></div>` : ""}
        <ul class="quest-topic-list">${(result.topics || []).map(topic => `<li><span>${escapeHTML(topic.label)}</span><span class="progress-track"><span style="width:${Math.round(topic.correct * 100 / topic.total)}%"></span></span><small>${topic.correct} / ${topic.total}</small></li>`).join("")}</ul>
        ${result.wrong_items.length ? `<div class="quest-wrong"><strong>错题回顾</strong>${result.wrong_items.map(item => `<p>${escapeHTML(item.stem)}<br>你的选择：${escapeHTML(item.your_choice)}${item.correct_choice_id ? ` · 正确选项：${escapeHTML(item.correct_choice_id)}` : ""}<br>${escapeHTML(item.explanation)}</p>`).join("")}</div>` : ""}
        <p class="supporting-copy">闯关参考水平：${escapeHTML(levelLabels[result.suggested_level] || result.suggested_level)}。这只是起点参考，不是能力评分。</p>`;
    }
    const egg = result ? easterEggLine(result, questMode) : "";
    if (egg) box.innerHTML += `<div class="quest-easter"><span class="quest-easter-icon">🥚</span><div><strong>彩蛋</strong><small>${escapeHTML(egg)}</small></div></div>`;
    $("#quest-status").textContent = "本局已结束";
    $("#quest-retry").textContent = questMode === "revenge" ? "再复仇一次 ↻" : "再挑战一次 ↻";
    $("#quest-retry").classList.remove("hidden");
    $("#quest-to-path").classList.remove("hidden");
    await refreshPath();
  } catch (error) { showToast(error.message); }
}

async function startQuest(mode = "quest") {
  if (!requireLogin("闯关")) return;
  questMode = mode;
  questMissStreak = 0;
  questLastBoss = false;
  try {
    const result = await zhixingApi.startQuizRun({mode});
    questRun = result.run;
    renderQuestion();
    openModal("#quest-modal");
  } catch (error) { showToast(error.message); }
}

async function adoptQuizLevel() {
  try {
    const result = await zhixingApi.adoptQuizLevel();
    showToast(result.message);
    await refreshPath();
  } catch (error) { showToast(error.message); }
}
async function clearQuizReference() {
  if (!window.confirm("确定清空你的全部闯关数据吗？\n\n将删除：闯关记录、历史最佳、错题本和画像参考水平。\n\n一旦确认不可恢复，需要重新闯关。")) return;
  try {
    const result = await zhixingApi.clearQuizReference();
    showToast(result.message);
    await refreshPath();
  } catch (error) { showToast(error.message); }
}

$("#quest-start").onclick = () => startQuest("quest");
$("#quest-quick").onclick = () => startQuest("quick");
$("#quest-revenge").onclick = () => startQuest("revenge");
$("#quest-retry").onclick = () => startQuest(questMode);
$("#quest-to-path").onclick = async () => {
  if (await closeModals()) $("#learning-path").scrollIntoView({behavior: "smooth"});
};
$("#quest-next").onclick = () => {
  if (!questRun) return;
  if (questRun.finished) showQuestSummary();
  else renderQuestion();
};
$("#quest-confirm").onclick = () => {
  if (!questRun || !questRun.question) return;
  submitAnswer(questRun.question, serializePick(questRun.question));
};
$("#quest-choices").onclick = event => {
  const button = event.target.closest("[data-choice]");
  if (!button || !questRun || questRun.finished) return;
  const question = questRun.question;
  if (question.kind === "single") submitAnswer(question, button.dataset.choice);
  else togglePick(button, question);
};
