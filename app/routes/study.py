"""Practice, notes and recent tutor sessions, always scoped to the signed-in account."""

import hashlib
import json
from uuid import UUID, uuid4

from flask import jsonify, request, session
from psycopg.types.json import Jsonb

from app.models.content import MODULES
from app.models.learner import read_profile
from app.models.study import EXERCISES, focus_context, notebook, open_conversation, public_conversation
from app.models.tutor import TutorUnavailable, guided_answer, model_answer, tutor_mode


def course_context(db, user_id, course_id):
    row = db.execute("""SELECT c.id,c.title,c.description,p.slug,COALESCE(l.progress,0) AS progress
        FROM courses c LEFT JOIN prototype_courses p ON p.course_id=c.id
        LEFT JOIN learning_records l ON l.course_id=c.id AND l.user_id=%s WHERE c.id=%s""", (user_id,course_id)).fetchone()
    module = next((m for m in MODULES if row and m["slug"] == row["slug"]), None)
    if row and module:
        row = {**row, "title":module["title"]}
    return row, module


def exercise_result(row, exercise):
    return {"choice_id":row["choice_id"], "correct":row["correct"], "attempts":row["attempts"],
            "explanation":exercise["explanations"][row["choice_id"]], "correct_choice_id":exercise["correct"],
            "updated_at":row["updated_at"]} if row else None


def register_study(app, get_db, login_required):
    @app.get("/api/courses/<int:course_id>/exercise")
    @login_required
    def read_exercise(course_id):
        db = get_db()
        course, module = course_context(db, session["user_id"], course_id)
        if not course:
            return jsonify(error="课程不存在或已下架"),404
        exercise = EXERCISES.get(module["slug"]) if module else None
        if not exercise:
            return jsonify(exercise=None, result=None)
        row = db.execute("""SELECT * FROM lesson_exercise_results WHERE user_id=%s AND course_id=%s AND question_version=%s""",
                         (session["user_id"],course_id,exercise["version"])).fetchone()
        return jsonify(exercise={k:exercise[k] for k in ("version","question","choices")}, result=exercise_result(row,exercise))

    @app.post("/api/courses/<int:course_id>/exercise")
    @login_required
    def submit_exercise(course_id):
        db = get_db()
        course,module = course_context(db,session["user_id"],course_id)
        if not course:
            return jsonify(error="课程不存在或已下架"),404
        exercise = EXERCISES.get(module["slug"]) if module else None
        if not exercise:
            return jsonify(error="本课暂未配置固定练习"),404
        data = request.get_json(silent=True)
        if not isinstance(data,dict) or data.get("version") != exercise["version"] or not isinstance(data.get("choice_id"),str) or not any(c["id"] == data["choice_id"] for c in exercise["choices"]):
            return jsonify(error="请选择有效选项；题目更新后请重新打开课时"),400
        row = db.execute("""INSERT INTO lesson_exercise_results (user_id,course_id,question_version,choice_id,correct)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(user_id,course_id,question_version) DO UPDATE
            SET choice_id=EXCLUDED.choice_id,correct=EXCLUDED.correct,attempts=lesson_exercise_results.attempts+1,
            updated_at=CURRENT_TIMESTAMP RETURNING *""", (session["user_id"],course_id,exercise["version"],data["choice_id"],data["choice_id"]==exercise["correct"])).fetchone()
        db.commit()
        return jsonify(result=exercise_result(row,exercise))

    @app.get("/api/courses/<int:course_id>/notebook")
    @login_required
    def read_notebook(course_id):
        if not course_context(get_db(),session["user_id"],course_id)[0]:
            return jsonify(error="课程不存在或已下架"),404
        return jsonify(notebook=notebook(get_db(),session["user_id"],course_id))

    @app.patch("/api/courses/<int:course_id>/notebook")
    @login_required
    def save_notebook(course_id):
        data = request.get_json(silent=True)
        if not isinstance(data,dict) or set(data)-{"notes","task_draft","revision"} or type(data.get("revision")) is not int or data["revision"] < 0:
            return jsonify(error="笔记版本无效，请重新载入后重试"),400
        if not any(key in data for key in ("notes","task_draft")) or any(key in data and (not isinstance(data[key],str) or len(data[key])>limit) for key,limit in (("notes",12000),("task_draft",4000))):
            return jsonify(error="笔记最多 12000 字，任务草稿最多 4000 字"),400
        db = get_db()
        if not course_context(db,session["user_id"],course_id)[0]:
            return jsonify(error="课程不存在或已下架"),404
        current = notebook(db,session["user_id"],course_id)
        if current["revision"] != data["revision"]:
            return jsonify(error="笔记已在其他窗口更新。请先复制本地内容，再重新载入账号版本。"),409
        notes = data.get("notes",current["notes"])
        draft = data.get("task_draft",current["task_draft"])
        row = None
        if data["revision"] == 0:
            row = db.execute("""INSERT INTO lesson_notebooks (user_id,course_id,notes,task_draft)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING *""", (session["user_id"],course_id,notes,draft)).fetchone()
        if row is None:
            row = db.execute("""UPDATE lesson_notebooks SET notes=%s,task_draft=%s,revision=revision+1,updated_at=CURRENT_TIMESTAMP
                WHERE user_id=%s AND course_id=%s AND revision=%s RETURNING *""", (notes,draft,session["user_id"],course_id,data["revision"])).fetchone()
        if row is None:
            db.rollback()
            return jsonify(error="笔记已在其他窗口更新。请先复制本地内容，再重新载入账号版本。"),409
        db.commit()
        return jsonify(notebook=notebook(db,session["user_id"],course_id))

    @app.post("/api/courses/<int:course_id>/conversation")
    @login_required
    def restore_conversation(course_id):
        db = get_db()
        if not course_context(db,session["user_id"],course_id)[0]:
            return jsonify(error="课程不存在或已下架"),404
        row = open_conversation(db,session["user_id"],course_id)
        db.commit()
        return jsonify(conversation=public_conversation(row))

    @app.delete("/api/courses/<int:course_id>/conversation")
    @login_required
    def new_conversation(course_id):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or not isinstance(data.get("token"),str) or type(data.get("revision")) is not int:
            return jsonify(error="会话版本无效，请恢复会话后重试"),400
        db=get_db()
        row=db.execute("""UPDATE lesson_conversations SET token=%s,revision=0,messages='[]',last_request_id=NULL,
            last_fingerprint=NULL,last_reply=NULL,updated_at=CURRENT_TIMESTAMP
            WHERE user_id=%s AND course_id=%s AND token=%s AND revision=%s RETURNING *""",
                       (uuid4().hex,session["user_id"],course_id,data["token"],data["revision"])).fetchone()
        if not row:
            db.rollback()
            return jsonify(error="会话已改变，请先恢复最新会话"),409
        db.commit()
        return jsonify(conversation=public_conversation(row))


