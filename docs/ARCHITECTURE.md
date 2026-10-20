# 项目架构与协作分工

项目采用 **Flask 模块化单体 + 原生 JavaScript 前端 + PostgreSQL**。后端作为一个应用运行，内部按照账号、课程、学习、Tutor、任务划分模块。此次整理保留现有 HTTP 地址、JSON 格式、角色规则、数据库表和启动命令。

## 请求如何经过各层

```text
frontend/features/ 业务界面
    ↓ 调用函数
frontend/api/client.js
    ↓ HTTP + session Cookie
app/<业务>/routes.py
    ↓ 显式传入当前用户、参数及数据库连接提供函数
app/<业务>/service.py
    ↓ 调用数据访问函数，决定提交或回滚
app/<业务>/repository.py
    ↓ 参数化 SQL
PostgreSQL
```

服务通常接收 `user_id`、`data`、`get_db` 等明确参数；`get_db` 是延迟获取连接的函数，因此参数错误或匿名状态查询不必连接数据库。HTTP session 的读取、设置和清除在路由层完成。服务返回业务结果字典，失败时附带原有状态码；Flask 在路由出口将字典序列化为 JSON。

这是适合当前项目的轻量分层，服务仍使用已有的表单文件对象和基础设施适配器。无需引入 ORM、微服务或前端构建流程。

## 后端模块归属

五个业务目录都包含 `routes.py`、`service.py`、`repository.py`。

| 模块 | 负责的业务 | 主要数据 |
| --- | --- | --- |
| `app/auth/` | 注册、登录、退出、资料、密码、注销、管理员汇总；security.py 为登录及角色装饰器，serializers.py 过滤账号敏感字段 | users；注销和管理员汇总涉及关联数据 |
| `app/courses/` | 课程搜索、上传、教师/管理员管理课程、管理学习人员 | courses、learning_records |
| `app/learning/` | 学习画像、路径选择、学习位置、进度、正文、笔记、固定练习 | learning_profiles、learner_preferences、learning_path_positions、learning_records、lesson_notebooks、lesson_exercise_results |
| `app/tutor/` | 提问校验、选段上下文、持久会话、请求去重、重置对话、知识卡/模型调用编排 | lesson_conversations |
| `app/missions/` | 创建/恢复情境任务、步骤校验、计分、历史结果 | mission_attempts |

辅助文件也按所属业务放置：

- `learning/content.py`：三节课与任务的内置内容定义。
- `learning/paths.py`：路径模板、推荐、学习快照和位置记录，通过本模块 repository 访问数据。
- `learning/study.py`：固定题目、笔记读取、课时选段定位。
- `tutor/conversations.py`：会话创建/读取和公开会话格式，通过 Tutor repository 访问数据。

跨模块调用通过明确导入完成。例如学习快照调用任务结果查询，Tutor 使用学习模块提供的课时上下文；新增依赖应保持单向，避免模块之间相互导入 service。

## 基础设施与应用组装

| 文件 | 责任 |
| --- | --- |
| `app/factory.py` | `create_app(settings)`、配置、蓝图注册、错误处理和 CLI 命令 |
| `app/infrastructure/database.py` | 按 Flask 上下文复用 psycopg 连接，结束时关闭；导入时不连库 |
| `app/infrastructure/storage.py` | 获取上传目录、扩展名检查 |
| `app/infrastructure/tutor_provider.py` | 外部模型协议、超时、错误脱敏及知识卡适配 |
| `app/infrastructure/migrations.py` | 有编号 SQL 迁移、版本记录、初始化编排 |
| `app/infrastructure/seeds.py` | 课程和管理员种子数据；与结构迁移分开 |
| `app/infrastructure/web.py` | 首页、明确列出的静态文件、附件和头像路由 |
| `run.py` | CLI / WSGI 入口及本地启动 |
| `config.py` | `.env` 和默认环境配置 |

`create_app({"TESTING": True, "DATABASE_URL": "..."})` 支持创建独立配置的应用实例。`run:app` 与 `import app; app.app` 继续提供默认实例。导入不会执行迁移或写入数据库。

正式部署先运行 `flask --app run migrate`；需要示例课程与管理员时执行 `init-db`。本地 `python run.py` 保持原有初始化行为。多 worker 场景应在启动 worker 前统一完成迁移。迁移细节见 [migrations/README.md](../migrations/README.md)。

## 前端目录与加载方式

