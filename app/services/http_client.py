from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator
from urllib import error, request


@dataclass(frozen=True)
class HttpResponse:
    body: bytes
    media_type: str | None = None


class HttpClientError(Exception):
    pass


class HttpStatusError(HttpClientError):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class HttpTransportError(HttpClientError):
    pass


class UrllibHttpClient:
    def request_bytes(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout: int = 60,
    ) -> HttpResponse:
        req = request.Request(url, data=body, headers=headers or {}, method=method)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                media_type = resp.headers.get_content_type()
                return HttpResponse(body=resp.read(), media_type=media_type)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HttpStatusError(detail) from exc
        except (error.URLError, TimeoutError) as exc:
            raise HttpTransportError(str(exc)) from exc

    def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: dict | None = None,
        timeout: int = 60,
    ) -> dict:
        encoded_body = None
        request_headers = dict(headers or {})
        if body is not None:
            encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        response = self.request_bytes(
            url,
            method=method,
            headers=request_headers,
            body=encoded_body,
            timeout=timeout,
        )
        try:
            data = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HttpTransportError(f"Invalid JSON response: {exc}") from exc
        if not isinstance(data, dict):
            raise HttpTransportError("JSON response must be an object")
        return data

    def stream_lines(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: dict | None = None,
        timeout: int = 60,
    ) -> Iterator[bytes]:
        encoded_body = None
        request_headers = dict(headers or {})
        if body is not None:
            encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        req = request.Request(url, data=encoded_body, headers=request_headers, method=method)
        try:
            resp = request.urlopen(req, timeout=timeout)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HttpStatusError(detail) from exc
        except (error.URLError, TimeoutError) as exc:
            raise HttpTransportError(str(exc)) from exc

        buffer = b""
        try:
            while True:
                data = resp.read(4096)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    yield line.strip()
        finally:
            resp.close()
