from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .mongo import logs_collection
from bson.json_util import dumps
from .metrics import log_created_counter, log_listed_counter
from .tasks import create_log_task
from .utils import verify_log_signature
import json
import csv
from rest_framework.permissions import IsAuthenticated
from .throttles import RedisUserRateThrottle  
from rest_framework.pagination import PageNumberPagination
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from django.http import StreamingHttpResponse

class Echo:
    """An object that implements just the write method for streaming."""
    def write(self, value):
        return value

class LogCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RedisUserRateThrottle]  

    @extend_schema(
        summary="Create a new log entry",
        description="Creates a new log entry asynchronously using Celery. Requires JWT authentication.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "The action being logged (e.g., 'login')"},
                    "details": {"type": "object", "description": "Additional details about the action"},
                },
                "required": ["action"],
                "example": {
                    "action": "login",
                    "details": {"ip_address": "192.168.1.1"}
                }
            }
        },
        responses={
            201: {"description": "Log created successfully", "example": {"message": "Log created"}},
            400: {"description": "Invalid request", "example": {"error": "Action is required"}},
        },
    )
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
    page_size_query_param = "page_size"
    max_page_size = 100

class LogListView(APIView):
    throttle_classes = [RedisUserRateThrottle]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List audit logs with filters",
        description="Retrieve a paginated list of audit logs with optional filters. Requires JWT authentication.",
        parameters=[
            OpenApiParameter(name="user_id", type=str, description="Filter by user ID"),
            OpenApiParameter(name="action", type=str, description="Filter by exact action name"),
            OpenApiParameter(name="action__contains", type=str, description="Filter by partial action name (regex)"),
            OpenApiParameter(name="action__in", type=str, description="Filter by a comma-separated list of actions"),
            OpenApiParameter(name="action__nin", type=str, description="Exclude a comma-separated list of actions"),
            OpenApiParameter(name="start_time", type=str, description="Filter logs after this timestamp (ISO format)"),
            OpenApiParameter(name="end_time", type=str, description="Filter logs before this timestamp (ISO format)"),
            OpenApiParameter(name="page", type=int, description="Page number for pagination"),
            OpenApiParameter(name="page_size", type=int, description="Number of logs per page (max 100)"),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "next": {"type": "string", "nullable": True},
                    "previous": {"type": "string", "nullable": True},
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "_id": {"type": "string"},
                                "timestamp": {"type": "string"},
                                "action": {"type": "string"},
                                "user_id": {"type": "string"},
                                "details": {"type": "object"},
                                "signature": {"type": "string"},
                            }
                        }
                    }
                },
                "example": {
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "_id": "12345",
                            "timestamp": "2025-05-18T09:35:00Z",
                            "action": "login",
                            "user_id": "user123",
                            "details": {"ip_address": "192.168.1.1"},
                            "signature": "abc123..."
                        }
                    ]
                }
            }
        }
    )
    def get(self, request, *args, **kwargs):
        log_listed_counter.inc()

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
            actions = action_in.split(",")
            query["action"] = {"$in": actions}
        if action_nin:
            actions = action_nin.split(",")
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

        if os.getenv("DEBUG", "False").lower() == "true":
            print(f"Query: {query}")
        logs_cursor = logs_collection.find(query).sort("timestamp", -1)
        logs_list = list(logs_cursor)
        if os.getenv("DEBUG", "False").lower() == "true":
            print(f"Retrieved Logs: {logs_list}")
        filtered_logs = [log for log in logs_list if verify_log_signature(log)]
        if os.getenv("DEBUG", "False").lower() == "true":
            print(f"Filtered Logs: {filtered_logs}")

        paginator = LogPagination()
        page = paginator.paginate_queryset(filtered_logs, request)
        serialized_page = json.loads(dumps(page))

        return paginator.get_paginated_response(serialized_page)

class LogExportView(APIView):
    throttle_classes = [RedisUserRateThrottle]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Export audit logs with filters",
        description="Export audit logs in CSV or JSON format with optional filters. Requires JWT authentication.",
        parameters=[
            OpenApiParameter(name="user_id", type=str, description="Filter by user ID"),
            OpenApiParameter(name="action", type=str, description="Filter by exact action name"),
            OpenApiParameter(name="action__contains", type=str, description="Filter by partial action name (regex)"),
            OpenApiParameter(name="action__in", type=str, description="Filter by a comma-separated list of actions"),
            OpenApiParameter(name="action__nin", type=str, description="Exclude a comma-separated list of actions"),
            OpenApiParameter(name="start_time", type=str, description="Filter logs after this timestamp (ISO format)"),
            OpenApiParameter(name="end_time", type=str, description="Filter logs before this timestamp (ISO format)"),
            OpenApiParameter(name="format", type=str, description="Export format: 'csv' (default) or 'json'"),
        ],
        responses={
            200: {
                "description": "File streamed successfully",
                "content": {
                    "text/csv": {
                        "example": "_id,timestamp,action,user_id,details,signature\n12345,2025-05-18 09:35:00,login,user123,{\"ip_address\": \"192.168.1.1\"},abc123..."
                    },
                    "application/json": {
                        "example": [
                            {
                                "_id": "12345",
                                "timestamp": "2025-05-18T09:35:00Z",
                                "action": "login",
                                "user_id": "user123",
                                "details": {"ip_address": "192.168.1.1"},
                                "signature": "abc123..."
                            }
                        ]
                    }
                }
            },
            400: {"description": "Invalid request parameters"}
        }
    )
    def get(self, request, *args, **kwargs):
        # Reuse filtering logic from LogListView
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
            actions = action_in.split(",")
            query["action"] = {"$in": actions}
        if action_nin:
            actions = action_nin.split(",")
            query["action"] = {"$nin": actions}
        if start_time:
            start_dt = parse_datetime(start_time)
            if start_dt:
                query["timestamp"] = query.get("timestamp", {})
                query["timestamp"]["$gte"] = start_dt
            else:
                return Response({"error": "Invalid start_time format. Use ISO format."}, status=status.HTTP_400_BAD_REQUEST)
        if end_time:
            end_dt = parse_datetime(end_time)
            if end_dt:
                query["timestamp"] = query.get("timestamp", {})
                query["timestamp"]["$lte"] = end_dt
            else:
                return Response({"error": "Invalid end_time format. Use ISO format."}, status=status.HTTP_400_BAD_REQUEST)

        logs_cursor = logs_collection.find(query).sort("timestamp", -1)
        verified_logs = [log for log in logs_cursor if verify_log_signature(log)]

        # Determine export format (default to CSV)
        export_format = request.query_params.get("format", "csv")

        if export_format.lower() == "json":
            # Stream JSON response
            def stream_json():
                yield "["
                for i, log in enumerate(verified_logs):
                    yield json.dumps(log, default=str)
                    if i < len(verified_logs) - 1:
                        yield ","
                yield "]"

            response = StreamingHttpResponse(stream_json(), content_type="application/json")
            response["Content-Disposition"] = 'attachment; filename="logs_export.json"'
            return response

        else:
            # Stream CSV response
            def stream_csv():
                writer = csv.writer(Echo(), lineterminator="\n")
                # Write header
                yield writer.writerow(["_id", "timestamp", "action", "user_id", "details", "signature"])
                # Write rows
                for log in verified_logs:
                    yield writer.writerow([
                        log["_id"],
                        log["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        log["action"],
                        log["user_id"],
                        json.dumps(log["details"]),
                        log["signature"],
                    ])

            response = StreamingHttpResponse(stream_csv(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="logs_export.csv"'
            return response