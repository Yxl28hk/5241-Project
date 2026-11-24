"""Short-lived, owner-scoped AI results shared by serverless instances."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from app.infrastructure.database import get_db

# Vercel terminates this invocation after 300s; allow 30s for clock/cleanup.
LEASE_SECONDS = 330


def expire(db):
    db.execute("""UPDATE studio_ai_jobs SET
        state=CASE WHEN cancelled THEN 'cancelled' ELSE 'error' END,
        payload=(payload-'result') || jsonb_build_object(
            'error_code','task_expired','message',CASE WHEN cancelled
                THEN '已取消的任务已结束，可以重新生成。'
                ELSE '上次生成已超时，可以重新生成；原草稿仍保留。' END),
        updated_at=NOW()
        WHERE state IN ('queued','parsing','generating')
        AND (created_at < NOW() - %s * INTERVAL '1 second'
             OR updated_at < NOW() - INTERVAL '8 minutes')""", (LEASE_SECONDS,))


def current(owner):
    """Recover only this teacher's still-running invocation, including draining cancellations."""
    db=get_db()
    if not db.execute("SELECT to_regclass('studio_ai_jobs') AS name").fetchone()['name']:
        db.commit()
        return None
    expire(db)
    row=db.execute("""SELECT id FROM studio_ai_jobs WHERE owner=%s
        AND state IN ('queued','parsing','generating') ORDER BY created_at DESC LIMIT 1""",(owner,)).fetchone()
    db.commit()
    return row['id'] if row else None


def reserve(owner, request_id):
    db = get_db()
    # Serialize reservation and shared limits across workers, not just this process.
    db.execute("SELECT pg_advisory_xact_lock(hashtext(current_schema()), 524108)")
    db.execute("""CREATE TABLE IF NOT EXISTS studio_ai_jobs (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_id TEXT NOT NULL,
        state TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}',
        cancelled BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(owner,request_id))""")
    db.execute("DELETE FROM studio_ai_jobs WHERE created_at < NOW() - INTERVAL '24 hours'")
    expire(db)
    existing = db.execute("SELECT id FROM studio_ai_jobs WHERE owner=%s AND request_id=%s", (owner, request_id)).fetchone()
    if existing:
        db.commit()
        return existing['id'], False, None
    counts = db.execute("""SELECT
        COUNT(*) FILTER (WHERE state IN ('queued','parsing','generating')) AS active,
        COUNT(*) FILTER (WHERE owner=%s AND state IN ('queued','parsing','generating')) AS own_active,
        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') AS recent,
        COUNT(*) FILTER (WHERE owner=%s AND created_at > NOW() - INTERVAL '1 hour') AS own_recent
        FROM studio_ai_jobs""", (owner, owner)).fetchone()
    error = None
    active=db.execute("""SELECT id,cancelled FROM studio_ai_jobs WHERE owner=%s
        AND state IN ('queued','parsing','generating') ORDER BY created_at DESC LIMIT 1""",(owner,)).fetchone()
    if active:
        message='正在结束上次已取消的生成，请稍候。' if active['cancelled'] else '正在恢复已有生成任务。'
        error = ({'error': message, 'job_id': active['id']}, 409)
    elif counts['active'] >= 2:
        error = ({'error': '生成服务正忙，请稍后重试。'}, 429)
    elif counts['recent'] >= 30 or counts['own_recent'] >= 6:
        error = ({'error': '本小时生成次数已达限制，请稍后再试。'}, 429)
    if error:
        db.commit()
        return None, False, error
    jid = uuid4().hex
    db.execute("""INSERT INTO studio_ai_jobs(id,owner,request_id,state,payload)
        VALUES (%s,%s,%s,'queued',%s)""", (jid, owner, request_id, Jsonb({'message': '资料已接收，等待解析。'})))
    db.commit()
    return jid, True, None


def update(jid, **values):
    db = get_db()
    state = values.pop('state', None)
    db.execute("""UPDATE studio_ai_jobs SET state=COALESCE(%s,state),
        payload=payload || %s, updated_at=NOW()
        WHERE id=%s AND state IN ('queued','parsing','generating')
        AND (NOT cancelled OR %s='cancelled')""", (state, Jsonb(values), jid, state))
    db.commit()


def cancelled(jid):
    db = get_db()
    row = db.execute('SELECT cancelled FROM studio_ai_jobs WHERE id=%s', (jid,)).fetchone()
    db.commit()
    return not row or row['cancelled']


def get(owner, *, jid=None, request_id=None):
    db = get_db()
    if not db.execute("SELECT to_regclass('studio_ai_jobs') AS name").fetchone()['name']:
        db.commit()
        return None
    expire(db)
    row = db.execute("""SELECT id,state,payload,cancelled,
        updated_at < NOW() - INTERVAL '8 minutes' AS stale
        FROM studio_ai_jobs WHERE owner=%s AND (id=%s OR request_id=%s)
        AND created_at > NOW() - INTERVAL '30 minutes'""", (owner, jid, request_id)).fetchone()
    db.commit()
    if not row:
        return None
    if row['cancelled']:
        in_flight=row['state'] in {'queued','parsing','generating'}
        return {'id':row['id'], 'state':'cancelled', 'in_flight':in_flight,
                'message':'已取消，正在等待上一次生成结束，请稍候。' if in_flight else '已取消的任务已结束，可以重新生成。'}
    if row['stale'] and row['state'] in {'queued', 'parsing', 'generating'}:
        return {'id': row['id'], 'state': 'error', 'message': '生成已超时，请检查资料后手动重试。'}
    return {**row['payload'], 'id': row['id'], 'state': row['state']}


def cancel(owner, jid):
    db = get_db()
    if not get(owner, jid=jid):
        return False
    db.execute("""UPDATE studio_ai_jobs SET cancelled=TRUE,
        state=CASE WHEN state IN ('done','error') THEN 'cancelled' ELSE state END,
        payload=(payload - 'result') || '{"message":"已停止等待；已发送的模型请求可能仍计费。"}',
        updated_at=NOW() WHERE id=%s AND owner=%s""", (jid, owner))
    db.commit()
    return True
