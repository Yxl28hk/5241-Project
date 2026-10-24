"""Session-scoped async AI generation. No automatic publish or database writes."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import hmac
import os
from secrets import token_urlsafe
from threading import Lock
from time import time
from urllib.parse import urlparse
from uuid import uuid4
from flask import jsonify, request, session
from app.studio.course_ai import ai_settings, parse_file, request_course, CourseAIError


def register_studio_ai(app,get_db):
    JOBS={};RATE=[];LOCK=Lock();EXECUTOR=ThreadPoolExecutor(max_workers=2)
    def owner():
        if request.args.get('preview')=='1':
            local=(request.remote_addr in {'127.0.0.1','::1'} and request.host.split(':')[0] in {'127.0.0.1','localhost'})
            if local and os.environ.get('STUDIO_AI_LOCAL_PREVIEW')=='1':
                if 'studio_preview_id' not in session:session['studio_preview_id']=token_urlsafe(20)
                return 'local:'+session['studio_preview_id']
            return None
        if not session.get('user_id'):return None
        user=get_db().execute('SELECT role FROM users WHERE id=%s',(session['user_id'],)).fetchone()
        return 'user:'+str(session['user_id']) if user and user['role'] in {'teacher','admin'} else None

    def csrf_ok():
        origin=request.headers.get('Origin')
        return (not origin or origin==request.host_url.rstrip('/')) and hmac.compare_digest(request.headers.get('X-Studio-CSRF',''),session.get('studio_ai_csrf','missing'))

    def trim():
        now=time()
        for jid,job in list(JOBS.items()):
            if job['state'] in {'done','error','cancelled'} and now-job['created']>1800:del JOBS[jid]
        RATE[:]=[(who,when) for who,when in RATE if now-when<3600]

    @app.get('/api/studio/ai/config')
    def ai_config():
        if not owner():return jsonify(error='请使用教师账号登录后生成课程。'),403
        session.setdefault('studio_ai_csrf',token_urlsafe(24))
        settings=ai_settings()
        return jsonify(configured=bool(settings['key'] and settings['base'].startswith('https://')),model=settings['model'],
                       csrf=session['studio_ai_csrf'],max_mb=20,max_pages=60,max_characters=45000)

    @app.post('/api/studio/ai/jobs')
    def generate():
        who=owner()
        if not who:return jsonify(error='请使用教师账号登录后生成课程。'),403
        if not csrf_ok():return jsonify(error='页面验证已失效，请重新打开编辑器。'),403
        if request.content_length and request.content_length>21*1024*1024:return jsonify(error='自动整理最多支持 20MB 文件。'),413
        settings=ai_settings()
        if not settings['key'] or not settings['base'].startswith('https://'):return jsonify(error='教师端 AI 未配置。'),503
        audience=request.form.get('audience','auto')
        if audience not in {'auto','beginner','intermediate','advanced'}:return jsonify(error='学习基础选项无效。'),400
        token=request.form.get('request_id','')
        if not 10<=len(token)<=100:return jsonify(error='请求标识无效，请刷新页面。'),400
        file=request.files.get('file');extension=file.filename.rsplit('.',1)[-1].lower() if file and file.filename else ''
        if extension not in {'pdf','pptx'}:return jsonify(error='请上传 PDF 或 PPTX；旧版 PPT 请先另存为 PPTX。'),400
        blob=file.read(20*1024*1024+1)
        if not blob or len(blob)>20*1024*1024:return jsonify(error='文件为空或超过 20MB。'),400
        with LOCK:
            trim()
            existing=next((j for j in JOBS.values() if j['owner']==who and j['token']==token),None)
            if existing:return jsonify(job_id=existing['id']),202
            active=[j for j in JOBS.values() if j['state'] in {'queued','parsing','generating'}]
            if any(j['owner']==who for j in active):return jsonify(error='已有生成任务，请等待完成。'),409
            if len(active)>=2:return jsonify(error='生成服务正忙，请稍后重试。'),429
            if len(RATE)>=30 or sum(x[0]==who for x in RATE)>=6:return jsonify(error='本小时生成次数已达限制，请稍后再试。'),429
            if len(JOBS)>=60:return jsonify(error='服务暂存任务已满，请稍后重试。'),429
            jid=uuid4().hex
            JOBS[jid]={'id':jid,'owner':who,'token':token,'state':'queued','created':time(),'message':'资料已接收，等待解析。','cancel':False}
            RATE.append((who,time()))
        EXECUTOR.submit(work,jid,blob,extension,audience,file.filename[:160])
        return jsonify(job_id=jid),202

    def work(jid,blob,extension,audience,filename):
        def update(**values):
            with LOCK:JOBS[jid].update(values)
        def cancelled():
            with LOCK:return JOBS[jid]['cancel']
        try:
            if cancelled():update(state='cancelled',message='已取消。');return
            update(state='parsing',message='正在提取资料文字和页码…')
            extracted=parse_file(blob,extension)
            if cancelled():update(state='cancelled',message='已取消，未调用模型。');return
            update(state='generating',stage='generating',extraction={'total_pages':extracted['total_pages'],'characters':extracted['characters']},
                   message=f"已解析 {extracted['total_pages']} 页、{extracted['characters']} 个字符。正在等待云渡生成，可能需要数分钟，请勿重复提交。")
            result=request_course(extracted,audience,on_progress=lambda message:update(message=message))
            if cancelled():update(state='cancelled',message='结果已丢弃；已发出的模型请求仍可能计费。');return
            result['source']={'filename':filename,'sha256':sha256(blob).hexdigest()}
            result['generated_at']=time()
            if result['course']['example']:result['course']['example']='【AI 整理 / 补充示例，请教师核对】\n'+result['course']['example']
            if result['course']['task']:result['course']['task']='【AI 建议练习，请教师核对】\n'+result['course']['task']
            # Published course retains traceable references independently of the teacher-only report.
            result['course']['source_notes']='AI 根据 '+filename+' 的提取文字生成草稿；教师应核对后使用。以下页码对应初始 AI 草稿，调整正文后请重新核对引用。\n'+'\n'.join(
                f"第 {s['section']} 节「{s['title']}」：原资料第 {', '.join(map(str,s['pages']))} 页；引文{'已匹配' if s['quote_matched'] else '待核对'}。" for s in result['sources'])+'\n学习难度与时长为 AI 建议。页码匹配不等于内容准确性认证。'
            # Prefixes must still fit the same publish contract.
            from app.studio.authoring import validate_content
            validate_content(result['course'])
            update(state='done',message='课程草稿已生成，尚未发布。',result=result)
        except CourseAIError as error:
            app.logger.warning('Studio AI job=%s error_code=%s',jid,error.code)
            update(state='error',error_code=error.code,message=str(error))
        except Exception:update(state='error',message='生成过程中出现错误，未覆盖已有课程。请重试或使用高级编辑。')

    @app.get('/api/studio/ai/jobs/<jid>')
    def status(jid):
        who=owner()
        if not who:return jsonify(error='没有访问权限。'),403
        with LOCK:
            trim();job=JOBS.get(jid)
            if not job or job['owner']!=who:return jsonify(error='任务不存在、已过期或服务已重启，请保留原资料重新生成。'),404
            return jsonify({k:job[k] for k in ['id','state','message','result','stage','extraction','error_code'] if k in job})

    @app.delete('/api/studio/ai/jobs/<jid>')
    def cancel(jid):
        who=owner()
        if not who or not csrf_ok():return jsonify(error='没有访问权限。'),403
        with LOCK:
            job=JOBS.get(jid)
            if not job or job['owner']!=who:return jsonify(error='任务不存在。'),404
            job['cancel']=True
            if job['state'] in {'done','error'}:job['state']='cancelled';job.pop('result',None)
        return jsonify(message='停止等待；已发出的模型请求可能仍计费。')
