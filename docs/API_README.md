# API 函数使用说明（合作者接入）

[`frontend/api/client.js`](../frontend/api/client.js) 是项目所有现有 HTTP API 的统一 JavaScript 封装，不依赖页面 DOM，也不需要 npm 或前端构建。`frontend/features/` 下的业务脚本均使用该模块。后端启动和数据库配置见根目录 [README](../README.md)，模块分工见 [架构说明](ARCHITECTURE.md)。旧 `/api.js` 地址保留兼容，新页面使用 `/frontend/api/client.js`。

## 1. 快速使用

在 Flask 提供的页面中，先加载客户端，再加载业务脚本：

```html
<script src="/frontend/api/client.js"></script>
<script src="my-feature.js"></script>
```

在 `my-feature.js` 中直接使用全局对象 `zhixingApi`：

```javascript
// 替换为已注册的账号；注册也会自动登录。
const { user } = await zhixingApi.login({
  email: "your-account@example.com",
  password: "your-password",
});
const { courses } = await zhixingApi.listCourses({ q: "", category: "全部" });
if (courses.length) {
  const courseId = courses[0].id; // 使用服务返回的 ID，不要写死示例课 ID。
  await zhixingApi.startLearning(courseId);
  const { lesson } = await zhixingApi.getLesson(courseId);
  console.log(user.name, lesson.title);
  await zhixingApi.updateProgress(courseId, 50);
}
```

以上 `await` 代码放在 `async function` 中执行，或在开发者控制台执行。普通 `<script>` 文件不能直接使用顶层 `await`。

登录使用 Flask session Cookie，不使用 Bearer token。默认请求使用 `credentials: "same-origin"`，浏览器负责保存和发送 Cookie；同一浏览器的多个客户端实例共享登录状态。公开接口有 `getConfig`、`getCurrentUser`、`listCourses`、注册和登录；`getCurrentUser()` 在未登录时返回 `{ user: null }`。其余业务接口需要登录，退出后重新调用登录接口即可。

模块还导出 `createApiClient` 和 `ApiError`。通常使用默认 `zhixingApi` 即可；测试时可注入 `fetchImpl`：

```javascript
const client = createApiClient({ baseUrl: "" }); // 服务根地址，不包含 /api。
const { database, tutor_mode } = await client.getConfig();
```

客户端允许设置 `baseUrl`，但当前后端没有配置跨域 CORS。合作开发优先通过同一 Flask 服务或同源反向代理访问。仅改 `baseUrl` 无法解决跨域；浏览器跨域还需要服务端允许指定来源、凭据和预检，并检查 Cookie 策略。Node 的 `require('./frontend/api/client.js')` 主要供自动化测试使用；原生 Node fetch 不会自动维持登录 Cookie，需要自行注入带 Cookie 管理的 `fetchImpl` 才能持续登录。

## 2. 统一返回值和错误

所有请求函数返回 `Promise`，成功时保留后端完整 JSON 对象，不自动提取内部字段。例如 `listCourses()` 返回 `{ courses: [...] }`，`getNotebook()` 返回 `{ notebook: {...} }`。204 空响应返回 `null`。`getUploadUrl`、`getAvatarUrl` 同步返回字符串。

每个请求函数最后一个参数是可选的 fetch 配置，例如 `{ signal, keepalive }`。业务方法固定请求方法和请求体；不要用 options 覆盖这些内容。需要直接访问其他 JSON 接口时可用 `request(path, options)`，其中 path 为以 `/` 开头的服务相对路径。

```javascript
try {
  await zhixingApi.updateProgress(123, 50);
} catch (error) {
  if (error instanceof ApiError) {
    console.error(error.status, error.message, error.body);
    if (error.status === 401) { /* 展示登录入口 */ }
    if (error.status === 409) { /* 重新读取最新状态，由用户决定后再提交 */ }
  } else {
    // 网络错误、AbortError 或本地参数 TypeError。
    console.error(error);
  }
}
```

