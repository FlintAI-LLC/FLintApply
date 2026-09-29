"""Regenerate policy for degraded Phase 3 output.

When a rerun can only be delivered through the deterministic fallback and the
user already has a tailored resume, keep the existing resume and return the
charge instead of replacing good work with a rebuilt tree.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog

from app.agent.phase3_hollow import phase3_total_bullets
from app.db.engine import async_session_factory
from app.models.rewrite import TailoredResumeOutput
from app.models.session import Session
from app.services.billing.phase3_refund import refund_phase3_charge

log = structlog.get_logger("phase3_delivery")

KEPT_PRIOR_NOTE = (
    "Regenerate discarded incomplete model output; "
    "your previous tailored resume was kept."
)
CREDIT_RETURNED_NOTE = " Credit returned."


@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    output: TailoredResumeOutput
    prior_kept: bool
    credit_refunded: bool


def _prior_is_usable(prior: TailoredResumeOutput | None) -> bool:
    return prior is not None and phase3_total_bullets(prior) > 0


async def _refund_if_charged(session: Session) -> bool:
    """True when the ledger shows this run's charge was returned."""
    charge = session.phase3_charge
    if charge is None:
        return False
    if charge.refunded:
        return True
    if not session.user_id:
        return False
    try:
        user_id = uuid.UUID(session.user_id)
        async with async_session_factory() as db:
            outcome = await refund_phase3_charge(
                db, user_id=user_id, charge=charge, session_id=session.session_id
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001 — a refund failure must not fail the run
        log.warning("phase3_refund_failed", session_id=session.session_id, error=str(exc))
        return False
    returned = outcome in ("reversed", "already_reversed")
    if returned:
        session.phase3_charge = charge.model_copy(update={"refunded": True})
    return returned


async def apply_delivery_policy(
    session: Session,
    output: TailoredResumeOutput,
    prior: TailoredResumeOutput | None,
) -> DeliveryOutcome:
    """Decide what to persist for a full Phase 3 run; mutates only ``session.phase3_charge``."""
    if (
        output.phase3_delivery != "deterministic_fallback"
        or prior is None
        or not _prior_is_usable(prior)
    ):
        return DeliveryOutcome(output=output, prior_kept=False, credit_refunded=False)

    refunded = await _refund_if_charged(session)
    note = KEPT_PRIOR_NOTE + (CREDIT_RETURNED_NOTE if refunded else "")
    kept = prior.model_copy(deep=True)
    kept.phase3_delivery = "llm"
    kept.rewrite_notes = [n for n in kept.rewrite_notes if not n.startswith(KEPT_PRIOR_NOTE)]
    kept.rewrite_notes.append(note)
    return DeliveryOutcome(output=kept, prior_kept=True, credit_refunded=refunded)


def credit_was_charged(session: Session) -> bool:
    """True when this run's charge is still standing after any reversal."""
    charge = session.phase3_charge
    return charge is not None and not charge.refunded


__all__ = [
    "CREDIT_RETURNED_NOTE",
    "DeliveryOutcome",
    "KEPT_PRIOR_NOTE",
    "apply_delivery_policy",
    "credit_was_charged",
]
