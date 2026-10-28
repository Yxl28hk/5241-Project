# 软件工程水平闯关（Level Quest）功能规格说明

> 状态：**v3 · A 档 + B 档趣味性迭代**（v1 基础版已上线；v2 已完成 B 档：30 题 / 抽题 / 多题型 / Boss / 速测 / 复仇 / 生命值）
> 目标里程碑：替换学习路径区块右侧的 Release Rescue 实践挑战卡
> 关联文档：`docs/ARCHITECTURE.md`（分层约定）、`docs/API_README.md`（接口契约）、`migrations/README.md`（迁移流程）

> **v3 变更摘要（A 档 + 题目质量）**
> | 编号 | 增强 | 性质 |
> | --- | --- | --- |
> | A1 | **连击 Combo**：连续答对计数与演出文案（**不加分**） | 后端派生 + 前端 |
> | A2 | **共情式错题反馈**：复用既有 `explanations`，按连错次数给不同安慰话术 | 纯前端 |
> | A3 | **人格标签**：由维度正确率派生的趣味称号（替代/补充徽章） | 后端纯函数 |
> | Q1 | **打散正确选项**：修掉「29/30 题正确项都是 A」的题目质量缺陷 | 题库内容 |
>
> **v2 变更摘要（B 档，已完成）**
> | 编号 | 增强 | 性质 |
> | --- | --- | --- |
> | B1 | 题库 18 → **30 题**（每关 10 题池，每局分层抽样 6 题） | 后端取题逻辑 |
> | B2 | 题目形态多样化：单选 / **多选** / **排序** / **代码片段题** | 迁移 + 判定 |
> | B3 | **Boss 关**：L3 最后一题为综合大题 | 题库 + 前端 |
> | B4 | **错题复仇**：错题进池，独立短局重做 | 新模式 |
> | B5 | **速测模式**：8 题快速体验 | 新模式 |
> | B6 | **生命值**：仅 L3 显示 3 颗心 | 纯展示 |
>
> **贯穿原则：趣味层与判定层隔离。** 随机、题型、Boss、生命值、连击、人格标签都不改变「答对题数 → 分数 → 徽章 → 画像参考」这条链路，见 §6.0。

---

## 1. 背景与目标

### 1.1 项目总体要求中的定位

本项目要交付一个"由生成式人工智能驱动的学习平台"，学习内容与活动的形式包含**游戏/小游戏**，并且：

- 内容要**便于非计算机专业学生理解**软件开发与软件工程，同时**适合计算机专业毕业生**为 AI 时代的职业做准备；
- 要**个性化与定制化**，以吸引不同背景、不同学习目标的学生；
- 教师应能手动或借助 AI 自定义/新建迷你课程，并**跟踪学生的参与度与投入情况**。

本功能（下称 **Level Quest / 水平闯关**）对应其中的"游戏/小游戏 + 个性化摸底"：

| 总体要求 | 本功能的落点 |
| --- | --- |
| 游戏/小游戏形式的学习活动 | 关卡解锁 + 徽章的答题闯关 |
| 个性化与定制化 | 闯关结果产出**维度能力参考**，为学习画像与路径推荐提供信号 |
| 兼顾非计算机 / 计算机背景 | 题目分 3 个难度层，L1 不需要任何专业背景也能作答 |
| 教师跟踪参与度 | 复用既有管理员/教师数据视图（本次仅预留字段，面板不在范围内） |

### 1.2 本次目标

1. 用**答题闯关游戏**替换学生工作台 `#learning-path` 区块右侧的 `aside.mission-card`（Release Rescue 实践挑战卡）。
2. 通过宽泛的软件开发题目**初步了解使用者水平**，为**学生画像**提供**参考**（不是能力评分，不覆盖学生自报信息）。
3. 提供**关卡解锁 + 徽章**的正反馈，支持重刷最高分。
4. **题库必须基于现有的答题表实现**（见 §4 的复用策略）。
5. **[v2/v3] 提升趣味性**：随机抽题、多题型、Boss 关、错题复仇、速测模式、生命值、连击、共情反馈、人格标签（见 §3.7）。
6. **[v3] 保证题目质量**：正确选项不能集中在同一位置，必须打散（见 §6.14）。

### 1.3 非目标（本次不做）

- ~~题库增删改界面~~ → **[v4 已完成]** 由**管理员**维护（题库无 owner 列，故不挂教师），入口在导航「资源管理」之后，见 §7.5
- AI 自动生成题目的接口（P2，见 §11）
- 排行榜、多人对战、限时抢答
- 音效 / 动画演出（纯表现层，不影响任何数据与接口，可随时追加）
- **自适应难度**（C 档，需接 LLM 通道，见 §11）

> **关于生命值**：v1 曾明确排除生命值（担心打击零基础学生）。v2 重新评估后**改为仅在 L3 启用**，且经 §6.8 论证：3 颗心的消耗速度与 L3「答对 ≥ 4/6」的关卡规则**完全同步**，因此它不会造成任何额外失败，只是把已有的失败阈值可视化。L1 / L2 不显示生命值。

---

## 2. 现状分析

### 2.1 现有数据库没有独立的题库表

当前 schema（`public`，共 12 张表）中：

| 表 | 与本题的关系 |
| --- | --- |
| `lesson_exercise_results` | **答题结果表**。PK `(user_id, course_id, question_version)`，含 `choice_id / correct / attempts` |
| `mission_attempts` | **闯关局表**。`(id, user_id, mission_id, step, score, answers JSON)` |
| `learning_profiles` | **学习画像**。`(user_id, goal, level, weekly_hours)` |
| `prototype_courses` | 内置内容 `slug → course_id` 映射 |
| `courses` | 课程主表（内置 3 节短课也是这里面的行，`resource_type='lesson'`） |

题目内容本身**硬编码在 Python 里**：`app/learning/study.py` 的 `EXERCISES` 字典，仅 3 道题（每个课时 1 道固定单选）。

即：**有"答题结果表"，没有"题目表"**。要做 18 题闯关，必须新增题目表；但答题记录与闯关局可以完全复用现有两张表。

### 2.2 被替换的区块

`frontend/index.html:87`：

```html
<aside class="mission-card">
  <span class="section-kicker">PUT IT INTO PRACTICE</span>
  <div class="mission-icon">⌘</div>
  <h3>Release Rescue</h3><strong>拯救周五发布</strong>
  <p>登录异常、红色 CI、上线事故。你将如何带领团队完成一次安全发布？</p>
  <p>4 个决策 · 约 3 分钟 · 75 分通过<br>可随时挑战，建议先完成左侧课程。</p>
  <small id="mission-best">尚未开始</small>
  <button class="button" id="mission-start">开始 / 继续挑战 ↗</button>
</aside>
```

联动位置（**改动时必须全部处理**）：

| 位置 | 现有引用 |
| --- | --- |
| `frontend/index.html:221` | `#mission-modal` 弹窗容器 |
| `frontend/index.html:231` | `<script src="/frontend/features/missions/release-rescue.js">` |
| `frontend/features/missions/release-rescue.js` | `renderMission` / `startMission` / 选择按钮事件 |
| `frontend/features/learning/workspace.js:43` | `#mission-best` 历史最高分 |
| `workspace.js:189-191` | `completionTarget = {type:"mission"}` + `#completion-next-label` 文案 |
| `workspace.js:260` | 路径完成后自动 `startMission()` |
| `workspace.js:338` | `completionTarget.type === "mission"` 分支 |
| `app/learning/service.py:214-229` | `path()` 里拼装 `result["mission"]` |
| `app/learning/content.py:192-270` | `MISSION` 常量（4 步情境决策） |
| `app/missions/{routes,service,repository}.py` | Release Rescue 后端实现 |
| `frontend/api/client.js:97-98` | `startMission` / `answerMission` |

---

## 3. 功能需求

### FR-1 闯关入口卡片

- 学生登录后，在原 `mission-card` 的位置展示 **Level Quest 卡片**（`#quest-card`）。
- 卡片内容（DOM 结构与文案映射见 **§8.0**）：
  - 标题「软件工程水平闯关」+ 副标题「LEVEL QUEST · 18 题摸底」
  - **3 个关卡指示器**（已通关 ✅ / 当前 ⏳ / 未解锁 🔒）
  - 进度条 `<progress>`：已答题数 / 18（当前局）或历史最佳
  - 历史最佳徽章：`#quest-best`（`尚未开始` / `历史最佳 13 / 18 · 银徽章`）
  - 主按钮 `#quest-start`：`开始闯关 →` / `继续闯关 →` / `再挑战一次 ↗`
- 学生可见；教师/管理员角色不展示（与现有 `mission-card` 一致）。

### FR-2 闯关流程

1. 点击开始 → `POST /api/quiz/runs`，创建或**恢复未完成的局**。
2. 逐题作答，前端**发送选项 ID，服务端判定**，返回正确性与解析。
3. 答完 6 题 → **关卡结算**：答对 ≥ 4 题解锁下一关；否则本局结束（提示可重试本关）。
4. 三关全部通过 → **终局结算**：总分、徽章、维度条形图、错题回顾。
5. 中途关闭弹窗 → 进度保留在服务端，下次进入自动恢复（断点续玩）。
6. 已通关后可随时重刷，取历史最佳。

### FR-3 关卡与题目

- **3 个关卡 × 6 题 = 18 题**（固定题目，首版不做随机抽题）。
- 关卡主题：

| 关卡 | 名称 | 定位 | 面向 |
| --- | --- | --- | --- |
| L1 | 开发常识 | 不需要专业背景，凭常识与基本逻辑可答 | 非计算机专业学生也能上手 |
| L2 | 情境判断 | 给一个小场景，选择更合适的做法 | 学过一点编程 / 参与过小组作业 |
| L3 | 流程与权衡 | 涉及 CI、发布、事故、技术债的取舍 | 计算机专业毕业生 / 有项目经验 |

- 题目覆盖 4 个维度（`topic`），对齐总体要求的三大主题：

| topic | 含义 | 题数 |
| --- | --- | --- |
| `concepts` | 软件工程与开发基础知识（版本控制、分支、测试、CI、需求、缺陷） | 5 |
| `ai-assistant` | 有效利用 AI 编码助手（何时信任、如何验证、幻觉、隐私与版权） | 5 |
| `soft-skills` | 软技能与产品技能（沟通、评审、需求澄清、优先级、协作） | 4 |
| `process` | 流程与工程权衡（发布、回滚、事故、技术债、权衡） | 4 |

每关内维度分布：

