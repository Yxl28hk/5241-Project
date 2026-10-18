"""Learning-path, tutor and mission routes.

This module is kept as an adapter around the existing Flask application
registration API. The adapter lets the feature move into the application
package without changing endpoint names or the existing test fixture.
"""

from prototype import initialize_prototype, register_prototype

__all__ = ["initialize_prototype", "register_prototype"]
