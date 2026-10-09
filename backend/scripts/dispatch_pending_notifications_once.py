#!/usr/bin/env python3
"""Flush pending email / web-push notification rows (VM cron or manual ops)."""

from __future__ import annotations

import asyncio
import sys

from app.db.engine import async_session_factory, engine
from app.services.notifications.scheduler import dispatch_pending_notifications


async def main() -> None:
    async with async_session_factory() as session:
        result = await dispatch_pending_notifications(session)
        await session.commit()
    print(
        "Notification dispatch complete",
        f"inspected={result.inspected}",
        f"dispatched={result.dispatched}",
        f"failed={result.failed}",
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
