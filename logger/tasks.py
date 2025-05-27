from celery import shared_task
from pymongo.errors import PyMongoError, AutoReconnect
from logger.utils import create_log_sync
from collections import deque
from django.core.management import call_command

# In-memory buffer for batching logs (max 100 logs)
LOG_BUFFER = deque(maxlen=100)

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    acks_late=True 
)
def flush_log_buffer(self):
    """
    Flush the in-memory log buffer to MongoDB in a batch.
    """
    try:
        logs_to_flush = list(LOG_BUFFER)  
        if not logs_to_flush:
            return  

        # Batch insert into MongoDB
        batch = []
        for log in logs_to_flush:
            log_entry = {
                "action": log["action"],
                "user_id": log["user_id"],
                "details": log["details"]
            }
            batch.append(create_log_sync(**log_entry)) 

        LOG_BUFFER.clear()  
    except (PyMongoError, AutoReconnect) as exc:
        raise self.retry(exc=exc)

@shared_task
def create_log_task(action, user_id=None, details=None):
    """
    Queue a log entry into the in-memory buffer. Flush if buffer is full.
    """
    LOG_BUFFER.append({"action": action, "user_id": user_id, "details": details})
    if len(LOG_BUFFER) >= 100:  # Flush at 100 logs
        flush_log_buffer.delay()

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True
)
def archive_logs_task(self, days=30):
    """
    Archive logs older than the specified number of days by calling the archive_logs command.
    """
    try:
        call_command('archive_logs', days=days)
    except Exception as exc:
        raise self.retry(exc=exc)