| 关卡 | concepts | ai-assistant | soft-skills | process |
| --- | --- | --- | --- | --- |
| L1 | 2 | 2 | 2 | 0 |
| L2 | 2 | 1 | 1 | 2 |
| L3 | 1 | 2 | 1 | 2 |

### FR-4 反馈与奖励

- **即时反馈**：提交后立即显示"正确 / 不正确"、正确选项、本题解析（**绝不向前端泄露 `correct_choice_id` 直到作答后**）。
- **关卡解锁**：本关答对率 ≥ 60%（6 题答对 4 题）解锁下一关。
- **徽章**（按历史最佳单局答对率，占 18 题）：

| 徽章 | 阈值 | 展示 |
| --- | --- | --- |
| 🥉 铜 | ≥ 50%（≥ 9 题） | 入门探索者 |
| 🥈 银 | ≥ 70%（≥ 13 题） | 实践新秀 |
| 🥇 金 | ≥ 85%（≥ 16 题） | 流程掌控者 |
| — | < 50% | 继续加油，无徽章 |

- **不扣分、不扣血**：答错只给解析，不惩罚。明确排除生命值/连击玩法。

### FR-5 与学习画像的关系（关键约束）

现有平台的价值观是「**基础是学生自报信息，不伪造能力评分**」（`docs/ARCHITECTURE.md` / README）。因此：

- 闯关结果写入 **`learning_profiles` 的新增参考字段**：`quiz_level` / `quiz_badge` / `quiz_topic_scores` / `quiz_best_score` / `quiz_updated_at`。
- **绝不覆盖**学生自报的 `goal` / `level` / `weekly_hours`。
- 前台展示措辞必须是「**闯关参考**（非能力评分）」，并在画像卡提供：
  - 「采用该建议」按钮 → 学生显式确认后才写入 `level`；
  - 「清空闯关参考」按钮。
- 路径推荐 `recommend_paths()` 中：**仅在学生未自报 `level` 时**，用 `quiz_level` 作为替代信号参与打分（+3），并给出可解释文案。

### FR-6 教师 / 管理员视角（本次最小）

- 管理员用户列表（`/api/admin/users`）返回体新增 `quiz` 摘要字段（最佳分数、徽章、最近闯关时间），供后续教师面板使用。
- 不新增独立后台页面。

### FR-7 [v2] 玩法增强（B 档）

| 编号 | 需求 | 关键约束 |
| --- | --- | --- |
| **B1** 随机抽题 | 题库扩容到 **30 题**（每关 10 题池），每局**分层抽样** 6 题 | 同一局内题目固定（写入 `answers.codes`）；跨局不同；维度配额不变 |
| **B2** 题目形态 | `single` / `multi`（多选）/ `order`（排序）/ 代码片段题 | 只用 `kind` + `snippet` 两列表达；判定见 §6.7 |
| **B3** Boss 关 | L3 最后一题为**综合大题**（`boss=true`），配 Boss 横幅与血量条 | Boss 题固定占用 L3 第 6 题位，不参与随机 |
| **B4** 错题复仇 | 错题进入复仇池，单独开一局重做；答对即出池 | 独立 `mission_id`，**不计入 best_score / 徽章 / 画像** |
| **B5** 速测模式 | 8 题快速体验，无关卡解锁 | 独立 `mission_id`，**不计入 best_score / 徽章 / 画像** |
| **B6** 生命值 | 仅 L3 显示 3 颗心，答错扣 1 | 纯展示，由本关错题数推导；不改变任何判定 |

#### FR-7.1 三种模式

| mode | mission_id | 题数 | 关卡结算 | 计入 best_score / 徽章 / 画像 |
| --- | --- | --- | --- | --- |
| `quest`（默认） | `level-quest-v1` | 18 | ✅ 有 | ✅ 是 |
| `quick` | `level-quest-quick-v1` | 8 | ❌ 无 | ❌ 否 |
| `revenge` | `level-quest-revenge-v1` | ≤ 6 | ❌ 无 | ❌ 否 |

> 主闯关的 `mission_id` **保持 `level-quest-v1` 不变**，因此 v1 已产生的数据（若有）与既有测试断言全部不受影响。

#### FR-7.2 分层抽样配额（保证维度分布恒定）

每关池子 10 题，每局抽 6 题：

| 关卡 | 池子构成 | 抽取配额 | 抽后维度分布 |
| --- | --- | --- | --- |
| L1 | concepts 4 / ai 3 / soft 3 | concepts 2 · ai 2 · soft 2 | 2 / 2 / 2 / 0 |
| L2 | concepts 3 / ai 2 / soft 2 / process 3 | concepts 2 · ai 1 · soft 1 · process 2 | 2 / 1 / 1 / 2 |
| L3 | concepts 2 / **ai 3（含 1 Boss）** / soft 2 / process 3 | **Boss 1** + concepts 1 · ai 1 · soft 1 · process 2 | 1 / 2 / 1 / 2 |

> 抽后各维度题数与 v1 的 18 题固定分布**完全一致**（concepts 5 / ai 5 / soft 4 / process 4），因此 `topic_scores` 与徽章分母（18）语义不变。

速测（8 题）配额：L1（concepts 1 · ai 1 · soft 1）+ L2（concepts 1 · ai 1 · process 1）+ L3（ai 1 · process 1），**不含 Boss**。

> **范围说明**：A 档的「连击 Combo / 共情式错题反馈 / 人格标签」见 **§6.11–§6.13**，额外的展示层演出（关卡解锁动画 / AI 同伴吐槽 / 彩蛋文案）见 **§6.15**。全部为**纯展示层**：连击不加分、人格标签不写画像、共情反馈复用既有 `explanations`，**都不新增迁移与字段**。仍未纳入的只剩音效。

---

## 4. 数据模型

### 4.1 复用策略总览

| 数据 | 处理 | 说明 |
| --- | --- | --- |
| **题目内容** | 🆕 新增 `quiz_questions` | 现有题库只有 3 道硬编码题，不足以支撑闯关 |
| **每题作答** | ♻️ 复用 `lesson_exercise_results` | `question_version` 存题号版本，`correct` / `attempts` 直接可用 |
| **闯关局** | ♻️ 复用 `mission_attempts` | `mission_id='level-quest-v1'`，`step`=已答题数，`score`=答对题数，`answers`=JSON 明细 |
| **画像参考** | ♻️ 扩展 `learning_profiles` | 仅新增可空列，不动原有列 |
| **关卡解锁** | ♻️ 由已完成局的 `answers` 推导 | 不新增表，见 §6.3 |

### 4.2 锚点课程（Anchor Course）——复用 `lesson_exercise_results` 的前提

`lesson_exercise_results.course_id` 是 `NOT NULL` 且外键指向 `courses.id`，闯关并非课程，因此需要一个**锚点课程行**提供合法 `course_id`：

- `courses` 插入一行：`title='软件工程水平闯关'`，`category='技术'`，`resource_type='quiz'`（新增类型值），`author='知行软件工程实验室'`，`badge='水平摸底'`，`owner_id = NULL`。
- 定位方式（**不要写入 `prototype_courses`**）：

```sql
SELECT id FROM courses WHERE resource_type = 'quiz' ORDER BY id LIMIT 1
```

> 若查不到则惰性创建（首次访问闯关接口时创建），保证已初始化数据库无需手工执行额外命令。

**⚠️ 为什么不能用 `prototype_courses`**：`tests/test_flows.py:196` 有硬断言
`SELECT COUNT(*) FROM prototype_courses == 3`，注册 `level-quest` 会使其变成 4 并**直接测试失败**。
改用 `resource_type='quiz'` 定位后，`list_lesson_progress`（`FROM prototype_courses p JOIN courses c`）完全不受影响。

**必须同步的副作用处理**（否则闯关会出现在课程目录里）：

| 文件 | 改动 |
| --- | --- |
| `app/courses/repository.py` `search_courses` | 在 `conditions` 起始处无条件加入 `"resource_type <> 'quiz'`（注意：该函数在无筛选条件时 `where` 为空串，需改为始终带条件） |
| `app/courses/repository.py` `list_all_courses` | `WHERE` 增加 `resource_type <> 'quiz'` |
| `app/learning/service.py` `course_lesson` | `resource_type='quiz'` 时返回 `404`（该课不可作为课时打开） |
| `app/learning/service.py` `start_learning` | 同上，返回 `400` |

> `learning_snapshot()` 中 `list_lesson_progress` 会 JOIN 出全部 `prototype_courses` 行；锚点课程不写入该表，因此**整条学习路径链路零影响**。
> 另：`app/auth/repository.py::list_owned_courses` 带 `owner_id IS NOT NULL` 条件，锚点课程 `owner_id` 为 NULL，**管理员账户视图不受影响**。

**级联删除风险**：管理员可执行 `DELETE FROM courses WHERE id=%s` 删除任意课程。若误删锚点课程，`lesson_exercise_results` 中该 `course_id` 的闯关答题记录会**级联清空**（下次 init 会重建课程行，但历史记录不恢复）。建议：
- `seed_quiz` 每次启动时确保锚点课程存在；
- 可选：`app/courses/service.py` 删除课程时，对 `resource_type='quiz'` 返回 400 并提示"闯关锚点课程不可删除"。

### 4.3 新增迁移 `migrations/005_quiz.sql`

```sql
-- 1. 题库
CREATE TABLE IF NOT EXISTS quiz_questions (
    code              TEXT PRIMARY KEY,               -- 稳定题号，如 'concepts-l1-01'
    version           TEXT NOT NULL UNIQUE,           -- 写入 lesson_exercise_results.question_version
    level             INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
    topic             TEXT NOT NULL CHECK (topic IN ('concepts','ai-assistant','soft-skills','process')),
    difficulty        INTEGER NOT NULL CHECK (difficulty BETWEEN 1 AND 3),
    stem              TEXT NOT NULL,
    choices           JSONB NOT NULL,                 -- [{"id":"a","text":"..."}, ...]
    correct_choice_id TEXT NOT NULL,
    explanation       TEXT NOT NULL,                  -- 正确项解析
    explanations      JSONB NOT NULL DEFAULT '{}',    -- {choice_id: 解析}
    source            TEXT NOT NULL DEFAULT 'seed',   -- seed | teacher | ai （后续扩展）
    active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS quiz_questions_level_idx
    ON quiz_questions (level, active);

-- 2. 学习画像：闯关参考（全部可空，不改动既有列语义）
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_best_score INTEGER;
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_badge TEXT;
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_level TEXT;
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_topic_scores JSONB;
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_updated_at TIMESTAMPTZ;
```

**迁移注册**：`app/infrastructure/migrations.py`

