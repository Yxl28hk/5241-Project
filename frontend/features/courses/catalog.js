function courseCover(cover) {
  return ["design", "tech", "business", "humanities"].includes(cover) ? cover : "design";
}

function renderCourses() {
  const list = state.courses;
  $("#course-grid").innerHTML = list.map((course) => `
    <article class="course-card" data-course-id="${escapeHTML(course.id)}">
      <div class="course-cover cover-${courseCover(course.cover)}">
        <span class="cover-label">${escapeHTML(course.badge || "我的课程")}</span><div class="cover-shape"></div><div class="cover-title">${escapeHTML(course.title)}</div>
      </div>
      <div class="course-info"><h3 class="course-title">${escapeHTML(course.title)}</h3><p class="course-description">${escapeHTML(course.description || "开始探索新的知识与技能")}</p>
      <div class="course-meta"><span class="course-author"><span class="author-avatar">${escapeHTML((course.author || "我").slice(0, 1))}</span>${escapeHTML(course.author || "我的课程")}</span><span class="course-duration">◷ ${escapeHTML(course.duration || "待学习")}</span></div></div>
    </article>`).join("");
  $("#empty-state").classList.toggle("hidden", list.length > 0);
  $(".category-tab[data-category='全部'] span").textContent = state.courses.length;
}
async function loadCourses() {
  const result = await zhixingApi.listCourses({ q: state.query, category: state.category });
  state.courses = result.courses;
  renderCourses();
}
function openCourse(course) {
  $("#detail-cover").className = `detail-cover cover-${courseCover(course.cover)}`;
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
    try { await openLesson(course.id); }
    catch (error) { showToast(error.message); }
  };
  openModal("#course-modal");
}
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
async function openSpace(type) {
  if (!requireLogin("查看内容")) return;
  if (type === "uploads" && !state.user.can_upload) { showToast("学生账号没有资源管理权限"); return; }
  try {
    const result = await (type === "learning" ? zhixingApi.listLearningCourses() : zhixingApi.listManagedCourses());
    const isLearning = type === "learning";
    const isAdminResourceView = !isLearning && state.user?.is_admin;
    $("#learning-title").textContent = isLearning ? "我的学习" : "资源管理";
    $("#learning-description").textContent = isLearning
      ? "查看你正在学习的课程。"
      : isAdminResourceView ? "查看并管理平台内的全部课程。" : "查看并管理你上传的课程。";
    $("#space-list").innerHTML = result.courses.length ? result.courses.map((course) => `
      <div class="space-item" data-space-course-id="${escapeHTML(course.id)}">
        <span class="space-item-cover course-cover cover-${courseCover(course.cover)}"></span>
        <span class="space-item-info"><strong>${escapeHTML(course.title)}</strong><small>${isLearning ? `学习进度 ${progressPercent(course.progress)}% · ${escapeHTML(course.author)}` : `上传者 ${escapeHTML(course.author)} · ${escapeHTML(course.type.toUpperCase())}`}</small></span>
        ${isLearning ? `<span class="progress-track"><span style="width:${progressPercent(course.progress)}%"></span></span>` : ""}
        ${isLearning ? `<button class="delete-course stop-learning" type="button" data-stop-learning-id="${escapeHTML(course.id)}">停止学习</button>` : ""}
        ${!isLearning ? `<button class="button button-ghost" type="button" data-edit-course-id="${escapeHTML(course.id)}">编辑课程</button>` : ""}
        ${!isLearning ? `<button class="delete-course manage-learners" type="button" data-manage-learners-id="${escapeHTML(course.id)}">学习人员 (${escapeHTML(course.learner_count || 0)})</button>` : ""}
        ${!isLearning ? `<button class="delete-course" type="button" data-delete-course-id="${escapeHTML(course.id)}">${isAdminResourceView ? "管理员删除" : "删除"}</button>` : ""}
      </div>`).join("") : `<div class="space-empty">${isLearning ? "还没有正在学习的课程，去发现一门好课吧。" : isAdminResourceView ? "平台内还没有课程。" : "你还没有上传课程。"}</div>`;
    openModal("#learning-modal");
    $$(".space-item").forEach((item) => item.addEventListener("click", async (event) => {
      const editButton=event.target.closest("[data-edit-course-id]");
      if(editButton){await openStudio(Number(editButton.dataset.editCourseId));return;}
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
          await zhixingApi.stopLearning(courseId);
          showToast("已停止学习该课程");
          await openSpace("learning");
          await refreshPath();
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
          await zhixingApi.deleteCourse(courseId);
          showToast("课程已删除");
          await openSpace("uploads");
          await loadCourses();
          await refreshPath();
        } catch (error) { showToast(error.message); }
        return;
      }
      const course = result.courses.find((candidate) => String(candidate.id) === item.dataset.spaceCourseId);
      if (course) { closeModals(); openCourse(course); }
    }));
  } catch (error) { showToast(error.message); }
}
