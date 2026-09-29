"""Poll failure handling, deactivation scope, host concurrency, and fetch circuit rules."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.career_watch import CareerAtsType, WatchedCompany
from app.services.career_watch import fetch as fetch_mod
from app.services.career_watch import poller
from app.services.career_watch.fetch import CareerWatchFetchError, fetch_json
from app.services.career_watch.job_corpus_seed import STALE_FAIL_DEACTIVATE

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)


def _company(*, seed: bool, fails: int = 0, host: str = "boards.greenhouse.io") -> WatchedCompany:
    return WatchedCompany(
        id=uuid.uuid4(),
        name="Acme",
        slug=f"acme-{uuid.uuid4().hex[:6]}",
        careers_page_url=f"https://{host}/acme",
        ats_type=CareerAtsType.greenhouse,
        ats_board_token="acme",
        is_global_seed=seed,
        is_active=True,
        poll_fail_count=fails,
    )


def _status_error(code: int) -> CareerWatchFetchError:
    request = httpx.Request("GET", "https://boards-api.greenhouse.io/v1/boards/acme/jobs")
    response = httpx.Response(code, request=request)
    cause = httpx.HTTPStatusError("boom", request=request, response=response)
    err = CareerWatchFetchError(str(cause))
    err.__cause__ = cause
    return err


def _timeout_error() -> CareerWatchFetchError:
    err = CareerWatchFetchError("timeout")
    err.__cause__ = httpx.ReadTimeout("t")
    return err


class _Savepoint:
    async def __aenter__(self) -> "_Savepoint":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _session() -> AsyncMock:
    session = AsyncMock()
    session.begin_nested = MagicMock(side_effect=lambda: _Savepoint())
    session.scalar = AsyncMock(return_value=False)  # no active user watch by default
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [404, 410])
async def test_global_seed_deactivated_at_threshold_on_gone_status(code: int) -> None:
    company = _company(seed=True, fails=STALE_FAIL_DEACTIVATE - 1)
    await poller._record_poll_failure(_session(), company, _status_error(code), now=NOW)
    assert company.poll_fail_count == STALE_FAIL_DEACTIVATE
    assert company.is_active is False


@pytest.mark.asyncio
async def test_seed_watched_by_a_user_is_never_deactivated() -> None:
    session = _session()
    session.scalar = AsyncMock(return_value=True)
    company = _company(seed=True, fails=STALE_FAIL_DEACTIVATE + 3)

    await poller._record_poll_failure(session, company, _status_error(404), now=NOW)

    assert company.is_active is True
    assert company.poll_fail_count == STALE_FAIL_DEACTIVATE + 4


@pytest.mark.asyncio
async def test_forbidden_is_not_treated_as_gone() -> None:
    company = _company(seed=True, fails=STALE_FAIL_DEACTIVATE + 3)
    await poller._record_poll_failure(_session(), company, _status_error(403), now=NOW)
    assert company.is_active is True


@pytest.mark.asyncio
async def test_forbidden_still_counts_toward_host_circuit() -> None:
    fetch_mod.reset_fetch_circuits_for_tests()
    url = "https://boards-api.greenhouse.io/v1/boards/blocked/jobs"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for _ in range(fetch_mod.CIRCUIT_FAILURE_THRESHOLD):
            with pytest.raises(CareerWatchFetchError):
                await fetch_json(client, url)
    assert fetch_mod._circuit_open("boards-api.greenhouse.io")
    fetch_mod.reset_fetch_circuits_for_tests()


@pytest.mark.asyncio
async def test_global_seed_not_deactivated_below_threshold() -> None:
    company = _company(seed=True, fails=STALE_FAIL_DEACTIVATE - 2)
    await poller._record_poll_failure(_session(), company, _status_error(404), now=NOW)
    assert company.is_active is True


@pytest.mark.asyncio
async def test_user_watch_company_never_deactivated() -> None:
    company = _company(seed=False, fails=STALE_FAIL_DEACTIVATE + 10)
    await poller._record_poll_failure(_session(), company, _status_error(404), now=NOW)
    assert company.is_active is True


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [_status_error(500), _status_error(429), _timeout_error()])
async def test_transient_errors_never_deactivate(error: CareerWatchFetchError) -> None:
    company = _company(seed=True, fails=STALE_FAIL_DEACTIVATE + 10)
    await poller._record_poll_failure(_session(), company, error, now=NOW)
    assert company.is_active is True


@pytest.mark.asyncio
async def test_poll_due_companies_counts_failure_and_deactivates() -> None:
    dead = _company(seed=True, fails=STALE_FAIL_DEACTIVATE - 1)
    live = _company(seed=True)

    async def fake_fetch(company: WatchedCompany, *, client: httpx.AsyncClient):
        if company is dead:
            raise _status_error(404)
        return []

    with (
        patch.object(poller, "_due_companies_global_then_watchlist", AsyncMock(return_value=[dead, live])),
        patch.object(poller, "fetch_company_jobs", side_effect=fake_fetch),
        patch.object(poller, "sync_polled_jobs_to_caches", AsyncMock(return_value=0)),
        patch.object(poller, "poll_enabled_aggregators", AsyncMock(return_value=poller.PollStats())),
        patch.object(poller, "_HOST_DELAY_SECONDS", 0),
    ):
        stats = await poller.poll_due_companies(_session(), limit=10, now=NOW)

    assert stats.failures == 1
    assert stats.companies_polled == 1
    assert dead.is_active is False
    assert live.is_active is True
    assert live.last_polled_at == NOW


@pytest.mark.asyncio
async def test_host_concurrency_is_bounded() -> None:
    companies = [_company(seed=True, host="api.smartrecruiters.com") for _ in range(20)]
    limit = poller._HOST_LIMITS["api.smartrecruiters.com"]
    running = 0
    peak = 0

    async def fake_fetch(company: WatchedCompany, *, client: httpx.AsyncClient):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return []

    with (
        patch.object(poller, "_due_companies_global_then_watchlist", AsyncMock(return_value=companies)),
        patch.object(poller, "fetch_company_jobs", side_effect=fake_fetch),
        patch.object(poller, "sync_polled_jobs_to_caches", AsyncMock(return_value=0)),
        patch.object(poller, "poll_enabled_aggregators", AsyncMock(return_value=poller.PollStats())),
        patch.object(poller, "_HOST_DELAY_SECONDS", 0),
    ):
        stats = await poller.poll_due_companies(_session(), limit=50, now=NOW)

    assert stats.companies_polled == 20
    assert 1 < peak <= limit


@pytest.mark.asyncio
async def test_sequential_upserts_after_parallel_fetch() -> None:
    companies = [_company(seed=True) for _ in range(6)]
    in_upsert = 0
    overlap = False

    async def fake_sync(session, company, jobs, *, now):
        nonlocal in_upsert, overlap
        in_upsert += 1
        if in_upsert > 1:
            overlap = True
        await asyncio.sleep(0.005)
        in_upsert -= 1
        return 0

    with (
        patch.object(poller, "_due_companies_global_then_watchlist", AsyncMock(return_value=companies)),
        patch.object(poller, "fetch_company_jobs", AsyncMock(return_value=[])),
        patch.object(poller, "sync_polled_jobs_to_caches", side_effect=fake_sync),
        patch.object(poller, "poll_enabled_aggregators", AsyncMock(return_value=poller.PollStats())),
        patch.object(poller, "_HOST_DELAY_SECONDS", 0),
    ):
        await poller.poll_due_companies(_session(), limit=50, now=NOW)

    assert overlap is False


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [404, 410])
async def test_gone_board_does_not_open_host_circuit(code: int) -> None:
    fetch_mod.reset_fetch_circuits_for_tests()
    url = "https://boards-api.greenhouse.io/v1/boards/dead/jobs"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for _ in range(fetch_mod.CIRCUIT_FAILURE_THRESHOLD + 3):
            with pytest.raises(CareerWatchFetchError):
                await fetch_json(client, url)
    assert not fetch_mod._circuit_open("boards-api.greenhouse.io")


@pytest.mark.asyncio
async def test_server_errors_still_open_host_circuit() -> None:
    fetch_mod.reset_fetch_circuits_for_tests()
    url = "https://boards-api.greenhouse.io/v1/boards/x/jobs"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for _ in range(fetch_mod.CIRCUIT_FAILURE_THRESHOLD):
            with pytest.raises(CareerWatchFetchError):
                await fetch_json(client, url)
    assert fetch_mod._circuit_open("boards-api.greenhouse.io")
    fetch_mod.reset_fetch_circuits_for_tests()