```python
CORE = ("001_core.sql",)
LEARNING = ("002_learning.sql", "003_study.sql")
PROTOTYPE = (*LEARNING, "004_prototype.sql", "005_quiz.sql")   # ← 追加
ALL = (*CORE, *PROTOTYPE)
```

> 追加到 `PROTOTYPE` 而非 `ALL` 的尾部，是为了让 `init-db`（调用 `initialize_core` + `initialize_prototype`）与 `run.py` 的增量初始化都能自动应用；已有库执行 `flask --app run migrate` 或启动服务时也会补齐。

### 4.3b [v2] 新增迁移 `migrations/006_quiz_play.sql`

```sql
-- 题目形态（B2）
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'single'
    CHECK (kind IN ('single','multi','order'));
-- 代码片段 / 情境文本，供"找茬题""情境题"展示（B2）
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS snippet TEXT;
-- Boss 题标记（B3）：每关最多 1 道，仅 L3 使用
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS boss BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS quiz_questions_pool_idx ON quiz_questions (level, topic, active);
```

```python
PROTOTYPE = (*LEARNING, "004_prototype.sql", "005_quiz.sql", "006_quiz_play.sql")
```

> 全部为 `ADD COLUMN IF NOT EXISTS` + `DEFAULT`，对已有 18 行**零影响**（默认值 `single` / `NULL` / `FALSE`），可重复执行。
> **不新增表、不改现有列类型** —— 复仇池复用 `lesson_exercise_results`，抽题结果复用 `mission_attempts.answers`，因此 §10.1 的测试断言无需再改。

### 4.4 复用表的字段语义约定

**`lesson_exercise_results`**

| 列 | 取值 |
| --- | --- |
| `user_id` | 当前用户 |
| `course_id` | 锚点课程 ID |
| `question_version` | `quiz_questions.version`，如 `quiz-concepts-l1-01-v1` |
| `choice_id` | 学生所选选项 ID；**[v2] `multi` / `order` 题为逗号分隔序列**，如 `"a,c"` / `"b,a,c,d"` |
| `correct` | 服务端判定结果（**复仇池即 `correct = FALSE` 的行**） |
| `attempts` | 累计作答次数（`ON CONFLICT` 已自动 +1） |

**`mission_attempts`**

| 列 | 取值 |
| --- | --- |
| `mission_id` | 主闯关 `'level-quest-v1'`；[v2] 速测 `'level-quest-quick-v1'`、复仇 `'level-quest-revenge-v1'`（与 `'release-rescue-v1'` 四者共存、互不干扰） |
| `step` | 已答题数；**局结束时必定置为该模式总题数**（18 / 8 / 实际复仇题数） |
| `score` | 本局答对题数 |
| `answers` | JSON，结构见 §6.4 |

> 约定：`step = 总题数` 表示"本局已结束"，通关与否由 `answers.outcome` 区分。这样可以**零改动复用** `find_unfinished_attempt`（`step < total`）与 `find_best_mission_score`（`step = total`）。

#### [v2] `correct_choice_id` 的语义扩展

`quiz_questions.correct_choice_id` 是 `TEXT`，v2 按 `kind` 复用它承载不同形态的正确答案，**不新增列**：

| kind | `correct_choice_id` 取值 | 学生提交 `choice_id` | 判定 |
| --- | --- | --- | --- |
| `single` | `"a"` | `"a"` | 字符串相等 |
| `multi` | `"a,c"`（按选项顺序拼接） | `"a,c"`（前端排序后拼接） | **集合相等**（顺序无关） |
| `order` | `"a,b,c,d"`（正确顺序） | `"b,a,c,d"`（学生排的顺序） | **字符串相等**（顺序有关） |

> 对已有的 `single` 题语义**完全不变**，因此 v1 数据与判定逻辑零影响。

---

## 5. 后端设计

严格遵循 `routes.py → service.py → repository.py` 三层（见 `docs/ARCHITECTURE.md`）。

### 5.1 新增文件

```
app/quiz/
  __init__.py
  content.py        QUESTION_BANK（18 题）+ 关卡/徽章常量
  routes.py         HTTP + session
  service.py        规则、计分、事务
  repository.py     SQL
migrations/
  005_quiz.sql
```

### 5.2 修改文件

| 文件 | 改动 |
| --- | --- |
| `app/infrastructure/migrations.py` | `PROTOTYPE` 追加 `005_quiz.sql`；新增 `initialize_quiz` 或在 `initialize_prototype` 内调用 `seed_quiz` |
| `app/infrastructure/seeds.py` | 新增 `seed_quiz(db)`：幂等写入题库 + 确保锚点课程与 slug |
| `app/factory.py` | `from app.quiz.routes import bp as quiz` 并加入蓝图元组 |
| `app/courses/repository.py` | `search_courses` / `list_all_courses` 过滤 `resource_type <> 'quiz'` |
| `app/learning/service.py` | `course_lesson` / `start_learning` 拒绝 quiz 课；`path()` 的 `result["mission"]` → `result["quest"]` |
| `app/learning/paths.py` | `recommend_paths` 支持 `quiz_level` 兜底信号 |

### 5.3 常量（`app/quiz/content.py`）

```python
MISSION_ID = "level-quest-v1"                 # 主闯关（v1 起不变）
MISSION_IDS = {                                # [v2] 三种模式
    "quest":   "level-quest-v1",
    "quick":   "level-quest-quick-v1",
    "revenge": "level-quest-revenge-v1",
}
QUEST_SLUG = "level-quest"
ANCHOR_COURSE_TITLE = "软件工程水平闯关"

LEVELS_META = [
    {"level": 1, "name": "开发常识",   "hint": "不需要专业背景，凭常识判断即可"},
    {"level": 2, "name": "情境判断",   "hint": "读一个小场景，选更合适的做法"},
    {"level": 3, "name": "流程与权衡", "hint": "涉及协作、发布与取舍"},
]

QUESTIONS_PER_LEVEL = 6
TOTAL_QUESTIONS = 18            # quest 模式
QUICK_TOTAL = 8                 # quick 模式
REVENGE_MAX = 6                 # revenge 模式上限
HEARTS_PER_LEVEL = 3            # 仅 L3 显示
UNLOCK_RATIO = 0.6              # 6 题答对 4 题

# [v2] 分层抽样：每关的抽取配额（B1）
DRAW_QUOTA = {
    1: {"concepts": 2, "ai-assistant": 2, "soft-skills": 2},
    2: {"concepts": 2, "ai-assistant": 1, "soft-skills": 1, "process": 2},
    3: {"concepts": 1, "ai-assistant": 1, "soft-skills": 1, "process": 2},  # + 1 Boss
}
QUICK_QUOTA = {
    1: {"concepts": 1, "ai-assistant": 1, "soft-skills": 1},
    2: {"concepts": 1, "ai-assistant": 1, "process": 1},
    3: {"ai-assistant": 1, "process": 1},
}
KINDS = ("single", "multi", "order")

BADGES = [("gold", 0.85, "流程掌控者"),
          ("silver", 0.70, "实践新秀"),
          ("bronze", 0.50, "入门探索者")]
TOPICS = ("concepts", "ai-assistant", "soft-skills", "process")
TOPIC_LABELS = {"concepts": "软件工程基础",
                "ai-assistant": "AI 编码助手",
                "soft-skills": "软技能与产品",
                "process": "流程与工程权衡"}
LEVEL_SUGGESTION = [(0.70, "experienced"), (0.40, "intermediate"), (0.0, "beginner")]
```

`QUESTION_BANK` 每题结构（与 `app/learning/study.py::EXERCISES` 保持同构，便于复用解析器）：

```python
{
    "code": "concepts-l1-01",
    "version": "quiz-concepts-l1-01-v1",
    "level": 1,
    "topic": "concepts",
    "difficulty": 1,
    "stem": "团队多人同时修改同一个文件时，为什么通常用版本控制工具而不是互相发文件？",
    "choices": [
        {"id": "a", "text": "版本控制能保留每次修改的记录，并帮助合并不同人的改动"},
        {"id": "b", "text": "因为版本控制工具可以让代码运行得更快"},
        {"id": "c", "text": "因为文件太大，网络传输不方便"},
    ],
    "correct": "a",
    "explanations": {
        "a": "正确。版本控制保留历史、支持回退，并能合并多人改动。",
        "b": "运行速度与是否使用版本控制无关。",
        "c": "传输便利只是附带好处，核心是可追溯与可协作。",
    },
}
```

### 5.4 服务层核心逻辑

```python
# --- v1 ---
def overview(*, user_id, get_db) -> dict          # FR-1 卡片数据
def start(*, user_id, get_db) -> (dict, int)      # 创建或恢复未完成局
def answer(run_id, *, user_id, data, get_db)      # 提交一题；服务端判定
def result(*, user_id, get_db) -> dict            # 终局/历史结果 + 徽章 + 维度
def adopt_suggestion(*, user_id, get_db)          # 学生显式采用 → 写 learning_profiles.level
def clear_progress(*, user_id, get_db)          # 清空该学生全部闯关数据（局 + 答题 + 画像参考）

# --- [v2] B 档新增 ---
def start(*, user_id, mode, get_db) -> (dict, int)   # mode: quest | quick | revenge
def draw_questions(pool, mode, exclude) -> list[dict]   # B1 分层抽样（含 Boss 定位）
def judge(question, choice_id) -> bool                 # B2 按 kind 分派判定
def valid_choice(question, choice_id) -> bool          # B2 提交合法性
def revenge_pool(db, user_id, course_id) -> list[str]  # B4 错题 version 列表
```

**判定与防重放**（对齐现有 Release Rescue 的实现风格）：

- `answer` 校验：`run_id` 归属本人；`data["step"] == row["step"]` 否则 `409`（步骤已更新）；`choice_id` 必须存在于该题选项，否则 `400`。
- 正确性由服务端用 `quiz_questions.correct_choice_id` + `kind` 判定，**忽略任何客户端传来的分数或正确性字段**。
- 同一题重复提交 → `409`。
- [v2] `multi` / `order` 题额外校验：提交 id 数量必须与题意一致、不可重复、必须都在选项内（§6.7）。

---

## 6. 规则细节

### 6.1 计分

- 每题答对 +1 分，答错 +0；`score` = 本局答对题数（0–18）。
- 无时间加分、无连击加分。

### 6.2 关卡解锁

- 一关 6 题答完后结算：`correct_count / 6 >= UNLOCK_RATIO(0.6)` → 解锁下一关并继续；否则本局结束（`outcome="stopped"`）。
- 三关全通 → `outcome="cleared"`。
- **已解锁关卡不回退**：从历史已完成局推导 `max_cleared_level`，取最大值。

