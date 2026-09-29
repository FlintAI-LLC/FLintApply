"""Integration: job API returns normalized descriptions (no raw HTML)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.jobs import JobCache
from app.services.jobs.cache_writer import upsert_job_cache
from tests.integration.test_auth import REGISTER_PAYLOAD

pytestmark = pytest.mark.integration


async def _register(client: AsyncClient) -> str:
    payload = {**REGISTER_PAYLOAD, "email": f"jd-{uuid.uuid4().hex[:8]}@example.com"}
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_get_job_by_id_description_has_no_html_tags(
    app_client: AsyncClient,
    db_session,
) -> None:
    now = datetime.now(timezone.utc)
    job_id = uuid.uuid4()
    record = {
        "sources": ["corpus"],
        "external_ids": {"corpus": "ext-1"},
        "title": "Backend Engineer",
        "company": "Acme",
        "company_normalized": "acme",
        "location": "Remote",
        "location_city": None,
        "location_country": None,
        "remote": True,
        "salary_min_usd": None,
        "salary_max_usd": None,
        "salary_currency_original": None,
        "employment_type": "",
        "posted_date": now,
        "description": "<div><p>Build APIs</p><ul><li>Python</li></ul></div>",
        "apply_url": "https://example.com/jobs/1",
        "raw_json": {"vendor": "unchanged"},
        "cached_at": now,
        "expires_at": now + timedelta(days=7),
        "dedup_key": f"integration-normalize-{job_id.hex[:8]}",
        "first_seen_at": now,
        "last_seen_at": now,
        "is_active": True,
    }
    row = await upsert_job_cache(db_session, record)
    await db_session.commit()

    token = await _register(app_client)
    resp = await app_client.get(
        f"/api/jobs/{row.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    desc = resp.json()["description"]
    assert "Build APIs" in desc
    assert "- Python" in desc
    assert "<" not in desc
