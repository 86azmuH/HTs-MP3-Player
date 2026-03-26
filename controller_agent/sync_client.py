from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib import error, parse, request


class SyncClientError(Exception):
    pass


class SyncClient:
    def __init__(self, base_url: str, timeout_seconds: float = 2.0):
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = request.Request(
            url=f"{self._base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as resp:
                raw = resp.read().decode("utf-8") or "{}"
                return json.loads(raw)
        except error.HTTPError as exc:
            payload_text = exc.read().decode("utf-8") if exc.fp else ""
            raise SyncClientError(f"HTTP {exc.code}: {payload_text}") from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise SyncClientError(str(exc)) from exc

    def pull(self, device_id: str, since_version: Optional[int]) -> Dict[str, Any]:
        query = {"device_id": device_id}
        if since_version is not None:
            query["since_version"] = str(int(since_version))
        qs = parse.urlencode(query)
        return self._request("GET", f"/v1/sync/pull?{qs}")

    def push(self, device_id: str, base_version: Optional[int], state: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "device_id": device_id,
            "state": state,
        }
        if base_version is not None:
            payload["base_version"] = int(base_version)
        return self._request("POST", "/v1/sync/push", payload=payload)
