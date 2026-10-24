"""Built-in Level Quest content: fixed 18 questions across 3 levels and 4 topics.

Questions are deliberately broad software-engineering literacy rather than language
syntax, so that students without a computing background can attempt level 1 while
graduates still meet trade-off questions at level 3.
"""

MISSION_ID = "level-quest-v1"
MISSION_IDS = {
    "quest": "level-quest-v1",
    "quick": "level-quest-quick-v1",
    "revenge": "level-quest-revenge-v1",
}
QUEST_TITLE = "软件工程水平闯关"
QUEST_SUBTITLE = "LEVEL QUEST · 18 题摸底"
QUEST_DESCRIPTION = (
    "18 道题，3 个关卡。每关答对 4 题即可解锁下一关，结果仅作为起点参考，不是能力评分。"
)
ANCHOR_DESCRIPTION = "软件工程水平闯关的答题载体，不对外作为课程开放。"
ANCHOR_DURATION = "18 题"

QUESTIONS_PER_LEVEL = 6
LEVEL_COUNT = 3
TOTAL_QUESTIONS = QUESTIONS_PER_LEVEL * LEVEL_COUNT
UNLOCK_RATIO = 0.6
QUICK_TOTAL = 8
REVENGE_MAX = 6
# Nominal size per mode; used for "unfinished" / "finished" lookups.
MODE_TOTAL = {"quest": TOTAL_QUESTIONS, "quick": QUICK_TOTAL, "revenge": REVENGE_MAX}
HEARTS_PER_LEVEL = 3
HEART_LEVEL = 3  # Hearts only appear on the last level; see spec §6.8.

# Stratified sampling quota per level, so the topic mix stays identical to v1.
DRAW_QUOTA = {
    1: {"concepts": 2, "ai-assistant": 2, "soft-skills": 2},
    2: {"concepts": 2, "ai-assistant": 1, "soft-skills": 1, "process": 2},
    3: {"concepts": 1, "ai-assistant": 1, "soft-skills": 1, "process": 2},
}
QUICK_QUOTA = {
    1: {"concepts": 1, "ai-assistant": 1, "soft-skills": 1},
    2: {"concepts": 1, "ai-assistant": 1, "process": 1},
    3: {"ai-assistant": 1, "process": 1},
}

LEVELS_META = (
    {"level": 1, "name": "开发常识", "hint": "不需要专业背景，凭常识与基本逻辑判断"},
    {"level": 2, "name": "情境判断", "hint": "读一个小场景，选择更合适的做法"},
    {"level": 3, "name": "流程与权衡", "hint": "涉及协作、发布与取舍"},
)

TOPICS = ("concepts", "ai-assistant", "soft-skills", "process")
TOPIC_LABELS = {
    "concepts": "软件工程基础",
    "ai-assistant": "AI 编码助手",
    "soft-skills": "软技能与产品",
    "process": "流程与工程权衡",
}

# Ordered from highest threshold to lowest; the first match wins.
BADGES = (
    {"id": "gold", "icon": "\U0001F947", "ratio": 0.85, "label": "流程掌控者"},
    {"id": "silver", "icon": "\U0001F948", "ratio": 0.70, "label": "实践新秀"},
    {"id": "bronze", "icon": "\U0001F949", "ratio": 0.50, "label": "入门探索者"},
)

LEVEL_SUGGESTION = ((0.70, "experienced"), (0.40, "intermediate"), (0.0, "beginner"))

# [v3 A3] Fun title derived from the strongest dimension. Sits next to the badge
# and never feeds score, badge or profile.
ALL_ROUND_RATIO = 0.80
ALL_ROUND_PERSONA = {
    "id": "allround",
    "icon": "\U0001F31F",
    "topic": None,
    "label": "全能工程师",
    "note": "四个维度都在 80% 以上，基础很扎实，可以直接进项目实战。",
}
PERSONAS = (
    {"id": "commander", "icon": "\U0001F916", "topic": "ai-assistant", "label": "AI 指挥官",
     "note": "你最擅长判断 AI 的产出能不能用，而不是照单全收。"},
    {"id": "guardian", "icon": "\U0001F6E1️", "topic": "process", "label": "流程守护者",
     "note": "发布、协作、回滚这类流程题你答得最稳，适合当发布把关人。"},
    {"id": "analyst", "icon": "\U0001F9E9", "topic": "concepts", "label": "概念拆解者",
     "note": "基础概念你抓得最准，分得清「是什么」和「为什么」。"},
    {"id": "mediator", "icon": "\U0001F91D", "topic": "soft-skills", "label": "协作润滑剂",
     "note": "沟通与协作场景你判断得最好，这在团队里很稀缺。"},
)

