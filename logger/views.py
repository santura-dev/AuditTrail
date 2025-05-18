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
from rest_framework.pagination import PageNumberPagination
from django.utils.dateparse import parse_datetime

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


class LogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class LogListView(APIView):
    throttle_classes = [RedisUserRateThrottle]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        log_listed_counter.inc()

        # Filters
        user_id = request.query_params.get("user_id")
        action = request.query_params.get("action")
        action_contains = request.query_params.get("action__contains")
        action_in = request.query_params.get("action__in")
        action_nin = request.query_params.get("action__nin")
        start_time = request.query_params.get("start_time") 
        end_time = request.query_params.get("end_time")      

        query = {}

        if user_id:
            query["user_id"] = user_id
        if action:
            query["action"] = action
        if action_contains:
            query["action"] = {"$regex": action_contains, "$options": "i"} 
        if action_in:
            actions = action_in.split(",")  # e.g., "login,logout"
            query["action"] = {"$in": actions}
        if action_nin:
            actions = action_nin.split(",")  # e.g., "login,logout"
            query["action"] = {"$nin": actions}
        if start_time:
            start_dt = parse_datetime(start_time)
            if start_dt:
                query["timestamp"] = query.get("timestamp", {})
                query["timestamp"]["$gte"] = start_dt
        if end_time:
            end_dt = parse_datetime(end_time)
            if end_dt:
                query["timestamp"] = query.get("timestamp", {})
                query["timestamp"]["$lte"] = end_dt

        # Fetch filtered logs sorted descending by timestamp
        logs_cursor = logs_collection.find(query).sort("timestamp", -1)

        # Filter out unsigned logs
        filtered_logs = [log for log in logs_cursor if verify_log_signature(log)]

        # Pagination
        paginator = LogPagination()
        page = paginator.paginate_queryset(filtered_logs, request)
        serialized_page = json.loads(dumps(page))

        return paginator.get_paginated_response(serialized_page)