> ⚠️ **「解锁」是单局内的推进机制，不是跨局的地图进度。** 卡片上关卡项的 `cleared` / `unlocked` 只表示**历史曾通过**（见 `_level_states`，遍历所有已完成局取并集），**不决定下一局从哪里开始**。每一局 `quest` 都固定从第 1 关第 1 题开始、做满 18 题 —— 因为 `best_score` 是 18 分制、徽章比率与参考水平都依赖完整一局，跳过关卡会破坏可比性。
>
> 因此 UI 不得把关卡项写成可单独进入的地图：`cleared` 应表述为「历史通过 · 最佳 N / 6」，`locked` 应表述为「需在同一局内通过第 N 关」，并在关卡列表上方写明「每局都从第 1 关开始做完整 18 题」。

### 6.3 历史最佳与徽章

`best_score = MAX(score) FROM mission_attempts WHERE user_id=? AND mission_id='level-quest-v1' AND step=18`
→ 直接复用 `app/missions/repository.py::find_best_mission_score`。

徽章：`ratio = best_score / 18`，按 `BADGES` 阈值从高到低匹配。

### 6.4 `mission_attempts.answers` JSON 结构

```json
{
  "mode": "quest",
  "codes": ["concepts-l1-01", "soft-skills-l1-03", "... 18 个题号，顺序即出题顺序 ..."],
  "outcome": "cleared",
  "score": 13,
  "max_level": 3,
  "levels": [
    {"level": 1, "correct": 5, "total": 6, "passed": true},
    {"level": 2, "correct": 5, "total": 6, "passed": true},
    {"level": 3, "correct": 3, "total": 6, "passed": true}
  ],
  "items": [
    {"code": "concepts-l1-01", "version": "quiz-concepts-l1-01-v1",
     "level": 1, "topic": "concepts", "choice_id": "a", "correct": true}
  ]
}
```

> **[v2] `codes` 是 B1 的关键**：抽题结果在建局时写入并冻结，后续所有作答按 `codes[step]` 取题。`outcome` 增加取值 `hearts_out`（L3 生命值耗尽，与 `stopped` 同义但文案不同，见 §6.8）。

> 关卡解锁状态 = `MAX(所有已完成局的 levels[].level where passed)`，与当前局取并集。

### 6.5 画像参考映射

```
ratio = best_score / 18
suggested_level = 第一个满足 ratio >= 阈值的 LEVEL_SUGGESTION
topic_scores = {topic: 该维度答对题数 / 该维度总题数}   # 取自最近一局 items
```

- 写入 `learning_profiles.quiz_*`，**不动 `level`**。
- 前端措辞固定为「闯关参考」，并附「这不是能力评分，仅用于给出起点建议」。

### 6.0 [v2] 趣味层与判定层的隔离原则（硬性）

B 档的所有玩法增强**只允许**作用于「展示」与「取题」，**不允许**作用于「计分」：

| 增强 | 是否影响 `correct` 判定 | 是否影响 `score` | 是否影响 `best_score` / 徽章 / 画像 |
| --- | --- | --- | --- |
| B1 随机抽题 | 否（只换题目，判定不变） | 否 | 否（题数恒为 18） |
| B2 多题型 | **是（判定分派）** | 否（仍然「对 +1 / 错 +0」） | 否 |
| B3 Boss 关 | 否 | 否 | 否 |
| B4 错题复仇 | 否 | 否 | **否（独立 mission_id）** |
| B5 速测 | 否 | 否 | **否（独立 mission_id）** |
| B6 生命值 | 否 | 否 | 否（纯展示） |

> 唯一允许影响判定的只有 B2（因为题型变了判定规则必须跟着变），但它只改「怎么判对」，不改「判对之后怎么算分」。

### 6.6 [v2] 抽题（B1）

- 每局**新建时**抽一次，把结果 `codes` 数组**持久化到 `answers`**（见 §6.4 新增字段）。此后 `answer` / `read_run` 一律按 `codes[step]` 取题，保证**同局稳定、断点续玩不错位**。
- 抽样用 Python `random.sample`，按 `DRAW_QUOTA` 分层：每关每个 `topic` 独立抽所需数量，再按关卡顺序拼接。
- **Boss 题**（`boss=true`）：L3 抽取时先选 1 道 Boss，其余 5 道按配额抽（排除已选），Boss **固定放在 L3 第 6 题位**（即全局第 18 题）。
- 池子不足时（如教师后续停用题目）降级：缺额用同关卡其他 topic 的题补齐；仍不足则返回 `503` + 「题库暂不可用」。
- **兼容旧局**：若 `answers` 中无 `codes`（v1 时期的局），回退为「按 `level, code` 排序取前 18」，不报错。

### 6.7 [v2] 题型判定（B2）

```python
def judge(question, choice_id):
    kind = question["kind"]
    if kind == "single":
        return choice_id == question["correct_choice_id"]
    if kind == "multi":
        return set(choice_id.split(",")) == set(question["correct_choice_id"].split(","))
    if kind == "order":
        return choice_id == question["correct_choice_id"]
    return False
```

提交合法性（`valid_choice`）：

| kind | 校验 |
| --- | --- |
| `single` | `choice_id` 必须在选项 id 内 |
| `multi` | 逗号拆分后：无重复、全部在选项内、**数量等于正确答案的数量**（防止靠全选蒙对） |
| `order` | 逗号拆分后：无重复、全部在选项内、**数量等于选项总数** |

前端提交前不做任何正确性判断，只负责把用户操作序列化成 `choice_id` 字符串。

### 6.8 [v2] 生命值（B6）

- **仅 L3 显示**，`HEARTS_PER_LEVEL = 3`，答错 1 题扣 1 颗。
- 后端在 `public_run` 中返回 `hearts`（`3 - 本关已答错题数`）与 `hearts_enabled`（`level == 3 and mode == "quest"`）。
- **不新增任何状态、不改变任何判定**：生命值纯粹由本关错题数推导。

> **为什么它不会变成惩罚**：L3 的通关线是「答对 ≥ 4/6」，即**最多只能错 2 题**；3 颗心在错第 3 题时归零，而错第 3 题时关卡结算本来就已经判定 `passed=false` 并结束本局。**二者同步，生命值不会造成任何额外失败**，只是把"还剩几次机会"可视化，制造紧张感而不制造挫败感。

### 6.9 [v2] 速测模式（B5）

- `mission_id = 'level-quest-quick-v1'`，固定 8 题，**无关卡结算、无解锁、无 Boss**。
- 结束后结果页给出「大致水平倾向 + 建议做完整 18 题摸底」，并直接提供跳转按钮。
- **不写 `learning_profiles.quiz_*`，不计入 `best_score`**，避免 8 分制的分数污染 18 分制的历史最佳。

### 6.10 [v2] 错题复仇（B4）

- 复仇池 = `lesson_exercise_results` 中 `course_id = 锚点课程 AND user_id = ? AND correct = FALSE` 的 `question_version` 集合，反查 `quiz_questions` 得到题目。
- 每次最多 `REVENGE_MAX = 6` 题，随机排序；**按当前错题池实时抽取**，因此答对后（upsert 把 `correct` 置为 `TRUE`）该题自动出池。
- `mission_id = 'level-quest-revenge-v1'`，一局到底，不计分入画像。
- 池子为空时 `POST /api/quiz/runs {"mode":"revenge"}` 返回 `400` + 「暂时没有错题可以复仇」。
- 卡片在 `revenge_count > 0` 时显示「错题复仇 →」按钮。

### 6.11 [v3] 连击 Combo（A1）

- 定义：**连续答对的题数**，答错即归零。
- 后端在 `public_run` 返回 `streak`：由 `answers.items` 末尾连续 `correct=true` 推导。**不新增列、不新增迁移**，断点续玩时由服务端重算，前端无需持久化。
- **连击不加分**（§6.1 的「每题答对 +1、无连击加分」保持不变）。
- 前端在 `streak >= 2` 时显示 `🔥 连击 ×N`，并在 3 / 5 / 8 触发不同文案。

> **为什么不加分**：一旦连击加分，`score` 就不再是「答对题数」，会连带污染 `best_score`、徽章阈值（§5.2）与画像参考水平（§6.4），直接违反 §6.0。连击的价值在情绪反馈，不在数值。

### 6.12 [v3] 共情式错题反馈（A2）

- 复用既有 `explanations[错误项]` —— v1 起每题的每个错误选项都已写好解析，**不新增任何字段**。
- 前端在解析前加一句共情前缀，按**本局连续答错次数**升级：

| 连错次数 | 前缀示例 |
| --- | --- |
| 1 | 「这题有点绕，很多人第一次都会选这个。」 |
| 2 | 「连着两题没顺，很正常 —— 看一眼解析就过去了。」 |
| ≥ 3 | 「先歇口气。连续卡住不代表你不适合，这几题确实是分水岭。」 |

- Boss 题答错额外追加「Boss 本来就不是一次能过的」。
- **纯前端常量表**，后端返回体不变。

### 6.13 [v3] 人格标签（A3）

- 由**维度正确率**派生：`persona_for(topic_scores)` 取正确率最高的维度对应的称号；四个维度都 ≥ 80% 时给「全能工程师」；无维度数据时返回 `null`。

| 主导维度 | 标签 |
| --- | --- |
| `ai-assistant` | 🤖 AI 指挥官 |
| `process` | 🛡️ 流程守护者 |
| `concepts` | 🧩 概念拆解者 |
| `soft-skills` | 🤝 协作润滑剂 |
| 全部 ≥ 80% | 🌟 全能工程师 |

- 在 `GET /api/quiz/result?mode=quest` 的 `result.persona` 返回 `{id, icon, label, note}`。
- **与徽章并行、互不替代**：徽章按总分（§5.2），人格标签按维度倾向，结果页同时展示。
- 不写 `learning_profiles`、不影响画像参考水平。

### 6.14 [v3] 选项顺序与正确项分布（Q1）

- **缺陷**：v1 / v2 的 30 道题里 **29 道正确项都是 `a`**，学生会直接选 A 蒙题，是必须修掉的题目质量问题。
- **要求**：`single` 题的正确项在本题可用选项内**均匀分布**（当前 27 道单选题为 `a` / `b` / `c` 各 9 道）；`multi` / `order` 题的正确项集合与顺序同样打散，并排除 `a,b,c,d` 这种「看起来没打乱」的退化结果。
- **打散结果固化在题库内容里，不做运行时随机**：运行时随机会让重跑 seed 后正确项发生变化，导致历史答题记录在结果页显示错误的「正确选项」。
- 打散只交换 `(选项文本, 该选项解析)` 这一对的位置，选项 id 仍为 `a/b/c/d`，因此 `explanations` 与 `correct_choice_id` 始终自洽。

