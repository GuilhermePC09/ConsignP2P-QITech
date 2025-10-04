# consign_app/dataprev_mock/auth.py
from functools import wraps
from django.http import JsonResponse

def require_bearer(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not auth.split(" ", 1)[1].strip():
            return JsonResponse({
                "error": "invalid_token",
                "error_description": "Missing or invalid Bearer token"
            }, status=401)
        return view_func(request, *args, **kwargs)
    return _wrapped
