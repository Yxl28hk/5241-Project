# 数据库迁移

迁移 SQL 放在此目录，由 `app/infrastructure/migrations.py` 顺序执行。迁移仅改变表结构，示例课程与环境配置的管理员账号由 `app/infrastructure/seeds.py` 单独处理。

| 文件 | 结构 |
| --- | --- |
| `001_core.sql` | users、courses、learning_records |
| `002_learning.sql` | 学习画像、路径偏好、路径位置、last_opened_at |
| `003_study.sql` | 笔记、练习结果、Tutor 会话 |
| `004_prototype.sql` | 内置课程映射、任务记录 |

在项目根目录执行：

```powershell
# 仅升级结构；适用于已有数据库，也可为空库建表。
.\.venv\Scripts\python.exe -m flask --app run migrate

# 初始化结构，同时添加演示课程和按环境配置创建管理员。
.\.venv\Scripts\python.exe -m flask --app run init-db

# 已有平台只升级学习工具结构，不重新填充课程或账号。
.\.venv\Scripts\python.exe -m flask --app run init-learning
```

`schema_migrations(version, applied_at)` 记录已执行文件；重复执行跳过已记录的文件。同一 schema 的迁移通过 PostgreSQL 事务级 advisory lock 串行执行。迁移命令在全部成功后提交；执行失败时连接关闭并回滚，不会记录未完成的版本。

旧版本数据库没有迁移历史时，前四份 SQL 使用 `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` 接管已有表，不删除数据。它们只能补齐已知结构，不会自动修复与项目定义不一致的自定义表。执行命令前应确认 `.env` 指向预期数据库；团队共享数据库由指定成员统一安排迁移。

新增结构变更时：

1. 添加下一个编号的 SQL，例如 `005_course_metadata.sql`，不要修改已经应用过的迁移。
2. 将文件加入 `app/infrastructure/migrations.py` 的执行列表；按用途决定是否也属于学习初始化分组。
3. 在独立的 `TEST_DATABASE_URL` 验证空库初始化、旧库升级、重复执行和已有记录保留。
4. 更新相关模块 repository、业务逻辑和文档，再统一部署。

当前迁移执行器支持用分号分隔的普通 DDL；不支持带内部分号的函数体、DO 块或数据脚本。此类需求出现时应先升级执行器。当前没有自动降级命令，恢复需要经过验证的备份或后续修复迁移。
