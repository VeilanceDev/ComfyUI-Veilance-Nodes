"""
Small HTTP helpers shared by network-backed nodes.
"""

from __future__ import annotations

from typing import BinaryIO
import urllib.request


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_ERROR_BODY_LIMIT_BYTES = 64 * 1024


def read_stream_limited(
    stream: BinaryIO,
    *,
    max_bytes: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> bytes:
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break

        total += len(chunk)
        if total > max_bytes:
            raise RuntimeError(
                f"HTTP response exceeded the maximum size of {max_bytes} bytes."
            )
        chunks.append(chunk)

    return b"".join(chunks)


def read_url_limited(
    request: urllib.request.Request | str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int,
) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return read_stream_limited(response, max_bytes=max_bytes)


def read_http_error_body(
    error: Exception,
    *,
    max_bytes: int = DEFAULT_ERROR_BODY_LIMIT_BYTES,
) -> str:
    read = getattr(error, "read", None)
    if not callable(read):
        return ""

    try:
        body = read_stream_limited(error, max_bytes=max_bytes)
    except Exception:
        return ""
    return body.decode("utf-8", errors="replace")

