from pymongo import MongoClient
from django.conf import settings

MONGO_URI = getattr(settings, "MONGO_URI", "mongodb://localhost:27017")

client = MongoClient(MONGO_URI)
db = client.audittrail_db  
logs_collection = db.audit_logs  