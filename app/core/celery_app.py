# pyright: reportMissingTypeStubs=false
import logging

import rollbar

# RollbarHandler lives in a submodule that `import rollbar` does not load.
import rollbar.logger
from celery import Celery
from celery.signals import task_failure, worker_process_init
from tessera_sdk.config import get_settings as get_sdk_settings

from app.config import get_settings

settings = get_settings()
redis_settings = get_sdk_settings()

celery_app = Celery("vaulta-worker")


@worker_process_init.connect
def init_rollbar(**kwargs):
    """Initialize Rollbar in each worker process so task errors are reported."""
    if settings.is_production:
        rollbar.init(settings.rollbar_access_token, environment=settings.environment)

        handler = rollbar.logger.RollbarHandler()
        handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(handler)


@task_failure.connect
def report_task_failure(
    sender=None, exception=None, traceback=None, einfo=None, **kwargs
):
    """Explicitly report failed Celery tasks to Rollbar."""
    if settings.is_production:
        rollbar.report_exc_info(
            einfo, extra_data={"task": getattr(sender, "name", None)}
        )


celery_app.conf.update(
    broker_url=redis_settings.redis_connection_url,
    result_backend=redis_settings.redis_connection_url,
    task_default_queue="vaulta",  # Dedicated queue for vaulta tasks
    task_routes={
        "app.tasks.*": {"queue": "vaulta"},
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["app.tasks"])
