"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { ApiError, createApiClient } = require("../frontend/api/client.js");

function fixture(response = { ok: true, status: 200, json: async () => ({ success: true }) }) {
  const calls = [];
  const client = createApiClient({ baseUrl: "https://example.test/", fetchImpl: async (...args) => {
    calls.push(args);
    return response;
  } });
  return { client, calls };
}

test("all JSON business functions use the expected route, method and payload", async () => {
  const data = { revision: 2, token: "session", request_id: "uuid", notes: "笔记", choice_id: "pr", step: 0 };
  const cases = [
    ["getConfig", [], "GET", "/api/prototype/config"],
    ["getCurrentUser", [], "GET", "/api/auth/me"],
    ["register", [data], "POST", "/api/auth/register", data],
    ["login", [data], "POST", "/api/auth/login", data],
    ["logout", [], "POST", "/api/auth/logout"],
    ["changePassword", [data], "PATCH", "/api/profile/password", data],
    ["deleteAccount", [], "DELETE", "/api/profile"],
    ["listCourses", [], "GET", "/api/courses?q=&category=%E5%85%A8%E9%83%A8"],
    ["deleteCourse", [7], "DELETE", "/api/courses/7"],
    ["listManagedCourses", [], "GET", "/api/profile/courses"],
    ["listLearningCourses", [], "GET", "/api/profile/learning"],
    ["startLearning", [7], "POST", "/api/courses/7/learn"],
    ["stopLearning", [7], "DELETE", "/api/profile/learning/7"],
    ["listLearners", [7], "GET", "/api/courses/7/learners"],
    ["removeLearner", [7, "9"], "DELETE", "/api/courses/7/learners/9"],
    ["listUsers", [], "GET", "/api/admin/users"],
    ["getLearningProfile", [], "GET", "/api/learning-profile"],
    ["updateLearningProfile", [{ weekly_hours: null }], "PATCH", "/api/learning-profile", { weekly_hours: null }],
    ["getLearningPath", [], "GET", "/api/learning-path"],
    ["selectLearningPath", ["quality"], "POST", "/api/learning-path/select", { path_id: "quality" }],
    ["getLesson", [7], "GET", "/api/courses/7/lesson"],
    ["updateProgress", [7, 0], "PATCH", "/api/courses/7/progress", { progress: 0 }],
    ["getExercise", [7], "GET", "/api/courses/7/exercise"],
    ["submitExercise", [7, data], "POST", "/api/courses/7/exercise", data],
    ["getNotebook", [7], "GET", "/api/courses/7/notebook"],
    ["saveNotebook", [7, data], "PATCH", "/api/courses/7/notebook", data],
    ["restoreConversation", [7], "POST", "/api/courses/7/conversation"],
    ["resetConversation", [7, data], "DELETE", "/api/courses/7/conversation", data],
    ["askTutor", [data], "POST", "/api/tutor", data],
    ["startMission", [], "POST", "/api/missions/release-rescue/start"],
    ["answerMission", [9, data], "POST", "/api/missions/attempts/9/answer", data],
    ["getQuizOverview", [], "GET", "/api/quiz/overview"],
    ["startQuizRun", [data], "POST", "/api/quiz/runs", data],
    ["getQuizRun", [3], "GET", "/api/quiz/runs/3"],
    ["answerQuiz", [3, data], "POST", "/api/quiz/runs/3/answer", data],
    ["abandonQuizRun", [3], "POST", "/api/quiz/runs/3/abandon"],
    ["getQuizResult", ["quest"], "GET", "/api/quiz/result?mode=quest"],
    ["adoptQuizLevel", [], "POST", "/api/quiz/profile/adopt"],
    ["clearQuizReference", [], "DELETE", "/api/quiz/profile/reference"],
  ];
  for (const [name, args, method, path, body] of cases) {
    const { client, calls } = fixture();
    assert.deepEqual(await client[name](...args), { success: true }, name);
    const [url, options] = calls[0];
    assert.equal(url, `https://example.test${path}`, name);
    assert.equal(options.method || "GET", method, name);
    assert.equal(options.credentials, "same-origin", name);
    if (body) {
      assert.deepEqual(JSON.parse(options.body), body, name);
      assert.equal(options.headers.get("Content-Type"), "application/json", name);
    } else assert.equal(options.body, undefined, name);
  }
});

test("search values are encoded without turning them into extra query parameters", async () => {
  const { client, calls } = fixture();
  await client.listCourses({ q: "Git & PR?", category: "技术" });
  const url = new URL(calls[0][0]);
  assert.equal(url.searchParams.get("q"), "Git & PR?");
  assert.equal(url.searchParams.get("category"), "技术");
  assert.equal([...url.searchParams].length, 2);
});

