"""
Shared rate-limiter instance.

Lives in its own module (rather than app/main.py) so that router modules
can import and apply `@limiter.limit(...)` to individual endpoints without
creating a circular import with app.main (which mounts those routers).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(key_func=get_remote_address)

DEFAULT_RATE_LIMIT = f"{settings.rate_limit_per_minute}/minute"