### 6.15 [v3+] 纯展示层演出：解锁动画 / AI 同伴吐槽 / 彩蛋文案

三者**都在前端，不新增接口、不新增字段、不落库、不计分**，可整体移除而不影响任何数据。

**① 关卡地图解锁动画**

- `renderQuestCard()` 维护一份关卡状态快照 `questLevelStates`。
- 仅当某关**上一帧是 `locked`、这一帧不是** 时，给它加 `just-unlocked`，播放一次 `@keyframes quest-level-unlock`（横移淡入 + 光晕外扩）与图标的 `quest-mark-pop`。
- 快照为 `null`（首次渲染）时不播放 —— 否则每次刷新页面都会闪一遍。状态倒退（`unlocked` → `locked`）同样不播放。
- `prefers-reduced-motion: reduce` 下动画整体关闭。

**② AI 同伴吐槽**

- `COMPANION_LINES` 按情境分池：`correct` / `streak`（连击 ≥ 3）/ `wrong` / `bossWrong` / `bossCorrect`。
- 答题反馈区底部固定一行展示区 `.quest-companion`（🤖 + 文案），样式沿用 `.quest-comfort` 的 12.5px 灰字规格。
- 随机取一条并**排除上一条**，避免同一句连续出现两次。
- 与 §6.12 的共情反馈**并存不替代**：共情反馈按连错数固定升级（安慰），同伴吐槽随机（拟人），两者语气不同。

**③ 彩蛋文案**

- `EASTER_EGGS` 每项自带触发条件 `when(result, mode)`，命中则在结算页追加 `.quest-easter` 展示区（🥚 + 文案）。
- 当前三个：`perfect`（`score === total`，速测与完整闯关均可）、`revenge-clear`（复仇模式错题清零）、`april-fools`（4 月 1 日）。
- 条件只读取结算响应里已有的字段，**不额外请求**。

> **仍未纳入**：音效。同为纯展示层，需音频资源与静音开关，可随时追加。

---

## 7. API 契约

所有接口需登录（`@login_required`），统一返回 JSON，错误体 `{"error": "..."}`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/quiz/overview` | 卡片数据：关卡解锁、历史最佳、徽章、画像参考、[v2] 复仇池数量 |
| `POST` | `/api/quiz/runs` | 开始新局 / 恢复未完成局（未完成返回已有局，`200`；新建返回 `201`）。[v2] 请求体 `{"mode": "quest"\|"quick"\|"revenge"}`，缺省 `quest` |
| `GET` | `/api/quiz/runs/<int:run_id>` | 恢复指定局 |
| `POST` | `/api/quiz/runs/<int:run_id>/answer` | 提交一题 |
| `POST` | `/api/quiz/runs/<int:run_id>/abandon` | 放弃本局（标记结束，保留已得分数） |
| `GET` | `/api/quiz/result` | 最近一局结果、徽章、维度得分、错题回顾。[v3] 查询参数 `?mode=`，`quest` 时额外返回 `result.persona` |
| `POST` | `/api/quiz/profile/adopt` | 采纳闯关建议写入 `level`（学生显式操作） |
| `DELETE` | `/api/quiz/profile/reference` | 清空**当前登录者**的全部闯关数据：闯关局 + 答题记录 + 画像参考。**不可恢复**，前端必须先 `confirm` |

**`has_progress` 与「清空记录」按钮的可见性**：`has_progress` = 该学生在 `mission_attempts`（三种 `level-quest-*`）或 `lesson_exercise_results`（锚点课程）中是否还有数据，由服务端实时统计。

> 学习画像页面的「清空记录」按钮**不能**用 `reference` 是否存在来判断：`reference` 为空时仍可能残留闯关局与答题记录（清空过一次、或只玩过 `quick` / `revenge`），此时若不显示按钮，学生将无法清理自己的数据。正确条件是 `reference || has_progress`。
> 「采用」按钮仍只在 `reference` 存在时出现。

### 7.1 `GET /api/quiz/overview`

```json
{
  "quest": {
    "mission_id": "level-quest-v1",
    "title": "软件工程水平闯关",
    "description": "18 道题，3 个关卡。答对 4 题即可解锁下一关，结果仅作为起点参考。",
    "levels": [
      {"level": 1, "name": "开发常识", "state": "cleared",   "best_correct": 5, "total": 6},
      {"level": 2, "name": "情境判断", "state": "unlocked",  "best_correct": null, "total": 6},
      {"level": 3, "name": "流程与权衡", "state": "locked",  "best_correct": null, "total": 6}
    ],
    "total": 18,
    "best_score": 9,
    "badge": {"id": "bronze", "label": "入门探索者"},
    "has_unfinished": false,
    "has_progress": true,
    "revenge_count": 4,
    "modes": {
      "quest": {"total": 18, "label": "完整闯关"},
      "quick": {"total": 8, "label": "8 题速测"},
      "revenge": {"total": 4, "label": "错题复仇"}
    }
  },
  "reference": {
    "level": "intermediate",
    "badge": "bronze",
    "topic_scores": {"concepts": 0.8, "ai-assistant": 0.6, "soft-skills": 0.5, "process": 0.25},
    "updated_at": "2026-10-24T09:12:00+00:00",
    "note": "闯关参考，不是能力评分；可一键采用或清空。"
  }
}
```

### 7.2 `POST /api/quiz/runs`（新建 / 恢复）

请求（[v2]）：

```json
{"mode": "quest"}
```

响应：

```json
{
  "run": {
    "id": 42,
    "mode": "quest",
    "step": 0,
    "score": 0,
    "total": 18,
    "level": {"level": 1, "name": "开发常识", "index": 1, "of": 3},
    "hearts_enabled": false,
    "hearts": null,
    "streak": 0,
    "question": {
      "code": "concepts-l1-01",
      "version": "quiz-concepts-l1-01-v1",
      "kind": "single",
      "pick_count": 1,
      "snippet": null,
      "boss": false,
      "stem": "团队多人同时修改同一个文件时……",
      "choices": [{"id": "a", "text": "……"}, {"id": "b", "text": "……"}],
      "topic": "concepts",
      "topic_label": "软件工程基础"
    }
  }
}
```

- `kind = "multi"` 时前端渲染为多选（底部「确认提交」按钮）；`kind = "order"` 时渲染为排序（点击按顺序编号）。
- **`pick_count`** 是本题需要提交的选项数量：`single` 为 1，`multi` 为正确项数量，`order` 为选项总数。它只暴露"要选几个"，不暴露"哪几个"，用于前端判断「确认提交」是否可点。
- `snippet` 非空时在题干上方以等宽代码块展示（"找茬题" / 情境题）。
- `boss = true` 时展示 Boss 横幅与血条。
- `hearts_enabled = true`（仅 L3 + quest 模式）时展示 `♥♥♥`；`hearts` 为剩余数量。
- **`streak`** 是当前连续答对题数（答错归零），由服务端从已答记录推导，**不额外计分**（§6.11）。
- 错误：`400` mode 非法 / 复仇池为空；`503` 题库未初始化。

> 恢复未完成的局时返回 `200`，新建返回 `201`。已答过的题不重复出现（题目由 `answers.codes` 冻结）。

### 7.3 `POST /api/quiz/runs/<id>/answer`

请求：

```json
{"step": 0, "question_code": "concepts-l1-01", "choice_id": "a"}
```

响应：

```json
{
  "correct": true,
  "explanation": "正确。版本控制保留历史、支持回退，并能合并多人改动。",
  "correct_choice_id": "a",
  "run": {
    "id": 42, "step": 1, "score": 1, "total": 18,
    "level": {"level": 1, "name": "开发常识", "index": 1, "of": 3},
    "question": { "...": "下一题；若为 null 表示本局结束" }
  },
  "level_result": null
}
```

关卡结算时额外返回：

```json
{
  "level_result": {
    "level": 1, "correct": 5, "total": 6, "passed": true,
    "unlocked_level": 2,
    "message": "本关答对 5 / 6，已解锁「情境判断」。"
  }
}
```

错误码：`400` 选项无效 / `404` 局不存在 / `409` 步骤已更新（重复提交）。

### 7.4 `GET /api/quiz/result`

```json
{
  "result": {
    "outcome": "cleared",
    "score": 13,
    "total": 18,
    "percent": 72,
    "badge": {"id": "silver", "label": "实践新秀"},
    "best_score": 13,
    "levels": [{"level": 1, "correct": 5, "total": 6, "passed": true}, "..."],
    "topics": [
      {"topic": "concepts", "label": "软件工程基础", "correct": 4, "total": 5},
      {"topic": "ai-assistant", "label": "AI 编码助手", "correct": 4, "total": 5},
      {"topic": "soft-skills", "label": "软技能与产品", "correct": 3, "total": 4},
      {"topic": "process", "label": "流程与工程权衡", "correct": 2, "total": 4}
    ],
    "wrong_items": [
      {"code": "process-l3-02", "stem": "……", "your_choice": "b",
       "correct_choice_id": "c", "explanation": "……"}
    ],
    "suggested_level": "intermediate",
    "suggested_level_label": "入门 · 已写过简单程序"
  }
}
```

---

### 7.5 [v4] 题库管理接口（管理员）

题库是**全局基准**（`quiz_questions` 没有 owner 列），维护权归**管理员**，接口一律使用 `admin_required`：

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/admin/quiz/questions` | 全部题目（含停用的），附带 `source` / `active` 与下拉元数据 |
| `POST` | `/api/admin/quiz/questions` | 新增，`source='admin'`，默认启用 |
| `PUT` | `/api/admin/quiz/questions/<code>` | 局部更新内容字段 |
| `PATCH` | `/api/admin/quiz/questions/<code>/active` | 启用 / 停用，body `{ "active": bool }` |
| `DELETE` | `/api/admin/quiz/questions/<code>` | 删除（已有作答记录则拒绝） |

**不变式**：`code`、`version`、`source` 落库后不再修改。`version` 是 `lesson_exercise_results.question_version` 的取值来源，改动会让历史作答与错题本对不上号。

**两个守卫**——避免一次编辑就让完整闯关开不了局：

1. **配额守卫**：停用 / 删除前用 `DRAW_QUOTA` 复核每关每个维度的剩余可用题数（第 3 关另外要求至少 1 道 Boss 题）。不足则 400，并把缺口逐条列出。
2. **作答守卫**：`DELETE` 前统计该题 `version` 在 `lesson_exercise_results` 中的作答数，> 0 则 409，提示改用「停用」。

