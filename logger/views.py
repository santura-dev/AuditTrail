from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .utils import create_log
from .mongo import logs_collection
from bson.json_util import dumps
import json

class LogCreateView(APIView):
    def post(self, request):
        try:
            data = request.data
            action = data.get("action")
            user_id = data.get("user_id")
            details = data.get("details", {})

            if not action:
                return Response({"error": "Action is required"}, status=status.HTTP_400_BAD_REQUEST)

            create_log(action=action, user_id=user_id, details=details)
            return Response({"message": "Log created"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class LogListView(APIView):
    def get(self, request):
        try:
            logs = list(logs_collection.find().sort("timestamp", -1).limit(100))
            return Response(json.loads(dumps(logs)), status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)