test("multipart uploads support objects and existing FormData, and remove manual content type", async () => {
  const { client, calls } = fixture();
  await client.createCourse({ title: "讲义", file: new Blob(["pdf"], { type: "application/pdf" }), description: "", ignored: undefined });
  const [url, options] = calls[0];
  assert.equal(url, "https://example.test/api/courses");
  assert.equal(options.method, "POST");
  assert.equal(options.body.get("title"), "讲义");
  assert.equal(await options.body.get("file").text(), "pdf");
  assert.equal(options.body.get("description"), "");
  assert.equal(options.body.has("ignored"), false);
  assert.equal(options.headers.has("Content-Type"), false);
  const form = new FormData();
  form.set("name", "合作者");
  await client.updateProfile(form, { headers: { "Content-Type": "multipart/form-data", "X-Test": "yes" } });
  assert.equal(calls[1][1].method, "PATCH");
  assert.equal(calls[1][1].body, form);
  assert.equal(calls[1][1].headers.has("Content-Type"), false);
  assert.equal(calls[1][1].headers.get("X-Test"), "yes");
});

test("conflict and retryable errors retain status and full server response", async () => {
  for (const status of [401, 403, 404, 409, 413, 502]) {
    const body = { error: "请重试", retryable: status === 502, revision: 3 };
    const { client, calls } = fixture({ ok: false, status, json: async () => body });
    await assert.rejects(client.getCurrentUser(), (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.message, body.error);
      assert.equal(error.status, status);
      assert.equal(error.body, body);
      assert.equal(error.retryable, status === 502);
      return true;
    });
    assert.equal(calls.length, 1); // No automatic retries of business operations.
  }
});

test("non-JSON responses are errors and 204 is handled without parsing JSON", async () => {
  for (const ok of [true, false]) {
    const { client } = fixture({ ok, status: ok ? 200 : 500, json: async () => { throw new SyntaxError(); } });
    await assert.rejects(client.getConfig(), (error) => error instanceof ApiError && error.body === null);
  }
  const { client } = fixture({ ok: true, status: 204 });
  assert.equal(await client.logout(), null);
});

test("request options preserve cancellation, keepalive and custom headers", async () => {
  const { client, calls } = fixture();
  const controller = new AbortController();
  await client.saveNotebook(7, { revision: 0, notes: "" }, {
    signal: controller.signal, keepalive: true, headers: { "X-Test": "yes" },
  });
  assert.equal(calls[0][1].signal, controller.signal);
  assert.equal(calls[0][1].keepalive, true);
  assert.equal(calls[0][1].headers.get("X-Test"), "yes");
  for (const error of [new TypeError("offline"), new DOMException("cancelled", "AbortError")]) {
    const client = createApiClient({ fetchImpl: async () => { throw error; } });
    await assert.rejects(client.getConfig(), (caught) => caught === error);
  }
});

test("body-reading cancellation and network failures keep their original identity", async () => {
  for (const error of [new DOMException("cancelled", "AbortError"), new TypeError("connection lost")]) {
    const { client } = fixture({ ok: true, status: 200, json: async () => { throw error; } });
    await assert.rejects(client.getConfig(), (caught) => caught === error);
  }
});

test("aborting a real response after headers preserves AbortError", async (t) => {
  const http = require("node:http");
  const server = http.createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.write('{"value":'); // Leave the JSON body unfinished until cancelled.
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(async () => {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  });
  const controller = new AbortController();
  const client = createApiClient({
    baseUrl: `http://127.0.0.1:${server.address().port}`,
    fetchImpl: async (...args) => {
      const response = await fetch(...args);
      // Headers have arrived, so abort while request() is reading the body.
      setTimeout(() => controller.abort(), 0);
      return response;
    },
  });
  await assert.rejects(client.getConfig({ signal: controller.signal }), (error) => {
    assert.equal(error.name, "AbortError");
    assert.equal(error instanceof ApiError, false);
    return true;
  });
});

test("invalid IDs fail locally and file URL helpers encode filenames", () => {
  const { client, calls } = fixture();
  for (const id of [null, undefined, 0, -1, 1.5, "../profile", "1?admin=true"]) {
    assert.throws(() => client.getLesson(id), TypeError);
  }
  assert.equal(calls.length, 0);
  assert.equal(client.getUploadUrl("讲义 #1.pdf"), "https://example.test/uploads/%E8%AE%B2%E4%B9%89%20%231.pdf");
  assert.equal(client.getAvatarUrl("avatar.png"), "https://example.test/avatars/avatar.png");
});

test("plain browser script exports work without CommonJS or DOM", async () => {
  const context = vm.createContext({ fetch: async () => ({ ok: true, status: 200, json: async () => ({ user: null }) }) });
  vm.runInContext(fs.readFileSync(require.resolve("../frontend/api/client.js"), "utf8"), context);
  assert.equal(typeof context.createApiClient, "function");
  assert.equal(typeof context.ApiError, "function");
  assert.equal((await context.zhixingApi.getCurrentUser()).user, null);
});
