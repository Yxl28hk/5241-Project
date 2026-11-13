"""Account lifecycle endpoints. Credentials are one-use hashes bound to session versions."""
from hashlib import sha256
from secrets import token_urlsafe
import re
from flask import Blueprint, current_app, request, session
from werkzeug.security import generate_password_hash
from app.auth.security import admin_required, login_required
from app.auth.mail import check_delivery, send_account_mail, MailUnavailable
from app.infrastructure.database import get_db

bp = Blueprint('account_security', __name__)
GENERIC = '如果邮箱对应有效账号，我们已发送操作邮件，请检查收件箱及垃圾邮件。'


def issue(db, user, purpose):
    check_delivery()
    token = token_urlsafe(32)
    digest = sha256(token.encode()).hexdigest()
    # Serialize against password changes and concurrent resends.
    current = db.execute('SELECT session_version FROM users WHERE id=%s FOR UPDATE', (user['id'],)).fetchone()
    db.execute('DELETE FROM account_tokens WHERE user_id=%s AND purpose=%s', (user['id'], purpose))
    db.execute("INSERT INTO account_tokens(token_hash,user_id,purpose,session_version,expires_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP + %s * INTERVAL '1 minute')", (digest,user['id'],purpose,current['session_version'],1440 if purpose=='verify' else 30))
    send_account_mail(user['email'], purpose, token)
    db.commit()


@bp.post('/api/auth/verification/request')
@login_required
def request_verification():
    db = get_db()
    user = db.execute('SELECT id,email,email_verified_at FROM users WHERE id=%s', (session['user_id'],)).fetchone()
    if user['email_verified_at']:
        return {'message':'邮箱已验证'}
    try:
        issue(db, user, 'verify')
    except MailUnavailable:
        db.rollback()
        return {'error':'邮件服务尚未配置或暂不可用，请联系管理员；未发送验证邮件。'},503
    return {'message':'验证邮件已发送，请查收。' if current_app.config['MAIL_BACKEND']=='smtp' else '本地测试邮件已写入本机收件目录，不会发送到真实邮箱。'}


@bp.post('/api/auth/password/request')
def request_reset():
    data = request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('email'),str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',data['email']) or len(data['email'])>254:
        return {'error':'请输入有效邮箱'},400
    try:
        check_delivery()
    except MailUnavailable:
        return {'error':'邮件服务尚未配置，请联系管理员。'},503
    db = get_db()
    user = db.execute('SELECT id,email FROM users WHERE email=%s',(data['email'].strip().lower(),)).fetchone()
    if user:
        try:
            issue(db,user,'reset')
        except MailUnavailable:
            db.rollback()
            current_app.logger.warning('Account mail delivery unavailable')
    return {'message':GENERIC if current_app.config['MAIL_BACKEND']=='smtp' else '如账号存在，测试邮件已写入本机收件目录，不会发送到真实邮箱。'}


def consume(purpose):
    data = request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('token'),str) or not 20<=len(data['token'])<=200:
        return {'error':'链接无效，请重新申请'},400
    password = data.get('password')
    if purpose=='reset' and (not isinstance(password,str) or not 6<=len(password)<=128 or not password.strip()):
        return {'error':'新密码需要 6–128 位且不能全为空白'},400
    db = get_db();digest = sha256(data['token'].encode()).hexdigest()
    token = db.execute('SELECT user_id FROM account_tokens WHERE token_hash=%s AND purpose=%s',(digest,purpose)).fetchone()
    if not token:
        return {'error':'链接无效或已失效，请重新申请'},400
    user = db.execute('SELECT id,session_version FROM users WHERE id=%s FOR UPDATE',(token['user_id'],)).fetchone()
    valid = db.execute('UPDATE account_tokens SET used_at=CURRENT_TIMESTAMP WHERE token_hash=%s AND purpose=%s AND used_at IS NULL AND expires_at>CURRENT_TIMESTAMP AND session_version=%s RETURNING user_id',(digest,purpose,user['session_version'] if user else -1)).fetchone()
    if not valid:
        db.rollback()
        return {'error':'链接无效或已失效，请重新申请'},400
    if purpose=='verify':
        db.execute('UPDATE users SET email_verified_at=CURRENT_TIMESTAMP WHERE id=%s',(user['id'],))
    else:
        db.execute('UPDATE users SET password_hash=%s,session_version=session_version+1 WHERE id=%s',(generate_password_hash(password),user['id']))
    db.commit()
    if purpose=='reset':
        session.clear()
    return {'message':'邮箱验证成功，请返回登录。' if purpose=='verify' else '密码已重置，所有旧登录已失效，请重新登录。'}


@bp.post('/api/auth/verification/confirm')
def verify():
    return consume('verify')


@bp.post('/api/auth/password/reset')
def reset():
    return consume('reset')


@bp.post('/api/profile/teacher-application')
@login_required
def apply_teacher():
    data = request.get_json(silent=True)
    reason = data.get('reason') if isinstance(data,dict) else None
    if not isinstance(reason,str) or not 10<=len(reason.strip())<=1000:
        return {'error':'请填写 10–1000 字教学用途、所属机构或课程说明'},400
    db = get_db()
    user = db.execute('SELECT role,email_verified_at FROM users WHERE id=%s FOR UPDATE',(session['user_id'],)).fetchone()
    if user['role']!='student' or not user['email_verified_at']:
        return {'error':'请先验证邮箱；只有学生账号可以申请教师身份'},403
    db.execute("UPDATE users SET teacher_status='pending',teacher_reason=%s WHERE id=%s",(reason.strip(),session['user_id']))
    db.commit()
    return {'message':'教师申请已提交，审核前仍可作为学生学习。'}


@bp.get('/api/admin/teacher-applications')
@admin_required
def applications():
    rows = get_db().execute("SELECT id,name,email,teacher_reason,email_verified_at FROM users WHERE teacher_status='pending' AND role='student' ORDER BY id").fetchall()
    return {'applications':[dict(row) for row in rows]}


@bp.post('/api/admin/teacher-applications/<int:user_id>/review')
@admin_required
def review(user_id):
    data = request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('decision'),str) or data['decision'] not in {'approve','reject'} or not isinstance(data.get('reason'),str) or not 1<=len(data['reason'].strip())<=1000:
        return {'error':'请选择审核结论并填写 1–1000 字说明'},400
    db=get_db()
    user=db.execute('SELECT role,teacher_status,teacher_reason,email_verified_at FROM users WHERE id=%s FOR UPDATE',(user_id,)).fetchone()
    if not user or user['role']!='student' or user['teacher_status']!='pending':
        return {'error':'申请已处理或不存在，请刷新'},409
    if data['decision']=='approve' and (not user['email_verified_at'] or not user['teacher_reason']):
        return {'error':'申请人必须完成邮箱验证和教学用途说明'},409
    approved=data['decision']=='approve'
    db.execute('UPDATE users SET role=%s,teacher_status=%s,session_version=session_version+1 WHERE id=%s',('teacher' if approved else 'student','approved' if approved else 'rejected',user_id))
    db.execute('INSERT INTO teacher_reviews(user_id,reviewer_id,decision,reason) VALUES (%s,%s,%s,%s)',(user_id,session['user_id'],data['decision'],data['reason'].strip()))
    db.commit()
    return {'message':'审核已保存，请申请人重新登录以刷新身份。'}