**字段校验**：`level ∈ {1,2,3}`、`topic ∈ TOPICS`、`difficulty ∈ {1,2,3}`、`kind ∈ {single,multi,order}`、`choices ≥ 2` 且编号不重复、`correct_choice_id` 必须落在选项编号内（`multi` 允许逗号分隔）。

#### ⚠️ seed 覆盖策略（本功能的前置条件）

`run.py` 每次启动都会执行 `initialize_prototype` → `seed_quiz`。原先 `ON CONFLICT (code) DO UPDATE` **无条件覆盖**除 `source` 外的全部字段并强制 `active = TRUE`，界面上的任何编辑都会在下次重启被静默冲掉。现在追加了 `WHERE quiz_questions.source = 'seed'`：

- `source='seed'`：仍随代码升级刷新，题库内容改代码即可生效
- `source='admin'`：**免疫** seed，界面编辑得以留存

`app/quiz/repository.py` 的 `upsert_question` 与 seed 是同一份语义，已同步加上同样的 `WHERE`。

---

## 8. 前端改造

### 8.0 结果展示位置总览（现有 → 闯关）

闯关结果共出现在 **4 个位置**，其中 3 个是替换现有 Release Rescue 的展示点，1 个是新增。

| # | 位置 | 现有（Release Rescue） | 闯关后（Level Quest） |
| --- | --- | --- | --- |
| 1 | 路径区右侧卡片 | `index.html:87` `<small id="mission-best">尚未开始</small>`，由 `workspace.js:43/62` 写入 | `<small id="quest-best">`，显示 `尚未开始` / `尚无完成成绩` / `历史最佳 13 / 18 · 🥈 实践新秀` |
| 2 | 弹窗内实时反馈 | `release-rescue.js:3-16` 渲染 `#mission-status` / `#mission-progress` / `#mission-history` | `#quest-modal` 内 `#quest-status` / `#quest-run-progress` / `#quest-feedback` / `#quest-summary` |
| 3 | 路径完成后「下一步」 | `workspace.js:189-191` `completionTarget={type:"mission"}` + 「开始实践挑战 →」 | `{type:"quest"}` + 「开始水平闯关 →」 |
| 4 | 🆕 学习画像卡 | 无 | `index.html:78` `.profile-overview` 下追加「闯关参考」行（FR-5） |

#### 展示点 1：卡片最佳成绩的三种文案

现有逻辑（`workspace.js:43` / `:62`）：

```javascript
// :62 未登录
$("#mission-best").textContent = "尚未开始";
// :43 已登录
$("#mission-best").textContent = pathData.mission.best_score === null
    ? "尚无完成成绩"
    : `历史最高 ${pathData.mission.best_score} / 100`;
```

闯关后（条件语义不变，仅换分母与徽章）：

```javascript
$("#quest-best").textContent = "尚未开始";                       // 未登录
$("#quest-best").textContent = quest.best_score === null
    ? "尚无完成成绩"                                              // 从未完整完成一局
    : `历史最佳 ${quest.best_score} / ${quest.total}` +
      (quest.badge ? ` · ${quest.badge.icon} ${quest.badge.label}` : "");
```

> `best_score === null` 的判定来自 `find_best_mission_score`，要求 `step = total`（**必须完整走完一局**），中途放弃不计成绩。闯关沿用同一语义（`step = 18`），故 `尚无完成成绩` 文案可原样保留。

> ⚠️ **分母语义变化**：现有是 `100 分`（4 步 × 25 分），闯关是 `18 题`（答对题数）。不可沿用 `/ 100`，否则 `13 / 100` 观感像只得 13 分。徽章用于将"分数感"转为"成就感"。

#### 展示点 2：弹窗内的元素替换映射

| 现有元素（`release-rescue.js`） | 闯关元素 | 内容 |
| --- | --- | --- |
| `#mission-status` `2 / 4 个决策已完成 · 50 分` | `#quest-status` | `第 7 / 18 题 · 第 2 关「情境判断」· 已答对 5 题` |
| `#mission-progress`（`max=4`） | `#quest-run-progress`（`max=18`） | 本局已答题数 |
| `#mission-history`（每步选择 + 反馈） | `#quest-feedback` | 本题即时判定 + 解析（答错也显示正确项） |
| `#mission-scene-title`（`任务通过 · 发布守护者`） | `#quest-title` | 关卡名 / 终局标题 |
| `#mission-scenario`（`最终成绩 X / 100`） | `#quest-summary` | 总分、徽章、维度得分、错题回顾、建议水平 |
| `#mission-retry`（`再挑战一次 ↻`） | `#quest-retry` | 同上 |

**答案的即时对错与解析只在弹窗内展示，卡片只显示历史最佳。**

#### 展示点 3：路径完成后

```javascript
// workspace.js:188-191 改写为
} else if (pathComplete) {
    completionTarget = {type:"quest"};
    $("#completion-next-label").textContent =
        "用 18 道闯关题检验一下自己的起点。Level Quest · 约 5 分钟。";
    $("#completion-next").textContent = "开始水平闯关 →";
}
```

#### 后端数据源

`app/learning/service.py:219-228`：

```python
result["mission"] = {"title": ..., "description": ..., "best_score": best, "attempt": ...}
```

→ 改为 `result["quest"]`，其中 `len(MISSION["steps"])`(4) → `TOTAL_QUESTIONS`(18)，`best_score` 仍复用 `find_best_mission_score`。

### 8.1 `frontend/index.html`

1. 第 87 行 `aside.mission-card` → `aside.quest-card`：

```html
<aside class="quest-card">
  <span class="section-kicker">LEVEL QUEST / SELF-CHECK</span>
  <div class="quest-icon" aria-hidden="true">🎯</div>
  <h3>软件工程水平闯关</h3>
  <strong>18 题 · 3 关摸底</strong>
  <ol class="quest-levels" id="quest-levels"></ol>
  <progress id="quest-progress" max="18" value="0" aria-label="闯关进度"></progress>
  <small id="quest-best">尚未开始</small>
  <div class="quest-actions">
    <button class="button" id="quest-start">开始闯关 →</button>
    <button class="button button-ghost hidden" id="quest-quick">8 题速测 ⚡</button>
    <button class="button button-ghost hidden" id="quest-revenge">错题复仇 ⚔️</button>
  </div>
  <p class="supporting-copy">结果仅作为起点参考，不是能力评分；可随时重刷。</p>
</aside>
```

> `#quest-quick` / `#quest-revenge` 未登录时隐藏；复仇按钮仅在 `revenge_count > 0` 时显示。

2. 第 221 行 `#mission-modal` → `#quest-modal`（[v2] 增加 Boss 横幅、生命值、多题型确认按钮）：

```html
<div class="modal-backdrop hidden" id="quest-modal">
  <div class="modal quest-modal" role="dialog" aria-modal="true" aria-labelledby="quest-title">
    <button class="close-button" data-close-modal aria-label="关闭闯关">×</button>
    <span class="section-kicker">LEVEL QUEST</span>
    <p id="quest-status" aria-live="polite"></p>
    <div class="quest-hearts hidden" id="quest-hearts" aria-label="剩余机会"></div>
    <progress id="quest-run-progress" max="18" value="0" aria-label="本局进度"></progress>
    <div class="quest-boss hidden" id="quest-boss">⚔️ BOSS · 综合大题</div>
    <h2 id="quest-title"></h2>
    <p id="quest-topic"></p>
    <pre class="quest-snippet hidden" id="quest-snippet"></pre>
    <p id="quest-stem"></p>
    <div class="quest-choices" id="quest-choices"></div>
    <button class="button button-primary hidden" id="quest-confirm">确认提交 ✓</button>
    <div class="quest-feedback hidden" id="quest-feedback" aria-live="polite"></div>
    <button class="button button-primary hidden" id="quest-next">下一题 →</button>
    <div class="quest-summary hidden" id="quest-summary"></div>
    <button class="button button-primary hidden" id="quest-retry">再挑战一次 ↻</button>
    <button class="button button-ghost hidden" id="quest-to-path">查看推荐路径 →</button>
  </div>
</div>
```

3. 第 231 行脚本引用：`features/missions/release-rescue.js` → `features/quiz/level-quest.js`。

### 8.2 ⚠️ `app/infrastructure/web.py` 静态白名单（关键坑）

`SCRIPTS` 是**白名单**，且 `LEGACY_BUNDLES` 依赖**下标切片**：

```python
LEGACY_BUNDLES = {
    "app.js":       SCRIPTS[:6] + ("features/bootstrap.js",),
    "prototype.js": SCRIPTS[6:9],     # ← 下标 6,7,8
    "study.js":     SCRIPTS[9:11],    # ← 下标 9,10
}
```

**约束**：新脚本必须**原地替换下标 8**（`release-rescue.js` → `quiz/level-quest.js`），**不要在中间插入**，否则 `prototype.js` / `study.js` 两个旧版兼容包会错位。若确实需要新增文件，只能插在下标 11（bootstrap 之前）并同步核对切片。

### 8.3 新增 `frontend/features/quiz/level-quest.js`

结构对齐现有 `release-rescue.js`（同样是全局脚本 + `$` / `$$` / `escapeHTML` / `showToast` / `openModal` / `requireLogin`）：

**⚠️ 所有 [v2] 前端逻辑必须继续写在这一个文件里** —— `web.py::SCRIPTS` 的下标切片约束（§8.2）不允许新增脚本文件。

```javascript
let questRun = null;        // 当前局
let questPick = null;       // [v2] multi/order 题的本地选择状态
let questMode = "quest";    // [v2]

async function startQuest(mode = "quest") { ... }   // [v2] 支持 quick / revenge
function renderQuestion() { ... }                    // [v2] 按 kind 分派渲染
function renderSingle() / renderMulti() / renderOrder() { ... }   // [v2] B2
function renderBoss(question) { ... }                // [v2] B3
function renderHearts(run) { ... }                   // [v2] B6
function renderCombo(streak, correct) { ... }        // [v3] A1
function comfortFor(missStreak, isBoss) { ... }      // [v3] A2 共情前缀
async function submitChoice(choiceId) { ... }
function renderLevelResult(levelResult) { ... }
function renderSummary(result) { ... }
function renderQuestCard() { ... }                   // 供 workspace.js 调用
$("#quest-start").onclick   = () => startQuest("quest");
$("#quest-quick").onclick   = () => startQuest("quick");
$("#quest-revenge").onclick = () => startQuest("revenge");
$("#quest-confirm").onclick = submitPicked;          // [v2] multi / order 提交
$("#quest-next").onclick = ...;
$("#quest-retry").onclick = () => startQuest(questMode);
```

