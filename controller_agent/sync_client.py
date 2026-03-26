from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error, parse, request


class SyncClientError(Exception):
    pass


class SyncClient:
    def __init__(self, base_url: str, timeout_seconds: float = 2.0):
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        raw_body: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if payload is not None and raw_body is not None:
            raise ValueError("Provide either payload or raw_body, not both")

        request_headers: Dict[str, str] = dict(headers or {})
        body = raw_body
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        req = request.Request(
            url=f"{self._base_url}{path}",
            data=body,
            headers=request_headers,
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

    def upload_library_files(self, device_id: str, file_paths: list[Path]) -> Dict[str, Any]:
        boundary = f"----mp3player{uuid.uuid4().hex}"
        body_parts: list[bytes] = []

        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(b'Content-Disposition: form-data; name="device_id"\r\n\r\n')
        body_parts.append(device_id.encode("utf-8"))
        body_parts.append(b"\r\n")

        for file_path in file_paths:
            filename = file_path.name
            file_bytes = file_path.read_bytes()
            body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
            body_parts.append(
                f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode("utf-8")
            )
            body_parts.append(b"Content-Type: audio/mpeg\r\n\r\n")
            body_parts.append(file_bytes)
            body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(body_parts)
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self._request("POST", "/v1/library/upload", raw_body=body, headers=headers)

    def reconcile_library(self, device_id: str, filenames: list[str]) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/v1/library/reconcile",
            payload={"device_id": device_id, "files": filenames},
        )
