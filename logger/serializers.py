import json
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle datetime objects by converting them to ISO format strings.
    """
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)