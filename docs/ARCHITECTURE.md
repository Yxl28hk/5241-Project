# 现有代码结构与实现边界

分析基线：`Yxl28hk/5241-Project` 的 `d7163df`。原仓库只有下表文件和 README；没有测试、构建工具、ORM 或迁移目录。

## 原有流程和文件

浏览器加载 HTML → JS 同源 fetch → Flask session 获取用户 id → 装饰器查角色 → psycopg 参数化 SQL → JSON 返回。连接放在 Flask `g`，请求结束关闭。Werkzeug 保存密码哈希；文件以随机前缀保存在本机。

| 文件 | 原有责任 |
| --- | --- |
| `run.py` | Flask 启动入口、数据库连接和现有路由；配置集中在 `config.py`，应用模块位于 `app/` |
| `app.js` | 全局状态、fetch、弹窗、课程卡片、注册登录、资料、资源管理、学习名单和管理员列表；无客户端路由 |
| `index.html` | 首页和发现课程，以及登录/课程详情/上传/资料/我的学习/学习者/管理员账户弹窗 |
| `styles.css` | 绿色主题、卡片、响应式布局和弹窗；有重复媒体查询，本次未无故重构 |
| `requirements.txt` | Flask、psycopg binary、python-dotenv |
| `.env.example` / `.gitignore` | 配置模板和敏感文件/运行产物忽略规则 |
| `uploads/.gitkeep` | 文件存储目录占位 |

## 原数据模型与角色

- `users`：id、name、email、password_hash、role、avatar_filename、created_at。
- `courses`：id、title、category、resource_type、description、author、duration、cover、badge、filename、owner_id、created_at；owner_id 关联用户。
- `learning_records`：user_id + course_id 复合主键、progress、started_at、updated_at；用户/课程删除时级联删除记录。

学生只学习；教师管理自己的上传课程和学习者；管理员管理全部课程并汇总账户。教师角色可在注册时自行选择，这是原演示设计，正式上线需审核。

## 原有缺口

1. 加入学习只创建 0% 记录，没有更新进度接口。
2. 首页学习时长、用户数等是装饰数字。
3. 课程详情只登记学习，没有正文或打开附件的学习流程。
4. 没有 Tutor、任务模拟、任务成绩或测试。
5. import 模块就连接 Neon，没有配置无法运行。
6. 根目录被设为静态目录；登录序列化未过滤密码哈希；资料查询遗漏 role 导致前端角色丢失。

## 本次增量设计

项目采用按功能模块分层的 Flask 结构：根目录保留启动与配置，`app/models` 管理领域内容，`app/routes` 按功能承载 HTTP 入口，`app/utils` 放置复用工具。根目录的 `prototype.py` 和 `learning_content.py` 作为兼容导入层保留，避免已有部署或测试直接导入时发生破坏性变化。

保留 Flask 对象、权限装饰器、SQL 和单页结构，附加路由模块及前端文件。未引入 React、Node 服务、ORM 或新部署平台。

`prototype_courses(slug, course_id)` 关联内置内容与原课程；`mission_attempts(id, user_id, mission_id, step, score, answers, created_at)` 保存任务。课程进度继续写原表；任务成绩单独保存，不自动等同课程完成。

任务仅发送当前场景选项，由后端计分；更新条件含用户 id 和当前 step，防止跨用户修改和重放。公开源码含答案，因此是练习模拟，不是保密考试。

数据库统一通过 psycopg 连接 Neon PostgreSQL。已移除 SQLite 快速演示、模式开关和自动测试账号；未配置 DATABASE_URL 时明确报错。初始化增加新表/课程，不删除或重建旧 schema；多实例部署应先单独执行 `flask init-db`。

## 保留局限

上传资源仍使用公开 URL 和本地磁盘；旧前端仍有直接拼接 HTML 的位置；没有完整 CSRF、限流、审计、迁移和文件内容检查。部分旧接口只做基础输入校验。本次适合本地课堂演示，正式部署需完整安全与兼容审查。
