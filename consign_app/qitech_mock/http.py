# qitech_mock/http.py
import json
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

def bearer_ok(request) -> bool:
    auth = request.headers.get("Authorization","")
    return auth.startswith("Bearer ") and len(auth.split(" ",1)[1]) > 0

def parse_json(request):
    if request.body in (b"", None):
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return None

def ok(data, status=200):
    return JsonResponse(data, status=status, safe=False)

def err(msg, status=400, extra=None):
    body = {"title":"error", "description":msg}
    if extra: body["extra_fields"]=extra
    return JsonResponse(body, status=status, safe=False)

def method_guard(request, allowed: set[str]):
    if request.method not in allowed:
        return HttpResponse(status=405)
