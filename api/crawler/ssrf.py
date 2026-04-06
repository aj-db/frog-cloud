"""SSRF-safe URL validation for crawl targets."""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

_METADATA_HOST_PATTERNS = (
    re.compile(r"^metadata\.google\.internal$", re.I),
    re.compile(r"^metadata$", re.I),
    re.compile(r"^169\.254\.169\.254$"),
    re.compile(r"^metadata\.gce\.internal$", re.I),
)


class UnsafeUrlError(ValueError):
    """Raised when a URL is not allowed as a crawl target."""


def _is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_reserved:
        return True
    for net in _PRIVATE_NETWORKS:
        if ip in net:
            return True
    return False


def _hostname_blocked(hostname: str) -> bool:
    h = hostname.strip().lower().rstrip(".")
    for pat in _METADATA_HOST_PATTERNS:
        if pat.match(h):
            return True
    if h.endswith(".internal") and "metadata" in h:
        return True
    return False


def validate_public_http_url(url: str) -> str:
    """
    Ensure URL uses http(s), is not obviously private, and resolves only to public IPs.

    Raises:
        UnsafeUrlError: if validation fails.
    """
    raw = url.strip()
    if not raw:
        raise UnsafeUrlError("URL is empty")

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError("Only http and https URLs are allowed")

    if not parsed.hostname:
        raise UnsafeUrlError("URL must include a hostname")

    host = parsed.hostname
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]

    if _hostname_blocked(host):
        raise UnsafeUrlError("Host is blocked")

    # Reject file://-style paths smuggled in odd schemes (already limited to http/https)
    if "\\" in raw:
        raise UnsafeUrlError("URL contains invalid characters")

    # Literal IP in URL
    try:
        ip = ipaddress.ip_address(host)
        if _is_private_ip(ip):
            raise UnsafeUrlError("IP address is not publicly routable")
        return raw
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeUrlError(f"Could not resolve host: {e}") from e

    if not infos:
        raise UnsafeUrlError("Host resolved to no addresses")

    for info in infos:
        sockaddr = info[4]
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_private_ip(ip):
            raise UnsafeUrlError("Host resolves to a private or non-routable address")

    return raw
