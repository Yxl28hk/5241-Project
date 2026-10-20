"""Public account representation; password hashes never leave the server."""

from typing import Any, Mapping


def user_json(row: Mapping[str, Any]) -> dict:
    user = dict(row)
    user.pop("password_hash", None)
    user["avatar_url"] = (
        f"/avatars/{user['avatar_filename']}" if user.get("avatar_filename") else None
    )
    user["is_admin"] = user.get("role") == "admin"
    user.pop("avatar_filename", None)
    user["is_teacher"] = user.get("role") == "teacher"
    user["can_upload"] = user.get("role") in {"teacher", "admin"}
    return user
