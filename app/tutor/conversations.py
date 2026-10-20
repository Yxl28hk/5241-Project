"""Conversation persistence and public representation."""

from uuid import uuid4

from app.tutor import repository


def public_conversation(row):
    return {
        "token": row["token"],
        "revision": row["revision"],
        "messages": row["messages"],
        "updated_at": row["updated_at"],
    }


def open_conversation(db, user_id, course_id):
    repository.insert_conversation(db, (user_id, course_id, uuid4().hex))
    return repository.find_conversation(db, (user_id, course_id))