QUESTION_BANK = (
    {
        "code": "concepts-l1-01",
        "level": 1,
        "topic": "concepts",
        "stem": "团队多人同时修改同一个文件时，为什么通常用版本控制工具，而不是互相发文件？",
        "choices": [
            {"id": "a", "text": "版本控制保留每次修改的记录，并帮助合并不同人的改动"},
            {"id": "b", "text": "因为使用版本控制可以让代码运行得更快"},
            {"id": "c", "text": "因为文件太大，网络传输不方便"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。版本控制的核心价值是可追溯、可回退，并能合并多人改动。",
            "b": "运行速度取决于实现和运行环境，与是否用版本控制无关。",
            "c": "传输便利只是附带好处；即使文件很小，多人协作仍需要历史与合并能力。",
        },
    },
    {
        "code": "concepts-l1-02",
        "level": 1,
        "topic": "concepts",
        "stem": "同伴说「给登录功能补几个测试」，测试最直接的作用是什么？",
        "choices": [
            {"id": "a", "text": "保证程序永远不会再出错"},
            {"id": "b", "text": "用可重复的方式验证功能在特定输入下的表现"},
            {"id": "c", "text": "让代码行数变多，方便统计工作量"},
        ],
        "correct": "b",
        "explanations": {
            "a": "测试只能覆盖写到的场景，不能保证零缺陷。",
            "b": "正确。测试把「预期行为」固定下来，任何人都能重复验证。",
            "c": "代码量不是目的，测试关注的是行为是否被验证。",
        },
    },
    {
        "code": "ai-assistant-l1-01",
        "level": 1,
        "topic": "ai-assistant",
        "stem": "AI 助手给了一段看起来能运行的代码，下一步最稳妥的做法是什么？",
        "choices": [
            {"id": "a", "text": "先读懂它，验证关键输入下的行为，再决定是否合入"},
            {"id": "b", "text": "直接合入，能运行就说明是对的"},
            {"id": "c", "text": "让 AI 再生成三版，选最短的一版"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。能运行不等于覆盖了边界情况，验证责任仍在使用者。",
            "b": "能跑通常见输入不代表边界、异常和并发场景都正确。",
            "c": "代码短不等于正确，比较标准应是行为是否符合需求。",
        },
    },
    {
        "code": "ai-assistant-l1-02",
        "level": 1,
        "topic": "ai-assistant",
        "stem": "AI 很自信地给了一段调用某个库函数的代码，但你从没听过这个函数，最可能是什么情况？",
        "choices": [
            {"id": "a", "text": "AI 不会出错，一定是你记错了"},
            {"id": "b", "text": "它可能编造了不存在的接口，应先查官方文档确认"},
            {"id": "c", "text": "说明本地版本太旧，直接升级依赖就好"},
        ],
        "correct": "b",
        "explanations": {
            "a": "生成式模型会出错，而且往往表现得很自信。",
            "b": "正确。模型会生成看似合理但不存在的接口，官方文档才是依据。",
            "c": "盲目升级依赖可能引入新问题，应先确认接口是否真实存在。",
        },
    },
    {
        "code": "soft-skills-l1-01",
        "level": 1,
        "topic": "soft-skills",
        "stem": "接到一个任务「优化一下登录页」，但你不清楚要优化什么，最合适的第一步是什么？",
        "choices": [
            {"id": "a", "text": "先问清目标和衡量方式，再动手"},
            {"id": "b", "text": "同时做几种方案，让对方自己挑"},
            {"id": "c", "text": "凭自己的理解直接改，做完再问"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。需求不清时先澄清，可以避免返工，也让结果可衡量。",
            "b": "并行做多套方案会放大成本，应先缩小目标范围。",
            "c": "先做再问容易造成返工，方向错了成本更高。",
        },
    },
    {
        "code": "soft-skills-l1-02",
        "level": 1,
        "topic": "soft-skills",
        "stem": "同伴在你的改动下面留言提问，最合适的回应是什么？",
        "choices": [
            {"id": "a", "text": "直接合并，避免讨论拖慢进度"},
            {"id": "b", "text": "坚持原样，因为功能已经能跑"},
            {"id": "c", "text": "当作改进机会，解释清楚或按反馈修改"},
        ],
        "correct": "c",
        "explanations": {
            "a": "未回应反馈就合并，会让评审失去意义。",
            "b": "能跑不等于没有隐患，评审意见值得逐条回应。",
            "c": "正确。评审的目的是在合入前发现风险，提问本身就是信号。",
        },
    },
    {
        "code": "concepts-l1-03",
        "level": 1,
        "topic": "concepts",
        "stem": "同事说「这个 bug 我本地复现不了」。这里的「复现」指的是什么？",
        "choices": [
            {"id": "a", "text": "把出问题的代码重新写一遍"},
            {"id": "b", "text": "重启电脑，直到问题再次出现"},
            {"id": "c", "text": "找到能让这个问题稳定出现的条件和步骤"},
        ],
        "correct": "c",
        "explanations": {
            "a": "重写可能碰巧掩盖问题，但不会告诉你原因，问题很可能换个形式再出现。",
            "b": "重启只是碰运气，没有缩小问题范围，也无法确认是否真的修好。",
            "c": "正确。复现是定位问题的前提：固定输入、环境和操作步骤，让问题稳定出现。",
        },
    },
    {
        "code": "concepts-l1-04",
        "level": 1,
        "topic": "concepts",
        "stem": "一个功能写了 800 行，后来想改其中一个小地方，却牵连到很多别的地方。这通常说明什么？",
        "choices": [
            {"id": "a", "text": "注释写得太少"},
            {"id": "b", "text": "电脑性能不够，跑不动这么多代码"},
            {"id": "c", "text": "这段代码承担了太多职责，改动的影响面太大"},
        ],
        "correct": "c",
        "explanations": {
            "a": "注释不足会影响理解，但不会造成改动牵连；牵连来自结构上的耦合。",
            "b": "性能与「改一处牵连一片」没有任何关系，后者是代码结构问题。",
            "c": "正确。职责混杂会造成高耦合，任何改动都难以局部化，这是需要拆分的信号。",
        },
    },
    {
        "code": "ai-assistant-l1-03",
        "level": 1,
        "topic": "ai-assistant",
        "stem": "你让 AI 助手帮忙，它一口气给了五段不同的写法。选择时最应该看什么？",
        "choices": [
            {"id": "a", "text": "选看起来最短的那个"},
            {"id": "b", "text": "哪种写法你能读懂、能验证，并且符合团队现有的约定"},
            {"id": "c", "text": "选语法最新的那个"},
        ],
        "correct": "b",
        "explanations": {
            "a": "短不等于清晰，过度压缩往往牺牲可读性。",
            "b": "正确。可维护性优先：能读懂、能验证、与团队一致，后续才改得动。",
            "c": "语法新不等于合适，团队的工具链和成员熟悉度都是约束。",
        },
    },
    {
        "code": "soft-skills-l1-03",
        "level": 1,
        "topic": "soft-skills",
        "stem": "你和同伴对一个做法有分歧，谁也说服不了谁。比较有效的做法是？",
        "choices": [
            {"id": "a", "text": "让职位更高的人直接拍板"},
            {"id": "b", "text": "把两种做法的代价和收益写下来，用一个具体场景来比较"},
            {"id": "c", "text": "各做各的，最后再合并"},
        ],
        "correct": "b",
        "explanations": {
            "a": "依赖权威能快速结束讨论，但不一定选到更合适的方案。",
            "b": "正确。把分歧转成可比较的事实，讨论往往就能收敛。",
            "c": "各做各的通常会导致返工和合并冲突，成本更高。",
        },
    },
    {
        "code": "concepts-l2-01",
        "level": 2,
        "topic": "concepts",
        "stem": "你要修复登录按钮，同时同伴正在 main 上开发别的功能。应该怎么做？",
        "choices": [
            {"id": "a", "text": "等同伴开发完再开始动手"},
            {"id": "b", "text": "从 main 新建一个分支做修复，再通过 PR 交给同伴评审"},
            {"id": "c", "text": "直接在 main 上改，改完通知大家"},
        ],
        "correct": "b",
        "explanations": {
            "a": "不必串行等待，分支协作正是为了并行开发。",
            "b": "正确。分支隔离未完成的工作，PR 让改动可审查、可回退。",
            "c": "直接改 main 会让所有人的工作受影响，且无法审查。",
        },
    },
    {
        "code": "concepts-l2-02",
        "level": 2,
        "topic": "concepts",
        "stem": "你本地能正常登录，但 CI 上一个「空密码应被拒绝」的测试失败了，先做什么？",
        "choices": [
            {"id": "a", "text": "忽略 CI，本地能跑就行"},
            {"id": "b", "text": "读失败日志，用相同条件在本地复现，确认输入与预期"},
            {"id": "c", "text": "删掉这条测试，让 CI 变绿"},
        ],
        "correct": "b",
        "explanations": {
            "a": "正常输入能登录，不代表空密码这类边界场景处理正确。",
            "b": "正确。先拿到可比较的证据，才能判断是实现、测试还是环境的问题。",
            "c": "删除测试只是掩盖信号，绿灯失去意义。",
        },
    },
    {
        "code": "ai-assistant-l2-01",
        "level": 2,
        "topic": "ai-assistant",
        "stem": "你让 AI 帮忙写了单元测试，运行后全部通过。能否认为功能已经验证完成？",
        "choices": [
            {"id": "a", "text": "不能，还要确认这些测试真的覆盖了关键场景，而不是空跑"},
            {"id": "b", "text": "可以，测试通过就说明验证完成"},
            {"id": "c", "text": "只要 AI 说覆盖全面就可以"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。测试可能断言过弱或根本没执行到关键路径，需要人检查。",
            "b": "通过率不等于覆盖率，未覆盖的场景仍有风险。",
            "c": "AI 的自我描述不能替代对测试内容的检查。",
        },
    },
    {
        "code": "soft-skills-l2-01",
        "level": 2,
        "topic": "soft-skills",
        "stem": "你原以为今天能完成的修复，实际上还需要三天。最合适的做法是什么？",
        "choices": [
            {"id": "a", "text": "等到截止日当天再说明情况"},
            {"id": "b", "text": "先不说话，尽量赶在截止前完成"},
            {"id": "c", "text": "尽早告知相关人，说明原因和新的预计时间"},
        ],
        "correct": "c",
        "explanations": {
            "a": "到截止日才说明，团队已没有调整空间。",
            "b": "隐瞒延迟会让依赖方无法调整，风险更大。",
            "c": "正确。风险越早暴露，团队越有机会调整安排。",
        },
    },
    {
        "code": "process-l2-01",
        "level": 2,
        "topic": "process",
        "stem": "代码评审和 CI 都通过了。发布之前还应该做什么？",
        "choices": [
            {"id": "a", "text": "直接全量上线，检查通过就够了"},
            {"id": "b", "text": "先只发给内部员工试用一个月"},
            {"id": "c", "text": "在测试环境验证关键流程，并确认回滚方案可用"},
        ],
        "correct": "c",
        "explanations": {
            "a": "CI 不覆盖生产环境的数据、配置和真实流量。",
            "b": "内部试用不能替代发布前的环境检查与回滚准备。",
            "c": "正确。自动化检查不等于生产可用，还需要验证关键流程和恢复手段。",
        },
    },
    {
        "code": "process-l2-02",
        "level": 2,
        "topic": "process",
        "stem": "上线后登录错误率从 1% 升到 30%，上一版正常且回滚方案已验证，优先做什么？",
        "choices": [
            {"id": "a", "text": "先观察一小时，等错误率自己恢复"},
            {"id": "b", "text": "按预案回滚并通知团队，保留日志后再调查根因"},
            {"id": "c", "text": "让用户等一等，在生产环境继续尝试修改"},
        ],
        "correct": "b",
        "explanations": {
            "a": "等待会让影响持续扩大，应先按预案止损。",
            "b": "正确。先降低对真实用户的影响，恢复后再调查与预防。",
            "c": "用户持续受影响，且未经验证的生产修改可能带来二次故障。",
        },
    },
    {
        "code": "concepts-l2-03",
        "level": 2,
        "topic": "concepts",
        "snippet": "$ git status\nOn branch main\nYour branch is ahead of 'origin/main' by 3 commits.",
        "stem": "看到上面这段输出，说明什么？",
        "choices": [
            {"id": "a", "text": "本地有 3 个提交还没推送到远程仓库"},
            {"id": "b", "text": "本地改动和远程冲突了，必须立刻回滚"},
            {"id": "c", "text": "远程仓库有 3 个提交本地还没拉取"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。ahead by 3 commits 表示本地领先远程 3 个提交，需要推送。",
            "b": "ahead 并不等于冲突，只是尚未推送；冲突是推送/拉取时才可能发生的。",
            "c": "那是 behind by N commits 的含义，方向正好相反。",
        },
    },
    {
        "code": "ai-assistant-l2-02",
        "level": 2,
        "topic": "ai-assistant",
        "stem": "AI 帮你写好了功能代码，但一行测试都没写。你觉得接下来最该补什么？",
        "choices": [
            {"id": "a", "text": "不用补，功能能跑就行"},
            {"id": "b", "text": "至少补上正常路径和一个边界情况的验证"},
            {"id": "c", "text": "让 AI 再写一份说明文档就够了"},
        ],
        "correct": "b",
        "explanations": {
            "a": "能跑只说明当前这一次没出错，不代表其它输入下也正确。",
            "b": "正确。至少覆盖典型输入和一个边界，后续改动才知道有没有破坏它。",
            "c": "文档帮助理解，但不能替代可执行的验证。",
        },
    },
    {
        "code": "soft-skills-l2-02",
        "level": 2,
        "topic": "soft-skills",
        "stem": "你在评审时看到一段看不懂的代码。比较合适的做法是？",
        "choices": [
            {"id": "a", "text": "默默通过，免得显得自己不懂"},
            {"id": "b", "text": "直接提问，并说明你尝试理解后卡在哪一步"},
            {"id": "c", "text": "直接改掉，换成自己看得懂的写法"},
        ],
        "correct": "b",
        "explanations": {
            "a": "看不懂就通过，风险被藏起来，最后一起在生产环境暴露。",
            "b": "正确。提问者读不懂本身就是质量信号；说清卡点能让作者有效回应。",
            "c": "没理解意图就重写，很可能改掉原本刻意保留的行为。",
        },
    },
    {
        "code": "process-l2-03",
        "level": 2,
        "topic": "process",
        "kind": "order",
        "stem": "「发现线上登录失败 → 恢复服务」，请按合理顺序排列下面这些动作（点选排序）。",
        "choices": [
            {"id": "a", "text": "通知团队与相关方"},
            {"id": "b", "text": "回滚到上一个正常版本"},
            {"id": "c", "text": "确认影响范围，并保留现场证据（日志、截图）"},
            {"id": "d", "text": "定位根因并补上回归测试"},
        ],
        "correct": "c,a,b,d",
        "explanations": {
            "a": "正确：让相关方知道正在处理，避免重复排查和无效上报。",
            "b": "回滚恢复服务，但它排在保留证据和通知之后：先止损，再恢复。",
            "c": "正确且应最先做：确认影响范围并保留证据，否则回滚后现场消失，无法定位。",
            "d": "正确且应最后做：服务恢复后再定位根因、补测试，防止复发。",
        },
    },
    {
        "code": "concepts-l3-01",
        "level": 3,
        "topic": "concepts",
        "stem": "为了赶上线，有一处实现明知不够优雅。比较合理的处理是什么？",
        "choices": [
            {"id": "a", "text": "记录为技术债，说明风险并安排后续重构"},
            {"id": "b", "text": "上线后就当没发生过"},
            {"id": "c", "text": "立刻重构，推迟上线时间"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。技术债需要被显式记录和排期，否则会无声累积。",
            "b": "不记录就会被遗忘，后续维护成本更高。",
            "c": "是否推迟取决于业务判断，但不应在发布前临时大改。",
        },
    },
    {
        "code": "ai-assistant-l3-01",
        "level": 3,
        "topic": "ai-assistant",
        "stem": "你想把一段含用户真实数据和公司内部代码的内容贴给外部 AI 助手求助，应该怎么做？",
        "choices": [
            {"id": "a", "text": "先脱敏，或改用团队批准的方式；不把敏感数据发给外部服务"},
            {"id": "b", "text": "直接贴，AI 不会保存这些数据"},
            {"id": "c", "text": "只贴代码不贴数据就没问题"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。外部服务的数据处理方式不受你控制，敏感信息必须先脱敏。",
            "b": "无法保证外部服务不留存或用于训练，不能依赖这个假设。",
            "c": "内部代码同样可能涉及商业机密和许可问题。",
        },
    },
    {
        "code": "ai-assistant-l3-02",
        "level": 3,
        "topic": "ai-assistant",
        "stem": "AI 建议「把失败的测试删掉就能合并」，你怎么判断这条建议？",
        "choices": [
            {"id": "a", "text": "让 AI 直接执行删除操作"},
            {"id": "b", "text": "采纳，AI 比人更懂这个项目"},
            {"id": "c", "text": "这是掩盖信号，应先调查失败原因，再按流程决定是否调整测试"},
        ],
        "correct": "c",
        "explanations": {
            "a": "把破坏性操作交给 AI 自动执行风险极高。",
            "b": "模型不了解项目上下文，也不承担后果。",
            "c": "正确。失败是信息，删除测试只会隐藏问题；确需调整也要走评审。",
        },
    },
    {
        "code": "soft-skills-l3-01",
        "level": 3,
        "topic": "soft-skills",
        "stem": "同时有三个需求：导致所有用户无法登录的缺陷、一处界面文案优化、一个内部工具改进。优先做哪个？",
        "choices": [
            {"id": "a", "text": "先修导致所有用户无法登录的缺陷"},
            {"id": "b", "text": "按需求提出的先后顺序做"},
            {"id": "c", "text": "先做最快的文案优化，快速看到成果"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。影响范围和严重程度是排序的主要依据。",
            "b": "提出顺序与紧急程度、影响范围没有必然关系。",
            "c": "先做容易的事会让高风险问题继续影响用户。",
        },
    },
    {
        "code": "process-l3-01",
        "level": 3,
        "topic": "process",
        "stem": "回滚之后服务恢复正常，接下来最重要的动作是什么？",
        "choices": [
            {"id": "a", "text": "立刻重新上线，继续原计划"},
            {"id": "b", "text": "关闭事故记录，等待用户反馈"},
            {"id": "c", "text": "调查根因、补上回归测试并做一次复盘"},
        ],
        "correct": "c",
        "explanations": {
            "a": "未定位根因就重新发布，很可能复现同样的问题。",
            "b": "不做复盘和补测试，同类事故会重复发生。",
            "c": "正确。回滚只是止损，根因未解决前重上线会再次故障。",
        },
    },
    {
        "code": "process-l3-02",
        "level": 3,
        "topic": "process",
        "stem": "判断一次发布是否成功，最可靠的依据是什么？",
        "choices": [
            {"id": "a", "text": "CI 通过就说明发布成功"},
            {"id": "b", "text": "页面能打开就说明发布成功"},
            {"id": "c", "text": "发布后把登录成功率、错误率等关键指标与基线对比"},
        ],
        "correct": "c",
        "explanations": {
            "a": "CI 只覆盖发布前的检查，不覆盖生产环境的真实条件。",
            "b": "页面能打开不代表所有功能正常，很多故障是部分失败。",
            "c": "正确。真实指标才能反映用户是否受影响。",
        },
    },
    {
        "code": "soft-skills-l3-02",
        "level": 3,
        "topic": "soft-skills",
        "stem": "项目只剩一天，你发现一个不影响主流程、但会让部分用户困惑的问题。更合适的处理是？",
        "choices": [
            {"id": "a", "text": "默默修掉，不告诉任何人"},
            {"id": "b", "text": "当作没看见，先上线再说"},
            {"id": "c", "text": "记录问题并告知相关人，由大家一起决定是修还是延后"},
        ],
        "correct": "c",
        "explanations": {
            "a": "不告知就改，其他人无法评估这次改动引入的风险。",
            "b": "不记录就会被遗忘，后续维护成本更高。",
            "c": "正确。临上线前的任何改动都需要被看见，风险应由团队共同评估。",
        },
    },
    {
        "code": "process-l3-03",
        "level": 3,
        "topic": "process",
        "stem": "团队想减少线上事故带来的影响。下列做法中，对「降低事故影响」最直接的是？",
        "choices": [
            {"id": "a", "text": "发布时灰度放量，并准备好经过验证的回滚方案"},
            {"id": "b", "text": "事故发生后写一份详细报告"},
            {"id": "c", "text": "要求每个人提交前自己多测几遍"},
        ],
        "correct": "a",
        "explanations": {
            "a": "正确。灰度与可回滚直接缩小了任何一次问题的影响范围和持续时间。",
            "b": "复盘能防止复发，但对本次事故的影响已经发生，属于事后手段。",
            "c": "人工测试有价值，但无法保证覆盖，也不能缩短事故发生后的影响时间。",
        },
    },
    {
        "code": "concepts-l3-02",
        "level": 3,
        "topic": "concepts",
        "kind": "multi",
        "snippet": "def login(username, password):\n    user = db.find(username)\n    if user and user.password == password:\n        return issue_token(user)\n    return None",
        "stem": "这段代码能正常登录，但存在哪些真实风险？（多选，选出所有你认为成立的）",
        "choices": [
            {"id": "a", "text": "没有区分「用户不存在」和「密码错误」，提示不够明确"},
            {"id": "b", "text": "没有对失败次数做任何限制，容易被反复尝试"},
            {"id": "c", "text": "已经用上了 token，所以认证环节一定是安全的"},
            {"id": "d", "text": "密码以明文方式比较和存储，泄露风险很高"},
        ],
        "correct": "b,d",
        "explanations": {
            "a": "不区分失败原因其实是常见的安全做法；过度提示反而会泄露账号是否存在。",
            "b": "正确。缺少限流会让暴力尝试变得可行。",
            "c": "token 解决的是会话状态问题，不代表认证环节本身安全。",
            "d": "正确。明文存储或比较密码是严重安全问题，应使用加盐哈希。",
        },
    },
    {
        "code": "ai-assistant-l3-03",
        "level": 3,
        "topic": "ai-assistant",
        "kind": "multi",
        "boss": True,
        "snippet": "你：帮我把这个登录接口改快一点\nAI：已优化，删掉了参数校验和日志，速度提升明显",
        "stem": "⚔️ BOSS · 综合大题：面对 AI 的这个「优化」，你会怎么处理？（多选，选出所有合适的做法）",
        "choices": [
            {"id": "a", "text": "直接合入，AI 说提升明显就足够可信了"},
            {"id": "b", "text": "先问清楚「变快」的衡量方式和目标值，再决定要不要优化"},
            {"id": "c", "text": "拒绝直接合入：删掉校验和日志会让问题无法被发现"},
            {"id": "d", "text": "要求保留关键校验与日志，并用可比较的方式验证是否真的变快"},
        ],
        "correct": "b,c,d",
        "explanations": {
            "a": "AI 的自述不能作为依据，而且「变快」未必是真实瓶颈所在。",
            "b": "正确。没有衡量标准的「优化」无法判断成败，可能是伪需求。",
            "c": "正确。校验和日志是发现问题的手段，不能为了速度砍掉。",
            "d": "正确。保留可观测性并用数据验证，才是可接受的优化方式。",
        },
    },
)


# The 18 questions of v1, in the exact order the fixed bank produced
# (ORDER BY level, code). Runs created before random draw existed have no
# frozen "codes" list, so this order is replayed for them.
V1_CODES = (
    "concepts-l1-01", "concepts-l1-02", "ai-assistant-l1-01", "ai-assistant-l1-02",
    "soft-skills-l1-01", "soft-skills-l1-02",
    "concepts-l2-01", "concepts-l2-02", "ai-assistant-l2-01", "soft-skills-l2-01",
    "process-l2-01", "process-l2-02",
    "concepts-l3-01", "ai-assistant-l3-01", "ai-assistant-l3-02", "soft-skills-l3-01",
    "process-l3-01", "process-l3-02",
)
# Must match the v1 query order "ORDER BY level, code": level first, then code.
_LEVEL_OF = {item["code"]: item["level"] for item in QUESTION_BANK}
LEGACY_CODES = tuple(sorted(V1_CODES, key=lambda code: (_LEVEL_OF.get(code, 99), code)))


def bank_version(code: str) -> str:
    """Stable question version written into lesson_exercise_results."""
    return f"quiz-{code}-v1"


def question_rows() -> list[dict]:
    """Seed rows in level order; used by the idempotent seeder."""
    rows = []
    for item in QUESTION_BANK:
        correct = item["correct"]
        explanations = item["explanations"]
        # multi / order answers are id sequences, so the summary explanation is
        # built from the per-option texts in the correct order.
        summary = explanations.get(correct) or " ".join(
            explanations[key] for key in correct.split(",") if key in explanations
        )
        rows.append(
            {
                "code": item["code"],
                "version": bank_version(item["code"]),
                "level": item["level"],
                "topic": item["topic"],
                "difficulty": item["level"],
                "stem": item["stem"],
                "snippet": item.get("snippet"),
                "kind": item.get("kind", "single"),
                "boss": item.get("boss", False),
                "choices": item["choices"],
                "correct_choice_id": item["correct"],
                "explanation": summary,
                "explanations": explanations,
                "source": "seed",
            }
        )
    return rows


def judge(question: dict, choice_id: str) -> bool:
    """Score one submission. Only *how* correctness is derived depends on kind."""
    kind = question.get("kind", "single")
    if kind == "single":
        return choice_id == question["correct_choice_id"]
    if kind == "multi":
        return set(choice_id.split(",")) == set(question["correct_choice_id"].split(","))
    if kind == "order":
        return choice_id == question["correct_choice_id"]
    return False


def valid_choice(question: dict, choice_id) -> bool:
    """Reject malformed submissions before scoring (multi cannot be gamed by selecting all)."""
    if not isinstance(choice_id, str) or not choice_id:
        return False
    ids = [choice["id"] for choice in question["choices"]]
    kind = question.get("kind", "single")
    if kind == "single":
        return choice_id in ids
    picked = choice_id.split(",")
    if len(set(picked)) != len(picked) or any(item not in ids for item in picked):
        return False
    if kind == "multi":
        return len(picked) == len(question["correct_choice_id"].split(","))
    if kind == "order":
        return len(picked) == len(ids)
    return False


def badge_for(score: int, total: int) -> dict | None:
    if not total:
        return None
    ratio = score / total
    for badge in BADGES:
        if ratio >= badge["ratio"]:
            return badge
    return None


def public_persona(persona: dict) -> dict:
    """Contract is {id, icon, label, note}; `topic` only selects the persona."""
    return {key: persona[key] for key in ("id", "icon", "label", "note")}


def persona_for(topic_scores: list[dict]) -> dict | None:
    """[v3 A3] Strongest dimension -> fun title. Pure display, never stored."""
    if not topic_scores:
        return None
    ratios = {
        score["topic"]: score["correct"] / score["total"]
        for score in topic_scores
        if score.get("total")
    }
    if not ratios:
        return None
    if len(ratios) == len(TOPICS) and min(ratios.values()) >= ALL_ROUND_RATIO:
        return public_persona(ALL_ROUND_PERSONA)
    best = max(ratios, key=lambda topic: (ratios[topic], topic))
    persona = next((item for item in PERSONAS if item["topic"] == best), None)
    return public_persona(persona) if persona else None


def suggested_level(score: int, total: int) -> str:
    ratio = score / total if total else 0
    for threshold, level in LEVEL_SUGGESTION:
        if ratio >= threshold:
            return level
    return "beginner"
