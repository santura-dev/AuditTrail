from pymongo import MongoClient
from django.conf import settings
import logging

MONGO_URI = getattr(settings, "MONGO_URI", "mongodb://localhost:27017")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.server_info()  # Force connection on init
    db = client.audittrail_db
    logs_collection = db.audit_logs
except Exception as e:
    logging.error(f"[MongoDB] Connection failed: {e}")
    logs_collection = None