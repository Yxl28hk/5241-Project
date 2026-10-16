# 知行学习平台 · Week 8 Prototype

保留 **Flask + Neon PostgreSQL + HTML/CSS/JavaScript**，增加软件工程学习路径、课程内学习助手和可玩的发布事故模拟。不需要前端构建工具。

## 快速演示：无需数据库账号或 AI key

Python 3.10+，在项目目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_demo.py
```

打开 <http://127.0.0.1:5000>。本机已准备好环境，可直接执行最后一行。

| 角色 | 邮箱 | 演示密码 |
| --- | --- | --- |
| 学生 | student@demo.local | Demo@123456 |
| 教师 | teacher@demo.local | Demo@123456 |
| 管理员 | admin@zhixing.com | Admin@123456 |

这些是仅供本地演示的公开测试凭据。管理员配置以 `.env` 为准，已有账号不会在重启时重置密码。`run_demo.py` 强制使用 SQLite，不连接 Neon；数据保存在被 Git 忽略的 `demo.db`。重启保留学习记录，未配置固定 session secret 时需要重新登录。

## 正常运行：Neon PostgreSQL

```powershell
Copy-Item .env.example .env
# 编辑 .env：填写 DATABASE_URL、随机 ZHIXING_SECRET_KEY 和管理员密码
# 保持 DEMO_MODE=0；清除终端中可能存在的演示模式覆盖
Remove-Item Env:DEMO_MODE -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe app.py
```

读取项目根目录 `.env`，已有环境变量优先。Neon URL 保留 `sslmode=require`。启动创建缺失表并添加三节短课，不清空旧账号、课程或学习记录。旧的六门示例课只在课程表为空时添加。

Flask CLI / WSGI 启动前先初始化：

```powershell
.\.venv\Scripts\python.exe -m flask --app app init-db
.\.venv\Scripts\python.exe -m flask --app app run
```

初始化已移出模块 import 阶段。多 worker 部署应单独执行一次初始化。Flask 内置服务仅用于本地演示。

| 环境变量 | 用途 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 模式必填；Neon connection string |
| `DEMO_MODE` | 默认 `0`；`1` 使用 SQLite；`run_demo.py` 强制为 `1` |
| `DEMO_DATABASE_PATH` | 可选，SQLite 路径，默认项目内 `demo.db` |
| `ZHIXING_SECRET_KEY` | 固定随机 session 密钥；未配置时生成临时密钥，重启登录失效 |
| `ZHIXING_ADMIN_EMAIL` | 默认 `admin@zhixing.com` |
| `ZHIXING_ADMIN_PASSWORD` | PostgreSQL 新建管理员时需设置；不设置则不创建管理员。已有密码不自动更新 |
| `PORT` | `app.py` / `run_demo.py` 端口，默认 `5000` |

`.env`、数据库、上传文件和虚拟环境不提交。当前 Tutor 不调用外部 API，无需 key；以后接入真实模型时，key 必须只从后端环境变量读取，不能放进 JS、源码或 Git。

## 已实现

- **Learning path**：Git/PR → 测试与 CI → 安全发布；每节进度、完成数、总进度和推荐下一节。推荐是第一节未完成的课，不是 AI 推荐。
- **课程学习页**：内置短课、检查问题、打开上传资源、主动记录 0/50/100% 进度。进度是学生自评，不是考试成绩或自动计时。
- **AI Learning Assistant 演示**：明确标为规则式助手（非大模型）；结合课程和进度提供知识卡、提示、下一步。自由提问映射预设规则，不读取上传 PDF/视频，聊天不持久化。
- **Release Rescue**：四个情境决策，每步 25 分，75 分通过；错误解释、最终结果、历史最高分、刷新续玩和重试。后端计分，忽略客户端分数，重复步骤返回冲突。
- **兼容原有功能**：学生学习；教师上传/管理自己课程和学习者；管理员查看全部课程、账户和记录；昵称头像密码、停止学习、删除课程、注销账号。
- **关联修复**：只允许指定前端静态文件，避免暴露根目录；登录响应移除密码哈希；修改资料后保留角色；正式模式取消固定默认管理员密码；关闭默认 debug；首页移除虚构统计。

## 代码结构

```text
app.py                  原有 Flask 路由、角色权限、数据库连接和启动
index.html              单页 UI 和各功能弹窗
app.js / styles.css     原有账号、课程、教师和管理员交互与样式
prototype.py            学习路径、进度、Tutor、任务 API 和新增表
learning_content.py     三节短课、四步任务、反馈和评分规则
prototype.js / .css     新增学习路径、课程、Tutor 和任务 UI
demo_db.py              显式启用的本地 SQLite 适配层
run_demo.py             本地演示启动和测试账号初始化
tests/test_flows.py     核心流程与角色权限回归测试
uploads/                原有本地文件存储
docs/                   架构、演示脚本和验证记录
```

完整分析见 [架构梳理](docs/ARCHITECTURE.md)。原表 `users`、`courses`、`learning_records` 保留；新增 `prototype_courses` 映射短课到原课程，`mission_attempts` 保存个人任务记录。教师/管理员查询继续读取同一份学习记录。管理员删除内置短课后，下次初始化会补回。

## 接口

| 新接口 | 用途 |
| --- | --- |
| `GET /api/prototype/config` | 环境和 Tutor 模式，不返回密钥 |
| `GET /api/learning-path` | 当前账号路径和任务结果；需登录 |
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

## 测试与演示

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
node --check app.js
node --check prototype.js
```

测试使用独立临时 SQLite，不修改演示数据或 Neon。结果见 [验证记录](docs/VALIDATION.md)，课堂演示见 [5–7 分钟脚本](docs/WEEK8_DEMO.md)。

## 下一步

1. 在独立 Neon 测试分支完成数据库联调，再连接团队共享数据库。
2. 在 `/api/tutor` 后端接入真实模型、课程检索、超时降级和限流。
3. 增加客观检查题、教师任务成绩面板、更多分支情境和学习效果评估。
4. 正式上线前补齐 CSRF、教师审核、文件私有访问/内容校验、对象存储、数据库迁移和生产服务器；当前是课堂 prototype。
