from pymongo import MongoClient, ASCENDING, DESCENDING
from django.conf import settings
import logging
import sys

# Lazy initialization variables
_client = None
_db = None

def get_mongo_collection(collection_name):
    """
    Get a MongoDB collection by name from the audittrail_db database.
    Lazily initializes the connection if not already established.
    """
    global _client, _db
    if _client is None or _db is None:
        try:
            MONGO_URI = getattr(settings, "MONGO_URI", "mongodb://localhost:27017")
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            _client.server_info()  # Test connection
            _db = _client.audittrail_db

            # Create compound indexes for common query patterns on audit_logs
            audit_logs = _db.audit_logs
            audit_logs.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
            audit_logs.create_index([("action", ASCENDING), ("timestamp", DESCENDING)])
            audit_logs.create_index([("timestamp", DESCENDING)])
        except Exception as e:
            logging.error(f"[MongoDB] Connection failed: {e}")
            sys.exit(1)

    collection = _db[collection_name]
    if collection is None:
        raise Exception(f"Collection {collection_name} is None after DB connection.")
    return collection

# Backward compatibility for existing code
def get_logs_collection():
    """Get the audit_logs collection (legacy function)."""
    return get_mongo_collection('audit_logs')

logs_collection = get_logs_collection()