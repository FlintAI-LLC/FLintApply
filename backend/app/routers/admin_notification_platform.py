"""Admin platform notification settings."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.dependencies.admin_auth import require_admin_role
from app.limiter import limiter
from app.models.admin import AdminRole, AdminUser
from app.services.admin_auth.audit import write_admin_audit
from app.services.auth.client_ip import resolve_client_ip
from app.services.notifications.platform_settings import (
    get_notification_platform_settings,
)

router = APIRouter(tags=["admin"])


class NotificationPlatformSettingsOut(BaseModel):
    job_alert_digest_hour_local: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationPlatformSettingsPatch(BaseModel):
    job_alert_digest_hour_local: int = Field(..., ge=0, le=23)


class AuditedNotificationPlatformResponse(BaseModel):
    audit_log_id: uuid.UUID
    settings: NotificationPlatformSettingsOut


@router.get(
    "/notification-platform-settings",
    response_model=NotificationPlatformSettingsOut,
)
@limiter.limit("120/minute")
async def admin_get_notification_platform_settings(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[
        AdminUser,
        Depends(
            require_admin_role(
                AdminRole.super_admin,
                AdminRole.admin,
                AdminRole.support_agent,
                AdminRole.read_only_analyst,
            )
        ),
    ],
) -> NotificationPlatformSettingsOut:
    row = await get_notification_platform_settings(db)
    return NotificationPlatformSettingsOut(
        job_alert_digest_hour_local=row.job_alert_digest_hour_local,
        updated_at=row.updated_at,
    )


@router.patch(
    "/notification-platform-settings",
    response_model=AuditedNotificationPlatformResponse,
)
@limiter.limit("30/minute")
async def admin_patch_notification_platform_settings(
    request: Request,
    body: NotificationPlatformSettingsPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[
        AdminUser,
        Depends(require_admin_role(AdminRole.super_admin, AdminRole.admin)),
    ],
) -> AuditedNotificationPlatformResponse:
    row = await get_notification_platform_settings(db)
    before = row.job_alert_digest_hour_local
    row.job_alert_digest_hour_local = body.job_alert_digest_hour_local
    row.updated_by_admin_id = admin.id
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    audit_row = await write_admin_audit(
        db,
        actor_admin_id=admin.id,
        action="notification_platform_settings.update",
        target_kind="notification_platform_settings",
        target_id=str(row.id),
        before={"job_alert_digest_hour_local": before},
        after={"job_alert_digest_hour_local": body.job_alert_digest_hour_local},
        ip=resolve_client_ip(request),
    )
    await db.flush()
    return AuditedNotificationPlatformResponse(
        audit_log_id=audit_row.id,
        settings=NotificationPlatformSettingsOut(
            job_alert_digest_hour_local=row.job_alert_digest_hour_local,
            updated_at=row.updated_at,
        ),
    )


__all__ = ["router"]
