"""Phase 3 regenerate policy: hollow reruns keep the prior resume and return the credit."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import orchestrator
from app.db.engine import engine as app_engine
from app.agent.phase3_delivery import (
    CREDIT_RETURNED_NOTE,
    KEPT_PRIOR_NOTE,
    apply_delivery_policy,
    credit_was_charged,
)
from app.models.billing import CreditKind
from app.models.keywords import KeywordExtractionOutput
from app.models.audit import AuditOutput, KeywordCoverage
from app.models.resume import ExperienceEntry, ParsedResume
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput
from app.models.session import PhaseStatus
from app.models.user import AuthProvider, CreditTransaction, User, UserTier
from app.services.billing.credits import consume_credit, get_balance, grant_credit
from app.services.billing.phase3_refund import (
    DAILY_REFUND_CAP,
    PHASE3_REFUND_REASON,
    refund_phase3_charge,
)
from app.services.session_store import create_session, get_session, update_session

pytestmark = pytest.mark.integration

PRIOR_BULLET = "Owned the payments API."


@pytest.fixture(autouse=True)
async def _fresh_app_engine_pool():
    """The app-level engine pools connections bound to the previous test's loop."""
    await app_engine.dispose()
    yield
    await app_engine.dispose()


class _FakeLLM:
    provider_name = "test"
    model_name = "test-model"


def _prior() -> TailoredResumeOutput:
    return TailoredResumeOutput(
        summary="Prior summary.",
        skills=["Languages: Python"],
        experience=[
            TailoredExperienceEntry(
                title="Engineer", company="Acme", dates="2020", bullets=[PRIOR_BULLET]
            )
        ],
    )


def _good_llm_output() -> TailoredResumeOutput:
    return TailoredResumeOutput(
        summary="Fresh summary.",
        skills=["Languages: Python"],
        experience=[
            TailoredExperienceEntry(
                title="Engineer", company="Acme", dates="2020", bullets=["Led API work."]
            )
        ],
    )


async def _user_with_credits(db: AsyncSession, credits: int) -> uuid.UUID:
    user = User(
        id=uuid.uuid4(),
        email=f"regen-{uuid.uuid4().hex[:8]}@example.com",
        auth_provider=AuthProvider.email,
        password_hash="x",
        display_name="Regen",
        tier=UserTier.free,
        credit_balance=0,
        accepted_tos_version="2026-06",
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    user_id = user.id
    await grant_credit(
        db, user_id=user_id, credit_kind=CreditKind.free, delta=credits, reason="admin_grant"
    )
    await db.commit()
    return user_id


async def _seed_session(user_id: uuid.UUID, *, with_prior: bool) -> str:
    session = await create_session()
    session.user_id = str(user_id)
    session.phase1_output = KeywordExtractionOutput()
    session.phase2_output = AuditOutput(
        keyword_coverage=KeywordCoverage(present=["Python"]),
        overall_score=70,
        summary="ok",
    )
    session.resume_parsed = ParsedResume(
        summary="Source summary.",
        skills=["Python"],
        experience=[ExperienceEntry(title="Engineer", company="Acme", bullets=["Built."])],
    )
    session.phase1_status = PhaseStatus.done
    session.phase2_status = PhaseStatus.done
    if with_prior:
        session.phase3_status = PhaseStatus.done
        session.phase3_output = _prior()
    await update_session(session)
    return session.session_id


async def _run_regenerate(
    client: AsyncClient, monkeypatch, session_id: str, llm_output: TailoredResumeOutput
) -> dict[str, object]:
    async def fake_complete(*args, **kwargs):
        return llm_output

    async def fake_resolve(session, llm, queue):
        return llm, None

    monkeypatch.setattr("app.agent.phase3_rewrite.complete_structured", fake_complete)
    monkeypatch.setattr(orchestrator, "_resolve_phase3_llm", fake_resolve)

    response = await client.post(
        f"/api/sessions/{session_id}/phases/3/run", json={"force": True}
    )
    assert response.status_code == 202, response.text

    queue: asyncio.Queue = asyncio.Queue()
    await orchestrator.run_phase(session_id, 3, _FakeLLM(), queue)
    events: list[dict[str, object]] = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return next(e for e in events if e["event"] == "done")


async def _balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    return await get_balance(db, user_id=user_id, credit_kind=CreditKind.free, for_share=False)


async def _refund_rows(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(CreditTransaction)
                .where(CreditTransaction.user_id == user_id)
                .where(CreditTransaction.reason == PHASE3_REFUND_REASON)
            )
        ).scalar_one()
    )


