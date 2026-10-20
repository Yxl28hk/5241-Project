/** Standalone browser API client. See docs/API_README.md for the public contract. */
(function (root, factory) {
  const exports = factory();
  if (typeof module === "object" && module.exports) module.exports = exports;
  else Object.assign(root, exports);
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  class ApiError extends Error {
    constructor(message, status, body) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.body = body;
      this.retryable = body?.retryable === true;
    }
  }

  /** Each client uses the browser's session cookies; creating one does not log in. */
  function createApiClient({ baseUrl = "", fetchImpl = (...args) => globalThis.fetch(...args) } = {}) {
    const base = baseUrl.replace(/\/+$/, "");
    const id = (value) => {
      const text = String(value);
      if (!/^[1-9]\d*$/.test(text)) throw new TypeError("ID 必须是正整数");
      return text;
    };
    const course = (courseId) => `/api/courses/${id(courseId)}`;

    async function request(path, options = {}) {
      const response = await fetchImpl(`${base}${path}`, { credentials: "same-origin", ...options });
      if (response.status === 204) return null;
      let body;
      try { body = await response.json(); }
      catch (error) {
        // Reading a response body can fail because it was cancelled or the
        // connection broke. Preserve those errors for the caller's retry UI.
        if (error?.name !== "SyntaxError") throw error;
        throw new ApiError("服务返回了非 JSON 响应，请检查服务地址和运行状态", response.status, null);
      }
      if (!response.ok) {
        throw new ApiError(body?.error || `请求失败（HTTP ${response.status}）`, response.status, body);
      }
      return body;
    }
    function json(method, path, data, options = {}) {
      const headers = new Headers(options.headers);
      headers.set("Content-Type", "application/json");
      return request(path, { ...options, method, headers, body: JSON.stringify(data) });
    }
    function form(method, path, fields, options = {}) {
      const body = fields instanceof FormData ? fields : new FormData();
      if (!(fields instanceof FormData)) {
        for (const [key, value] of Object.entries(fields)) {
          if (value !== undefined && value !== null) body.append(key, value);
        }
      }
      const headers = new Headers(options.headers);
      headers.delete("Content-Type"); // The browser supplies the multipart boundary.
      return request(path, { ...options, method, headers, body });
    }
    const send = (method, path, options) => request(path, { ...options, method });

    return Object.freeze({
      request,
      getConfig: (options) => request("/api/prototype/config", options),
      getCurrentUser: (options) => request("/api/auth/me", options),
      register: (data, options) => json("POST", "/api/auth/register", data, options),
      login: (data, options) => json("POST", "/api/auth/login", data, options),
      logout: (options) => send("POST", "/api/auth/logout", options),
      updateProfile: (data, options) => form("PATCH", "/api/profile", data, options),
      changePassword: (data, options) => json("PATCH", "/api/profile/password", data, options),
      deleteAccount: (options) => send("DELETE", "/api/profile", options),
      listCourses: ({ q = "", category = "全部" } = {}, options) =>
        request(`/api/courses?${new URLSearchParams({ q, category })}`, options),
      createCourse: (data, options) => form("POST", "/api/courses", data, options),
      deleteCourse: (courseId, options) => send("DELETE", course(courseId), options),
      listManagedCourses: (options) => request("/api/profile/courses", options),
      listLearningCourses: (options) => request("/api/profile/learning", options),
      startLearning: (courseId, options) => send("POST", `${course(courseId)}/learn`, options),
      stopLearning: (courseId, options) => send("DELETE", `/api/profile/learning/${id(courseId)}`, options),
      listLearners: (courseId, options) => request(`${course(courseId)}/learners`, options),
      removeLearner: (courseId, userId, options) => send("DELETE", `${course(courseId)}/learners/${id(userId)}`, options),
      listUsers: (options) => request("/api/admin/users", options),
      getLearningProfile: (options) => request("/api/learning-profile", options),
      updateLearningProfile: (data, options) => json("PATCH", "/api/learning-profile", data, options),
      getLearningPath: (options) => request("/api/learning-path", options),
      selectLearningPath: (pathId, options) => json("POST", "/api/learning-path/select", { path_id: pathId }, options),
      getLesson: (courseId, options) => request(`${course(courseId)}/lesson`, options),
      updateProgress: (courseId, progress, options) => json("PATCH", `${course(courseId)}/progress`, { progress }, options),
      getExercise: (courseId, options) => request(`${course(courseId)}/exercise`, options),
      submitExercise: (courseId, data, options) => json("POST", `${course(courseId)}/exercise`, data, options),
      getNotebook: (courseId, options) => request(`${course(courseId)}/notebook`, options),
      saveNotebook: (courseId, data, options) => json("PATCH", `${course(courseId)}/notebook`, data, options),
      restoreConversation: (courseId, options) => send("POST", `${course(courseId)}/conversation`, options),
      resetConversation: (courseId, data, options) => json("DELETE", `${course(courseId)}/conversation`, data, options),
      askTutor: (data, options) => json("POST", "/api/tutor", data, options),
      startMission: (options) => send("POST", "/api/missions/release-rescue/start", options),
      answerMission: (attemptId, data, options) => json("POST", `/api/missions/attempts/${id(attemptId)}/answer`, data, options),
      // File endpoints return binary content: use these URLs in links, images or fetch.
      getUploadUrl: (filename) => `${base}/uploads/${encodeURIComponent(filename)}`,
      getAvatarUrl: (filename) => `${base}/avatars/${encodeURIComponent(filename)}`,
    });
  }

  return { ApiError, createApiClient, zhixingApi: createApiClient() };
});
