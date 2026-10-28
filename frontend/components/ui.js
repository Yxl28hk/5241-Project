const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function openModal(id) {
  $$(".modal-backdrop").forEach((modal) => {
    if (modal.id !== id.slice(1)) modal.classList.add("hidden");
  });
  $(id).classList.remove("hidden");
  document.body.style.overflow = "hidden";
}
async function closeModals() {
  const completionAssistant = $("#completion-ai-modal");
  if (completionAssistant && !completionAssistant.classList.contains("hidden")) {
    if ($("#completion-ai-submit").disabled) return false;
    completionAssistant.classList.add("hidden");
    return true;
  }
  if (!$("#lesson-modal").classList.contains("hidden") && typeof flushNotebook === "function" && !await flushNotebook()) {
    showToast("笔记尚未同步，请重试保存后再离开，或复制内容后重新载入。");
    return false;
  }
  $$(".modal-backdrop").forEach(modal => modal.classList.add("hidden"));
  document.body.style.overflow = "";
  return true;
}
function showToast(message) { $("#toast-message").textContent = message; $("#toast").classList.remove("hidden"); setTimeout(() => $("#toast").classList.add("hidden"), 2800); }
function showError(selector, error) { $(selector).textContent = error instanceof Error ? error.message : error; }
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
function progressPercent(value) {
  const progress = Number(value);
  return Number.isFinite(progress) ? Math.min(100, Math.max(0, progress)) : 0;
}
$$("[data-close-modal]").forEach((button) => button.addEventListener("click", closeModals));
$$(".modal-backdrop").forEach((backdrop) => backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeModals(); }));

document.addEventListener("keydown", event => { if (event.key === "Escape") closeModals(); });