@pytest.mark.asyncio
async def test_hollow_regenerate_keeps_prior_and_reverses_the_debit_once(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    user_id = await _user_with_credits(db_session, 2)
    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)

    done = await _run_regenerate(app_client, monkeypatch, session_id, TailoredResumeOutput())

    output = done["output"]
    assert output["experience"][0]["bullets"] == [PRIOR_BULLET]
    assert output["skills"] == ["Languages: Python"]
    assert any(
        n == KEPT_PRIOR_NOTE + CREDIT_RETURNED_NOTE for n in output["rewrite_notes"]
    )
    assert done["prior_kept"] is True
    assert done["credit_charged"] is False
    assert done["credit_refunded"] is True

    assert await _balance(db_session, user_id) == 2
    assert await _refund_rows(db_session, user_id) == 1

    stored = await get_session(session_id)
    assert stored is not None and stored.phase3_output is not None
    assert stored.phase3_output.experience[0].bullets == [PRIOR_BULLET]
    assert stored.phase3_status == PhaseStatus.done
    assert stored.phase3_charge is not None and stored.phase3_charge.refunded is True

    outcome = await apply_delivery_policy(
        stored,
        TailoredResumeOutput(phase3_delivery="deterministic_fallback"),
        _prior(),
    )
    assert outcome.prior_kept is True
    assert await _refund_rows(db_session, user_id) == 1
    assert await _balance(db_session, user_id) == 2


@pytest.mark.asyncio
async def test_repeated_policy_calls_never_return_more_than_one_credit(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    user_id = await _user_with_credits(db_session, 2)
    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)
    await _run_regenerate(app_client, monkeypatch, session_id, TailoredResumeOutput())

    stored = await get_session(session_id)
    assert stored is not None and stored.phase3_charge is not None
    stored.phase3_charge = stored.phase3_charge.model_copy(update={"refunded": False})
    for _ in range(3):
        outcome = await apply_delivery_policy(
            stored,
            TailoredResumeOutput(phase3_delivery="deterministic_fallback"),
            _prior(),
        )
        assert outcome.credit_refunded is True
        assert CREDIT_RETURNED_NOTE in " ".join(outcome.output.rewrite_notes)
    assert stored.phase3_charge is not None and stored.phase3_charge.refunded is True
    assert credit_was_charged(stored) is False
    assert await _refund_rows(db_session, user_id) == 1
    assert await _balance(db_session, user_id) == 2


@pytest.mark.asyncio
async def test_concurrent_reversals_of_one_charge_write_a_single_row(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    from app.db.engine import async_session_factory

    user_id = await _user_with_credits(db_session, 2)
    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)
    response = await app_client.post(
        f"/api/sessions/{session_id}/phases/3/run", json={"force": True}
    )
    assert response.status_code == 202
    stored = await get_session(session_id)
    assert stored is not None and stored.phase3_charge is not None
    charge = stored.phase3_charge

    async def reverse() -> str:
        async with async_session_factory() as db:
            outcome = await refund_phase3_charge(
                db, user_id=user_id, charge=charge, session_id=session_id
            )
            await db.commit()
            return outcome

    outcomes = await asyncio.gather(reverse(), reverse())
    assert sorted(outcomes) == ["already_reversed", "reversed"]
    assert await _refund_rows(db_session, user_id) == 1
    assert await _balance(db_session, user_id) == 2


@pytest.mark.asyncio
async def test_reminted_charge_id_cannot_reverse_the_same_debit_twice(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    from app.models.session import Phase3Charge

    user_id = await _user_with_credits(db_session, 2)
    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)
    await app_client.post(f"/api/sessions/{session_id}/phases/3/run", json={"force": True})
    stored = await get_session(session_id)
    assert stored is not None and stored.phase3_charge is not None
    original = stored.phase3_charge

    first = await refund_phase3_charge(
        db_session, user_id=user_id, charge=original, session_id=session_id
    )
    await db_session.commit()
    replay = Phase3Charge(
        charge_id=uuid.uuid4().hex,
        charged_to=original.charged_to,
        credit_transaction_id=original.credit_transaction_id,
    )
    second = await refund_phase3_charge(
        db_session, user_id=user_id, charge=replay, session_id=session_id
    )
    await db_session.commit()

    assert (first, second) == ("reversed", "already_reversed")
    assert await _refund_rows(db_session, user_id) == 1
    assert await _balance(db_session, user_id) == 2


