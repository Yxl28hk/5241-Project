"""Structured teacher-authored courses. Reads never initialize or seed tables."""
import json
from secrets import token_hex
from flask import jsonify, request, session
from psycopg.types.json import Jsonb
from app.infrastructure.storage import upload_folder

MODES = {'resource', 'video', 'guided', 'practice', 'blended'}
EXTENSIONS = {'pdf':'pdf','doc':'word','docx':'word','ppt':'ppt','pptx':'ppt','mp4':'video','mov':'video'}

def read_studio(db, course_id):
    if not db.execute("SELECT to_regclass('course_studio') AS name").fetchone()['name']:
        return None
    row = db.execute('SELECT content, revision FROM course_studio WHERE course_id=%s', (course_id,)).fetchone()
    return {**row['content'], 'revision':row['revision']} if row else None

def validate_content(raw, file_type=None):
    if not isinstance(raw, dict):
        raise ValueError('课程配置格式不正确')
    def field(key, maximum, required=False):
        value=raw.get(key,'')
        if not isinstance(value,str):raise ValueError(f'{key} 必须是文字')
        value=value.strip()
        if len(value)>maximum or (required and not value):raise ValueError(f'请填写有效的 {key}（最多 {maximum} 字）')
        return value
    mode=field('mode',20,True)
    if mode not in MODES:raise ValueError('请选择有效的课程模式')
    minutes=raw.get('minutes')
    if isinstance(minutes,bool) or not isinstance(minutes,int) or not 1<=minutes<=600:raise ValueError('预计时长应为 1–600 分钟')
    result={'mode':mode,'title':field('title',120,True),'description':field('description',1000,True),
            'audience':field('audience',300,True),'objectives':field('objectives',2000,True),
            'level':field('level',20,True),'category':field('category',20,True),'minutes':minutes,
            'example':field('example',6000),'task':field('task',4000),'checklist':field('checklist',2000),'reference':field('reference',4000),'source_notes':field('source_notes',6000)}
    if result['level'] not in {'beginner','intermediate','advanced'}:raise ValueError('请选择有效难度')
    if result['category'] not in {'技术','设计','商业','人文'}:raise ValueError('请选择有效分类')
    sections=raw.get('sections',[])
    if not isinstance(sections,list) or len(sections)>8:raise ValueError('正文最多 8 个小节')
    result['sections']=[]
    for section in sections:
        if not isinstance(section,dict):raise ValueError('小节格式不正确')
        title,body=section.get('title',''),section.get('body','')
        if not isinstance(title,str) or not isinstance(body,str) or not title.strip() or not body.strip() or len(title)>120 or len(body)>6000:raise ValueError('每个小节需要标题和正文，标题最多120字、正文最多6000字')
        result['sections'].append({'title':title.strip(),'body':body.strip()})
    if mode in {'guided','blended'} and not result['sections']:raise ValueError('分步讲解和混合课程至少需要一个正文小节')
    if mode=='practice' and (not result['task'] or not result['checklist']):raise ValueError('动手实践需要任务说明和完成标准')
    if mode in {'resource','video','blended'} and not file_type:raise ValueError('此模式需要上传课程附件')
    if mode=='video' and file_type!='video':raise ValueError('视频模式需要 MP4 或 MOV 文件')
    return result

def register_studio(app,get_db,teacher_required,managed_course,course_json):
    @app.get('/api/studio/courses/<int:course_id>')
    @teacher_required
    def editor_course(course_id):
        course=managed_course(course_id)
        if course is None:return jsonify(error='没有权限编辑此课程'),404
        db=get_db()
        if db.execute('SELECT course_id FROM prototype_courses WHERE course_id=%s',(course_id,)).fetchone():
            return jsonify(error='内置示范课由课程内容模块维护，请创建自己的课程'),409
        config=read_studio(db,course_id)
        return jsonify(course=course_json(course),content=config)

    @app.post('/api/studio/courses')
    @teacher_required
    def publish_course():return save(None)

    @app.patch('/api/studio/courses/<int:course_id>')
    @teacher_required
    def edit_course(course_id):return save(course_id)

    def save(course_id):
        UPLOAD_FOLDER=upload_folder()
        db=get_db();original=None
        if course_id is not None:
            original=managed_course(course_id)
            if original is None:return jsonify(error='没有权限编辑此课程'),404
            if db.execute('SELECT course_id FROM prototype_courses WHERE course_id=%s',(course_id,)).fetchone():return jsonify(error='内置示范课不能在此编辑'),409
        upload=request.files.get('file');stored=None
        try:
            text=request.form.get('content','')
            if len(text)>90000:raise ValueError('课程内容过长')
            raw=json.loads(text)
            extension=upload.filename.rsplit('.',1)[-1].lower() if upload and upload.filename else None
            if extension and extension not in EXTENSIONS:raise ValueError('附件格式不支持')
            resource_type=EXTENSIONS.get(extension) if extension else original['resource_type'] if original and original['filename'] else None
            content=validate_content(raw,resource_type)
            revision=raw.get('revision',0)
            if isinstance(revision,bool) or not isinstance(revision,int) or revision<0:raise ValueError('课程版本无效，请重新打开编辑器')
        except (ValueError,TypeError) as error:return jsonify(error=str(error)),400
        try:
            # Created transactionally only when a teacher explicitly publishes/saves.
            db.execute('''CREATE TABLE IF NOT EXISTS course_studio (
                course_id BIGINT PRIMARY KEY REFERENCES courses(id) ON DELETE CASCADE,
                content JSONB NOT NULL, revision INTEGER NOT NULL DEFAULT 1)''')
            if course_id is not None:
                db.execute('SELECT id FROM courses WHERE id=%s FOR UPDATE',(course_id,))
                current=read_studio(db,course_id)
                if revision!=(current['revision'] if current else 0):
                    db.rollback();return jsonify(error='课程已被其他窗口修改，请重新打开后编辑'),409
            if extension:
                stored=f'{token_hex(16)}.{extension}';upload.save(UPLOAD_FOLDER/stored)
            filename=stored or (original['filename'] if original else None)
            fields=(content['title'],content['category'],resource_type or 'text',content['description'],f"约 {content['minutes']} 分钟",filename)
            if course_id is None:
                author=db.execute('SELECT name FROM users WHERE id=%s',(session['user_id'],)).fetchone()['name']
                course_id=db.execute('''INSERT INTO courses (title,category,resource_type,description,duration,filename,author,owner_id,cover,badge)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'tech','新课程') RETURNING id''',(*fields,author,session['user_id'])).fetchone()['id']
            else:db.execute('UPDATE courses SET title=%s,category=%s,resource_type=%s,description=%s,duration=%s,filename=%s WHERE id=%s',(*fields,course_id))
            db.execute('''INSERT INTO course_studio (course_id,content) VALUES (%s,%s)
                ON CONFLICT(course_id) DO UPDATE SET content=EXCLUDED.content,revision=course_studio.revision+1''',(course_id,Jsonb(content)))
            db.commit()
        except Exception:
            db.rollback()
            if stored:(UPLOAD_FOLDER/stored).unlink(missing_ok=True)
            app.logger.exception('Course publish failed')
            return jsonify(error='保存失败，请稍后重试；若数据库账号无建表权限，请联系平台负责人初始化课程配置表'),500
        course=db.execute('SELECT * FROM courses WHERE id=%s',(course_id,)).fetchone()
        return jsonify(course=course_json(course),content=read_studio(db,course_id)),201 if original is None else 200
