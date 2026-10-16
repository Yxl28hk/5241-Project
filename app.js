const state = { category: "全部", query: "", authMode: "login", user: null, courses: [] };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "请求失败，请确认 Flask 服务已启动");
  return body;
}
function openModal(id) {
  $$(".modal-backdrop").forEach((modal) => {
    if (modal.id !== id.slice(1)) modal.classList.add("hidden");
  });
  $(id).classList.remove("hidden");
  document.body.style.overflow = "hidden";
}
function closeModals() { $$(".modal-backdrop").forEach((modal) => modal.classList.add("hidden")); document.body.style.overflow = ""; }
function showToast(message) { $("#toast-message").textContent = message; $("#toast").classList.remove("hidden"); setTimeout(() => $("#toast").classList.add("hidden"), 2800); }
function showError(selector, error) { $(selector).textContent = error instanceof Error ? error.message : error; }
function updateUserUI() {
  const user = state.user;
  $("#user-name").textContent = user ? user.name : "游客";
  $("#user-role-badge").textContent = user?.is_admin ? "管理员" : user?.is_teacher ? "教师" : user ? "学生" : "";
  $("#user-role-badge").classList.toggle("hidden", !user);
  $$("[data-upload-only]").forEach((element) => element.classList.toggle("hidden", !user?.can_upload));
  $$("[data-admin-only]").forEach((element) => element.classList.toggle("hidden", !user?.is_admin));
  $("#user-avatar").textContent = user ? user.name.slice(0, 1) : "游";
  $("#profile-avatar").textContent = user ? user.name.slice(0, 1) : "游";
  $("#user-avatar").style.backgroundImage = "";
  $("#profile-avatar").style.backgroundImage = "";
  if (user?.avatar_url) {
    $("#user-avatar").style.backgroundImage = `url("${user.avatar_url}")`;
    $("#profile-avatar").style.backgroundImage = `url("${user.avatar_url}")`;
    $("#user-avatar").style.backgroundSize = "cover";
    $("#profile-avatar").style.backgroundSize = "cover";
    $("#user-avatar").textContent = "";
    $("#profile-avatar").textContent = "";
  }
}
function requireLogin(action) {
  if (!state.user) { openModal("#auth-modal"); showToast(`请先登录后再${action}`); return false; }
  return true;
}
function requireUploadPermission() {
  if (!requireLogin("上传资源")) return false;
  if (!state.user.can_upload) { showToast("学生账号只能学习课程，教师账号才可以上传资源"); return false; }
  return true;
}
function renderCourses() {
  const list = state.courses;
  $("#course-grid").innerHTML = list.map((course) => `
    <article class="course-card" data-course-id="${course.id}">
      <div class="course-cover cover-${course.cover || "design"}">
        <span class="cover-label">${course.badge || "我的课程"}</span><div class="cover-shape"></div><div class="cover-title">${course.title}</div>
      </div>
      <div class="course-info"><h3 class="course-title">${course.title}</h3><p class="course-description">${course.description || "开始探索新的知识与技能"}</p>
      <div class="course-meta"><span class="course-author"><span class="author-avatar">${(course.author || "我").slice(0, 1)}</span>${course.author || "我的课程"}</span><span class="course-duration">◷ ${course.duration || "待学习"}</span></div></div>
    </article>`).join("");
  $("#empty-state").classList.toggle("hidden", list.length > 0);
  $(".category-tab[data-category='全部'] span").textContent = state.courses.length;
}
async function loadCourses() {
  const params = new URLSearchParams({ q: state.query, category: state.category });
  const result = await api(`/api/courses?${params}`);
  state.courses = result.courses;
  renderCourses();
}
function openCourse(course) {
  $("#detail-cover").className = `detail-cover cover-${course.cover || "design"}`;
  $("#detail-badge").textContent = course.badge || "我的课程";
  $("#detail-category").textContent = course.category;
  $("#course-detail-title").textContent = course.title;
  $("#detail-description").textContent = course.description || "开始探索新的知识与技能";
  $("#detail-author").textContent = `讲师 ${course.author || "我的课程"}`;
  $("#detail-duration").textContent = `时长 ${course.duration || "待学习"}`;
  $("#detail-type").textContent = `资源 ${course.type.toUpperCase()}`;
  $("#detail-learners").textContent = `学习人数 ${course.learner_count || 0}`;
  $("#start-learning").onclick = async () => {
    if (!requireLogin("开始学习")) return;
    try { await api(`/api/courses/${course.id}/learn`, { method: "POST" }); closeModals(); showToast(`已开始学习《${course.title}》`); }
    catch (error) { showToast(error.message); }
  };
  openModal("#course-modal");
}
function switchAuth(mode) {
  state.authMode = mode;
  $$(".auth-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.authTab === mode));
  $$(".register-only").forEach((field) => field.classList.toggle("hidden", mode !== "register"));
  $("#auth-title").textContent = mode === "login" ? "欢迎回来" : "创建你的账号";
  $(".form-hint").textContent = mode === "login" ? "输入你的账号信息继续学习" : "注册后即可开始你的学习之旅";
  $("#auth-submit").innerHTML = mode === "login" ? "登录 <span>→</span>" : "创建账号 <span>→</span>";
  $("#auth-error").textContent = "";
}

$$(".nav-link").forEach((button) => button.addEventListener("click", () => {
  if (button.dataset.view !== "explore" && !requireLogin("查看内容")) return;
  $$(".nav-link").forEach((item) => item.classList.remove("active")); button.classList.add("active");
  if (button.dataset.view === "explore") $("#courses").scrollIntoView({ behavior: "smooth" });
  else if (button.dataset.view === "uploads") {
    if (state.user?.can_upload) openSpace("uploads");
    else showToast("学生账号没有资源管理权限");
  }
  else if (button.dataset.view === "my-learning") openSpace("learning");
  else if (button.dataset.view === "admin-users") openAdminUsers();
}));
$$(".category-tab").forEach((tab) => tab.addEventListener("click", async () => {
  state.category = tab.dataset.category; $$(".category-tab").forEach((item) => item.classList.toggle("active", item === tab));
  try { await loadCourses(); } catch (error) { showToast(error.message); }
}));
let searchTimer;
$("#search-input").addEventListener("input", (event) => {
  state.query = event.target.value; clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadCourses().catch((error) => showToast(error.message)), 180);
});
$("#course-grid").addEventListener("click", (event) => {
  const card = event.target.closest(".course-card");
  if (card) openCourse(state.courses.find((course) => String(course.id) === card.dataset.courseId));
});
$("[data-scroll-courses]").addEventListener("click", () => $("#courses").scrollIntoView({ behavior: "smooth" }));
$$("[data-open-upload]").forEach((button) => button.addEventListener("click", () => { if (requireUploadPermission()) openModal("#upload-modal"); }));
$("#user-menu").addEventListener("click", () => {
  if (!state.user) openModal("#auth-modal");
  else {
    $("#profile-name").value = state.user.name;
    $("#profile-email").value = state.user.email;
    openModal("#profile-modal");
  }
});
$$("[data-close-modal]").forEach((button) => button.addEventListener("click", closeModals));
$$(".modal-backdrop").forEach((backdrop) => backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeModals(); }));
$$(".auth-tab").forEach((tab) => tab.addEventListener("click", () => switchAuth(tab.dataset.authTab)));
$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = { name: $("#auth-name").value.trim(), email: $("#auth-email").value.trim(), password: $("#auth-password").value, role: $("#auth-role").value };
  try {
    const result = await api(`/api/auth/${state.authMode === "login" ? "login" : "register"}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.user = result.user; updateUserUI(); closeModals(); showToast(state.authMode === "login" ? "登录成功，欢迎回来" : "注册成功，开始学习吧"); event.target.reset();
  } catch (error) { showError("#auth-error", error); }
});
$("#course-file").addEventListener("change", (event) => {
  const file = event.target.files[0]; if (!file) return;
  $("#file-name").textContent = file.name; $("#selected-file").classList.remove("hidden");
});
$("#remove-file").addEventListener("click", () => { $("#course-file").value = ""; $("#selected-file").classList.add("hidden"); });
$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (!requireUploadPermission()) return;
  const file = $("#course-file").files[0];
  if (!file) { $("#upload-error").textContent = "请选择一个课程文件"; return; }
  const form = new FormData();
  form.append("title", $("#course-title").value.trim()); form.append("category", $("#course-category").value);
  form.append("type", $("#course-type").value); form.append("description", $("#course-description").value.trim()); form.append("file", file);
  try {
    const result = await api("/api/courses", { method: "POST", body: form });
    state.courses.unshift(result.course); renderCourses(); closeModals(); event.target.reset(); $("#selected-file").classList.add("hidden"); showToast("课程发布成功，文件已保存");
  } catch (error) { showError("#upload-error", error); }
});
async function openSpace(type) {
  if (!requireLogin("查看内容")) return;
  if (type === "uploads" && !state.user.can_upload) { showToast("学生账号没有资源管理权限"); return; }
  try {
    const endpoint = type === "learning" ? "learning" : "courses";
    const result = await api(`/api/profile/${endpoint}`);
    const isLearning = type === "learning";
    const isAdminResourceView = !isLearning && state.user?.is_admin;
    $("#learning-title").textContent = isLearning ? "我的学习" : "资源管理";
    $("#learning-description").textContent = isLearning
      ? "查看你正在学习的课程。"
      : isAdminResourceView ? "查看并管理平台内的全部课程。" : "查看并管理你上传的课程。";
    $("#space-list").innerHTML = result.courses.length ? result.courses.map((course) => `
      <div class="space-item" data-space-course-id="${course.id}">
        <span class="space-item-cover course-cover cover-${course.cover}"></span>
        <span class="space-item-info"><strong>${course.title}</strong><small>${isLearning ? `学习进度 ${course.progress || 0}% · ${course.author}` : `上传者 ${course.author} · ${course.type.toUpperCase()}`}</small></span>
        ${isLearning ? `<span class="progress-track"><span style="width:${course.progress || 0}%"></span></span>` : ""}
        ${isLearning ? `<button class="delete-course stop-learning" type="button" data-stop-learning-id="${course.id}">停止学习</button>` : ""}
        ${!isLearning ? `<button class="delete-course manage-learners" type="button" data-manage-learners-id="${course.id}">学习人员 (${course.learner_count || 0})</button>` : ""}
        ${!isLearning ? `<button class="delete-course" type="button" data-delete-course-id="${course.id}">${isAdminResourceView ? "管理员删除" : "删除"}</button>` : ""}
      </div>`).join("") : `<div class="space-empty">${isLearning ? "还没有正在学习的课程，去发现一门好课吧。" : isAdminResourceView ? "平台内还没有课程。" : "你还没有上传课程。"}</div>`;
    openModal("#learning-modal");
    $$(".space-item").forEach((item) => item.addEventListener("click", async (event) => {
      const manageButton = event.target.closest("[data-manage-learners-id]");
      if (manageButton) {
        event.stopPropagation();
        await openLearners(manageButton.dataset.manageLearnersId);
        return;
      }
      const stopButton = event.target.closest("[data-stop-learning-id]");
      if (stopButton) {
        event.stopPropagation();
        const courseId = stopButton.dataset.stopLearningId;
        const course = result.courses.find((candidate) => String(candidate.id) === courseId);
        if (!course || !window.confirm(`确定停止学习《${course.title}》吗？`)) return;
        try {
          await api(`/api/profile/learning/${courseId}`, { method: "DELETE" });
          showToast("已停止学习该课程");
          await openSpace("learning");
        } catch (error) { showToast(error.message); }
        return;
      }
      const deleteButton = event.target.closest("[data-delete-course-id]");
      if (deleteButton) {
        event.stopPropagation();
        const courseId = deleteButton.dataset.deleteCourseId;
        const course = result.courses.find((candidate) => String(candidate.id) === courseId);
        if (!course || !window.confirm(`确定删除《${course.title}》吗？删除后无法恢复。`)) return;
        try {
          await api(`/api/courses/${courseId}`, { method: "DELETE" });
          showToast("课程已删除");
          await openSpace("uploads");
          await loadCourses();
        } catch (error) { showToast(error.message); }
        return;
      }
      const course = result.courses.find((candidate) => String(candidate.id) === item.dataset.spaceCourseId);
      if (course) { closeModals(); openCourse(course); }
    }));
  } catch (error) { showToast(error.message); }
}
async function openLearners(courseId) {
  try {
    const result = await api(`/api/courses/${courseId}/learners`);
    const course = state.courses.find((candidate) => String(candidate.id) === String(courseId));
    $("#learners-title").textContent = `${course?.title || "课程"} · 学习人员`;
    $("#learners-description").textContent = `共 ${result.learners.length} 人正在学习`;
    $("#learners-list").innerHTML = result.learners.length
      ? result.learners.map((learner) => `
        <div class="space-item learner-item">
          <span class="author-avatar">${learner.name.slice(0, 1)}</span>
          <span class="space-item-info"><strong>${learner.name}</strong><small>学习进度 ${learner.progress || 0}%</small></span>
          <button class="delete-course" type="button" data-remove-learner-id="${learner.id}">移除</button>
        </div>`).join("")
      : '<div class="space-empty">暂时还没有学习人员。</div>';
    openModal("#learners-modal");
    $$("#learners-list [data-remove-learner-id]").forEach((button) => button.addEventListener("click", async () => {
      const learner = result.learners.find((item) => String(item.id) === button.dataset.removeLearnerId);
      if (!learner || !window.confirm(`确定将 ${learner.name} 移出这门课程吗？`)) return;
      try {
        await api(`/api/courses/${courseId}/learners/${learner.id}`, { method: "DELETE" });
        showToast("已移除学习人员");
        await openLearners(courseId);
      } catch (error) { showToast(error.message); }
    }));
  } catch (error) { showToast(error.message); }
}
async function openAdminUsers() {
  if (!state.user?.is_admin) { showToast("需要管理员权限"); return; }
  try {
    const result = await api("/api/admin/users");
    const roleNames = { admin: "管理员", teacher: "教师", student: "学生" };
    $("#admin-users-list").innerHTML = result.users.length
      ? result.users.map((user) => `
        <section class="admin-user-card">
          <div class="admin-user-heading">
            <div class="author-avatar">${user.name.slice(0, 1)}</div>
            <div class="space-item-info"><strong>${user.name}</strong><small>${user.email} · ${roleNames[user.role] || user.role}</small></div>
            <span class="admin-user-count">${user.courses.length} 门课程 · ${user.learning_records.length} 条学习记录</span>
          </div>
          ${user.courses.length ? `<div class="admin-data-group"><h3>创建的课程</h3>${user.courses.map((course) => `<div class="admin-data-row"><span>${course.title}</span><small>${course.category} · ${course.resource_type.toUpperCase()}</small></div>`).join("")}</div>` : ""}
          ${user.learning_records.length ? `<div class="admin-data-group"><h3>学习记录</h3>${user.learning_records.map((record) => `<div class="admin-data-row"><span>${record.title}</span><small>${record.author} · 进度 ${record.progress || 0}% · ${record.updated_at ? new Date(record.updated_at).toLocaleString("zh-CN") : "暂无时间"}</small></div>`).join("")}</div>` : ""}
          ${!user.courses.length && !user.learning_records.length ? '<p class="admin-user-empty">暂时没有课程或学习记录。</p>' : ""}
        </section>`).join("")
      : '<div class="space-empty">暂时没有注册账户。</div>';
    openModal("#admin-users-modal");
  } catch (error) { showToast(error.message); }
}
$("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(); form.append("name", $("#profile-name").value.trim());
  const avatar = $("#profile-avatar-file").files[0]; if (avatar) form.append("avatar", avatar);
  try { const result = await api("/api/profile", { method: "PATCH", body: form }); state.user = result.user; updateUserUI(); showToast("个人资料已更新"); }
  catch (error) { showError("#profile-error", error); }
});
$("#password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/profile/password", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: $("#current-password").value, new_password: $("#new-password").value }) });
    event.target.reset(); $("#password-error").textContent = ""; showToast("密码修改成功");
  } catch (error) { showError("#password-error", error); }
});
$("#profile-logout").addEventListener("click", async () => {
  try { await api("/api/auth/logout", { method: "POST" }); state.user = null; updateUserUI(); closeModals(); showToast("已安全退出"); }
  catch (error) { showToast(error.message); }
});
$("#profile-delete-account").addEventListener("click", async () => {
  if (!window.confirm("注销账号后，账号信息、已上传课程和课程文件都会被永久删除，确定继续吗？")) return;
  try {
    await api("/api/profile", { method: "DELETE" });
    state.user = null;
    updateUserUI();
    closeModals();
    await loadCourses();
    showToast("账号已注销");
  } catch (error) { showToast(error.message); }
});

(async function initialize() {
  try {
    const result = await api("/api/auth/me"); state.user = result.user; updateUserUI(); await loadCourses();
  } catch (error) {
    showToast(error.message);
    $("#course-grid").innerHTML = "";
  }
})();
