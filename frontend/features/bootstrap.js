(async function initialize() {
  try {
    const result = await zhixingApi.getCurrentUser(); state.user = result.user; updateUserUI(); await loadCourses();
  } catch (error) {
    showToast(error.message);
    $("#course-grid").innerHTML = "";
  }
})();
