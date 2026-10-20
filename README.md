# 知行学习平台 · Week 8 Prototype

保留 **Flask + Neon PostgreSQL + HTML/CSS/JavaScript**，增加软件工程学习路径、课程内学习助手和可玩的发布事故模拟。不需要前端构建工具。

## 合作者 API 函数入口

现有 API 已统一封装到独立的 [`frontend/api/client.js`](frontend/api/client.js)，页面加载后可直接通过 `zhixingApi` 调用账号、课程、学习路径、笔记、练习、Tutor 和任务函数，无需自己拼接 URL 或处理 JSON / FormData。该模块不依赖页面 DOM，无需 npm 安装；`frontend/features/` 下的业务脚本使用同一套函数。

完整的函数与 HTTP 接口对照、参数、权限、返回值、登录会话、文件上传及版本冲突示例见 **[合作者 API 使用 README](docs/API_README.md)**。

```javascript
// 在加载 /frontend/api/client.js 后的 async 函数中使用。
const { user } = await zhixingApi.login({ email: "your-account@example.com", password: "your-password" });
const { courses } = await zhixingApi.listCourses({ category: "技术" });
if (courses.length) {
  await zhixingApi.startLearning(courses[0].id);
  const { lesson } = await zhixingApi.getLesson(courses[0].id);
  console.log(user.name, lesson.title);
}
```

客户端验证：`node --test tests/api.test.js`（Node 18+，模拟请求，无需数据库）。项目服务本身仍只需下方 Python 环境。

## 运行：Neon PostgreSQL

