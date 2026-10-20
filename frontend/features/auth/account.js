function updateUserUI() {
  const user = state.user;
  const studentSession = user?.role === "student";
  const previousStudent = document.body.dataset.studentId;
  document.body.classList.toggle("learner-signed-in", studentSession);
  document.body.dataset.studentId = studentSession ? String(user.id) : "";
  if (studentSession && previousStudent !== String(user.id)) {
    $$(".nav-link").forEach(button => button.classList.toggle("active", button.dataset.view === "my-learning"));
    window.scrollTo({top:0, behavior:"instant"});
  } else if (!user && previousStudent) {
    $$(".nav-link").forEach(button => button.classList.toggle("active", button.dataset.view === "explore"));
    window.scrollTo({top:0, behavior:"instant"});
  }
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
  if (typeof refreshPath === "function") refreshPath();
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
function switchAuth(mode) {
  state.authMode = mode;
  $$(".auth-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.authTab === mode));
  $$(".register-only").forEach((field) => field.classList.toggle("hidden", mode !== "register"));
  $("#auth-title").textContent = mode === "login" ? "欢迎回来" : "创建你的账号";
  $(".form-hint").textContent = mode === "login" ? "输入你的账号信息继续学习" : "注册后即可开始你的学习之旅";
  $("#auth-submit").innerHTML = mode === "login" ? "登录 <span>→</span>" : "创建账号 <span>→</span>";
  $("#auth-error").textContent = "";
}

$("#user-menu").addEventListener("click", () => {
  if (!state.user) openModal("#auth-modal");
  else {
    $("#profile-name").value = state.user.name;
    $("#profile-email").value = state.user.email;
    openModal("#profile-modal");
  }
});
$$(".auth-tab").forEach((tab) => tab.addEventListener("click", () => switchAuth(tab.dataset.authTab)));
$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = { name: $("#auth-name").value.trim(), email: $("#auth-email").value.trim(), password: $("#auth-password").value, role: $("#auth-role").value };
  try {
    const result = await zhixingApi[state.authMode === "login" ? "login" : "register"](payload);
    state.user = result.user; updateUserUI(); closeModals(); showToast(state.authMode === "login" ? "登录成功，欢迎回来" : "注册成功，开始学习吧"); event.target.reset();
  } catch (error) { showError("#auth-error", error); }
});
async function openAdminUsers() {
  if (!state.user?.is_admin) { showToast("需要管理员权限"); return; }
  try {
    const result = await zhixingApi.listUsers();
    const roleNames = { admin: "管理员", teacher: "教师", student: "学生" };
    $("#admin-users-list").innerHTML = result.users.length
      ? result.users.map((user) => `
        <section class="admin-user-card">
          <div class="admin-user-heading">
            <div class="author-avatar">${escapeHTML(user.name.slice(0, 1))}</div>
            <div class="space-item-info"><strong>${escapeHTML(user.name)}</strong><small>${escapeHTML(user.email)} · ${escapeHTML(roleNames[user.role] || user.role)}</small></div>
            <span class="admin-user-count">${user.courses.length} 门课程 · ${user.learning_records.length} 条学习记录</span>
          </div>
          ${user.courses.length ? `<div class="admin-data-group"><h3>创建的课程</h3>${user.courses.map((course) => `<div class="admin-data-row"><span>${escapeHTML(course.title)}</span><small>${escapeHTML(course.category)} · ${escapeHTML(course.resource_type.toUpperCase())}</small></div>`).join("")}</div>` : ""}
          ${user.learning_records.length ? `<div class="admin-data-group"><h3>学习记录</h3>${user.learning_records.map((record) => `<div class="admin-data-row"><span>${escapeHTML(record.title)}</span><small>${escapeHTML(record.author)} · 进度 ${progressPercent(record.progress)}% · ${record.updated_at ? new Date(record.updated_at).toLocaleString("zh-CN") : "暂无时间"}</small></div>`).join("")}</div>` : ""}
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
  try { const result = await zhixingApi.updateProfile(form); state.user = result.user; updateUserUI(); showToast("个人资料已更新"); }
  catch (error) { showError("#profile-error", error); }
});
$("#password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await zhixingApi.changePassword({ current_password: $("#current-password").value, new_password: $("#new-password").value });
    event.target.reset(); $("#password-error").textContent = ""; showToast("密码修改成功");
  } catch (error) { showError("#password-error", error); }
});
$("#profile-logout").addEventListener("click", async () => {
  if (typeof flushNotebook === "function" && !await flushNotebook()) { showToast("请先保存笔记或处理版本冲突再退出"); return; }
  try { await zhixingApi.logout(); state.user = null; updateUserUI(); closeModals(); showToast("已安全退出"); }
  catch (error) { showToast(error.message); }
});
$("#profile-delete-account").addEventListener("click", async () => {
  if (!window.confirm("注销账号后，账号信息、已上传课程和课程文件都会被永久删除，确定继续吗？")) return;
  try {
    await zhixingApi.deleteAccount();
    state.user = null;
    updateUserUI();
    closeModals();
    await loadCourses();
    showToast("账号已注销");
  } catch (error) { showToast(error.message); }
});
