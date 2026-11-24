"""Local files or transactionally stored PostgreSQL attachments."""

from pathlib import Path
from io import BytesIO
import mimetypes

from flask import current_app, abort, send_file, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from app.infrastructure.database import get_db

from app.utils.files import has_allowed_extension
from config import ALLOWED_EXTENSIONS


def upload_folder() -> Path:
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def allowed_file(filename: str) -> bool:
    return has_allowed_extension(filename, ALLOWED_EXTENSIONS)


def database_storage():
    return current_app.config.get("UPLOAD_STORAGE", "local") == "database"


def asset_path(filename):
    root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    path = (root / filename).resolve()
    if path.parent != root or "\\" in filename or "/" in filename:
        raise ValueError("Invalid attachment name")
    return path


def asset_row(filename):
    db = get_db()
    if not db.execute("SELECT to_regclass('uploaded_assets') AS name").fetchone()["name"]:
        return None
    return db.execute("SELECT content,content_type FROM uploaded_assets WHERE filename=%s", (filename,)).fetchone()


def save_upload(file, filename):
    """DB writes share the caller's course/profile transaction; never commit here."""
    asset_path(filename)
    if not database_storage():
        file.save(upload_folder() / filename)
        return
    limit = current_app.config.get("UPLOAD_MAX_BYTES", 3 * 1024 * 1024)
    content = file.read(limit + 1)
    if len(content) > limit:
        raise RequestEntityTooLarge()
    db = get_db()
    # Additive bootstrap supports existing cloud installs without reseeding accounts.
    db.execute("SELECT pg_advisory_xact_lock(hashtext(current_schema()), 524109)")
    db.execute("""CREATE TABLE IF NOT EXISTS uploaded_assets (
        filename TEXT PRIMARY KEY, content BYTEA NOT NULL, content_type TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("INSERT INTO uploaded_assets(filename,content,content_type) VALUES (%s,%s,%s)",
               (filename, content, mimetypes.guess_type(filename)[0] or "application/octet-stream"))


def read_upload(filename, limit=20 * 1024 * 1024):
    path = asset_path(filename)
    if database_storage():
        row = asset_row(filename)
        if row is not None:
            content = bytes(row["content"])
            if len(content) > limit:
                raise ValueError("Attachment exceeds read limit")
            return content
    with path.open("rb") as handle:
        content = handle.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Attachment exceeds read limit")
    return content


def serve_upload(filename):
    try:
        path = asset_path(filename)
    except ValueError:
        abort(404)
    if database_storage():
        row = asset_row(filename)
        if row is not None:
            response = send_file(BytesIO(bytes(row["content"])), mimetype=row["content_type"],
                                 download_name=filename, conditional=True)
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
    if not path.is_file():
        return {"error": "课件附件缺失，请联系课程教师重新上传文件；课程文字和学习记录仍保留。"}, 404
    return send_from_directory(path.parent, path.name)


def delete_upload(filename):
    if not filename:
        return
    path = asset_path(filename)
    if database_storage():
        db = get_db()
        if db.execute("SELECT to_regclass('uploaded_assets') AS name").fetchone()["name"]:
            db.execute("DELETE FROM uploaded_assets WHERE filename=%s", (filename,))
    # Packaged legacy assets are read-only on Vercel; new assets are in PostgreSQL.
    elif path.is_file():
        path.unlink()