HTTP 错误抛出 `ApiError`：`status` 为 HTTP 状态码，`body` 为后端完整 JSON，`retryable` 仅当后端明确返回 `true` 时为真。非 JSON 响应也抛出 `ApiError`，`body` 为 `null`。网络及取消错误保留 fetch 原始错误。ID 接受正整数或正整数字符串，否则抛出 `TypeError`；其余业务参数由服务端校验。

| 状态 | 含义 / 建议 |
| --- | --- |
| 400 | 参数不合法，按错误信息修正 |
| 401 | 尚未登录或凭据不正确 |
| 403 | 角色没有权限 |
| 404 | 资源不存在、尚未加入学习或无权访问的资源 |
| 409 | 重复注册、笔记/会话/任务版本冲突；重新读取状态，避免盲目重试 |
| 413 | 上传超过服务器 500MB 总请求限制 |
| 502 | Tutor 上游不可用，检查 `retryable` |

客户端不自动重试写入，也不自动刷新笔记/会话版本，防止覆盖其他窗口的修改。

## 3. 完整函数与接口对照

表中省略最后的可选 `options` 参数；`data` 字段名与后端保持一致。

| 函数 | HTTP 接口 | 参数 / 返回 / 权限 |
| --- | --- | --- |
| `getConfig()` | GET `/api/prototype/config` | `{ database, tutor_mode }`；公开 |
| `getCurrentUser()` | GET `/api/auth/me` | `{ user }`；公开，未登录为 null |
| `register(data)` | POST `/api/auth/register` | `{ name, email, password, role? }`；密码至少 6 位，role 为 student（默认）或 teacher；返回 `{ user }` 并登录 |
| `login(data)` | POST `/api/auth/login` | `{ email, password }` → `{ user }` |
| `logout()` | POST `/api/auth/logout` | `{ message }`，清除会话 |
| `updateProfile(data)` | PATCH `/api/profile` | `{ name, avatar? }` 或 FormData；name 必填，1–40 字；返回 `{ user }` |
| `changePassword(data)` | PATCH `/api/profile/password` | `{ current_password, new_password }`；新密码至少 6 位 → `{ message }` |
| `deleteAccount()` | DELETE `/api/profile` | 注销当前账号并删除其课程和学习记录 → `{ message }` |
| `listCourses(filters?)` | GET `/api/courses` | `{ q?, category? }`；默认空搜索、全部分类 → `{ courses }`；公开 |
| `createCourse(data)` | POST `/api/courses` | `{ title, category, type, description?, file }` 或 FormData → `{ course }`；教师/管理员 |
| `deleteCourse(courseId)` | DELETE `/api/courses/<id>` | `{ message }`；教师仅自己的课，管理员全部 |
| `listManagedCourses()` | GET `/api/profile/courses` | `{ courses }`；教师自己的课，管理员全部 |
| `listLearningCourses()` | GET `/api/profile/learning` | `{ courses }`，当前账号的学习课程及 progress |
| `startLearning(courseId)` | POST `/api/courses/<id>/learn` | 加入/打开课程、记录学习位置 → `{ message }` |
| `stopLearning(courseId)` | DELETE `/api/profile/learning/<id>` | 移除自己的学习记录 → `{ message }` |
| `listLearners(courseId)` | GET `/api/courses/<id>/learners` | `{ learners }`；课程所属教师/管理员 |
| `removeLearner(courseId, userId)` | DELETE `/api/courses/<id>/learners/<userId>` | `{ message }`；课程所属教师/管理员 |
| `listUsers()` | GET `/api/admin/users` | `{ users }`，含课程及学习记录；仅管理员 |
| `getLearningProfile()` | GET `/api/learning-profile` | `{ profile }`，当前账号画像 |
| `updateLearningProfile(data)` | PATCH `/api/learning-profile` | 部分更新 `{ goal?, level?, weekly_hours? }` → `{ profile }` |
| `getLearningPath()` | GET `/api/learning-path` | 完整学习快照，含 `catalog`、`active_path_id`、`modules`、`mission`、`quest` 等 |
| `selectLearningPath(pathId)` | POST `/api/learning-path/select` | collaboration / quality / engineering → `{ active_path_id, message }` |
| `getLesson(courseId)` | GET `/api/courses/<id>/lesson` | `{ lesson }`；含正文、progress、status、file_url |
| `updateProgress(courseId, progress)` | PATCH `/api/courses/<id>/progress` | progress 为 0–100 整数；需先 startLearning → `{ progress }` |
| `getExercise(courseId)` | GET `/api/courses/<id>/exercise` | `{ exercise, result }`；未配置练习时均为 null |
| `submitExercise(courseId, data)` | POST `/api/courses/<id>/exercise` | `{ version, choice_id }` → `{ result }`；版本及选项取自 getExercise |
| `getNotebook(courseId)` | GET `/api/courses/<id>/notebook` | `{ notebook }`，含 notes、task_draft、revision |
| `saveNotebook(courseId, data)` | PATCH `/api/courses/<id>/notebook` | `{ revision, notes?, task_draft? }` → `{ notebook }`；至少一个内容字段 |
| `restoreConversation(courseId)` | POST `/api/courses/<id>/conversation` | 恢复或创建当前课会话 → `{ conversation }` |
| `resetConversation(courseId, data)` | DELETE `/api/courses/<id>/conversation` | `{ token, revision }` → `{ conversation }`；清空本课会话 |
| `askTutor(data)` | POST `/api/tutor` | 必填 `{ course_id, message }`，其余见下文；返回 `{ answer, mode, label, context, conversation? }` |
| `startMission()` | POST `/api/missions/release-rescue/start` | 创建或恢复未完成任务 → `{ attempt }` |
| `answerMission(attemptId, data)` | POST `/api/missions/attempts/<id>/answer` | `{ step, choice_id }` → `{ attempt, feedback }` |
| `getQuizOverview()` | GET `/api/quiz/overview` | `{ quest, reference }`，关卡状态与历史最佳；需登录 |
| `startQuizRun(data)` | POST `/api/quiz/runs` | `{ mode }` 为 `quest`（默认）/ `quick` / `revenge`；创建或恢复未完成局 → `{ run }`；新建 201，恢复 200；复仇池为空返回 400 |
| `getQuizRun(runId)` | GET `/api/quiz/runs/<id>` | `{ run }`；仅本人 |
| `answerQuiz(runId, data)` | POST `/api/quiz/runs/<id>/answer` | `{ step, question_code, choice_id }` → `{ correct, explanation, run, level_result, finished }` |
| `abandonQuizRun(runId)` | POST `/api/quiz/runs/<id>/abandon` | 结束本局并保留已答成绩 → `{ run, message }` |
| `getQuizResult(mode)` | GET `/api/quiz/result?mode=<mode>` | `{ result, best_score, badge, reference }`；未完成时 `result` 为 null |
| `adoptQuizLevel()` | POST `/api/quiz/profile/adopt` | 学生显式采用闯关参考作为基础水平 → `{ level, message }` |
| `clearQuizReference()` | DELETE `/api/quiz/profile/reference` | 清空全部闯关数据（闯关局、答题记录、画像参考），不影响自报画像 → `{ message }`。**不可撤销，前端须先 `confirm`** |
| `getUploadUrl(filename)` | GET `/uploads/<filename>` | 生成文件链接；不发请求 |
| `getAvatarUrl(filename)` | GET `/avatars/<filename>` | 生成头像链接；不发请求 |