Python 3.10+，在项目目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# 编辑 .env，填写 DATABASE_URL、随机 ZHIXING_SECRET_KEY 和管理员密码。
.\.venv\Scripts\python.exe run.py
```

打开 <http://127.0.0.1:5000>。必须先配置数据库 URL；不再提供本地 SQLite 快速演示或自动测试账号。学生和教师通过注册创建账号；管理员由环境配置创建，已有账号密码不会被重置。

读取项目根目录 `.env`，已有环境变量优先。Neon URL 保留 `sslmode=require`。启动创建缺失表并添加三节短课，不清空旧账号、课程或学习记录。旧的六门示例课只在课程表为空时添加。

Flask CLI / WSGI 启动前先初始化：

```powershell
.\.venv\Scripts\python.exe -m flask --app run init-db
.\.venv\Scripts\python.exe -m flask --app run run
```

初始化已移出模块 import 阶段。多 worker 部署应单独执行一次初始化。Flask 内置服务仅用于本地演示。

| 环境变量 | 用途 |
| --- | --- |
| `DATABASE_URL` | 必填；Neon PostgreSQL connection string |
| `ZHIXING_SECRET_KEY` | 固定随机 session 密钥；未配置时生成临时密钥，重启登录失效 |
| `ZHIXING_ADMIN_EMAIL` | 默认 `admin@zhixing.com` |
| `ZHIXING_ADMIN_PASSWORD` | 新建管理员时需设置；不设置则不创建管理员。已有密码不自动更新 |
| `TEST_DATABASE_URL` | 可选；独立 PostgreSQL 测试库，不能使用团队共享库 |
| `PORT` | `run.py` 端口，默认 `5000` |

`.env`、数据库、上传文件和虚拟环境不提交。默认 Tutor 使用无需 key 的课时知识卡；可选真实 AI 的密钥只从后端环境变量读取，不能放进 JS、源码或 Git。

### 团队共享数据库与文件

团队成员在各自本地 `.env` 中配置指向同一个 Neon 数据库和 schema 的 `DATABASE_URL` 后，会读写同一份账号、课程、学习进度和任务记录。页面上的注册、上传课程记录、更新进度和删除操作会影响共享数据；本地运行并不意味着数据只保存在本机。

课程附件和头像仍保存在运行服务的本机文件目录，数据库只保存相关信息及文件路径。共享数据库或拉取 GitHub 代码不会同步这些文件，因此其他电脑可能看得到课程却打不开附件。多人演示建议使用同一个运行实例和文件目录；正式部署再接入对象存储等共享文件服务。

拿到此分支后按上面的步骤安装依赖并配置自己的 `.env`。仓库不会携带数据库密码、session 密钥或上传文件。若使用已初始化的团队数据库，可直接执行 `python -m flask --app run run`；新数据库先执行 `python -m flask --app run init-db`。初始化会补充课程和按环境配置处理管理员账号，应由团队统一安排。

## 已实现

- **学生学习工作台**：学生登录后默认进入“我的学习”，隐藏宣传大图，首屏展示当前课时、路径与完成率；路径完成后提供实践挑战。游客保留介绍页，教师/管理员入口不变。
- **学习画像**：目标、基础、每周 1–40 小时投入均可选填、修改和清空，按账号保存。基础是学生自报信息，不伪造能力评分。
- **路径选择与推荐**：三条短课路径为团队协作入门、测试与发布基础、软件工程流程体验，分别强调 PR 交接、调查与恢复清单、流程衔接与情境挑战。目录按当前路径从第 1 节编号，保留原课程 ID、共同课时进度和各路径最近位置；画像变更不会自动切换路径。
- **专注学习页**：全屏学习空间，三节短课包含目标、情境、讲解、示例、任务与回顾；每节有一道服务端判定的固定单选练习，提交后查看解析、可重做，结果单独保存，不自动完成课时。
- **完成与下一步**：课时显示未开始/学习中/已完成；先保存，再展示回顾和下一节入口。路径完成后可进入 Release Rescue，支持重新学习与显式重试。
- **助手增强**：段落/示例提问、两步任务提示与独立参考解析、回答保存为笔记。按账号和课时保存最近 20 轮会话，切换/刷新/重登后恢复，可开启新对话。版本和请求 ID 防止旧回答覆盖新会话及重复写入。
- **账号笔记**：笔记与任务草稿自动保存到 PostgreSQL，离开课时或退出前先同步；失败可重试，多窗口冲突时由学生选择账号版本或本机未同步草稿。
- **Learning path**：Git/PR → 测试与 CI → 安全发布；每节进度、完成数、总进度和推荐下一节。推荐是第一节未完成的课，不是 AI 推荐。
- **进度兼容**：保留原 0–100 进度接口与旧 50% 阅读记录；学生页面不再要求选择阅读百分比。打开课时只进入学习中，不自动完成；完成状态不是成绩或计时结果。
- **AI Learning Assistant**：默认明确标为规则式知识卡（非大模型），无需密钥。配置下方三项后调用真实模型；选段范围由服务端从当前课时提取，不读取上传 PDF/视频，不执行代码。
- **Release Rescue**：四个情境决策，每步 25 分，75 分通过；错误解释、最终结果、历史最高分、刷新续玩和重试。后端计分，忽略客户端分数，重复步骤返回冲突。
- **兼容原有功能**：学生学习；教师上传/管理自己课程和学习者；管理员查看全部课程、账户和记录；昵称头像密码、停止学习、删除课程、注销账号。
- **关联修复**：只允许指定前端静态文件，避免暴露根目录；登录响应移除密码哈希；修改资料后保留角色；正式模式取消固定默认管理员密码；关闭默认 debug；首页移除虚构统计。

## 代码结构

```text
run.py                       Flask CLI / WSGI / 本地启动入口
config.py                    环境变量和默认配置
frontend/
  index.html                 页面入口
  api/client.js              全部 API 调用函数
  components/ui.js           弹窗、提示、DOM 与文本转义工具
  features/
    state.js                 页面共享状态
    auth/account.js          账号、个人资料、管理员界面
    courses/catalog.js       课程发现、上传和学习人员管理
    learning/                路径、课时、笔记和练习
    tutor/                   助手面板、持久会话和提问
    missions/release-rescue.js
    navigation.js            导航事件
    bootstrap.js             页面初始化
  styles/                    页面及学习空间样式
