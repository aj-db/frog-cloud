"""Helpers for deriving external-facing URLs behind a proxy."""

from __future__ import annotations

from fastapi import Request
from starlette.datastructures import Headers, URL


def externalize_url(url: URL, headers: Headers) -> str:
    forwarded_proto = headers.get("x-forwarded-proto")
    if forwarded_proto:
        scheme = forwarded_proto.split(",", 1)[0].strip()
        if scheme:
            url = url.replace(scheme=scheme)
    return str(url)


def request_url(request: Request) -> str:
    return externalize_url(request.url, request.headers)