画像 `goal` 可取空字符串、collaboration、quality、engineering；`level` 可取空字符串、beginner、intermediate、experienced；`weekly_hours` 为 1–40 整数或 null。省略字段保留原值，传空字符串/null 可清空对应字段。

## 4. 文件上传

```javascript
const file = document.querySelector('input[type="file"]').files[0];
const { course } = await zhixingApi.createCourse({
  title: "协作开发讲义",
  category: "技术",
  type: "pdf",
  description: "团队学习资料",
  file,
});
console.log(course.file_url);

// 头像也支持直接传 File；name 始终必填。
// await zhixingApi.updateProfile({ name: "合作者", avatar: avatarFile });
```

课程分类为设计、技术、商业、人文；type 为 pdf、word、ppt、video；扩展名支持 pdf、doc/docx、ppt/pptx、mp4/mov。头像支持 jpg/jpeg、png、gif、webp。函数自动构造 multipart FormData，并让浏览器设置 Content-Type boundary；不要手动填写上传请求的 Content-Type。也可以传现有 FormData。

附件和头像保存在运行服务器的本地 `uploads/`，共享 Neon 数据库不会同步文件。优先使用响应自带的 `file_url`、`avatar_url`；只有拿到存储文件名时才用 URL 函数。文件接口返回二进制，不能用 JSON `request()` 读取。

