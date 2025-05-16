# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .mongo import logs_collection
from bson.json_util import dumps
from .metrics import log_created_counter, log_listed_counter
from .tasks import create_log_task
from .utils import verify_log_signature
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
import json


class LogCreateView(APIView):
    throttle_classes = [UserRateThrottle, AnonRateThrottle]

    def post(self, request, *args, **kwargs):
        log_created_counter.inc()
        data = request.data
        action = data.get("action")
        user_id = data.get("user_id")
        details = data.get("details", {})

        if not action:
            return Response({"error": "Action is required"}, status=status.HTTP_400_BAD_REQUEST)

        create_log_task.delay(action=action, user_id=user_id, details=details)
        return Response({"message": "Log created"}, status=status.HTTP_201_CREATED)

class LogListView(APIView):
    throttle_classes = [UserRateThrottle, AnonRateThrottle]

    def get(self, request, *args, **kwargs):
        log_listed_counter.inc()
        logs = list(logs_collection.find().sort("timestamp", -1).limit(100))

        valid_logs = []
        for log in logs:
            if verify_log_signature(log):
                valid_logs.append(log)
            else:
                pass

        return Response(json.loads(dumps(valid_logs)), status=status.HTTP_200_OK)