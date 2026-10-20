"""Legacy learning exports; use app.learning.paths in new code."""

from app.infrastructure.migrations import initialize_learning
from app.learning.paths import (
    DEFAULT_PROFILE,
    GOALS,
    LEVELS,
    PATHS,
    learning_snapshot,
    learning_status,
    read_profile,
    recommend_paths,
    record_visit,
)

__all__ = [
    "GOALS",
    "LEVELS",
    "PATHS",
    "DEFAULT_PROFILE",
    "learning_status",
    "read_profile",
    "recommend_paths",
    "learning_snapshot",
    "record_visit",
    "initialize_learning",
]