| 目录 / 文件 | 责任 |
| --- | --- |
| `frontend/index.html` | HTML 页面和脚本加载顺序 |
| `frontend/api/client.js` | 统一请求、API 函数、错误对象和上传 |
| `frontend/components/ui.js` | DOM 选择、弹窗、提示、错误显示、HTML 转义 |
| `frontend/features/state.js` | 当前账号、课程、路径、课时、笔记与会话的页面状态 |
| `frontend/features/auth/account.js` | 登录注册、资料、角色界面、管理员展示 |
| `frontend/features/courses/catalog.js` | 课程浏览、上传、删除、学习人员管理 |
| `frontend/features/learning/workspace.js` | 学习画像、路径、正文、进度、完成反馈 |
| `frontend/features/learning/study.js` | 笔记同步、冲突、草稿备份、固定练习 |
| `frontend/features/tutor/panel.js` | Tutor 面板与回答渲染 |
| `frontend/features/tutor/study.js` | 选段、会话恢复、重试、新对话 |
| `frontend/features/missions/release-rescue.js` | 情境任务界面与提交 |
| `frontend/features/navigation.js` | 主导航事件 |
| `frontend/features/bootstrap.js` | 所有定义加载后，读取当前账号和课程 |
| `frontend/styles/` | 页面及学习空间 CSS |

当前保留普通 `<script>` 和共享页面状态，以维持原生前端与现有交互。目录拆分后并没有改成 ES Modules，也没有引入组件框架。脚本顺序为 API → 状态 → 复用 UI → 各业务 → 初始化；新增脚本时，同时更新 HTML 和 `web.py` 的公开清单。可复用组件只放通用界面能力，业务校验放在对应 feature 或后端。

新页面通过 `/frontend/...` 访问资源。旧 `/api.js`、`/app.js`、`/prototype.js`、`/study.js`、两份 CSS URL 保留，由服务器从新目录读取或组合响应，不保存两份源码。后端只开放明确列出的前端资源，项目配置、迁移 SQL 和 Python 文件不会因此暴露。

## 数据与并发规则

- session 决定当前账号，业务操作不接受任意账号 ID 替代当前身份。移除学习人员时，操作人的 ID 和目标学习者 ID 分开传递。
- repository 执行参数化 SQL，不自行提交；service 组织事务。需要多个数据操作共同成功时，在同一数据库连接上完成。
- 笔记写入校验 revision；409 时由前端保留草稿并提示重新读取。
- Tutor 写入校验 token、revision、request_id；外部模型调用前释放数据库事务，返回后再次通过条件更新防止覆盖新会话。
- 任务分数由后端计算，更新条件包含所属账号和当前 step。
- 用户、课程、进度仍使用原有表和 ID。附件继续保存在服务器本地，数据库共享不会同步文件。

## 合作者如何添加功能

以“给课程增加标签”为例：

1. 在 `migrations/` 新增有编号的结构变更，并注册迁移。
2. 在 `app/courses/repository.py` 增加标签读写 SQL。
3. 在 `app/courses/service.py` 定义允许的标签、权限和事务行为。
4. 在 `app/courses/routes.py` 增加或调整 HTTP 入口，读取当前用户及请求参数。
5. 在 `frontend/api/client.js` 增加函数，再由 `frontend/features/courses/` 调用。
6. 更新 [API README](API_README.md)，增加对应的业务流程验证。

约定：路由里不写 SQL，repository 不操作 session，前端通过 API 模块发请求。密钥只从后端环境配置读取。发生跨模块数据操作时，在业务服务明确编排，不在前端模拟权限或计分。

## 兼容与验证

`app/models/`、根目录 `prototype.py` 和 `learning_content.py` 保留旧 Python 导入所需的薄兼容层。实际内容、数据库操作和业务实现均位于新模块；新增代码使用新路径。

```powershell
node --test tests/api.test.js
.\.venv\Scripts\python.exe -m pytest -q
```

`tests/test_architecture.py` 验证应用实例配置隔离、原 HTTP 合约、静态文件加载顺序与访问边界，以及操作人和目标用户的权限分离。PostgreSQL 流程测试仅在显式配置 `TEST_DATABASE_URL` 后运行，每例使用独立随机 schema，结束后清理该 schema。迁移测试覆盖重复执行、旧表接入和已有用户进度保留。

本次是结构整理，已有产品边界仍然存在：文件存储与访问方式、原生前端共享状态，以及生产环境的 CSRF、限流和文件内容检查等，需要在对应功能工作中继续完善。
