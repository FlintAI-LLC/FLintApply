"""Reverse the Phase 3 resume_build charge when the run produced no usable output.

The reversal is keyed on the original debit so SSE retries and duplicate calls
can never return more than the single unit that was taken.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import CreditKind, Subscription
from app.models.session import Phase3Charge
from app.models.user import CreditTransaction, CreditTransactionAction, User
from app.services.billing.credits import _refresh_user_credit_balance_cache
from app.services.billing.quota import QuotaAction

log = structlog.get_logger("billing.phase3_refund")

PHASE3_REFUND_REASON = "phase3_hollow_refund"
PHASE3_SPENT_REASON = "phase3_refund_spent"
FREE_CREDIT_CHARGE = "free_credit"
SUBSCRIPTION_CHARGE = "subscription_resume"


RefundOutcome = Literal["reversed", "already_reversed", "not_refundable"]

# Bounds provider spend: a reversed run still cost LLM tokens.
DAILY_REFUND_CAP = 5
_CAP_WINDOW = timedelta(hours=24)


def _idempotency_key(charge: Phase3Charge) -> str:
    """Key on the original debit so a re-minted charge_id cannot reverse it twice."""
    return charge.credit_transaction_id or charge.charge_id


async def _prior_outcome(
    db: AsyncSession, *, user_id: uuid.UUID, key: str
) -> RefundOutcome | None:
    """Outcome recorded for this debit earlier, so a retry never reinterprets it."""
    row = await db.execute(
        select(CreditTransaction.reason)
        .where(CreditTransaction.user_id == user_id)
        .where(CreditTransaction.reason.in_((PHASE3_REFUND_REASON, PHASE3_SPENT_REASON)))
        .where(CreditTransaction.note == key)
        .limit(1)
    )
    reason = row.scalar_one_or_none()
    if reason is None:
        return None
    return "already_reversed" if reason == PHASE3_REFUND_REASON else "not_refundable"


async def _refunds_in_window(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    count = await db.execute(
        select(func.count())
        .select_from(CreditTransaction)
        .where(CreditTransaction.user_id == user_id)
        .where(CreditTransaction.reason == PHASE3_REFUND_REASON)
        .where(CreditTransaction.created_at >= datetime.now(timezone.utc) - _CAP_WINDOW)
    )
    return int(count.scalar_one())


async def _original_debit_is_valid(
    db: AsyncSession, *, user_id: uuid.UUID, transaction_id: str
) -> bool:
    try:
        tx_id = uuid.UUID(transaction_id)
    except ValueError:
        return False
    original = await db.get(CreditTransaction, tx_id)
    return (
        original is not None
        and original.user_id == user_id
        and original.delta == -1
        and original.reason == QuotaAction.resume_build.value
        and original.credit_kind == CreditKind.free
    )


def _reversal_row(
    *,
    user_id: uuid.UUID,
    delta: int,
    key: str,
    session_id: str,
    subscription_id: uuid.UUID | None = None,
    reason: str = PHASE3_REFUND_REASON,
) -> CreditTransaction:
    return CreditTransaction(
        id=uuid.uuid4(),
        user_id=user_id,
        delta=delta,
        action=CreditTransactionAction.refund_reverse,
        reason=reason,
        credit_kind=CreditKind.free,
        session_id=session_id,
        related_subscription_id=subscription_id,
        note=key,
    )


async def refund_phase3_charge(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    charge: Phase3Charge,
    session_id: str,
) -> RefundOutcome:
    """Reverse ``charge`` at most once.

    The caller owns the transaction and must always commit: a subscription
    charge with nothing left to give back gets a spent marker, so a later
    counter increment can never be reversed by a retry.
    """
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    key = _idempotency_key(charge)
    earlier = await _prior_outcome(db, user_id=user_id, key=key)
    if earlier is not None:
        return earlier
    if await _refunds_in_window(db, user_id=user_id) >= DAILY_REFUND_CAP:
        log.warning("phase3_refund_cap_reached", session_id=session_id)
        return "not_refundable"

    if charge.charged_to == FREE_CREDIT_CHARGE:
        if not charge.credit_transaction_id or not await _original_debit_is_valid(
            db, user_id=user_id, transaction_id=charge.credit_transaction_id
        ):
            log.warning("phase3_refund_invalid_debit", session_id=session_id)
            return "not_refundable"
        db.add(_reversal_row(user_id=user_id, delta=1, key=key, session_id=session_id))
        await db.flush()
        await _refresh_user_credit_balance_cache(db, user_id=user_id)
        return "reversed"

    if charge.charged_to == SUBSCRIPTION_CHARGE and charge.subscription_id:
        subscription_id = uuid.UUID(charge.subscription_id)
        subscription = (
            await db.execute(
                select(Subscription)
                .where(Subscription.id == subscription_id)
                .where(Subscription.user_id == user_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if subscription is None:
            return "not_refundable"
        can_move = subscription.resumes_used > 0
        if can_move:
            subscription.resumes_used -= 1
        db.add(
            _reversal_row(
                user_id=user_id,
                delta=0,
                key=key,
                session_id=session_id,
                subscription_id=subscription_id,
                reason=PHASE3_REFUND_REASON if can_move else PHASE3_SPENT_REASON,
            )
        )
        await db.flush()
        return "reversed" if can_move else "not_refundable"

    return "not_refundable"


__all__ = [
    "DAILY_REFUND_CAP",
    "PHASE3_REFUND_REASON",
    "PHASE3_SPENT_REASON",
    "RefundOutcome",
    "refund_phase3_charge",
]
