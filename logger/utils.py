from .mongo import logs_collection
from datetime import datetime, timezone
import uuid
import json
import hmac
import hashlib
from django.conf import settings
import os

def create_log_sync(action, user_id=None, details=None, timestamp=None):
    """
    Create and insert a signed log entry synchronously into MongoDB.
    """
    # Use provided timestamp or default to current time
    timestamp = timestamp if timestamp else datetime.now(timezone.utc).replace(microsecond=0)
    log_entry = {
        "_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "action": action,
        "user_id": user_id,
        "details": details or {},
    }

    # Format timestamp consistently for signing
    signing_entry = log_entry.copy()
    signing_entry["timestamp"] = timestamp.strftime("%Y-%m-%d %H:%M:%S+00:00")
    signing_key = settings.LOG_SIGNING_KEY.encode()
    message = json.dumps(signing_entry, sort_keys=True).encode()
    signature = hmac.new(signing_key, message, hashlib.sha256).hexdigest()
    log_entry["signature"] = signature
    if os.getenv("DEBUG", "False").lower() == "true":
        print(f"Created with LOG_SIGNING_KEY: {settings.LOG_SIGNING_KEY}, Message: {message.decode()}, Signature: {signature}")

    logs_collection.insert_one(log_entry)
    return log_entry

def verify_log_signature(log_entry):
    """
    Verify the HMAC signature of a log entry.
    """
    if os.getenv("DEBUG", "False").lower() == "true":
        print(f"Verifying with LOG_SIGNING_KEY: {settings.LOG_SIGNING_KEY}")
    original_signature = log_entry.get("signature")
    if not original_signature:
        return False

    temp_entry = {k: v for k, v in log_entry.items() if k != "signature"}
    temp_entry["timestamp"] = temp_entry["timestamp"].replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S+00:00")
    serialized = json.dumps(temp_entry, sort_keys=True).encode()
    signing_key = settings.LOG_SIGNING_KEY.encode()
    expected_signature = hmac.new(signing_key, serialized, hashlib.sha256).hexdigest()
    if os.getenv("DEBUG", "False").lower() == "true":
        print(f"Verifying Message: {serialized.decode()}, Expected Signature: {expected_signature}, Actual Signature: {original_signature}")
    return hmac.compare_digest(original_signature, expected_signature)