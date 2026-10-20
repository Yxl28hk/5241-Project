"""Legacy module alias, including provider monkeypatch compatibility."""

import sys

from app.infrastructure import tutor_provider

sys.modules[__name__] = tutor_provider