要点：

- 选项按钮点击后立即 `disabled`，防止重复提交（对齐现有实现）。
- 提交失败时恢复按钮并 `showToast(error.message)`（`ApiError` 已带中文错误）。
- 所有插入 DOM 的文本必须走 `escapeHTML()`（现有浏览器回归测试会验证 HTML 注入）。
- 关闭弹窗不丢进度（进度在服务端，题目由 `answers.codes` 冻结）。
- **[v2] `multi` / `order` 的交互**：
  - `multi`：点击选项切换选中态（`.picked`），不立即提交；点「确认提交」才发送 `choice_id = 选中 id 按选项顺序拼接`（如 `"a,c"`）。未选满时确认按钮禁用。
  - `order`：点击选项按顺序编号（①②③），再次点击可取消；点「确认提交」发送序列字符串。编号未满时禁用确认。
  - 两种题型提交后禁用全部交互，等待服务端反馈。
- **[v2] Boss 题**：`question.boss === true` 时显示 `#quest-boss` 横幅，弹窗加 `.is-boss` 类。
- **[v2] 生命值**：`run.hearts_enabled` 为真时显示 `#quest-hearts`（`♥` × `hearts` + `♡` 补足到 3）。

### 8.7 [v2] 卡片的三种模式入口

| 按钮 | 显示条件 | 文案 |
| --- | --- | --- |
| `#quest-start` | 总是显示 | `开始闯关 →` / `继续闯关 →` / `再挑战一次 ↗` |
| `#quest-quick` | 已登录 | `8 题速测 ⚡` |
| `#quest-revenge` | 已登录 **且** `quest.revenge_count > 0` | `错题复仇 ⚔️`；hover 提示「还有 N 道错题等你翻盘」 |

### 8.4 `frontend/features/learning/workspace.js`

| 行 | 现有 | 改动 |
| --- | --- | --- |
| 43 | `$("#mission-best").textContent = pathData.mission.best_score === null ? "尚无完成成绩" : \`历史最高 ... / 100\`` | → `$("#quest-best")`，改用 `pathData.quest`，文案见 §8.0 展示点 1 |
| 62 | `$("#mission-best").textContent = "尚未开始"`（未登录分支） | → `$("#quest-best")`，文案不变 |
| 189-191 | `completionTarget = {type:"mission"}` + 「把课程内容用于四个发布决策…」 | → `{type:"quest"}` + 「用 18 道闯关题检验一下自己的起点。Level Quest · 约 5 分钟。」 |
| 260 | 路径完成后自动 `startMission()` | → `startQuest()` |
| 338 | `completionTarget.type === "mission"` 分支 | → `=== "quest"` |
| 新增 | — | `renderPath()` 末尾调用 `refreshQuestCard()`，用于闯关结束后同步卡片 |
| 新增 | — | 学习画像卡（`#profile-overview`）追加「闯关参考」行 + 「采用」/「清空」按钮（FR-5） |

### 8.5 `frontend/api/client.js`

```javascript
// 追加到 Object.freeze({...}) 内
getQuizOverview: (options) => request("/api/quiz/overview", options),
startQuizRun:   (data, options) => json("POST", "/api/quiz/runs", data, options),   // [v2] 传 {mode}
getQuizRun:     (runId, options) => request(`/api/quiz/runs/${id(runId)}`, options),
answerQuiz:     (runId, data, options) => json("POST", `/api/quiz/runs/${id(runId)}/answer`, data, options),
abandonQuizRun: (runId, options) => send("POST", `/api/quiz/runs/${id(runId)}/abandon`, options),
getQuizResult:  (mode, options) => request(`/api/quiz/result?mode=${encodeURIComponent(mode || "quest")}`, options),
adoptQuizLevel: (options) => send("POST", "/api/quiz/profile/adopt", options),
clearQuizReference: (options) => send("DELETE", "/api/quiz/profile/reference", options),
```

> `client.js` 有 `tests/api.test.js` 单测（Node 18+，模拟请求，无需数据库），**必须同步补用例**。

### 8.6 样式

在 `frontend/styles/main.css`（已在 `PUBLIC_ASSETS` 白名单内，无需改 `web.py`）新增：

`.quest-card`、`.quest-levels`（含 `.locked` / `.cleared` / `.current`）、`.quest-choices`、`.quest-feedback`（`.correct` / `.wrong`）、`.quest-summary`、`.quest-badge`。

沿用现有 CSS 变量与设计语言（参考 `.mission-card` / `.path-card`）。

[v2] 追加：

- `.quest-actions`（卡片按钮组，纵向堆叠 + `gap`）
- `.quest-hearts`（`♥` / `♡`，`.is-hit` 变灰）
- `.quest-boss`（Boss 横幅，警示色边框 + 轻微脉冲动画）
- `.quest-modal.is-boss`（Boss 态弹窗描边）
- `.quest-snippet`（`<pre>` 代码块，等宽字体 + 浅底）
- `.quest-choices .choice-button.picked`（multi 选中态）
- `.quest-choices .choice-button .order-badge`（order 题的 ①②③ 角标）

[v3] 追加（A 档）：

- `.quest-combo`（连击徽标，`streak >= 2` 时显示，带轻微弹入动画）
- `.quest-combo.is-hot`（`streak >= 5` 时换色强调）
- `.quest-feedback .quest-comfort`（共情前缀行，弱化字号 + 斜体）
- `.quest-persona`（结果页人格标签卡，与徽章并列）

> 项目目前几乎没有动画基础（`main.css` 中仅 1 处 `@keyframes`），Boss 脉冲与连击弹入都用**极简** `@keyframes` 实现，不引入动画库。

---

## 9. Release Rescue 的处置策略

**采用「替换前端入口 + 保留后端」的两阶段方案**，避免破坏已有数据与已演示功能：

| 阶段 | 内容 |
| --- | --- |
| 阶段一（本次） | 前端卡片/弹窗/脚本/入口全部换成 Level Quest；后端 `app/missions/` 与 `MISSION` 常量**保留但不再有 UI 入口**；`mission_attempts` 中 `mission_id='release-rescue-v1'` 的历史数据**原样保留** |
| 阶段二（待定） | 团队确认无回归后，再决定是否删除 `app/missions/`、`MISSION` 与旧接口；删除前需同步更新 README、测试与 `docs/` |

原因：

- Release Rescue 是 Week 8 已验收演示项，直接删除会同时改动 `tests/` 中的 HTTP 契约与浏览器回归测试，风险集中；
- 两张表通过 `mission_id` 天然隔离，保留旧代码几乎零成本，且便于回滚。

---

## 10. 测试计划

| 类型 | 位置 | 内容 |
| --- | --- | --- |
| 配置/架构（无需 DB） | `tests/` | 题库完整性：**[v2] 30 题**、每关池子配额满足 `DRAW_QUOTA`、每题选项数 ≥ 2、`correct` 存在于选项、`code` 唯一、`version` 唯一且与 `lesson_exercise_results` 约定一致 |
| 配置/架构（无需 DB） | `tests/` | **[v2] 抽样与判定纯函数**：分层抽样题数与维度分布恒定；Boss 固定在第 18 题位；`single` / `multi` / `order` 三种判定；`valid_choice` 拒绝数量不符与重复 id |
| 流程（需 `TEST_DATABASE_URL`） | `tests/` | 闯关全流程：开始局 → 逐题作答 → 关卡结算 → 解锁 → 终局徽章；重复提交返回 409；越权访问他人 run 返回 404；断点续玩；锚点课程不出现在 `/api/courses` |
| 流程（需 `TEST_DATABASE_URL`） | `tests/` | **[v2]** 连续两局题目不重复（随机生效）；同局内断点续玩题目不变；quick / revenge 不写入 `best_score` 与画像；复仇池在答对后缩小 |
| 客户端 | `tests/api.test.js` | `node --test`，为 §8.5 的 8 个新函数补模拟请求用例（[v2] `startQuizRun` 改为带 `{mode}` 请求体） |
| 浏览器回归（可选） | `tests/test_frontend_browser.py` | `RUN_BROWSER_TESTS=1`；验证闯关弹窗渲染、HTML 注入转义 |

> 迁移幂等性：`005_quiz.sql` 全部使用 `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`，重复执行安全；但**必须在独立测试库的随机 schema 上验证**（现有测试约定），不得对共享库执行写测试。

### 10.1 现有测试中会被本次改动打破的两处（必须同步修改）

| 测试 | 断言 | 冲突 | 修复 |
| --- | --- | --- | --- |
| `tests/test_architecture.py:27` `test_existing_http_contract_is_preserved` | `actual == expected \| {("GET","/frontend/<path:filename>")}`，`actual` 取自 `url_map.iter_rules()` | 新增 `/api/quiz/*` 8 个路由后 `actual` 多出元素，断言失败 | **同步更新 `tests/fixtures/http_routes.json`**，把新路由全部追加 |
| `tests/test_flows.py:196` `test_seed_idempotent_and_account_cascade` | `SELECT COUNT(*) FROM prototype_courses == 3` | 若锚点课程写入 `prototype_courses` 则变 4 | 锚点课程**不写入**该表（见 §4.2），测试无需改动 |

### 10.2 其他受影响的测试点

| 测试 | 影响 | 处理 |
| --- | --- | --- |
| `tests/test_architecture.py:41` `test_frontend_assets_load_in_declared_order...` | 校验 `index.html` 中 `<script src>` 顺序与 `web.py::SCRIPTS` **完全一致**，且每个 URL 返回 200 | 原地替换下标 8 的脚本名即可；**不要改变顺序** |
| `tests/test_architecture.py:95` `test_business_routes_and_services_do_not_execute_sql` | 遍历 `("auth","courses","learning","tutor","missions")`，新域不在列表内 → 不报错但**无覆盖** | 把 `"quiz"` 加入元组；前提是 quiz 的 `routes.py`/`service.py` 不直接执行 SQL |
| `tests/test_flows.py:211-213` | 注销账号后 `mission_attempts` / `lesson_exercise_results` 计数必须为 0 | 两张表的 `user_id` 均为 `ON DELETE CASCADE`，闯关数据会随账号删除 → ✅ 天然通过 |
| `tests/test_flows.py:127-155` | Release Rescue 完整流程测试 | 保留后端接口 → ✅ 不受影响（这也是 §9 两阶段方案的理由） |
| `tests/api.test.js` | 客户端函数单测 | 需为 §8.5 的 8 个新函数补用例；[v2] `startQuizRun` 签名变为 `(data, options)`，用例需同步 |
| `tests/fixtures/http_routes.json` | HTTP 契约集合 | **[v2] 无需再改** —— 三种模式复用 `POST /api/quiz/runs` 的请求体 `mode`，**不新增路由** |