def tutor_reply(app,get_db,data,course,module,user_id):
    db=get_db()
    key=data.get("context_key","overview")
    action=data.get("action","answer")
    if not isinstance(key,str) or len(key)>40 or not isinstance(action,str) or action not in {"answer","hint","reference"}:
        return jsonify(error="提问范围或操作无效"),400
    focus=focus_context(module,course,key)
    if not focus:
        return jsonify(error="所选段落不存在，请重新选择"),400
    if action in {"hint","reference"} and (not module or key not in {"task","exercise"}):
        return jsonify(error="请先选择本节任务或练习"),400
    if action == "hint" and (type(data.get("hint_step")) is not int or data["hint_step"] not in {1,2}):
        return jsonify(error="提示分为第 1 步和第 2 步"),400
    persisted="token" in data
    history=data.get("history",[])
    fingerprint=hashlib.sha256(json.dumps({k:data.get(k) for k in ("message","context_key","action","hint_step","mode")},sort_keys=True).encode()).hexdigest()
    conversation=None
    if persisted:
        if not isinstance(data["token"],str) or type(data.get("revision")) is not int or data["revision"] < 0:
            return jsonify(error="请先恢复课时会话"),400
        try:
            request_id=str(UUID(data.get("request_id","")))
        except (ValueError,TypeError,AttributeError):
            return jsonify(error="请求标识无效，请重试"),400
        conversation=db.execute("SELECT * FROM lesson_conversations WHERE user_id=%s AND course_id=%s AND token=%s", (user_id,course["id"],data["token"])).fetchone()
        if not conversation:
            return jsonify(error="会话已重置，请恢复最新会话后再提问"),409
        if conversation["last_request_id"] == request_id:
            if conversation["last_fingerprint"] != fingerprint:
                return jsonify(error="同一请求标识不能用于不同问题"),409
            return jsonify(**conversation["last_reply"],conversation=public_conversation(conversation))
        if conversation["revision"] != data["revision"]:
            return jsonify(error="会话已在其他窗口更新，请恢复最新会话"),409
        history=[{"role":m["role"],"content":m["content"][:3000]} for m in conversation["messages"][-10:]]
    profile=read_profile(db,user_id)
    db.commit()  # Do not hold a transaction across an external model call.
    mode="guided-demo" if data.get("mode") == "guided-demo" else tutor_mode(app)
    if action == "hint":
        group="quiz_hints" if key == "exercise" else "task_hints"
        answer=f"第 {data['hint_step']} 步提示："+EXERCISES[module["slug"]][group][data["hint_step"]-1]
        mode="guided-demo"
        label="预设分步提示"
    elif action == "reference":
        answer=(EXERCISES[module["slug"]]["explanations"][EXERCISES[module["slug"]]["correct"]] if key == "exercise" else module["guide"]["task"]["reference"])
        mode="guided-demo"
        label="参考解析"
    else:
        if mode == "live":
            try:
                answer=model_answer(app,module,{**course,"focus":focus},data["message"].strip(),history,profile)
            except TutorUnavailable as error:
                return jsonify(error=str(error),retryable=True),502
        elif key == "overview":
            answer=guided_answer(module,course,data["message"].strip(),history)
        else:
            answer="当前选段："+focus["title"]+"\n\n"+focus["text"]+"\n\n思考提示："+module["hint"]+"\n\n这是针对所选内容的预设知识卡。"
        label="AI 学习助手" if mode == "live" else "课时知识卡 · 规则式助手（非大模型）"
    result={"mode":mode,"label":label,"answer":answer,"context":{"title":course["title"],"progress":course["progress"],"key":key,"focus_title":focus["title"]}}
    if persisted:
        messages=[*conversation["messages"],{"role":"user","content":data["message"].strip(),"context_key":key},
                  {"role":"assistant","content":answer,"label":label,"mode":mode,"context_key":key,
                   "action":action,"hint_step":data.get("hint_step"),"focus_title":focus["title"]}][-40:]
        row=db.execute("""UPDATE lesson_conversations SET messages=%s,revision=revision+1,last_request_id=%s,
            last_fingerprint=%s,last_reply=%s,updated_at=CURRENT_TIMESTAMP
            WHERE user_id=%s AND course_id=%s AND token=%s AND revision=%s RETURNING *""",
                       (Jsonb(messages),request_id,fingerprint,Jsonb(result),user_id,course["id"],data["token"],data["revision"])).fetchone()
        if not row:
            db.rollback()
            return jsonify(error="会话已更新或重置，本次回答未写入，请恢复最新会话"),409
        db.commit()
        result["conversation"]=public_conversation(row)
    return jsonify(result)