@pytest.mark.asyncio
async def test_successful_regenerate_charges_exactly_once_and_replaces_the_resume(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    user_id = await _user_with_credits(db_session, 2)
    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)

    done = await _run_regenerate(app_client, monkeypatch, session_id, _good_llm_output())

    output = done["output"]
    assert isinstance(output, dict)
    assert output["phase3_delivery"] == "llm"
    assert output["experience"][0]["bullets"] == ["Led API work."]
    assert done["prior_kept"] is False
    assert done["credit_charged"] is True
    assert await _balance(db_session, user_id) == 1
    assert await _refund_rows(db_session, user_id) == 0


@pytest.mark.asyncio
async def test_hollow_first_run_without_prior_keeps_the_charge_and_flags_fallback(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    user_id = await _user_with_credits(db_session, 2)
    session_id = await _seed_session(user_id, with_prior=False)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)

    done = await _run_regenerate(app_client, monkeypatch, session_id, TailoredResumeOutput())

    output = done["output"]
    assert isinstance(output, dict)
    assert output["phase3_delivery"] == "deterministic_fallback"
    assert any("Python" in line for line in output["skills"])
    assert done["prior_kept"] is False
    assert done["credit_refunded"] is False
    assert done["credit_charged"] is True
    assert await _balance(db_session, user_id) == 1
    assert await _refund_rows(db_session, user_id) == 0


async def _plant_charge(session_id: str, tx_id: uuid.UUID, *, charged_to: str = "free_credit"):
    from app.models.session import Phase3Charge

    stored = await get_session(session_id)
    assert stored is not None
    stored.phase3_charge = Phase3Charge(
        charge_id=uuid.uuid4().hex,
        charged_to=charged_to,
        credit_transaction_id=str(tx_id),
    )
    return stored


@pytest.mark.asyncio
async def test_refund_cannot_target_another_users_resume_build_debit(
    db_session: AsyncSession,
) -> None:
    victim = await _user_with_credits(db_session, 2)
    attacker = await _user_with_credits(db_session, 1)
    victim_debit = await consume_credit(
        db_session, user_id=victim, credit_kind=CreditKind.free, reason="resume_build"
    )
    await db_session.commit()
    victim_debit_id = victim_debit.id
    session_id = await _seed_session(attacker, with_prior=True)

    stored = await _plant_charge(session_id, victim_debit_id)
    outcome = await apply_delivery_policy(
        stored,
        TailoredResumeOutput(phase3_delivery="deterministic_fallback"),
        _prior(),
    )

    assert outcome.prior_kept is True
    assert outcome.credit_refunded is False
    assert CREDIT_RETURNED_NOTE not in " ".join(outcome.output.rewrite_notes)
    assert await _balance(db_session, attacker) == 1
    assert await _balance(db_session, victim) == 1
    assert await _refund_rows(db_session, attacker) == 0
    assert await _refund_rows(db_session, victim) == 0


@pytest.mark.asyncio
async def test_refund_ignores_non_resume_build_debits(db_session: AsyncSession) -> None:
    user_id = await _user_with_credits(db_session, 3)
    ats_debit = await consume_credit(
        db_session, user_id=user_id, credit_kind=CreditKind.free, reason="ats_recalc"
    )
    await db_session.commit()
    ats_debit_id = ats_debit.id
    session_id = await _seed_session(user_id, with_prior=True)

    stored = await _plant_charge(session_id, ats_debit_id)
    outcome = await apply_delivery_policy(
        stored,
        TailoredResumeOutput(phase3_delivery="deterministic_fallback"),
        _prior(),
    )

    assert outcome.credit_refunded is False
    assert await _balance(db_session, user_id) == 2
    assert await _refund_rows(db_session, user_id) == 0


@pytest.mark.asyncio
async def test_no_charge_recorded_keeps_prior_without_claiming_a_refund(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    user_id = await _user_with_credits(db_session, 2)
    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: True)

    done = await _run_regenerate(app_client, monkeypatch, session_id, TailoredResumeOutput())

    assert done["prior_kept"] is True
    assert done["credit_charged"] is False
    assert done["credit_refunded"] is False
    notes = " ".join(done["output"]["rewrite_notes"])
    assert KEPT_PRIOR_NOTE in notes and CREDIT_RETURNED_NOTE not in notes
    assert await _balance(db_session, user_id) == 2
    assert await _refund_rows(db_session, user_id) == 0


