"""SSRF guard for Career Watch outbound HTTP and headless navigation."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import structlog

log = structlog.get_logger("career_watch.ssrf_guard")

METADATA_IPV4 = "169.254.169.254"


class CareerWatchSsrfError(ValueError):
    """Raised when a URL targets a disallowed host or address."""


_EXTRA_BLOCKED_IPV4 = frozenset(
    {
        "100.100.100.200",  # Alibaba metadata
        "168.63.129.16",  # Azure WireServer
    }
)


def is_public_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True when ``addr`` is safe to fetch (public, non-special)."""
    if str(addr) in _EXTRA_BLOCKED_IPV4 or str(addr) == METADATA_IPV4:
        return False
    if not addr.is_global:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return is_public_ip(addr.ipv4_mapped)
    return True


def validate_url_scheme(url: str) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise CareerWatchSsrfError(f"unsupported URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise CareerWatchSsrfError("URL missing hostname")


def _resolve_host_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(
            host,
            None,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise CareerWatchSsrfError(f"DNS resolution failed for {host!r}") from exc
    if not infos:
        raise CareerWatchSsrfError(f"no addresses for host {host!r}")
    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    seen: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_str = sockaddr[0]
        if ip_str in seen:
            continue
        seen.add(ip_str)
        try:
            addrs.append(ipaddress.ip_address(ip_str))
        except ValueError:
            continue
    if not addrs:
        raise CareerWatchSsrfError(f"no parseable addresses for host {host!r}")
    return addrs


def assert_host_ips_public(host: str) -> None:
    """Resolve ``host`` and reject private/special IPs."""
    for addr in _resolve_host_ips(host):
        if not is_public_ip(addr):
            raise CareerWatchSsrfError(
                f"blocked address {addr} for host {host!r}"
            )


def assert_url_safe(url: str) -> None:
    """Validate scheme and resolved IPs for ``url`` (sync)."""
    validate_url_scheme(url)
    parsed = urlparse(url.strip())
    host = parsed.hostname
    if host is None:
        raise CareerWatchSsrfError("URL missing hostname")
    if host.lower() in {"localhost", "metadata.google.internal"}:
        raise CareerWatchSsrfError(f"blocked hostname {host!r}")
    port = parsed.port
    if port is not None and port not in {80, 443}:
        raise CareerWatchSsrfError(f"blocked port {port}")
    assert_host_ips_public(host)


async def assert_url_safe_async(url: str) -> None:
    """Async wrapper around DNS + IP checks (runs resolution in a thread)."""
    await asyncio.to_thread(assert_url_safe, url)


__all__ = [
    "CareerWatchSsrfError",
    "assert_host_ips_public",
    "assert_url_safe",
    "assert_url_safe_async",
    "is_public_ip",
    "validate_url_scheme",
]
