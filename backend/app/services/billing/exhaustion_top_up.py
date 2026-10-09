"""One-time free-credit top-up when a verified free user exhausts signup credits."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import CreditKind
from app.models.user import CreditTransaction, CreditTransactionAction, User
from app.services.billing.credits import get_balance, grant_credit
from app.services.billing.effective_entitlement import is_free_entitlement


@dataclass(frozen=True, slots=True)
class ExhaustionTopUpEligibility:
    eligible: bool
    amount: int
    reason: str | None = None


async def _top_up_already_used(
    session: AsyncSession,
    *,
    email_canonical: str | None,
    device_fingerprint_hash: str | None,
) -> bool:
    if not email_canonical and not device_fingerprint_hash:
        return False

    clauses = []
    if email_canonical:
        clauses.append(User.email_canonical == email_canonical)
    if device_fingerprint_hash:
        clauses.append(User.signup_device_fingerprint_hash == device_fingerprint_hash)
    if not clauses:
        return False

    stmt = (
        select(CreditTransaction.id)
        .join(User, User.id == CreditTransaction.user_id)
        .where(CreditTransaction.action == CreditTransactionAction.exhaustion_top_up)
        .where(or_(*clauses))
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def get_exhaustion_top_up_eligibility(
    session: AsyncSession,
    *,
    user: User,
) -> ExhaustionTopUpEligibility:
    amount = settings.EXHAUSTION_TOP_UP_CREDITS
    if not await is_free_entitlement(session, user):
        return ExhaustionTopUpEligibility(False, amount, "has_subscription")
    if not user.is_email_verified:
        return ExhaustionTopUpEligibility(False, amount, "email_unverified")

    balance = await get_balance(session, user_id=user.id, credit_kind=CreditKind.free)
    if balance > 0:
        return ExhaustionTopUpEligibility(False, amount, "credits_remaining")

    if await _top_up_already_used(
        session,
        email_canonical=user.email_canonical,
        device_fingerprint_hash=user.signup_device_fingerprint_hash,
    ):
        return ExhaustionTopUpEligibility(False, amount, "already_claimed")

    return ExhaustionTopUpEligibility(True, amount)


async def grant_exhaustion_top_up(
    session: AsyncSession,
    *,
    user: User,
) -> int:
    await session.execute(
        select(User.id).where(User.id == user.id).with_for_update()
    )

    eligibility = await get_exhaustion_top_up_eligibility(session, user=user)
    if not eligibility.eligible:
        raise ValueError(eligibility.reason or "not_eligible")

    await grant_credit(
        session,
        user_id=user.id,
        credit_kind=CreditKind.free,
        delta=eligibility.amount,
        reason="exhaustion_top_up",
        note="One-time free-tier exhaustion top-up",
    )
    return eligibility.amount


__all__ = [
    "ExhaustionTopUpEligibility",
    "get_exhaustion_top_up_eligibility",
    "grant_exhaustion_top_up",
]