@pytest.mark.asyncio
async def test_hollow_prior_is_neither_kept_nor_refunded(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    user_id = await _user_with_credits(db_session, 2)
    session_id = await _seed_session(user_id, with_prior=False)
    hollow_prior = _prior()
    hollow_prior.experience = []
    stored = await get_session(session_id)
    assert stored is not None
    stored.phase3_status = PhaseStatus.done
    stored.phase3_output = hollow_prior
    await update_session(stored)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)

    done = await _run_regenerate(app_client, monkeypatch, session_id, TailoredResumeOutput())

    assert done["prior_kept"] is False
    assert done["credit_charged"] is True
    assert done["output"]["phase3_delivery"] == "deterministic_fallback"
    assert await _balance(db_session, user_id) == 1
    assert await _refund_rows(db_session, user_id) == 0


@pytest.mark.asyncio
async def test_refunds_stop_after_the_daily_cap(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    user_id = await _user_with_credits(db_session, DAILY_REFUND_CAP + 3)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)
    outcomes: list[bool] = []
    for _ in range(DAILY_REFUND_CAP + 1):
        session_id = await _seed_session(user_id, with_prior=True)
        done = await _run_regenerate(
            app_client, monkeypatch, session_id, TailoredResumeOutput()
        )
        assert done["prior_kept"] is True
        outcomes.append(bool(done["credit_refunded"]))

    assert outcomes == [True] * DAILY_REFUND_CAP + [False]
    assert await _refund_rows(db_session, user_id) == DAILY_REFUND_CAP
    assert await _balance(db_session, user_id) == DAILY_REFUND_CAP + 2


@pytest.mark.asyncio
async def test_scoped_regeneration_never_refunds_a_standing_full_run_charge(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    user_id = await _user_with_credits(db_session, 3)
    debit = await consume_credit(
        db_session, user_id=user_id, credit_kind=CreditKind.free, reason="resume_build"
    )
    await db_session.commit()
    debit_id = debit.id
    session_id = await _seed_session(user_id, with_prior=True)
    stored = await _plant_charge(session_id, debit_id)
    await update_session(stored)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: True)

    async def fake_complete(*args, **kwargs):
        return TailoredResumeOutput()

    async def fake_resolve(session, llm, queue):
        return llm, None

    monkeypatch.setattr("app.agent.phase3_rewrite.complete_structured", fake_complete)
    monkeypatch.setattr(orchestrator, "_resolve_phase3_llm", fake_resolve)
    response = await app_client.post(
        f"/api/sessions/{session_id}/phases/3/run",
        json={"scope": {"section": "experience", "company": "Acme"}},
    )
    assert response.status_code == 202, response.text
    await orchestrator.run_phase(session_id, 3, _FakeLLM(), asyncio.Queue())

    after = await get_session(session_id)
    assert after is not None and after.phase3_charge is not None
    assert after.phase3_charge.refunded is False
    assert await _refund_rows(db_session, user_id) == 0
    assert await _balance(db_session, user_id) == 2


@pytest.mark.asyncio
async def test_subscription_charge_is_reversed_once(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    from datetime import timedelta

    from app.models.billing import (
        Subscription,
        SubscriptionBillingCycle,
        SubscriptionPlan,
        SubscriptionStatus,
    )

    user_id = await _user_with_credits(db_session, 1)
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        id=uuid.uuid4(),
        user_id=user_id,
        plan=SubscriptionPlan.monthly,
        billing_cycle=SubscriptionBillingCycle.recurring,
        status=SubscriptionStatus.active,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=29),
        cancel_at_period_end=False,
        stripe_customer_id="cus_regen_test",
        stripe_subscription_id=f"sub_regen_{uuid.uuid4().hex[:8]}",
        stripe_price_id="price_monthly_test",
    )
    db_session.add(subscription)
    await db_session.commit()
    subscription_id = subscription.id

    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)

    async def resumes_used() -> int:
        db_session.expire_all()
        return int(
            (
                await db_session.execute(
                    select(Subscription.resumes_used).where(
                        Subscription.id == subscription_id
                    )
                )
            ).scalar_one()
        )

    balance_before = await _balance(db_session, user_id)
    done = await _run_regenerate(app_client, monkeypatch, session_id, TailoredResumeOutput())

    assert done["prior_kept"] is True
    assert done["credit_charged"] is False
    assert done["credit_refunded"] is True
    assert await resumes_used() == 0
    assert await _balance(db_session, user_id) == balance_before
    assert await _refund_rows(db_session, user_id) == 1

    stored = await get_session(session_id)
    assert stored is not None and stored.phase3_charge is not None
    assert stored.phase3_charge.charged_to == "subscription_resume"
    stored.phase3_charge = stored.phase3_charge.model_copy(update={"refunded": False})
    for _ in range(2):
        await apply_delivery_policy(
            stored,
            TailoredResumeOutput(phase3_delivery="deterministic_fallback"),
            _prior(),
        )
    assert await resumes_used() == 0
    assert await _refund_rows(db_session, user_id) == 1


