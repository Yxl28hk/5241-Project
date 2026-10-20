"""Serve only the public frontend manifest and existing attachment routes."""

from flask import Blueprint, Response, send_from_directory

from app.infrastructure.storage import upload_folder
from config import BASE_DIR

bp = Blueprint("web", __name__)
FRONTEND_DIR = BASE_DIR / "frontend"
SCRIPTS = (
    "api/client.js",
    "features/state.js",
    "components/ui.js",
    "features/auth/account.js",
    "features/courses/catalog.js",
    "features/navigation.js",
    "features/learning/workspace.js",
    "features/tutor/panel.js",
    "features/missions/release-rescue.js",
    "features/learning/study.js",
    "features/tutor/study.js",
    "features/bootstrap.js",
)
PUBLIC_ASSETS = {*SCRIPTS, "styles/main.css", "styles/learning.css"}
LEGACY_BUNDLES = {
    # Original HTML loads only app.js / prototype.js / study.js, without api.js.
    "app.js": SCRIPTS[:6] + ("features/bootstrap.js",),
    "prototype.js": SCRIPTS[6:9],
    "study.js": SCRIPTS[9:11],
}
LEGACY_FILES = {
    "api.js": "api/client.js",
    "styles.css": "styles/main.css",
    "prototype.css": "styles/learning.css",
}


@bp.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@bp.get("/frontend/<path:filename>")
def frontend_asset(filename):
    if filename not in PUBLIC_ASSETS:
        return {"error": "文件不存在"}, 404
    return send_from_directory(FRONTEND_DIR, filename)


@bp.get("/<filename>")
def static_asset(filename):
    if filename in LEGACY_FILES:
        return send_from_directory(FRONTEND_DIR, LEGACY_FILES[filename])
    if filename in LEGACY_BUNDLES:
        content = "\n;\n".join(
            (FRONTEND_DIR / path).read_text(encoding="utf-8")
            for path in LEGACY_BUNDLES[filename]
        )
        return Response(content, mimetype="text/javascript")
    return {"error": "文件不存在"}, 404


@bp.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(upload_folder(), filename)


@bp.get("/avatars/<path:filename>")
def avatar_file(filename):
    return send_from_directory(upload_folder(), filename)
