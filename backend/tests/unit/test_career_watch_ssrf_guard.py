"""SSRF guard for Career Watch outbound fetches."""

import ipaddress
import pytest

from app.services.career_watch.ssrf_guard import (
    CareerWatchSsrfError,
    assert_url_safe,
    is_public_ip,
)


def test_is_public_ip_rejects_metadata_address() -> None:
    assert not is_public_ip(ipaddress.ip_address("169.254.169.254"))


def test_is_public_ip_rejects_localhost() -> None:
    assert not is_public_ip(ipaddress.ip_address("127.0.0.1"))
    assert not is_public_ip(ipaddress.ip_address("::1"))


def test_is_public_ip_rejects_private_ranges() -> None:
    assert not is_public_ip(ipaddress.ip_address("10.0.0.1"))
    assert not is_public_ip(ipaddress.ip_address("172.16.0.1"))
    assert not is_public_ip(ipaddress.ip_address("192.168.1.1"))


def test_is_public_ip_allows_public() -> None:
    assert is_public_ip(ipaddress.ip_address("8.8.8.8"))


def test_assert_url_safe_rejects_localhost_hostname() -> None:
    with pytest.raises(CareerWatchSsrfError):
        assert_url_safe("http://localhost/jobs")


def test_assert_url_safe_rejects_non_http_scheme() -> None:
    with pytest.raises(CareerWatchSsrfError):
        assert_url_safe("file:///etc/passwd")


def test_assert_url_safe_rejects_ip_literal_localhost() -> None:
    with pytest.raises(CareerWatchSsrfError):
        assert_url_safe("http://127.0.0.1/jobs")


def test_assert_url_safe_rejects_non_standard_port() -> None:
    with pytest.raises(CareerWatchSsrfError):
        assert_url_safe("http://example.com:6379/jobs")
