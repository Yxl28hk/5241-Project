$$(".nav-link").forEach((button) => button.addEventListener("click", () => {
  if (button.dataset.view !== "explore" && !requireLogin("查看内容")) return;
  $$(".nav-link").forEach((item) => item.classList.remove("active")); button.classList.add("active");
  if (button.dataset.view === "explore") $("#courses").scrollIntoView({ behavior: "smooth" });
  else if (button.dataset.view === "uploads") {
    if (state.user?.can_upload) openSpace("uploads");
    else showToast("学生账号没有资源管理权限");
  }
  else if (button.dataset.view === "my-learning") $("#student-workbench").scrollIntoView({behavior:"smooth"});
  else if (button.dataset.view === "learning-profile") openLearningProfile();
  else if (button.dataset.view === "admin-quiz") openAdminQuiz();
  else if (button.dataset.view === "admin-users") openAdminUsers();
}));
$("[data-scroll-courses]").addEventListener("click", () => $("#courses").scrollIntoView({ behavior: "smooth" }));
$$("[data-open-upload]").forEach((button) => button.addEventListener("click", () => { openStudio(); }));
