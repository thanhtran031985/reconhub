"""Tiện ích nén HTTP (Gzip) và Cache-Control cho Flask server của ReconHub."""

from __future__ import annotations

import gzip
from typing import Final

from flask import Flask, Response, request

_MIN_GZIP_BYTES: Final[int] = 512
_COMPRESSIBLE_MIMETYPES: Final[frozenset[str]] = frozenset(
    {
        "application/javascript",
        "text/javascript",
        "application/x-javascript",
        "application/json",
        "application/xml",
        "image/svg+xml",
    }
)


def _is_compressible_mimetype(mimetype: str | None) -> bool:
    mt = (mimetype or "").lower()
    return mt.startswith("text/") or mt in _COMPRESSIBLE_MIMETYPES


def _apply_cache_control(response: Response) -> None:
    """Đặt Cache-Control chuẩn cho static assets và API/HTML động."""
    if response.status_code != 200:
        return

    path = request.path or ""
    if path.startswith("/_dash-component-suites/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return

    if path.startswith("/assets/"):
        if "m" in request.args or "v" in request.args:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=86400"
        return

    if path == "/_dash-update-component" and "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"


def _maybe_gzip_response(response: Response) -> None:
    """Nén Gzip cho response văn bản/JS/CSS/JSON đủ lớn khi client chấp nhận."""
    if response.status_code != 200 or request.method == "HEAD":
        return
    if "Content-Encoding" in response.headers:
        return
    disposition = response.headers.get("Content-Disposition", "")
    if disposition.lower().startswith("attachment"):
        return
    if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
        return
    if not _is_compressible_mimetype(response.mimetype):
        return

    response.direct_passthrough = False
    raw = response.get_data()
    if len(raw) < _MIN_GZIP_BYTES:
        return

    compressed = gzip.compress(raw, compresslevel=6)
    if len(compressed) >= len(raw):
        return

    response.set_data(compressed)
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(compressed))
    response.vary.add("Accept-Encoding")
    etag = response.headers.get("ETag")
    if etag and not etag.endswith("-gzip\"") and not etag.endswith("-gzip"):
        stripped = etag.removeprefix("W/").strip('"')
        response.headers["ETag"] = f'W/"{stripped}-gzip"'


def register_http_optimizations(flask_server: Flask) -> None:
    """Đăng ký after_request hook để bật Cache-Control và Gzip trên Flask server."""

    @flask_server.after_request
    def _optimize_http_response(response: Response) -> Response:
        _apply_cache_control(response)
        _maybe_gzip_response(response)
        return response
