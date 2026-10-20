function resetTutor() {
  tutorEpoch++;
  tutorController?.abort();
  tutorController = null;
  tutorPending = false;
  failedQuestion = "";
  $("#tutor-messages").innerHTML = '<p class="supporting-copy">围绕当前课时提问，或试试下面的快捷操作。</p>';
  $("#tutor-question").value = "";
  $("#tutor-status").textContent = "";
  $("#tutor-retry-actions").classList.add("hidden");
  setTutorBusy(false);
  if (typeof resetStudyConversation === "function") resetStudyConversation();
}

function setTutorBusy(busy) {
  tutorPending = busy;
  $("#tutor-send").disabled = busy;
  $("#tutor-send").textContent = busy ? "正在回答…" : "发送问题 →";
  $$("[data-tutor-prompt], #tutor-retry, #tutor-use-cards, #tutor-clear, #tutor-restore, #tutor-hint, #tutor-reference, [data-ask-context], [data-task-hint]").forEach(b => b.disabled = busy);
  $("#tutor-messages").setAttribute("aria-busy", String(busy));
}

function appendTutorInline(element, text) {
  String(text).split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g).forEach(part => {
    if (part.startsWith("**") && part.endsWith("**")) {
      const strong = document.createElement("strong"); strong.textContent = part.slice(2, -2); element.append(strong);
    } else if (part.startsWith("`") && part.endsWith("`")) {
      const code = document.createElement("code"); code.textContent = part.slice(1, -1); element.append(code);
    } else element.append(document.createTextNode(part));
  });
}
function appendTutorText(element, text) {
  let list = null;
  String(text).split("\n").forEach(line => {
    if (!line.trim()) { list = null; return; }
    const bullet = line.match(/^\s*([-*]|\d+[.)、])\s+(.+)$/);
    if (bullet) {
      const tag = /^\d/.test(bullet[1]) ? "OL" : "UL";
      if (!list || list.tagName !== tag) { list = document.createElement(tag.toLowerCase()); element.append(list); }
      const item = document.createElement("li"); appendTutorInline(item, bullet[2]); list.append(item);
    } else {
      list = null;
      const paragraph = document.createElement("p");
      const heading = line.match(/^#{1,6}\s+(.+)$/);
      if (heading) {
        const strong = document.createElement("strong"); appendTutorInline(strong, heading[1]); paragraph.append(strong);
      } else appendTutorInline(paragraph, line);
      element.append(paragraph);
    }
  });
}
function tutorMessage(label, text) {
  const message = document.createElement("div"); message.className = "tutor-message";
  const heading = document.createElement("strong"); heading.textContent = label;
  const body = document.createElement("div"); body.className = "tutor-answer";
  // Render fenced code as text nodes; never interpret model output as HTML.
  String(text).split(/(```[\s\S]*?```)/g).forEach(part => {
    if (part.startsWith("```")) {
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = part.slice(3, -3).replace(/^[a-z0-9_-]*\n/i, "");
      pre.append(code); body.append(pre);
    } else {
      appendTutorText(body, part);
    }
  });
  message.append(heading, body); $("#tutor-messages").append(message);
  $("#tutor-messages").scrollTop = $("#tutor-messages").scrollHeight;
}
async function sendTutor(question, {retry = false, mode = "auto"} = {}) {
  return sendStudyTutor(question,{retry,mode});
}
$("#tutor-form").onsubmit = event => { event.preventDefault(); sendTutor($("#tutor-question").value.trim()); };
$("#tutor-retry").onclick = () => sendTutor(failedQuestion, {retry:true});
$("#tutor-use-cards").onclick = () => sendTutor(failedQuestion, {retry:true, mode:"guided-demo"});
$("#tutor-clear").onclick = () => newStudyConversation();
$$("[data-tutor-prompt]").forEach(button => button.onclick = () => {
  if (button.dataset.tutorPrompt === "给我一道练习" && exerciseState?.exercise) {
    setStudyFocus("exercise");
    $("#fixed-exercise").scrollIntoView({block:"start",behavior:"smooth"});
    return;
  }
  if (["解释本课知识","总结重点"].includes(button.dataset.tutorPrompt)) setStudyFocus("overview");
  $("#tutor-question").value = button.dataset.tutorPrompt;
  sendTutor(button.dataset.tutorPrompt);
});

zhixingApi.getConfig().then(config => {
  $("#learning-environment").textContent = "学习画像与进度随账号保存";
  $("#tutor-mode-label").textContent = config.tutor_mode === "live" ? "AI 答疑 · 基于当前课时，不执行代码" : "课时知识卡 · 规则式助手（非大模型），未读取附件";
}).catch(() => { $("#learning-environment").textContent = "服务暂不可用"; });
