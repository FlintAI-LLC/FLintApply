#!/usr/bin/env python3
"""Send due daily Career Watch job-alert digest emails (hourly cron on prod VM)."""

from __future__ import annotations

import asyncio

from app.db.engine import async_session_factory, engine
from app.services.career_watch.job_alert_digest import send_daily_job_alert_digests


async def main() -> None:
    async with async_session_factory() as session:
        stats = await send_daily_job_alert_digests(session)
        await session.commit()
    print(
        "Job alert digest send complete",
        f"users_considered={stats.users_considered}",
        f"digests_sent={stats.digests_sent}",
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
