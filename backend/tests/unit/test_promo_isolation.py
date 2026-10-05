"""Adversarial promo grant-type and plan isolation tests (SLICE-020a)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminRole
from app.models.admin_grant import AdminGrantType
from app.models.promo_code import PromoCode
from app.models.user import AuthProvider, User, UserTier
from app.services.admin.grants import InvalidGrantPayloadError, validate_grant_payload
from app.services.billing.checkout_discount import resolve_checkout_discount
from tests.admin.conftest import issue_admin_session, make_admin
from tests.integration.test_auth import REGISTER_PAYLOAD

pytestmark = [pytest.mark.unit, pytest.mark.integration]


def _user() -> User:
    return User(
        id=uuid.uuid4(),
        email="isolation@example.com",
        display_name="Isolation",
        auth_provider=AuthProvider.email,
        password_hash="hash",
        tier=UserTier.free,
        credit_balance=0,
    )


async def _seed_price_discount(
    db_session: AsyncSession,
    *,
    code: str,
    applicable_plan_codes: list[str] | str | None,
) -> None:
    payload: dict = {
        "stripe_promotion_code_id": "promo_isolation_test",
    }
    if applicable_plan_codes is not None:
        payload["applicable_plan_codes"] = applicable_plan_codes
    promo = PromoCode(
        id=uuid.uuid4(),
        code=code,
        grant_type=AdminGrantType.price_discount,
        payload=payload,
        redemption_count=0,
        is_active=True,
    )
    db_session.add(promo)
    await db_session.flush()


async def _seed_extra_credits(db_session: AsyncSession, *, code: str) -> None:
    promo = PromoCode(
        id=uuid.uuid4(),
        code=code,
        grant_type=AdminGrantType.extra_credits,
        payload={"amount": 5, "credit_kind": "free"},
        redemption_count=0,
        is_active=True,
    )
    db_session.add(promo)
    await db_session.flush()


@pytest.mark.asyncio
async def test_validate_price_discount_rejects_empty_applicable_plan_codes() -> None:
    with pytest.raises(InvalidGrantPayloadError, match="applicable_plan_codes"):
        validate_grant_payload(
            AdminGrantType.price_discount,
            {
                "stripe_promotion_code_id": "promo_test",
                "applicable_plan_codes": [],
            },
        )


@pytest.mark.asyncio
async def test_validate_price_discount_rejects_missing_applicable_plan_codes() -> None:
    with pytest.raises(InvalidGrantPayloadError, match="applicable_plan_codes"):
        validate_grant_payload(
            AdminGrantType.price_discount,
            {"stripe_promotion_code_id": "promo_test"},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ninety_off_scoped_to_monthly_pro_only(
    db_session: AsyncSession,
) -> None:
    user = _user()
    await _seed_price_discount(
        db_session,
        code="90OFF",
        applicable_plan_codes=["monthly_pro"],
    )
    ok = await resolve_checkout_discount(
        db_session,
        user_id=user.id,
        promo_code="90off",
        plan_code="monthly_pro",
    )
    assert ok.applied is True

    for wrong_plan in ("yearly_pro", "weekly", "monthly_premium", "credits_5"):
        result = await resolve_checkout_discount(
            db_session,
            user_id=user.id,
            promo_code="90off",
            plan_code=wrong_plan,
        )
        assert result.applied is False
        assert result.message is not None
        assert "doesn't apply" in result.message.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extra_credits_at_checkout_returns_grant_aware_message(
    db_session: AsyncSession,
) -> None:
    user = _user()
    await _seed_extra_credits(db_session, code="CREDITS5")
    result = await resolve_checkout_discount(
        db_session,
        user_id=user.id,
        promo_code="credits5",
        plan_code="monthly_pro",
    )
    assert result.applied is False
    assert result.message is not None
    assert "redeem credits" in result.message.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_empty_applicable_plan_codes_fail_closed_at_checkout(
    db_session: AsyncSession,
) -> None:
    user = _user()
    await _seed_price_discount(
        db_session,
        code="LEGACYWILD",
        applicable_plan_codes=[],
    )
    result = await resolve_checkout_discount(
        db_session,
        user_id=user.id,
        promo_code="legacywild",
        plan_code="monthly_pro",
    )
    assert result.applied is False
    assert result.stripe_promotion_code_id is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_non_list_applicable_plan_codes_fail_closed(
    db_session: AsyncSession,
) -> None:
    user = _user()
    await _seed_price_discount(
        db_session,
        code="BADSHAPE",
        applicable_plan_codes="monthly_pro",
    )
    result = await resolve_checkout_discount(
        db_session,
        user_id=user.id,
        promo_code="badshape",
        plan_code="monthly_pro",
    )
    assert result.applied is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_create_price_discount_rejects_empty_applicable(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin, _ = await make_admin(
        db_session,
        email=f"iso-admin-{uuid.uuid4().hex[:6]}@example.com",
        role=AdminRole.super_admin,
    )
    await db_session.commit()
    _, headers = await issue_admin_session(admin.id)

    resp = await app_client.post(
        "/api/admin/promo-codes",
        json={
            "code": "NOPLANS",
            "grant_type": "price_discount",
            "payload": {
                "stripe_promotion_code_id": "promo_no_plans",
                "applicable_plan_codes": [],
            },
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_grant_payload"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redeem_price_discount_returns_wrong_flow_code(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin, _ = await make_admin(
        db_session,
        email=f"flow-admin-{uuid.uuid4().hex[:6]}@example.com",
        role=AdminRole.super_admin,
    )
    await db_session.commit()
    _, headers = await issue_admin_session(admin.id)

    create_resp = await app_client.post(
        "/api/admin/promo-codes",
        json={
            "code": "CHECKOUTONLY",
            "grant_type": "price_discount",
            "payload": {
                "stripe_promotion_code_id": "promo_flow",
                "applicable_plan_codes": ["monthly_pro"],
            },
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    payload = {**REGISTER_PAYLOAD, "email": "flow-user@example.com"}
    reg = await app_client.post("/api/auth/register", json=payload)
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]

    redeem = await app_client.post(
        "/api/promo/redeem",
        json={"code": "checkoutonly"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert redeem.status_code == 400
    assert redeem.json()["detail"]["code"] == "promo_code_wrong_flow"
