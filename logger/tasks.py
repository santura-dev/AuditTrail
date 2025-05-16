from celery import shared_task
from logger.utils import create_log_sync 

@shared_task
def create_log_task(action, user_id=None, details=None):
    create_log_sync(action=action, user_id=user_id, details=details)