app/
  factory.py                 create_app、蓝图组装和 CLI
  auth/                      账号与角色权限
  courses/                   课程及学习人员管理
  learning/                  路径、进度、笔记、练习与内置内容
  tutor/                     答疑与会话
  missions/                  情境任务和计分
  infrastructure/            数据库、文件、模型适配、迁移与静态文件
  models/                    旧 Python 导入路径的兼容导出
migrations/                  有编号的增量 SQL 迁移
tests/                       API 客户端、架构及 PostgreSQL 流程测试
docs/                        架构、接入指南、演示及验证记录
uploads/                     运行时本地附件，不提交
prototype.py                 旧初始化导入的兼容层
learning_content.py          旧内容导入的兼容层
```

完整分析见 [架构梳理](docs/ARCHITECTURE.md)。原表 `users`、`courses`、`learning_records` 保留；新增 `prototype_courses` 映射短课到原课程，`mission_attempts` 保存个人任务记录。教师/管理员查询继续读取同一份学习记录。管理员删除内置短课后，下次初始化会补回。

五个业务模块统一采用 `routes.py → service.py → repository.py`：路由负责 HTTP 与 session，服务负责规则及事务，repository 负责 SQL。[协作分工与依赖规则](docs/ARCHITECTURE.md) 说明新增功能应放在哪里。

只升级数据库结构、无需创建管理员或示例课程时，可运行：

```powershell
.\.venv\Scripts\python.exe -m flask --app run migrate
```

迁移按文件编号执行，并记录到 `schema_migrations`；已有数据库通过 `IF NOT EXISTS` 接入。新数据库仍可直接执行 `init-db`。新增或修改表结构时增加新的 SQL 文件，详细流程见 [迁移 README](migrations/README.md)。

## 接口

| 新接口 | 用途 |
| --- | --- |
| `GET /api/prototype/config` | 环境和 Tutor 模式，不返回密钥 |
| `GET /api/learning-path` | 当前账号路径和任务结果；需登录 |
| `GET/PATCH /api/learning-profile` | 读取/修改 `goal`、`level`、`weekly_hours`；不接受其他账号 ID |
| `POST /api/learning-path/select` | `{"path_id":"collaboration"}`；另有 `quality` / `engineering` |
| `GET /api/courses/<id>/lesson` | 读取正文、检查问题、附件入口及本人的进度 |
| `GET/POST /api/courses/<id>/exercise` | 获取题目与本人最近结果，提交选择并由服务端判定 |
| `GET/PATCH /api/courses/<id>/notebook` | 笔记与任务草稿；保存需携带当前 `revision` |
| `POST/DELETE /api/courses/<id>/conversation` | 恢复本课最近会话 / 按 token 与 revision 开启新对话 |
| `PATCH /api/courses/<id>/progress` | `{"progress":50}`；仅自己的已加入课程 |
| `POST /api/tutor` | `{"course_id":7,"message":"给我提示"}`；需登录，问题 1–1000 字 |
| `POST /api/missions/release-rescue/start` | 创建或恢复个人任务 |
| `POST /api/missions/attempts/<id>/answer` | `{"step":0,"choice_id":"pr"}`；校验归属和步骤 |

原有接口继续提供：

- `POST /api/auth/register`、`/api/auth/login`、`/api/auth/logout`，`GET /api/auth/me`。
- `PATCH/DELETE /api/profile`、`PATCH /api/profile/password`。
- `GET/POST /api/courses`、`DELETE /api/courses/<id>`。
- `GET /api/profile/courses`、`GET /api/profile/learning`。
- `POST /api/courses/<id>/learn`、`DELETE /api/profile/learning/<id>`。
- `GET /api/courses/<id>/learners`、`DELETE /api/courses/<id>/learners/<user_id>`。
- `GET /api/admin/users`、`GET /uploads/<filename>`、`GET /avatars/<filename>`。

上传只允许教师/管理员，教师只管理自己的课程；管理员管理全部课程。文件继续支持 PDF、Word、PPT、MP4、MOV，上限 500MB。旧示例课无附件，新短课有内置正文，上传课程有打开文件入口。

### 已有数据库升级

新增 `learning_profiles`、`learner_preferences`、`learning_path_positions` 三张表，并为原 `learning_records` 添加可空的 `last_opened_at`。不重建原表、不清空账号或学习记录。

第 4–7 项增强新增 `lesson_notebooks`、`lesson_exercise_results`、`lesson_conversations`。已使用前一版的数据库也需再次执行下方幂等升级命令。新增表按用户与课程关联，账号或课程删除时级联清理；不改动旧课程 ID 或完成进度。

已有项目先执行以下命令，再重启当前服务；该命令只更新学习数据结构，不重新创建管理员或课程：

```powershell
.\.venv\Scripts\python.exe -m flask --app run init-learning
```

全新数据库仍使用 `init-db`。直接运行 `run.py` 时也会进行增量初始化。路径不额外生成课程副本；同一课时在不同路径中复用完成记录，各路径分别记录最近学习位置。

### 可选真实 AI

在本机 `.env` 中设置 `TUTOR_API_URL`（完整的 chat-completions 兼容接口地址）、`TUTOR_API_KEY`、`TUTOR_MODEL`，重启服务生效。三项均配置后，界面显示真实 AI 模式；缺少配置时明确显示规则式知识卡。上游调用超时约 25 秒，不向浏览器泄露接口地址、密钥或上游错误原文；失败时学生可重试或主动使用课时知识卡。

仅传当前课时、服务器确认的选段、自报基础与本课最近对话，不传账号邮箱、私人笔记或其他学生数据。固定分步提示和参考解析不调用模型；适配器自动测试使用模拟上游，不代表特定提供商已联通。

## 测试与演示

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/api.test.js
```

