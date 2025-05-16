from rest_framework.throttling import SimpleRateThrottle
from rest_framework.exceptions import Throttled

class RedisUserRateThrottle(SimpleRateThrottle):
    scope = 'log_create'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return f'throttle_{self.scope}_{request.user.pk}'

    def throttle_failure(self):
        wait = self.wait()
        raise Throttled(detail={
            "error": "Rate limit exceeded",
            "retry_after_seconds": int(wait) if wait else None
        })