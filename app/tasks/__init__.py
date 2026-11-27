# Import celery app first
from app.core.celery_app import celery_app

# Initialize logging configuration for Celery workers
from app.core.logging_config import LoggingConfig

LoggingConfig()

# Import all models so SQLAlchemy relationships are initialized before any
# database work in the worker.
import app.models  # noqa: F401, E402


def _import_tasks():
    """Import tasks for registration."""
    from . import process_asset  # noqa: F401


_import_tasks()

__all__ = ["celery_app"]
