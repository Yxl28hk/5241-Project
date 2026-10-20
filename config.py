"""Runtime configuration shared by the application entry point."""

from __future__ import annotations

import os
from pathlib import Path
from secrets import token_hex

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "mp4", "mov"}
AVATAR_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_FILE_SIZE = 500 * 1024 * 1024
ADMIN_EMAIL = os.environ.get("ZHIXING_ADMIN_EMAIL", "admin@zhixing.com").strip().lower()
ADMIN_PASSWORD = os.environ.get("ZHIXING_ADMIN_PASSWORD", "")
SECRET_KEY = os.environ.get("ZHIXING_SECRET_KEY") or token_hex(32)
TUTOR_API_URL = os.environ.get("TUTOR_API_URL", "").strip()
TUTOR_API_KEY = os.environ.get("TUTOR_API_KEY", "").strip()
TUTOR_MODEL = os.environ.get("TUTOR_MODEL", "").strip()
