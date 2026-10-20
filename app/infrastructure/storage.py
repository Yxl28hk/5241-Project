"""Local upload storage shared by account, course and file endpoints."""

from pathlib import Path

from flask import current_app

from app.utils.files import has_allowed_extension
from config import ALLOWED_EXTENSIONS


def upload_folder() -> Path:
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def allowed_file(filename: str) -> bool:
    return has_allowed_extension(filename, ALLOWED_EXTENSIONS)
