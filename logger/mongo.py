from pymongo import MongoClient, ASCENDING, DESCENDING
from django.conf import settings
import logging
import sys

MONGO_URI = getattr(settings, "MONGO_URI", "mongodb://localhost:27017")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.server_info()  
    db = client.audittrail_db
    logs_collection = db.audit_logs

    if logs_collection is None:
        raise Exception("logs_collection is None after DB connection.")

    # Create compound indexes for common query patterns
    logs_collection.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
    logs_collection.create_index([("action", ASCENDING), ("timestamp", DESCENDING)])
    logs_collection.create_index([("timestamp", DESCENDING)]) 

except Exception as e:
    logging.error(f"[MongoDB] Connection failed: {e}")
    sys.exit(1)