## 5. 笔记与练习

```javascript
const { notebook } = await zhixingApi.getNotebook(courseId);
const { notebook: saved } = await zhixingApi.saveNotebook(courseId, {
  revision: notebook.revision,
  notes: "PR 合并前先检查 CI。",
});
// 后续写入使用 saved.revision；task_draft 未传时保留原内容。

const { exercise } = await zhixingApi.getExercise(courseId);
if (exercise) {
  const { result } = await zhixingApi.submitExercise(courseId, {
    version: exercise.version,
    choice_id: exercise.choices[0].id,
  });
  console.log(result.correct, result.explanation);
}
```

notes 最多 12000 字，task_draft 最多 4000 字；revision 必须是服务返回的非负整数。409 时先保留本地草稿，再重新读取并让用户处理冲突。练习提交不会自动完成课程；完成需要显式调用 `updateProgress(courseId, 100)`。

## 6. Tutor 与持久会话

简单提问只传 `{ course_id, message }`，不会写入持久会话。message 去除首尾空格后为 1–1000 字。`mode` 为 auto（默认）或 guided-demo（规则知识卡）；只有服务端完整配置 Tutor 环境变量时，auto 才可能调用真实模型。

持久会话先恢复，再携带 token、revision 和 UUID request_id 提问：

```javascript
const { conversation } = await zhixingApi.restoreConversation(courseId);
const payload = {
  course_id: courseId,
  message: "解释一下本节的关键概念",
  token: conversation.token,
  revision: conversation.revision,
  request_id: crypto.randomUUID(),
  context_key: "overview",
  action: "answer",
  mode: "auto",
};
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 30000);
try {
  const reply = await zhixingApi.askTutor(payload, { signal: controller.signal });
  console.log(reply.answer, reply.conversation);
  // 下一次提问使用 reply.conversation 的 token / revision 和新的 request_id。
} finally {
  clearTimeout(timer);
}
```

`context_key` 默认 overview，其他有效定位键以课时正文为准；task、exercise 可配合 `action: "hint"` 和 `hint_step: 1 | 2`，或 `action: "reference"` 获取预设解析。持久会话历史由服务端读取；非持久调用可传 history，格式为 `{ role: "user" | "assistant", content: "..." }` 数组（最多 12 条，每条去除首尾空格后为 1–3000 字）。

网络失败重试同一持久请求时，应复用整个 payload（含 request_id）；服务端对最近一次相同请求返回已保存回答。改变问题、mode 或操作必须生成新的 request_id。409 时重新恢复会话再决定下一步。超时取消只终止客户端等待，服务端可能已保存回答，所以不能直接换 request_id 盲目重发。

开启新对话时，传最新会话的 token 和 revision 给 `resetConversation`；成功后使用返回的新会话，原笔记及练习不受影响。

## 7. 情境任务

```javascript
const { attempt } = await zhixingApi.startMission();
if (!attempt.complete) {
  const result = await zhixingApi.answerMission(attempt.id, {
    step: attempt.step,
    choice_id: attempt.current.choices[0].id,
  });
  console.log(result.feedback, result.attempt);
}
```

总共四步，每步 25 分，75 分通过；使用返回的 step 和选项，不向服务器提交分数。重复或过期步骤返回 409。`startMission()` 恢复未完成记录；完成后再次调用才会创建新记录。

## 8. 水平闯关

