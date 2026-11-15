"""Explicit SMTP delivery or loopback-only file outbox; never print secret links."""
import json
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from flask import current_app


class MailUnavailable(Exception):
    pass


def check_delivery():
    cfg = current_app.config
    url = urlsplit(cfg.get("PUBLIC_BASE_URL", ""))
    backend = cfg.get("MAIL_BACKEND", "disabled")
    if url.username or url.password or url.query or url.fragment or not url.hostname:
        raise MailUnavailable()
    if backend == "file" and url.hostname in {"localhost", "127.0.0.1", "::1"} and url.scheme in {"http", "https"}:
        return
    if backend != "smtp" or url.scheme != "https" or not cfg.get("MAIL_HOST") or not cfg.get("MAIL_FROM") or any(c in cfg.get("MAIL_FROM", "") for c in "\r\n") or cfg.get("MAIL_SECURITY") not in {"ssl", "starttls"}:
        raise MailUnavailable()


def send_account_mail(email, purpose, token):
    check_delivery()
    cfg = current_app.config
    # Fragment keeps the credential out of HTTP requests, referrers and access logs.
    link = cfg['PUBLIC_BASE_URL'] + '/#account-' + purpose + '=' + token
    title = '验证知行邮箱' if purpose == 'verify' else '重置知行密码'
    minutes = 1440 if purpose == 'verify' else 30
    body = f'{title}：请打开以下链接并在页面确认。链接 {minutes} 分钟内有效，只能使用一次。\n{link}\n如果不是你本人申请，请忽略本邮件。'
    if cfg['MAIL_BACKEND'] == 'file':
        outbox = Path(cfg['MAIL_OUTBOX'])
        try:
            outbox.mkdir(parents=True, exist_ok=True)
            (outbox / (uuid4().hex + '.json')).write_text(json.dumps({'to': email, 'subject': title, 'body': body}, ensure_ascii=False), encoding='utf-8')
        except OSError as error:
            raise MailUnavailable() from error
        return
    message = EmailMessage()
    message['From'] = cfg['MAIL_FROM']
    message['To'] = email
    message['Subject'] = title
    message.set_content(body)
    try:
        factory = smtplib.SMTP_SSL if cfg['MAIL_SECURITY'] == 'ssl' else smtplib.SMTP
        kwargs = {'context': ssl.create_default_context()} if cfg['MAIL_SECURITY'] == 'ssl' else {}
        with factory(cfg['MAIL_HOST'], cfg['MAIL_PORT'], timeout=15, **kwargs) as smtp:
            if cfg['MAIL_SECURITY'] == 'starttls':
                smtp.starttls(context=ssl.create_default_context())
            if cfg.get('MAIL_USERNAME'):
                smtp.login(cfg['MAIL_USERNAME'], cfg['MAIL_PASSWORD'])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise MailUnavailable() from error
