(() => {
  "use strict";

  const SAVE_KEY = "iteration-ark-save-v1";
  const STATS_KEY = "iteration-ark-stats-v1";
  const stageNames = ["需求评审", "开发实现", "版本封版", "测试评审", "合并 Release", "AI 代码审查", "上线发布"];
  const versionCaptions = ["建立基础", "需求扩张", "模块耦合", "集成压力", "风险累积", "发布冲刺"];
  const $ = (id) => document.getElementById(id);

  const clamp = (value, min = 0, max = 100) => Math.max(min, Math.min(max, value));
  const chance = (percent) => Math.random() * 100 < percent;
  const escapeHTML = (value) => String(value).replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[char]));
  const formatEffects = (effects) => Object.entries(effects).filter(([, value]) => value).map(([key, value]) => {
    const labels = { debt: "技术债", satisfaction: "满意度", delivery: "交付余量", risks: "隐患", demand: "需求压力" };
    return `${labels[key] || key} ${value > 0 ? "+" : ""}${value}`;
  }).join(" · ");

  function freshState() {
    return { version: 1, stage: 0, debt: 0, satisfaction: 80, delivery: 100, demandPressure: 0, risks: 0, bAccidents: 0, sAccidents: 0, signals: [], reports: [], event: null, stageResolved: false, ended: false, outcome: null };
  }
  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(SAVE_KEY) || "null");
      return saved && saved.version >= 1 && saved.stage >= 0 ? {...freshState(), ...saved} : freshState();
    } catch (_error) { return freshState(); }
  }
  function saveState() {
    localStorage.setItem(SAVE_KEY, JSON.stringify(state));
    $("save-state").textContent = `已保存 · ${new Date().toLocaleTimeString("zh-CN", {hour:"2-digit", minute:"2-digit"})}`;
  }
  function loadStats() {
    try { return {...{finished:0, outcomes:{}, bestDebt:null, bestAccidents:null}, ...JSON.parse(localStorage.getItem(STATS_KEY) || "{}")}; }
    catch (_error) { return {finished:0, outcomes:{}, bestDebt:null, bestAccidents:null}; }
  }
  function recordStats() {
    const stats = loadStats();
    stats.finished += 1;
    stats.outcomes[state.outcome.code] = (stats.outcomes[state.outcome.code] || 0) + 1;
    stats.bestDebt = stats.bestDebt === null ? state.debt : Math.min(stats.bestDebt, state.debt);
    const accidents = state.bAccidents + state.sAccidents;
    stats.bestAccidents = stats.bestAccidents === null ? accidents : Math.min(stats.bestAccidents, accidents);
    localStorage.setItem(STATS_KEY, JSON.stringify(stats));
  }

  const stages = {
    0: { title: "需求评审", context: "产品负责人带来本版本需求清单。你可以把所有需求接下来，也可以协商砍掉次要需求，为后续留出工程空间。", risk: "业务压力" },
    1: { title: "开发实现", context: "进入开发。上一轮留下的技术债会影响模块耦合和实现速度。先把当前版本的工程状态看清楚，再继续编码。", risk: "耦合观察" },
    2: { title: "版本封版", context: "版本交付前，体验和产品会从使用流程出发提出反馈。临时改动往往发生在最接近上线的时候。", risk: "变更拉扯" },
    3: { title: "测试评审", context: "测试同学正在评审边界、异常路径和实现方案。他们提出的可能是重构要求，而不是简单的缺陷修复。", risk: "质量卡点" },
    4: { title: "合并 Release", context: "并行开发的代码需要合入 Release 分支。一次看似简单的冲突处理，可能会改掉你依赖的逻辑。", risk: "集成风险" },
    5: { title: "AI 代码审查", context: "AI 提供了重写和简化建议。你需要决定是否逐条理解改动，而不是把“看起来更干净”当作安全证明。", risk: "AI 风险" },
    6: { title: "上线发布", context: "版本准备发布。系统会综合技术债、隐患标记、版本阶段和需求压力，计算这次上线的事故风险。", risk: "线上后果" },
  };

  let state = loadState();
  let stageNotice = null;

  function addSignal(text, tone = "normal") {
    state.signals.unshift({text, tone, version: state.version});
    state.signals = state.signals.slice(0, 6);
  }
  function applyEffects(effects) {
    state.debt = clamp(state.debt + (effects.debt || 0));
    state.satisfaction = clamp(state.satisfaction + (effects.satisfaction || 0));
    state.delivery = clamp(state.delivery + (effects.delivery || 0));
    state.demandPressure = clamp(state.demandPressure + (effects.demand || 0), 0, 60);
    state.risks = clamp(state.risks + (effects.risks || 0), 0, 5);
  }
  function button(label, action, secondary = false) {
    return `<button class="button ${secondary ? "button-light" : ""}" type="button" data-action="${action}">${escapeHTML(label)}</button>`;
  }
  function choice(id, title, detail, effect) {
    return `<button class="decision-option" type="button" data-choice="${id}"><span><strong>${escapeHTML(title)}</strong><p>${escapeHTML(detail)}</p></span><span class="option-effect">${escapeHTML(effect)}</span></button>`;
  }

  function eventForStage(stage) {
    const v = state.version;
    if (stage === 2) {
      const ux = chance(18 + v * 3);
      const product = chance(13 + v * 4 + state.demandPressure * .25);
      if (ux || product) return {type: product && ux ? "both" : product ? "product" : "ux"};
    }
    if (stage === 3 && chance(16 + v * 4 + state.debt * .12)) return {type: "test"};
    if (stage === 4 && chance(11 + v * 4 + state.risks * 5)) return {type: "merge"};
    if (stage === 5 && chance(14 + v * 7 + state.debt * .08)) return {type: "ai"};
    return null;
  }
  function enterStage() {
    if (state.ended) { render(); return; }
    if (state.stageResolved) { render(); return; }
    stageNotice = null;
    if (state.stage === 0 || state.stage === 6) { state.stageResolved = true; render(); return; }
    state.event = eventForStage(state.stage);
    state.stageResolved = true;
    render();
  }

  function nextStage() {
    state.event = null;
    state.stageResolved = false;
    state.stage += 1;
    if (state.stage > 6) {
      state.version += 1;
      state.stage = 0;
      state.delivery = 100;
      state.reports.push({version: state.version - 1, text: stageNotice || "版本安全发布", risk: state.debt >= 50 ? "技术债进入关注区" : "风险在可控范围"});
      state.reports = state.reports.slice(-6);
      if (state.version > 6) return finish("complete");
    }
    saveState();
    enterStage();
  }

  function resolveChoice(id) {
    if (state.ended) return;
    const v = state.version;
    const map = {
      accept: {title:"接下全部需求", detail:"把全部范围纳入本版本，保证业务窗口期。", effects:{debt:8, delivery:8, demand:-2}, signal:"为了交付窗口接下全部需求，技术债上升 8。"},
      trim: {title:"协商砍掉次要需求", detail:"保留核心价值，给实现和验证留出余量。", effects:{debt:1, delivery:-8, satisfaction:-8, demand:6}, signal:"砍掉次要需求，产品满意度下降，但工程空间增加。"},
      uxHack: {title:"快速适配体验修改", detail:"用局部兼容方案满足本次验收。", effects:{debt:8, delivery:5}, signal:"体验修改采用局部兼容，旧逻辑的复杂度上升。"},
      delayUX: {title:"记录反馈，下版本处理", detail:"保留当前实现，向产品解释本次变更的成本。", effects:{satisfaction:-10, demand:5}, signal:"体验反馈延期，产品满意度下降，后续变更压力增加。"},
      productHack: {title:"临时变更直接适配", detail:"压缩验证时间，先让产品负责人看到结果。", effects:{debt:10, delivery:-5}, signal:"临时需求通过快速适配上线，技术债上升 10。"},
      productDefer: {title:"延后到下个版本", detail:"记录需求和影响范围，避免在封版前改动核心路径。", effects:{satisfaction:-12, demand:8}, signal:"产品变更延期，满意度下降，但没有新增技术债。"},
      testPatch: {title:"快速修补测试意见", detail:"先处理暴露出来的路径，保留原有内部结构。", effects:{debt:8, risks:1}, signal:"测试意见采用修补方式处理，新增 1 个隐患标记。"},
      refactor: {title:"认真重构内部逻辑", detail:"减少本版本交付范围，换取更稳定的实现基础。", effects:{debt:2, delivery:-12, satisfaction:-5}, signal:"为重构牺牲部分范围，技术债只增加 2。"},
      mergeFast: {title:"简单解决冲突，先合进去", detail:"完成合并速度快，但没有充分验证依赖逻辑。", effects:{debt:8, risks:1}, signal:"Release 合并缺少回归，新增 1 个集成隐患。"},
      mergeVerify: {title:"联调并做回归验证", detail:"投入时间核对依赖关系，接受本版本部分功能延期。", effects:{delivery:-12, satisfaction:-4}, signal:"完成联调和回归，交付余量下降但没有新增隐患。"},
      aiPass: {title:"认可 AI 修改，直接放行", detail:"代码看起来更简洁，但你没有逐条复核行为变化。", effects:{risks:2}, signal:"AI 修改未经充分复核，新增 2 个高风险标记。"},
      aiReview: {title:"逐条 Review AI 改动", detail:"理解每一处逻辑变化，修正不符合业务约束的建议。", effects:{delivery:-8}, signal:"完成 AI 改动复核，交付余量下降但没有新增隐患。"},
    };
    const selected = map[id];
    if (!selected) return;
    applyEffects(selected.effects);
    addSignal(selected.signal);
    stageNotice = selected.signal;
    state.stageResolved = false;
    saveState();
    nextStage();
  }

  function renderDecision() {
    const area = $("decision-area");
    if (state.ended) { renderOutcome(area); return; }
    if (state.stage === 0) {
      area.innerHTML = `<div class="event-callout"><span class="event-symbol">◎</span><span>本阶段是必选决策。你可以保护工程空间，也可以换取更高的短期交付确定性。</span></div><div class="decision-options">${choice("accept","接下全部需求","保证业务窗口期，但会压缩实现与验证空间。","技术债 +8 · 交付 +8")}${choice("trim","协商砍掉次要需求","保留核心价值，为实现和测试留下余量。","技术债 +1 · 满意度 -8")}</div>`;
      return;
    }
    if (state.stage === 1) {
      area.innerHTML = `<div class="event-callout"><span class="event-symbol">⌁</span><span>${state.debt >= 40 ? "旧模块耦合已经影响新增功能。现在花时间理清边界，能减少后面每次修改的成本。" : "当前模块仍有一定设计空间。先确认依赖，再进入封版。"}</span></div><div class="continue-wrap">${button("完成开发，进入封版", "continue")}</div>`;
      return;
    }
    if (!state.event) {
      area.innerHTML = `<div class="event-callout"><span class="event-symbol">✓</span><span>本阶段没有触发额外事件。流程按计划推进，但上线风险仍会综合技术债和已有隐患计算。</span></div><div class="continue-wrap">${button("继续下一阶段", "continue")}</div>`;
      return;
    }
    const events = {
      ux: {title:"体验人员提出流程修改", text:"试用后发现交互路径不够顺畅，要求本版本内完成调整。", options:[choice("uxHack","快速做兼容适配","先满足本次体验验收，再考虑统一设计。","技术债 +8"),choice("delayUX","记录反馈，下版本处理","保留当前实现，解释变更成本和风险。","满意度 -10")]},
      product: {title:"产品负责人临时增加需求", text:"验收时提出新的业务要求，希望直接赶在本次发布。", options:[choice("productHack","临时变更直接适配","缩短验证时间，保证业务窗口期。","技术债 +10"),choice("productDefer","延后到下个版本","记录需求和影响范围，保护当前发布。","满意度 -12")]},
      both: {title:"体验与产品同时提出变更", text:"体验反馈和业务调整叠加出现。你只能选择一条处理策略，另一个问题会被记录到下一轮。", options:[choice("uxHack","快速兼容主要路径","先处理最影响验收的路径。","技术债 +8"),choice("productDefer","冻结变更，统一排期","拒绝在封版前继续扩张范围。","满意度 -12")]},
      test: {title:"测试要求重构内部逻辑", text:"测试认为当前实现虽然能跑通，但边界条件和内部结构存在隐患。", options:[choice("testPatch","快速修补测试意见","先让当前用例通过，保留原有结构。","技术债 +8 · 隐患 +1"),choice("refactor","认真重构内部逻辑","牺牲部分范围，为后续版本还债。","技术债 +2 · 交付 -12")]},
      merge: {title:"Release 合入产生隐性冲突", text:"同事的并行代码改动了你依赖的逻辑，冲突不会立刻报错。", options:[choice("mergeFast","简单解决冲突，先合进去","优先完成合入，依赖隐藏风险稍后暴露。","技术债 +8 · 隐患 +1"),choice("mergeVerify","联调并做回归验证","投入时间核对依赖关系，接受部分延期。","交付 -12")]},
      ai: {title:"AI 建议重写关键逻辑", text:"AI 生成了更简洁的实现，但它不了解全部业务约束。", options:[choice("aiPass","认可 AI 修改，直接放行","代码更短，立即获得进度收益。","隐患 +2 · 严重风险上升"),choice("aiReview","逐条 Review AI 改动","理解行为变化并修正不合适的建议。","交付 -8")]},
    };
    const event = events[state.event.type];
    area.innerHTML = `<div class="event-callout"><span class="event-symbol">!</span><span><strong>${event.title}</strong><br />${event.text}</span></div><div class="decision-options">${event.options.join("")}</div>`;
  }

  function publish() {
    const base = 5 + state.version * 3;
    const debtImpact = state.debt * .35;
    const hiddenImpact = state.risks * 8;
    const pressureImpact = state.demandPressure * .1;
    let probability = Math.min(75, base + debtImpact + hiddenImpact + pressureImpact);
    const sources = [`基础风险 +${base.toFixed(0)}%`, `技术债 +${debtImpact.toFixed(0)}%`];
    if (state.risks) sources.push(`隐患标记 +${hiddenImpact.toFixed(0)}%`);
    if (state.demandPressure) sources.push(`需求压力 +${pressureImpact.toFixed(0)}%`);
    const forced = state.version === 6 && state.debt >= 70;
    let accident = null;
    if (forced || chance(probability)) {
      const severeChance = forced ? 100 : clamp(8 + state.version * 5 + state.debt * .18 + state.risks * 7);
      accident = chance(severeChance) ? "S" : "B";
    }
    if (accident === "B") state.bAccidents += 1;
    if (accident === "S") state.sAccidents += 1;
    if (accident) {
      const label = accident === "S" ? "S 级线上事故" : "B 级线上事故";
      const detail = accident === "S" ? "关键链路受到影响，年终奖评级归零。" : "线上出现可感知故障，团队需要投入时间修复和复盘。";
      addSignal(`${label}：${detail}`, "critical");
      stageNotice = `${label} · 风险来源：${sources.join("、")}`;
    } else {
      stageNotice = `安全发布 · 事故概率 ${probability.toFixed(0)}% · ${sources.join("、")}`;
      addSignal(`V${state.version} 安全发布，事故概率 ${probability.toFixed(0)}%。`);
    }
    if (state.bAccidents >= 5) return finish("fired");
    if (accident === "S") return finish("zeroBonus");
    nextStage();
  }

  function finish(code) {
    const outcomes = {
      fired: {title:"被裁员", badge:"质量底线失守", text:"B 级事故累计达到 5 条，线上质量失去控制，游戏提前结束。复盘：高频小事故会持续消耗用户和团队信任。", critical:true},
      zeroBonus: {title:"年终奖归 0", badge:"长期风险爆发", text:"S 级线上事故已经发生。复盘：事故往往是多个版本的技术债、隐患和赶工选择共同积累的结果。", critical:true},
      downgrade: {title:"年终奖降级", badge:"交付完成但风险偏高", text:"你完成了六个版本，但 B 级事故不断。复盘：质量风险没有越过底线，却已经持续消耗团队信任。"},
      complete: {title:"绩效优秀 · 全额奖金", badge:"平稳交付", text:"六个版本安全完成。复盘：持续管理技术债、合理安排需求、认真验证 AI 修改，能让质量和进度形成正循环。"},
    };
    if (code === "complete" && state.bAccidents >= 2) code = "downgrade";
    if (state.stage === 6 && !state.reports.some((report) => report.version === state.version)) {
      state.reports.push({version: state.version, text: stageNotice || "版本发布", risk: code === "complete" ? "" : "事故已进入年度复盘"});
      state.reports = state.reports.slice(-6);
    }
    state.outcome = {code, ...outcomes[code]};
    state.ended = true;
    recordStats();
    saveState();
    render();
  }

  function renderOutcome(area) {
    const result = state.outcome;
    area.innerHTML = `<div class="result-panel ${result.critical ? "critical" : ""}"><span class="result-badge">${escapeHTML(result.badge)}</span><h3>${escapeHTML(result.title)}</h3><p>${escapeHTML(result.text)}</p></div><div class="continue-wrap">${button("开启新的一年", "reset", true)}</div>`;
  }

  function renderMetrics() {
    $("year-label").textContent = state.ended ? "年度结算" : `V${state.version} / 6`;
    $("year-caption").textContent = state.ended ? "本局已完成 · 可重新挑战" : `第 ${state.version * 2 - 1}–${state.version * 2} 个月 · ${versionCaptions[state.version - 1]}`;
    $("debt-value").textContent = state.debt;
    $("debt-bar").style.width = `${state.debt}%`;
    $("debt-note").textContent = state.debt >= 70 ? "危险区 · V6 可能强制引爆 S 级事故" : state.debt >= 40 ? "关注区 · 修改成本正在上升" : "健康区间 · 后续风险较低";
    $("satisfaction-value").textContent = state.satisfaction;
    $("satisfaction-bar").style.width = `${state.satisfaction}%`;
    $("satisfaction-note").textContent = state.satisfaction < 40 ? "业务关系紧张 · 后续变更压力上升" : state.satisfaction < 65 ? "需要加强沟通" : "业务沟通顺畅";
    $("delivery-value").textContent = state.delivery;
    $("delivery-bar").style.width = `${state.delivery}%`;
    $("delivery-note").textContent = state.delivery < 45 ? "本版范围明显缩水" : state.delivery < 75 ? "需要管理交付范围" : "可以按计划推进";
    $("accident-value").textContent = `${state.bAccidents} B / ${state.sAccidents} S`;
    $("b-pill").textContent = `B 级 ${state.bAccidents}`;
    $("s-pill").textContent = `S 级 ${state.sAccidents}`;
    $("accident-note").textContent = state.bAccidents >= 2 ? "事故正在影响年度评价" : "当前没有严重质量压力";
  }
  function renderStages() {
    $("stage-counter").textContent = state.ended ? "年度已结算" : `阶段 ${state.stage + 1} / 7`;
    $("stage-line").innerHTML = stageNames.map((name, index) => `<div class="stage-node ${index < state.stage || state.ended ? "complete" : ""} ${index === state.stage && !state.ended ? "current" : ""}"><div class="stage-dot">${escapeHTML(name)}</div></div>`).join("");
  }
  function renderSide() {
    $("signal-count").textContent = `${state.signals.length} 条记录`;
    $("signals-list").innerHTML = state.signals.length ? state.signals.map((signal) => `<div class="signal-item"><i class="signal-dot ${signal.tone === "critical" ? "critical" : ""}"></i><span>V${signal.version} · ${escapeHTML(signal.text)}</span></div>`).join("") : `<p class="empty-side">还没有风险记录。你的每次选择都会在这里留下可复盘的线索。</p>`;
    $("report-count").textContent = `${state.reports.length} / 6`;
    $("reports-list").innerHTML = state.reports.length ? state.reports.map((report) => `<div class="report-item"><strong>V${report.version} · ${escapeHTML(report.text.split(" · ")[0])}</strong><p class="${report.risk && report.risk.includes("事故") ? "report-risk" : ""}">${escapeHTML(report.risk || "")}</p></div>`).join("") : `<p class="empty-side">完成每个版本后，这里会显示当轮决策和线上结果。</p>`;
  }
  function render() {
    renderMetrics(); renderStages(); renderSide();
    const stage = stages[state.stage] || stages[6];
    $("stage-badge").textContent = `阶段 ${Math.min(state.stage + 1, 7)} · ${stage.title}`;
    $("risk-label").textContent = stage.risk;
    $("stage-title").textContent = state.ended ? "年度结算" : stage.title;
    $("stage-context").textContent = state.ended ? "这次年度模拟已经结束。查看结果后，可以重新开始并尝试另一条工程路线。" : stage.context;
    renderDecision();
    const showFormula = $("classroom-mode").checked;
    $("teaching-copy").textContent = showFormula ? `事故概率 = 基础风险 + 技术债（${(state.debt * .35).toFixed(0)}%） + 隐患标记（${state.risks * 8}%） + 需求压力。V6 技术债达到 70 时会强制触发 S 级事故。` : "每次选择都会改变技术债、交付空间或后续风险；请根据团队当前状态做取舍。";
    saveState();
  }

  $("decision-area").addEventListener("click", (event) => {
    const choiceButton = event.target.closest("[data-choice]");
    if (choiceButton) return resolveChoice(choiceButton.dataset.choice);
    const actionButton = event.target.closest("[data-action]");
    if (!actionButton) return;
    if (actionButton.dataset.action === "continue") {
      if (state.stage === 6) publish(); else nextStage();
    }
    if (actionButton.dataset.action === "reset") resetGame();
  });
  $("classroom-mode").addEventListener("change", render);
  $("reset-game").addEventListener("click", resetGame);

  function resetGame() {
    if (!state.ended && !window.confirm("重新开始会覆盖当前这局的本地存档，确定吗？")) return;
    state = freshState(); stageNotice = null; saveState(); enterStage();
  }

  enterStage();
})();