```javascript
const { run } = await zhixingApi.startQuizRun();
const result = await zhixingApi.answerQuiz(run.id, {
  step: run.step,
  question_code: run.question.code,
  choice_id: run.question.choices[0].id,
});
console.log(result.correct, result.explanation, result.run);
```

共 3 关 × 6 题 = 18 题；每关答对 4 题解锁下一关，答错不扣分。服务端判定正确性，客户端不要提交分数或正确性。使用返回的 `step` 与 `question_code`，重复或过期步骤返回 409。`startQuizRun()` 恢复未完成记录；一局结束后才创建新的记录。

### 三种模式

| mode | 题数 | 关卡结算 | 计入历史最佳 / 徽章 / 画像 |
| --- | --- | --- | --- |
| `quest`（默认） | 18 | 有 | 是 |
| `quick` | 8 | 无 | **否** |
| `revenge` | ≤ 6（取自错题池） | 无 | **否** |

```javascript
const { run } = await zhixingApi.startQuizRun({mode: "quick"});
const data = await zhixingApi.getQuizResult("quick");
```

`quest` 每局从 30 题题库里**分层抽样** 18 题，题目顺序在建局时冻结在 `answers.codes`，因此同一局内断点续玩不错位，跨局则不同。第 18 题恒为 Boss 综合大题。

### 题目形态

`run.question.kind` 决定渲染方式：

| kind | 交互 | 提交 `choice_id` |
| --- | --- | --- |
| `single` | 点选即提交 | `"a"` |
| `multi` | 多选后点「确认提交」；`pick_count` 为需选项数 | `"a,c"`（顺序无关） |
| `order` | 依次点选排序后提交 | `"b,a,c,d"`（顺序有关） |

`question.snippet` 非空时以代码块展示；`question.boss` 为 true 时是 Boss 题。仅第 3 关且 `quest` 模式会返回 `hearts_enabled` 与 `hearts`（3 颗心，答错扣 1，纯展示）。

### 连击与人格标签

| 字段 | 位置 | 说明 |
| --- | --- | --- |
| `run.streak` | 每次返回 run 的地方 | 当前连续答对题数，答错归零。**纯展示，不加分** |
| `result.persona` | `GET /api/quiz/result?mode=quest` | 由维度正确率派生的趣味称号 `{id, icon, label, note}`，与按总分计算的 `badge` 并行展示 |

```javascript
// 连击只用于演出，score 始终等于答对题数
if (result.run.streak >= 2) showCombo(result.run.streak);
```

**正确选项已打散**（`a` / `b` / `c` 各占约三分之一），不要假设答案是 A。若某条历史错题的 `your_choice` 与当前 `correct_choice_id` 重合，后端会把后者置为 `null`（题库选项重排导致），前端此时不显示"正确选项"那一段。

闯关结果写入 `learning_profiles` 的 `quiz_*` 参考字段，**不会覆盖**学生自报的水平；只有学生显式调用 `adoptQuizLevel()` 才会写入 `level`。`clearQuizReference()` 只清空参考，不动自报画像。

## 9. 验证

```powershell
node --test tests/api.test.js
.\.venv\Scripts\python.exe -m pytest -q
```

客户端测试覆盖完整接口映射、JSON/FormData、Cookie 配置、错误、取消及版本字段透传。多数测试使用模拟 fetch；响应体取消测试使用临时本地 HTTP 服务，验证收到响应头后取消仍抛出原始 `AbortError`，不访问部署服务或数据库。响应体读取时的网络错误也保留原始异常，只有 JSON 解析失败包装为 `ApiError`。Python 测试保留项目原有规则：未显式配置 `TEST_DATABASE_URL` 时跳过 PostgreSQL 流程测试。Node 测试要求 Node 18+（提供 fetch、FormData、Headers）。

XSS 与旧页面兼容性另有可选浏览器回归，安装 `requirements-browser.txt` 并设置 `RUN_BROWSER_TESTS=1` 后执行 `python -m pytest tests/test_frontend_browser.py -q`，配置说明见根目录 [README](../README.md)。
