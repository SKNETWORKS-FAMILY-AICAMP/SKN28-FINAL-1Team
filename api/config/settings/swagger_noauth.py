"""Development settings — no-auth variant for local/external access."""

from .swagger import *  # noqa: F401,F403

# swagger.py already extends dev.py (which extends base.py).
# This file is a plain alias — no additional overrides needed.