---

## 11. 后续扩展（本次不做）

1. ~~**题库扩容与随机抽题**~~ → **[v2 B1 已完成]**（30 题 / 每关 10 题池 / 分层抽样）。下一步可继续扩到 45 题（每关 15），进一步降低记忆效应。
2. **AI 出题**：`quiz_questions.source='ai'`，教师输入主题/要求 → 服务端调用已配置的 `TUTOR_*` 环境变量生成题目，落库前需教师确认；绝不把密钥下发前端（与现有 Tutor 约束一致）。
3. ~~**题库管理界面**~~ → **[v4 已完成]** 由**管理员**维护：增删改查 + 停用启用（`active`），见 §7.5。前置的 seed 覆盖豁免已一并完成。
4. **教师参与度面板**：按学生展示闯关次数、徽章、维度雷达、最近活跃时间。
5. **跨学科迷你课程生成**：`quiz_questions` 与 `courses` 解耦后，可复用到其他学科的自测闯关。
6. **[v3 已完成]** 连击 Combo、共情式错题反馈（复用 `explanations` 中已写好的错误项解析）、人格标签（与徽章并行，不替代）—— 见 §6.11–§6.13。**[v3+ 已完成]** 关卡地图解锁动画、AI 同伴吐槽、彩蛋文案 —— 见 §6.15。仍未纳入的：**音效**，纯展示层，不新增接口与字段，可随时追加。
7. **[C 档]** 自适应难度（答对升难度、答错降难度，题量 18 → 8）、AI 个性化结语并直通推荐路径、角色扮演式「发布日模拟器」。

---

## 12. 工作量拆分

| # | 任务 | 涉及文件 | 预估 |
| --- | --- | --- | --- |
| T1 | 迁移 + 种子 + 锚点课程 | `migrations/005_quiz.sql`、`migrations.py`、`seeds.py` | 0.5 天 |
| T2 | 题库内容编写（18 题 + 解析） | `app/quiz/content.py` | 1 天 |
| T3 | 后端三层 + 蓝图注册 + 课程过滤 | `app/quiz/*`、`factory.py`、`courses/repository.py`、`learning/service.py` | 1.5 天 |
| T4 | 前端卡片 / 弹窗 / 脚本 / 客户端 | `index.html`、`level-quest.js`、`workspace.js`、`client.js`、`main.css`、`web.py` | 1.5 天 |
| T5 | 画像参考联动 | `learning/paths.py`、`learning/service.py`、`account.js`（画像卡） | 0.5 天 |
| T6 | 测试与文档 | `tests/`、`docs/API_README.md`、`README.md` | 1 天 |
| **T7** | **[v2] 迁移 006 + 题库扩到 30 题** | `006_quiz_play.sql`、`app/quiz/content.py`、`seeds.py` | **1 天** |
| **T8** | **[v2] 抽题 + 多题型判定 + Boss** | `app/quiz/service.py`、`repository.py` | **1 天** |
| **T9** | **[v2] 速测 / 复仇两种模式** | `app/quiz/service.py`、`routes.py` | **0.5 天** |
| **T10** | **[v2] 前端多题型交互 + Boss + 生命值 + 复仇入口** | `index.html`、`level-quest.js`、`main.css`、`client.js` | **1 天** |
| **T11** | **[v2] 抽样/判定单测 + 文档** | `tests/`、`docs/` | **0.5 天** |
| **T12** | **[v3] 打散正确选项（30 题重排 + 自洽校验）** | `app/quiz/content.py` | **0.25 天** |
| **T13** | **[v3] 连击 + 共情反馈 + 人格标签** | `content.py`、`service.py`、`level-quest.js`、`main.css` | **0.75 天** |

v1 合计约 **6 人天**；v2（B 档）追加约 **4 人天**；**v3（A 档 + Q1）追加约 1 人天**（不含评审与联调）。

---

## 13. 风险与未决问题

| # | 风险 / 问题 | 应对 |
| --- | --- | --- |
| R1 | 复用 `lesson_exercise_results` 需要"锚点课程"这一折中设计，语义上不够干净 | 已评估备选：新增 `quiz_answers` 表。若评审认为锚点课程不可接受，改用备选（多 1 张表，代码量相当） |
| R2 | 锚点课程泄漏到课程目录 / 课时页 | 已在 §4.2 列出全部过滤点，并纳入 T6 的测试断言 |
| R3 | `web.py` 的 `SCRIPTS` 下标切片会因插入脚本错位 | §8.2 明确规定原地替换下标 8；T4 后必须验证 `/app.js` `/prototype.js` `/study.js` 三个兼容包仍可用 |
| R4 | 闯关结果被误读为"能力评分" | §3 FR-5 硬性约束措辞 + 不覆盖自报 + 可清空；T5 需在 UI 上显著标注 |
| R5 | 共享 Neon 库上执行迁移会影响队友 | 迁移为纯增量 `IF NOT EXISTS`；但 `init-db` 会写入题库与锚点课程，应由团队统一在低峰执行一次 |
| Q1 | ~~18 题是否足够？首版固定题目会有记忆效应~~ | **[v2 B1 已解决]**：题库扩到 30 题、每局分层抽样 |
| R6 | [v2] 随机抽题导致维度分布漂移，`topic_scores` 分母变化 | 用 `DRAW_QUOTA` **分层抽样**而非纯随机，抽后各维度题数与 v1 固定分布完全一致（§FR-7.2），分母恒定 |
| R7 | [v2] `multi` 题可能靠"全选"蒙对 | `valid_choice` 强制**数量必须等于正确答案数量**（§6.7），全选直接 `400` |
| R8 | [v2] 抽题结果若不持久化，断点续玩会错位 | 抽题结果写入 `answers.codes` 并冻结（§6.6）；无 `codes` 的旧局回退到排序取题 |
| R9 | [v2] quick / revenge 的分数污染 18 分制的历史最佳 | 两者使用**独立 `mission_id`**，`best_score` / 徽章 / 画像只查 `'level-quest-v1'`（§FR-7.1） |
| R10 | [v2] 生命值打击零基础学生 | 仅在 L3 启用，且经 §6.8 论证与关卡规则同步，**不产生任何额外失败** |
| Q2 | 徽章阈值（50/70/85）是否合理 | 待首轮内测后按实际分布校准 |
| Q3 | Release Rescue 是否最终删除 | 见 §9 阶段二，待团队确认 |

---

## 14. 验收标准

- [ ] 学生登录后在原 Release Rescue 位置看到 Level Quest 卡片，关卡状态正确（首次进入：L1 解锁、L2/L3 锁定）
- [ ] 完整走通一局 18 题，关卡解锁与徽章阈值行为与 §6 一致
- [ ] 中途关闭弹窗后重新进入，进度恢复且题目不重复
- [ ] 重复提交同一题返回 `409`；访问他人 run 返回 `404`
- [ ] 前端不提前获得 `correct_choice_id`（抓包验证 `GET/POST /api/quiz/runs` 响应体）
- [ ] `/api/courses` 与课程目录页不出现"软件工程水平闯关"
- [ ] 卡片上的历史成绩分母为 **18（题数）** 而非 100，且带徽章图标；未打完一局显示「尚无完成成绩」
- [ ] 闯关结果在 §8.0 列出的 4 个位置均正确展示
- [ ] `flask --app run migrate` 与 `init-db` 均可重复执行且不破坏既有 7 个账号 / 11 门课 / 14 条学习记录
- [ ] `pytest -q`（需 `TEST_DATABASE_URL`）与 `node --test tests/api.test.js` 全绿
- [ ] `/app.js`、`/prototype.js`、`/study.js` 三个旧版兼容包仍可正常加载

### 14.1 [v2] B 档追加验收

- [ ] 题库共 **30 题**；每关池子满足 `DRAW_QUOTA` 配额（L1 10 / L2 10 / L3 10）
- [ ] 连续开两局 `quest`，**抽到的题目不完全相同**（随机生效）；但每局维度分布恒为 concepts 5 / ai 5 / soft 4 / process 4
- [ ] 同一局中途关闭弹窗再进入，**题目顺序与之前完全一致**
- [ ] L3 第 6 题（全局第 18 题）恒为 Boss 题，前端显示 Boss 横幅
- [ ] `multi` 题：少选 / 全选均返回 `400`；正确集合（顺序不同）判定为对
- [ ] `order` 题：序列错误返回 `错`；数量不符返回 `400`
- [ ] L3 显示 `♥♥♥`，答错一题变 `♥♥♡`；L1 / L2 不显示生命值
- [ ] 生命值归零与关卡 `passed=false` **同时发生**，不会出现"还有心却已结束"或"没心了还能继续"
- [ ] `quick` 模式共 8 题，结束后 `best_score` / 徽章 / 画像**均无变化**
- [ ] 闯关答错若干题后，卡片出现「错题复仇」按钮且计数正确；复仇局答对后该计数下降
- [ ] 复仇池为空时 `{"mode":"revenge"}` 返回 `400` + 中文提示
- [ ] `tests/fixtures/http_routes.json` **无需修改**（未新增路由）
- [ ] 006 迁移可重复执行；已有 18 题的 `kind` 全部为 `single`，判定行为不变

### 14.2 [v3] A 档 + 题目质量追加验收

- [ ] **正确项分布**：27 道单选题的正确项为 `a` / `b` / `c` 各 9 道，**不存在"大部分是 A"**
- [ ] 30 道题的 `explanations` 与 `choices` 一一对应，且每个正确项解析以「正确。」开头 —— 打散后配对未错乱
- [ ] 重跑 seed 后正确项**不发生变化**（打散固化在题库内容里，非运行时随机）
- [ ] `multi` / `order` 题的正确项同样被打散，`order` 题答案不是 `a,b,c,d`
- [ ] 连续答对 3 题后显示 `🔥 连击 ×3`；答错后连击消失
- [ ] 连击**不加分**：连对 5 题后 `score` 仍等于答对题数，`best_score` 未异常增长
- [ ] 答错第 1 / 2 / 3 题时，解析前的共情前缀各不相同；Boss 题答错有专属话术
- [ ] 结果页同时展示**徽章**（按总分）与**人格标签**（按最高维度），二者可不同
- [ ] 人格标签不写入 `learning_profiles`，画像卡与「闯关参考」数值无变化
- [ ] A 档三项均未新增迁移、未新增路由（`http_routes.json` 仍无需修改）
