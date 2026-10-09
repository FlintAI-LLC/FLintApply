"""Daily anonymous product surface counters (landing, web app, extension)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyProductMetric(Base):
    """One row per UTC calendar day and metric key; incremented by public beacons."""

    __tablename__ = "daily_product_metrics"

    metric_date: Mapped[date] = mapped_column(Date, primary_key=True)
    metric_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


__all__ = ["DailyProductMetric"]