@pytest.mark.asyncio
async def test_subscription_charge_charges_the_counter_not_the_credit_balance(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    from datetime import timedelta

    from app.models.billing import (
        Subscription,
        SubscriptionBillingCycle,
        SubscriptionPlan,
        SubscriptionStatus,
    )

    user_id = await _user_with_credits(db_session, 1)
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        id=uuid.uuid4(),
        user_id=user_id,
        plan=SubscriptionPlan.monthly,
        billing_cycle=SubscriptionBillingCycle.recurring,
        status=SubscriptionStatus.active,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=29),
        cancel_at_period_end=False,
        stripe_customer_id="cus_regen_test2",
        stripe_subscription_id=f"sub_regen_{uuid.uuid4().hex[:8]}",
        stripe_price_id="price_monthly_test",
    )
    db_session.add(subscription)
    await db_session.commit()
    subscription_id = subscription.id
    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)

    response = await app_client.post(
        f"/api/sessions/{session_id}/phases/3/run", json={"force": True}
    )
    assert response.status_code == 202, response.text

    db_session.expire_all()
    used = (
        await db_session.execute(
            select(Subscription.resumes_used).where(Subscription.id == subscription_id)
        )
    ).scalar_one()
    stored = await get_session(session_id)
    assert used == 1
    assert stored is not None and stored.phase3_charge is not None
    assert stored.phase3_charge.charged_to == "subscription_resume"
    assert await _balance(db_session, user_id) == 1


@pytest.mark.asyncio
async def test_spent_subscription_marker_is_not_reported_as_a_refund(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    from datetime import timedelta

    from sqlalchemy import update

    from app.models.billing import (
        Subscription,
        SubscriptionBillingCycle,
        SubscriptionPlan,
        SubscriptionStatus,
    )
    from app.services.billing.phase3_refund import PHASE3_SPENT_REASON

    user_id = await _user_with_credits(db_session, 1)
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        id=uuid.uuid4(),
        user_id=user_id,
        plan=SubscriptionPlan.monthly,
        billing_cycle=SubscriptionBillingCycle.recurring,
        status=SubscriptionStatus.active,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=29),
        cancel_at_period_end=False,
        stripe_customer_id="cus_regen_test3",
        stripe_subscription_id=f"sub_regen_{uuid.uuid4().hex[:8]}",
        stripe_price_id="price_monthly_test",
    )
    db_session.add(subscription)
    await db_session.commit()
    subscription_id = subscription.id
    session_id = await _seed_session(user_id, with_prior=True)
    monkeypatch.setattr("app.routers.phases.should_skip_billing_quota", lambda: False)
    await app_client.post(f"/api/sessions/{session_id}/phases/3/run", json={"force": True})
    await db_session.execute(
        update(Subscription).where(Subscription.id == subscription_id).values(resumes_used=0)
    )
    await db_session.commit()
    stored = await get_session(session_id)
    assert stored is not None and stored.phase3_charge is not None

    first = await apply_delivery_policy(
        stored, TailoredResumeOutput(phase3_delivery="deterministic_fallback"), _prior()
    )
    stored.phase3_charge = stored.phase3_charge.model_copy(update={"refunded": False})
    await db_session.execute(
        update(Subscription).where(Subscription.id == subscription_id).values(resumes_used=1)
    )
    await db_session.commit()
    second = await apply_delivery_policy(
        stored, TailoredResumeOutput(phase3_delivery="deterministic_fallback"), _prior()
    )

    assert first.credit_refunded is False and second.credit_refunded is False
    assert CREDIT_RETURNED_NOTE not in " ".join(second.output.rewrite_notes)
    db_session.expire_all()
    used = (
        await db_session.execute(
            select(Subscription.resumes_used).where(Subscription.id == subscription_id)
        )
    ).scalar_one()
    assert used == 1
    assert await _refund_rows(db_session, user_id) == 0
    spent = (
        await db_session.execute(
            select(func.count())
            .select_from(CreditTransaction)
            .where(CreditTransaction.user_id == user_id)
            .where(CreditTransaction.reason == PHASE3_SPENT_REASON)
        )
    ).scalar_one()
    assert spent == 1
