"""Legacy initialization entry point."""

from app.infrastructure.migrations import initialize_prototype
from app.missions.service import public_attempt

__all__ = ["initialize_prototype", "public_attempt"]
