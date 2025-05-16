# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .mongo import logs_collection
from bson.json_util import dumps
from .metrics import log_created_counter, log_listed_counter
from .tasks import create_log_task
from .utils import verify_log_signature
import json
from rest_framework.permissions import IsAuthenticated
from .throttles import RedisUserRateThrottle  
from rest_framework.permissions import IsAuthenticated

class LogCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RedisUserRateThrottle]  

    def post(self, request, *args, **kwargs):
        log_created_counter.inc()
        user = request.user
        data = request.data

        action = data.get("action")
        details = data.get("details", {})

        if not action:
            return Response({"error": "Action is required"}, status=status.HTTP_400_BAD_REQUEST)

        create_log_task.delay(action=action, user_id=str(user.id), details=details)
        return Response({"message": "Log created"}, status=status.HTTP_201_CREATED)


class LogListView(APIView):
    throttle_classes = [RedisUserRateThrottle]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        log_listed_counter.inc()
        logs = list(logs_collection.find().sort("timestamp", -1).limit(100))

        valid_logs = []
        for log in logs:
            if verify_log_signature(log):
                valid_logs.append(log)

        return Response(json.loads(dumps(valid_logs)), status=status.HTTP_200_OK)