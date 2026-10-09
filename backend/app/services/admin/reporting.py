"""Admin monitoring aggregates (DAU/WAU/MAU, funnel, web vs extension)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Subscription, SubscriptionStatus
from app.models.dashboard import ResumeRecord
from app.models.product_metrics import DailyProductMetric
from app.models.tracker import Application
from app.models.user import (
    AuthAuditEvent,
    AuthAuditLog,
    CreditTransaction,
    CreditTransactionAction,
    User,
)

PUBLIC_METRIC_KEYS = frozenset(
    {
        "landing_view",
        "auth_page_view",
        "web_app_view",
        "extension_open",
    }
)

_ACTIVE_SUB_STATUSES = (
    SubscriptionStatus.active,
    SubscriptionStatus.trialing,
    SubscriptionStatus.grace,
    SubscriptionStatus.cancel_at_period_end,
)


def _utc_day(dt: datetime) -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def _parse_report_dates(from_str: str, to_str: str) -> tuple[date, date]:
    try:
        start = date.fromisoformat(from_str.strip())
        end = date.fromisoformat(to_str.strip())
    except ValueError as exc:
        raise ValueError("from and to must be YYYY-MM-DD") from exc
    if end < start:
        raise ValueError("to must be on or after from")
    if (end - start).days > 366:
        raise ValueError("date range must be at most 366 days")
    return start, end


def _date_range(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _login_channel(metadata: dict[str, Any] | None) -> str:
    if (metadata or {}).get("source") == "extension":
        return "extension"
    return "web"


async def increment_daily_metric(
    db: AsyncSession,
    metric_key: str,
    *,
    metric_date: date | None = None,
) -> None:
    if metric_key not in PUBLIC_METRIC_KEYS:
        return
    day = metric_date or datetime.now(timezone.utc).date()
    stmt = (
        insert(DailyProductMetric)
        .values(metric_date=day, metric_key=metric_key, count=1)
        .on_conflict_do_update(
            index_elements=[DailyProductMetric.metric_date, DailyProductMetric.metric_key],
            set_={"count": DailyProductMetric.count + 1},
        )
    )
    await db.execute(stmt)
    await db.flush()


async def _fetch_login_events(
    db: AsyncSession,
    window_start: datetime,
    window_end: datetime,
) -> list[tuple[date, uuid.UUID, str]]:
    rows = (
        await db.execute(
            select(
                AuthAuditLog.created_at,
                AuthAuditLog.user_id,
                AuthAuditLog.event_metadata,
            ).where(
                AuthAuditLog.event == AuthAuditEvent.login_success,
                AuthAuditLog.user_id.is_not(None),
                AuthAuditLog.created_at >= window_start,
                AuthAuditLog.created_at < window_end,
            )
        )
    ).all()
    out: list[tuple[date, uuid.UUID, str]] = []
    for created_at, user_id, meta in rows:
        if user_id is None:
            continue
        out.append((_utc_day(created_at), user_id, _login_channel(meta)))
    return out


async def _registrations_by_day(
    db: AsyncSession,
    start: date,
    end: date,
) -> dict[date, int]:
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    rows = (
        await db.execute(
            select(func.date_trunc("day", User.created_at), func.count())
            .where(User.created_at >= start_dt, User.created_at < end_dt)
            .group_by(func.date_trunc("day", User.created_at))
        )
    ).all()
    return {row[0].date(): int(row[1]) for row in rows}


async def _beacon_counts_by_day(
    db: AsyncSession,
    start: date,
    end: date,
) -> dict[str, dict[date, int]]:
    rows = (
        await db.execute(
            select(
                DailyProductMetric.metric_key,
                DailyProductMetric.metric_date,
                DailyProductMetric.count,
            ).where(
                DailyProductMetric.metric_date >= start,
                DailyProductMetric.metric_date <= end,
            )
        )
    ).all()
    out: dict[str, dict[date, int]] = defaultdict(dict)
    for key, day, count in rows:
        out[key][day] = int(count)
    return out


async def build_activity_metrics(
    db: AsyncSession,
    from_str: str,
    to_str: str,
) -> list[dict[str, Any]]:
    start, end = _parse_report_dates(from_str, to_str)
    days = _date_range(start, end)
    lookback_start = start - timedelta(days=29)
    window_start = datetime.combine(lookback_start, datetime.min.time(), tzinfo=timezone.utc)
    window_end = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    logins = await _fetch_login_events(db, window_start, window_end)
    by_day_users: dict[date, set[uuid.UUID]] = defaultdict(set)
    by_day_web: dict[date, set[uuid.UUID]] = defaultdict(set)
    by_day_ext: dict[date, set[uuid.UUID]] = defaultdict(set)
    for day, uid, channel in logins:
        by_day_users[day].add(uid)
        if channel == "extension":
            by_day_ext[day].add(uid)
        else:
            by_day_web[day].add(uid)

    registrations = await _registrations_by_day(db, start, end)
    beacons = await _beacon_counts_by_day(db, start, end)
    landing = beacons.get("landing_view", {})

    metrics: list[dict[str, Any]] = []
    for day in days:
        wau_users: set[uuid.UUID] = set()
        mau_users: set[uuid.UUID] = set()
        for offset in range(7):
            wau_users |= by_day_users.get(day - timedelta(days=offset), set())
        for offset in range(30):
            mau_users |= by_day_users.get(day - timedelta(days=offset), set())
        metrics.append(
            {
                "date": day.isoformat(),
                "dau": len(by_day_users.get(day, set())),
                "dau_web": len(by_day_web.get(day, set())),
                "dau_extension": len(by_day_ext.get(day, set())),
                "wau": len(wau_users),
                "mau": len(mau_users),
                "new_registrations": registrations.get(day, 0),
                "landing_views": landing.get(day, 0),
            }
        )
    return metrics


async def build_channel_metrics(
    db: AsyncSession,
    from_str: str,
    to_str: str,
) -> list[dict[str, Any]]:
    start, end = _parse_report_dates(from_str, to_str)
    days = _date_range(start, end)
    window_start = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    window_end = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    logins = await _fetch_login_events(db, window_start, window_end)
    by_day_web: dict[date, set[uuid.UUID]] = defaultdict(set)
    by_day_ext: dict[date, set[uuid.UUID]] = defaultdict(set)
    for day, uid, channel in logins:
        if channel == "extension":
            by_day_ext[day].add(uid)
        else:
            by_day_web[day].add(uid)

    beacons = await _beacon_counts_by_day(db, start, end)
    web_beacon = beacons.get("web_app_view", {})
    ext_beacon = beacons.get("extension_open", {})

    return [
        {
            "date": day.isoformat(),
            "logins_web": len(by_day_web.get(day, set())),
            "logins_extension": len(by_day_ext.get(day, set())),
            "beacon_web_app": web_beacon.get(day, 0),
            "beacon_extension": ext_beacon.get(day, 0),
        }
        for day in days
    ]


async def build_funnel_metrics(
    db: AsyncSession,
    from_str: str,
    to_str: str,
) -> dict[str, int]:
    start, end = _parse_report_dates(from_str, to_str)
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    registered = int(
        (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.created_at >= start_dt, User.created_at < end_dt)
            )
        ).scalar()
        or 0
    )

    email_verified = int(
        (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.created_at >= start_dt,
                    User.created_at < end_dt,
                    User.email_verified_at.is_not(None),
                )
            )
        ).scalar()
        or 0
    )

    first_build = int(
        (
            await db.execute(
                select(func.count(func.distinct(User.id)))
                .select_from(User)
                .join(ResumeRecord, ResumeRecord.user_id == User.id)
                .where(User.created_at >= start_dt, User.created_at < end_dt)
            )
        ).scalar()
        or 0
    )

    first_export = int(
        (
            await db.execute(
                select(func.count(func.distinct(User.id)))
                .select_from(User)
                .join(CreditTransaction, CreditTransaction.user_id == User.id)
                .where(
                    User.created_at >= start_dt,
                    User.created_at < end_dt,
                    CreditTransaction.action == CreditTransactionAction.resume_build,
                )
            )
        ).scalar()
        or 0
    )

    subscribed = int(
        (
            await db.execute(
                select(func.count(func.distinct(User.id)))
                .select_from(User)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.created_at >= start_dt,
                    User.created_at < end_dt,
                    Subscription.status.in_(_ACTIVE_SUB_STATUSES),
                )
            )
        ).scalar()
        or 0
    )

    return {
        "registered": registered,
        "email_verified": email_verified,
        "first_build": first_build,
        "first_export": first_export,
        "subscribed": subscribed,
    }


async def build_monitoring_summary(
    db: AsyncSession,
    from_str: str,
    to_str: str,
) -> dict[str, Any]:
    start, end = _parse_report_dates(from_str, to_str)
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    users_total = int((await db.execute(select(func.count()).select_from(User))).scalar() or 0)
    signups = int(
        (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.created_at >= start_dt, User.created_at < end_dt)
            )
        ).scalar()
        or 0
    )

    logins = await _fetch_login_events(db, start_dt, end_dt)
    unique_logins = len({uid for _, uid, _ in logins})
    unique_web = len({uid for _, uid, ch in logins if ch == "web"})
    unique_extension = len({uid for _, uid, ch in logins if ch == "extension"})

    beacons = await _beacon_counts_by_day(db, start, end)

    def _sum_beacon(key: str) -> int:
        return sum(beacons.get(key, {}).values())

    subs_active = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Subscription)
                .where(Subscription.status.in_(_ACTIVE_SUB_STATUSES))
            )
        ).scalar()
        or 0
    )

    applications = int((await db.execute(select(func.count()).select_from(Application))).scalar() or 0)

    try:
        from app.models.jobs import JobSearchLog

        job_searches = int(
            (await db.execute(select(func.count()).select_from(JobSearchLog))).scalar() or 0
        )
    except ImportError:
        job_searches = 0

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "users_total": users_total,
        "signups_in_range": signups,
        "unique_users_logged_in": unique_logins,
        "unique_users_web_login": unique_web,
        "unique_users_extension_login": unique_extension,
        "active_subscriptions": subs_active,
        "landing_views": _sum_beacon("landing_view"),
        "auth_page_views": _sum_beacon("auth_page_view"),
        "web_app_beacon_views": _sum_beacon("web_app_view"),
        "extension_beacon_opens": _sum_beacon("extension_open"),
        "applications_total": applications,
        "job_searches_total": job_searches,
    }


__all__ = [
    "PUBLIC_METRIC_KEYS",
    "build_activity_metrics",
    "build_channel_metrics",
    "build_funnel_metrics",
    "build_monitoring_summary",
    "increment_daily_metric",
]
