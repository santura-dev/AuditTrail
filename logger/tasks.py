from celery import shared_task
from pymongo.errors import PyMongoError, AutoReconnect
from logger.utils import create_log_sync

@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def create_log_task(self, action, user_id=None, details=None):
    try:
        create_log_sync(action=action, user_id=user_id, details=details)
    except (PyMongoError, AutoReconnect) as exc:
        raise self.retry(exc=exc)