# consign_app/integrations/qitech_local.py
import requests
from typing import Optional, Dict, Any
from django.urls import reverse

MOCK_BEARER_FALLBACK = "mock-access-token"

class QiTechLocal:
    def __init__(self, request, *, user_uuid: Optional[str] = None):
        self.request = request
        self.user_uuid = user_uuid

    def _abs(self, name: str, **kwargs) -> str:
        return self.request.build_absolute_uri(reverse(f"qitech_mock:{name}", kwargs=kwargs or {}))

    def _headers(self, *, idem: Optional[str] = None) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        auth = self.request.META.get("HTTP_AUTHORIZATION")
        h["Authorization"] = auth if auth else f"Bearer {MOCK_BEARER_FALLBACK}"
        if self.user_uuid:
            h["X-User-UUID"] = str(self.user_uuid)
        if idem:
            h["Idempotency-Key"] = idem
        return h

    def post(self, name: str, json: Dict[str, Any], *, idem: Optional[str] = None, **kwargs):
        url = self._abs(name, **kwargs)
        return requests.post(url, json=json, headers=self._headers(idem=idem), timeout=10)

    def get(self, name: str, params: Optional[Dict[str, Any]] = None, **kwargs):
        url = self._abs(name, **kwargs)
        return requests.get(url, params=params or {}, headers=self._headers(), timeout=10)
