from __future__ import annotations

import json
import uuid
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


def encode_multipart(fields: dict[str, str], files: dict[str, tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = f"----ShinobuChat{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
            str(value).encode("utf-8"),
            b"\r\n",
        ])
    for name, (filename, content_type, content) in files.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            content,
            b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), boundary


def extract_text(data: object) -> str:
    if isinstance(data, dict):
        for key in ("text", "result", "transcript", "sentence"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (dict, list)):
                text = extract_text(value)
                if text:
                    return text
        for value in data.values():
            text = extract_text(value)
            if text:
                return text
    if isinstance(data, list):
        return " ".join(filter(None, (extract_text(item) for item in data))).strip()
    return ""


class UrllibHttpClient:
    def request_bytes(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout: int = 60,
        max_download_bytes: int | None = None,
        allow_internal_ips: bool = True,
    ) -> HttpResponse:
        if not allow_internal_ips:
            from app.core.url_validation import validate_url_safe

            validate_url_safe(url)

        req = request.Request(url, data=body, headers=headers or {}, method=method)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                media_type = resp.headers.get_content_type()
                if max_download_bytes is not None:
                    content_length = resp.headers.get("Content-Length")
                    if content_length is not None and int(content_length) > max_download_bytes:
                        raise HttpTransportError(
                            f"Response exceeds maximum size of {max_download_bytes} bytes"
                        )
                    body = resp.read(min(max_download_bytes + 1, 10 * 1024 * 1024))
                    if len(body) > max_download_bytes:
                        raise HttpTransportError(
                            f"Response exceeds maximum size of {max_download_bytes} bytes"
                        )
                else:
                    body = resp.read()
                return HttpResponse(body=body, media_type=media_type)
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
