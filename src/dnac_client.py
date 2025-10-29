from __future__ import annotations

import time
import requests
from typing import Any, Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

class DNACClient:
    # Minimal client for Catalyst Center (DNA Center) APIs.
    # - Auth via POST /dna/system/api/v1/auth/token using basic auth (username/password).
    # - Automatically injects the token in subsequent requests.
    # - Handles pagination for common list endpoints.

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify: bool = False,
        timeout: int = 30,
        proxies: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify = verify
        self.timeout = timeout
        self.proxies = proxies
        self._token: Optional[str] = None
        self._token_ts: float = 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _request_token(self) -> str:
        url = f"{self.base_url}/dna/system/api/v1/auth/token"
        resp = requests.post(
            url,
            auth=(self.username, self.password),
            verify=self.verify,
            timeout=self.timeout,
            proxies=self.proxies,
        )
        resp.raise_for_status()
        token = resp.json().get("Token")
        if not token:
            raise RuntimeError("No Token in auth response")
        self._token = token
        self._token_ts = time.time()
        return token

    def _ensure_token(self) -> str:
        # Token lifetime on Catalyst Center is typically ~1 hour; refresh defensively at 45 mins
        if not self._token or (time.time() - self._token_ts) > 45 * 60:
            return self._request_token()
        return self._token

    def _headers(self) -> Dict[str, str]:
        token = self._ensure_token()
        return {"X-Auth-Token": token, "Content-Type": "application/json"}

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = requests.get(
            url, headers=self._headers(), params=params, verify=self.verify,
            timeout=self.timeout, proxies=self.proxies
        )
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = requests.post(
            url, headers=self._headers(), json=json_body, verify=self.verify,
            timeout=self.timeout, proxies=self.proxies
        )
        resp.raise_for_status()
        return resp.json()

    def paginate(self, path: str, params: Optional[Dict[str, Any]] = None, key: str = "response") -> List[Dict[str, Any]]:
        # Handle DNA Center style pagination (offset/limit) when possible.
        params = dict(params or {})
        items: List[Dict[str, Any]] = []

        offset = 1
        limit = params.pop("limit", 500)

        while True:
            page_params = dict(params)
            page_params.update({"offset": offset, "limit": limit})
            data = self.get(path, params=page_params)
            page_items = data.get(key) or data.get("result") or []
            if not page_items:
                break
            items.extend(page_items)
            if len(page_items) < limit:
                break
            offset += limit
        return items