配置及架构测试无需数据库。45 项流程测试需要显式设置 `TEST_DATABASE_URL`，未配置则跳过，绝不自动使用 `DATABASE_URL`。请使用独立测试数据库（账号需可创建 schema）；每个测试创建随机 schema，结束时只删除该 schema。目录重构增加了 HTTP 合约、应用实例隔离、静态资源、权限参数分离及迁移保留数据的验证。结果见 [验证记录](docs/VALIDATION.md)，新功能见 [学习工具说明](docs/STUDY_TOOLS.md)。

浏览器回归为可选测试，使用本地页面与模拟 API，不连接数据库。覆盖课程及账号字段的 HTML 注入，以及新页面、原版三脚本页面、单独加载 API 脚本的过渡页面：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
$env:RUN_BROWSER_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_frontend_browser.py -q
Remove-Item Env:RUN_BROWSER_TESTS
```

Windows 默认使用已安装的 Edge。其他系统默认使用 Playwright Chromium，首次运行前执行 `python -m playwright install chromium`；也可通过 `BROWSER_CHANNEL` 指定已安装的浏览器通道（例如 `chrome`）。未开启 `RUN_BROWSER_TESTS` 时跳过浏览器测试。

2026-10-17 已完成 Neon 联调：**16 项测试通过**（3 项配置测试、13 项流程测试）。该次流程测试使用随机隔离 schema，未对既有业务表做写入或删除测试；这不等同于完整浏览器验收或生产安全审核。后续重复测试仍应使用独立测试数据库。

## 下一步

1. 在独立测试环境补齐多人浏览器验收和跨设备附件访问验证。
2. 配置实际模型提供商并验证回答质量、费用、课程检索与服务端调用限流。
3. 增加客观检查题、教师任务成绩面板、更多分支情境和学习效果评估。
4. 正式上线前补齐 CSRF、教师审核、文件私有访问/内容校验、对象存储、数据库备份恢复和生产服务器；当前是课堂 prototype。
