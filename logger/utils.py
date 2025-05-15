from .mongo import logs_collection
from datetime import datetime, timezone
import uuid
import json
import hmac
import hashlib
from django.conf import settings

def create_log(action, user_id=None, details=None):
    log_entry = {
        "_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc),
        "action": action,
        "user_id": user_id,
        "details": details or {},
    }

    signing_key = settings.LOG_SIGNING_KEY.encode()
    message = json.dumps(log_entry, sort_keys=True).encode()
    signature = hmac.new(signing_key, message, hashlib.sha256).hexdigest()
    log_entry["signature"] = signature

    logs_collection.insert_one(log_entry)