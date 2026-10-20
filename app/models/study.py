"""Fixed practice content and account-scoped study persistence."""

from uuid import uuid4

EXERCISES = {
    "git-pr": {
        "version": "git-pr-v1", "question": "你只验证了手机端按钮可以点击，哪份 PR 说明最适合交给同伴？",
        "choices": [{"id":"evidence", "text":"说明布局改动、手机端验证结果，并列出桌面端和验证码待检查。"},
                    {"id":"claim", "text":"为了方便评审，写“所有登录场景全部通过”。"},
                    {"id":"direct", "text":"修复很小，直接推到 main，不需要说明。"}],
        "correct": "evidence",
        "explanations": {"evidence":"正确。把已验证与待验证的范围写清，评审者才能判断风险和补充检查。",
                         "claim":"尚未做过的检查不能写成通过。应写明手机端验证结果，列出待补查项。",
                         "direct":"小修复也可能影响协作。应按团队流程创建分支和 PR，附上验证证据。"},
        "task_hints": ["先把“已观察到的故障”和“你实际修改的范围”分开列出，不急着写结论。",
                       "按“问题、修改、已验证、待验证”四项组织说明：手机端点击已查，桌面和验证码交给同伴补查。"],
        "quiz_hints": ["先找出哪个选项区分了真实证据和还没做过的检查。", "没有验证的内容不能声称通过，也不能因为修复小就跳过团队流程。"],
    },
    "ci-testing": {
        "version": "ci-testing-v1", "question": "本地正常登录，但 CI 的空密码测试失败，你首先应该怎么做？",
        "choices": [{"id":"remove", "text":"删掉失败测试，避免影响合并。"},
                    {"id":"reproduce", "text":"阅读失败输入、预期和实际输出，使用相同条件复现。"},
                    {"id":"ignore", "text":"本地能登录就足够，忽略 CI。"}],
        "correct": "reproduce",
        "explanations": {"reproduce":"正确。先复现同一失败场景，才能定位实现、测试或环境之间的差异。",
                         "remove":"删除测试会掩盖信号。先调查失败，确认测试与需求是否一致。",
                         "ignore":"正常输入能登录不代表空密码处理正确，应以失败场景的输入和输出为依据调查。"},
        "task_hints": ["先写下日志里的输入、预期结果和实际结果，确认自己调查的是空密码场景。",
                       "依次考虑：本地同条件复现、检查校验与环境差异、修复后重新执行相关和完整检查。只记录实际运行的结果。"],
        "quiz_hints": ["正常登录和空密码是不同场景，想想哪一步可以获得同条件的证据。", "保留有效测试，从失败输入和预期输出开始复现，再判断根因。"],
    },
    "safe-release": {
        "version": "safe-release-v1", "question": "发布后登录错误率显著升高，上一版可用且回滚方案已验证、数据兼容，优先做什么？",
        "choices": [{"id":"wait", "text":"让用户继续等待，在生产环境反复尝试修改。"},
                    {"id":"done", "text":"CI 已通过，所以不需要处理。"},
                    {"id":"recover", "text":"按预案恢复服务并通知团队，保留日志，恢复后继续调查。"}],
        "correct": "recover",
        "explanations": {"recover":"正确。在给定前提下先降低用户影响；恢复后仍需调查、补测试与复盘。",
                         "wait":"用户持续受影响时，应优先依据已验证预案降低影响，而不是尝试未经验证的生产修改。",
                         "done":"CI 不覆盖所有生产条件，仍需要观察真实指标并处理异常。"},
        "task_hints": ["先把清单分成“发布前、发布后、异常时”三栏，每栏写可执行的动作。",
                       "发布前看关键流程和恢复准备，发布后看具体指标；异常时写清恢复条件，别遗漏通知、日志和后续调查。"],
        "quiz_hints": ["先判断哪个动作能降低真实用户受到的影响，同时保留调查证据。", "题目已给出可回滚且兼容的前提；恢复不是调查结束，仍需通知、留日志和补测试。"],
    },
}


def initialize_study(db):
    db.execute("""CREATE TABLE IF NOT EXISTS lesson_notebooks (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        notes TEXT NOT NULL DEFAULT '', task_draft TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, course_id))""")
    db.execute("""CREATE TABLE IF NOT EXISTS lesson_exercise_results (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE, question_version TEXT NOT NULL,
        choice_id TEXT NOT NULL, correct BOOLEAN NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, course_id, question_version))""")
    db.execute("""CREATE TABLE IF NOT EXISTS lesson_conversations (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        token TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, messages JSONB NOT NULL DEFAULT '[]',
        last_request_id TEXT, last_fingerprint TEXT, last_reply JSONB,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, course_id))""")


def notebook(db, user_id, course_id):
    row = db.execute("SELECT notes, task_draft, revision, updated_at FROM lesson_notebooks WHERE user_id=%s AND course_id=%s",
                     (user_id, course_id)).fetchone()
    return dict(row) if row else {"notes":"", "task_draft":"", "revision":0, "updated_at":None}


def public_conversation(row):
    return {"token":row["token"], "revision":row["revision"], "messages":row["messages"], "updated_at":row["updated_at"]}


def open_conversation(db, user_id, course_id):
    db.execute("""INSERT INTO lesson_conversations (user_id, course_id, token) VALUES (%s,%s,%s)
        ON CONFLICT(user_id,course_id) DO NOTHING""", (user_id, course_id, uuid4().hex))
    return db.execute("SELECT * FROM lesson_conversations WHERE user_id=%s AND course_id=%s", (user_id, course_id)).fetchone()


def focus_context(module, course, key):
    if key == "overview":
        return {"key":key, "title":"整节课", "text":module["lesson"] if module else course["description"]}
    if not module:
        return None
    guide = module["guide"]
    if key.startswith("section-") and key[8:].isdigit():
        index = int(key[8:])
        if index < len(guide["sections"]):
            section = guide["sections"][index]
            return {"key":key, "title":section["title"], "text":section["body"]}
    if key == "example":
        example = guide["example"]
        return {"key":key, "title":example["title"], "text":example["code"] + "\n" + example["note"]}
    if key == "task":
        return {"key":key, "title":guide["task"]["title"], "text":guide["task"]["instruction"]}
    if key == "exercise":
        question = EXERCISES[module["slug"]]
        return {"key":key, "title":"本节固定练习", "text":question["question"] + "\n" + "\n".join(c["text"] for c in question["choices"])}
    return None
