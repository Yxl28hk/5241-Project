"""Read only the published course and its server-owned attachment for tutoring."""
from pathlib import Path

from app.studio.authoring import read_studio
from app.studio.course_ai import CourseAIError, parse_file
from app.infrastructure.storage import read_upload


def course_materials(app, db, course, module):
    sources = []
    warnings = []
    if module:
        sources.append({"source": "内置课文", "text": module["lesson"]})
    else:
        content = course.get("studio") if "studio" in course else read_studio(db, course["id"])
        content = content or {}
        for index, section in enumerate(content.get("sections", []), 1):
            sources.append({"source": f"课程第{index}节 {section['title']}", "text": section["body"]})
        for key, label in (("objectives", "学习目标"), ("example", "课程示例"), ("task", "课程任务"), ("checklist", "完成标准")):
            if content.get(key):
                sources.append({"source": label, "text": content[key]})
    filename = course.get("filename")
    if filename:
        root = Path(app.config["UPLOAD_FOLDER"]).resolve()
        path = (root / filename).resolve()
        if path.parent != root:
            warnings.append("附件路径无效，未读取附件。")
        elif path.suffix.lower() not in {".pdf", ".pptx"}:
            warnings.append("此附件格式暂不支持答疑读取，仅使用已发布课程正文和简介。")
        else:
            try:
                if app.config.get("UPLOAD_STORAGE") == "database":
                    blob = read_upload(filename)
                else:
                    with path.open("rb") as handle:
                        blob = handle.read(20 * 1024 * 1024 + 1)
                extracted = parse_file(blob, path.suffix.lower()[1:])
                for page in extracted["pages"]:
                    if page["text"]:
                        sources.append({"source": f"课件第{page['page']}页", "text": page["text"]})
                warnings.extend(extracted["warnings"])
            except (OSError, ValueError, CourseAIError) as error:
                warnings.append(str(error) if isinstance(error, CourseAIError) else "课程附件无法读取，请联系教师检查文件。")
    if not sources:
        warnings.append("未取得课程正文或课件文字，本次仅依据课程简介；无法回答资料细节。")
    return {"sources": sources, "warnings": warnings, "description": course["description"]}


def published_fallback(course, focus, action="answer", hint_step=1):
    """An explicitly non-generative fallback using only teacher-published text."""
    content = course.get("studio") or {}
    if action == "hint":
        text = content.get("task", "") if hint_step == 1 else content.get("checklist", "")
        text = text or "教师尚未填写完成标准，请结合任务要求向教师确认。"
        return ("先检查任务要求：" if hint_step == 1 else "再对照完成标准：") + "\n" + text + "\n\n以上为课程原文提示，未调用 AI。"
    if focus["key"] != "overview":
        return "课程原文 · " + focus["title"] + "\n\n" + focus["text"] + "\n\n这是已发布原文，不是 AI 解释；可稍后重试 AI 或向教师提问。"
    parts = [course["description"]]
    if content.get("objectives"):
        parts.append("学习目标：\n" + content["objectives"])
    for section in content.get("sections", []):
        parts.append(section["title"] + "\n" + section["body"])
    text = "\n\n".join(parts)
    if len(text) > 7000:
        text = text[:7000] + "\n（原文较长，此处仅展示前段，请返回课程查看全文。）"
    return "已发布课程原文\n\n" + text + "\n\n备用模式未调用 AI，也未重新读取附件；附件请通过课程资源打开。"
