"""Compatibility adapter for built-in learning content.

The canonical import path is ``app.models.content``. Keeping the definitions
here preserves the existing public module used by deployments and tests.
"""
MODULES = [
    {"slug": "git-pr", "title": "01 · Git 分支与 Pull Request", "duration": "5 分钟",
     "description": "从一个小需求出发，用分支、提交和代码评审协作。",
     "lesson": "团队要修复登录按钮。先从最新 main 创建 feature/login-fix 分支，用小而清晰的 commit 描述修改。推送分支后创建 Pull Request，写清问题、修改和测试证据。让同伴 review 并处理反馈后再合并。分支隔离未完成工作，PR 让变更可审查；Git 保存版本历史，GitHub 提供协作界面。",
     "question": "为什么不直接把未评审的修改推到 main？",
     "hint": "想一想：队友正在使用 main，谁来发现你的修改会影响登录？"},
    {"slug": "ci-testing", "title": "02 · 测试与 CI 质量关卡", "duration": "5 分钟",
     "description": "理解自动测试如何为合并和发布提供证据。",
     "lesson": "CI（持续集成）在提交或 PR 更新时自动运行检查。单元测试检查局部行为，集成测试验证组件协作。红色 CI 是调查信号：阅读失败日志、在本地复现、修复根因、重新运行。不要通过删除测试或忽略失败来获得绿灯。通过测试并不保证没有缺陷，仍需要 review 和发布后的监控。",
     "question": "如果 CI 失败但功能在你的电脑能运行，你会先做什么？",
     "hint": "先找出哪个测试失败、预期结果是什么，再比较本地与 CI 的环境。"},
    {"slug": "safe-release", "title": "03 · 安全发布与事故响应", "duration": "5 分钟",
     "description": "用监控、回滚和复盘完成一次可控的发布。",
     "lesson": "部署前确认 review、CI、环境变量和回滚方案。先在测试环境验证关键流程，发布后观察错误率和登录成功率。如果发布后大量用户无法登录，优先降低影响：按已验证的方案回滚或关闭问题功能，同时通知团队。保留日志，恢复服务后分析根因、补回归测试并复盘。回滚不代表修复已经完成。",
     "question": "发布后登录错误率突然升高，为什么通常先恢复服务再调查？",
     "hint": "比较持续影响真实用户的成本与暂时退回稳定版本的成本。"},
]

MISSION = {
    "id": "release-rescue-v1", "title": "Release Rescue · 拯救周五发布",
    "description": "你是学习平台值班工程师。修复登录缺陷、通过质量关卡，并处理上线事故。4 个决策，每步 25 分；75 分通过，可重新挑战。",
    "steps": [
        {"title": "09:00 · 一个登录缺陷", "scenario": "老师发现部分学生无法登录。你已经写好修复，现在如何交给团队？",
         "choices": [{"id": "pr", "text": "创建分支和 PR，附上测试证据，请同伴评审", "points": 25, "feedback": "正确。小范围分支和清晰 PR 让同伴检查修复与风险。"},
                     {"id": "main", "text": "直接推送 main，省去评审时间", "points": 0, "feedback": "速度有了，但未评审的改动可能影响所有人。先用分支和 PR 协作。"}]},
        {"title": "10:30 · CI 亮起红灯", "scenario": "PR 的登录回归测试失败，但你本地可以登录。下一步是什么？",
         "choices": [{"id": "skip", "text": "删除失败测试，让检查变绿", "points": 0, "feedback": "删除测试隐藏了信号。绿灯只有在真实检查通过时才有意义。"},
                     {"id": "investigate", "text": "查看日志、复现失败并修复后重新运行", "points": 25, "feedback": "正确。先理解失败证据，修复根因，再重新验证。"}]},
        {"title": "14:00 · 准备发布", "scenario": "评审完成，CI 已通过。你还需要做什么？",
         "choices": [{"id": "deploy", "text": "立即全量上线，不需要后续观察", "points": 0, "feedback": "测试通过不等于发布零风险。还需要环境检查、回滚准备和监控。"},
                     {"id": "prepare", "text": "测试环境验证登录，确认环境变量、回滚方案和监控", "points": 25, "feedback": "正确。验证关键用户流程，并准备在异常时快速恢复。"}]},
        {"title": "14:10 · 登录错误率升高", "scenario": "上线后错误率从 1% 升到 30%。已知上一版正常且有可用回滚方案。",
         "choices": [{"id": "rollback", "text": "回滚并通知团队，保留日志，恢复后补测试和复盘", "points": 25, "feedback": "正确。先恢复服务，再调查和预防复发；回滚只是止损。"},
                     {"id": "wait", "text": "让用户等一小时，在生产环境继续尝试修改", "points": 0, "feedback": "用户持续受影响。优先按已验证方案恢复服务，避免未经验证的生产修改。"}]},
    ],
}
