import graphene
from graphene.types.generic import GenericScalar
from .mongo import logs_collection

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

schema = graphene.Schema(query=Query)