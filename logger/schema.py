import graphene
from graphene.types.generic import GenericScalar
from bson.json_util import dumps
from .mongo import logs_collection
from .utils import verify_log_signature

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

class CreateLog(graphene.Mutation):
    class Arguments:
        action = graphene.String(required=True)
        user_id = graphene.String()
        details = GenericScalar()

    ok = graphene.Boolean()

    def mutate(self, info, action, user_id=None, details=None):
        from .tasks import create_log_task
        create_log_task.delay(action, user_id, details)
        return CreateLog(ok=True)

class VerifyLogSignature(graphene.Mutation):
    class Arguments:
        log_entry = GenericScalar(required=True)  # accept the entire log as input

    is_valid = graphene.Boolean()

    def mutate(self, info, log_entry):
        valid = verify_log_signature(log_entry)
        return VerifyLogSignature(is_valid=valid)

class Mutation(graphene.ObjectType):
    create_log = CreateLog.Field()
    verify_log_signature = VerifyLogSignature.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)