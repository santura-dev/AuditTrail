# logger/schema.py

import graphene
from graphene.types.generic import GenericScalar
from bson.json_util import dumps
from .mongo import logs_collection
from .utils import create_log, verify_log_signature

class LogEntryType(graphene.ObjectType):
    _id = graphene.String()
    timestamp = graphene.DateTime()
    action = graphene.String()
    user_id = graphene.String()
    details = GenericScalar()
    signature = graphene.String()

class Query(graphene.ObjectType):
    logs = graphene.List(LogEntryType, action=graphene.String())

    def resolve_logs(self, info, action=None):
        query = {}
        if action:
            query["action"] = action

        logs = list(logs_collection.find(query).sort("timestamp", -1).limit(100))
        for log in logs:
            log["_id"] = str(log["_id"])
        return logs

class Mutation(graphene.ObjectType):
    create_log = create_log.Field()
    verify_log_signature = verify_log_signature.Field()

schema = graphene.Schema(query=Query)