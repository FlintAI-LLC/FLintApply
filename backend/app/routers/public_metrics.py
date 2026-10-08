"""Anonymous daily product surface beacons (no PII)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.limiter import limiter
from app.services.admin.reporting import PUBLIC_METRIC_KEYS, increment_daily_metric

router = APIRouter(prefix="/api/public/metrics", tags=["public-metrics"])

BeaconKey = Literal[
    "landing_view",
    "auth_page_view",
    "web_app_view",
    "extension_open",
]


class MetricBeaconRequest(BaseModel):
    key: BeaconKey = Field(description="Surface identifier")


@router.post("/beacon")
@limiter.limit("60/minute")
async def record_metric_beacon(
    request: Request,
    body: MetricBeaconRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, bool]:
    if body.key not in PUBLIC_METRIC_KEYS:
        return {"ok": False}
    await increment_daily_metric(db, body.key)
    await db.commit()
    return {"ok": True}
