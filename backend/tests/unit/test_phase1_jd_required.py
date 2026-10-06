"""Phase 1 cannot start without a persisted job description."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers.phases import trigger_phase


def _session(jd_raw: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        jd_raw=jd_raw,
        user_id=None,
        phase1_status=None,
        phase2_status=None,
        phase3_status=None,
        phase4_status=None,
        phase4_stale_since=None,
    )


@pytest.mark.asyncio
async def test_phase1_run_rejects_empty_jd(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _load_session(*_args, **_kwargs):
        return _session("")

    monkeypatch.setattr("app.routers.phases.load_session_for_request", _load_session)

    with pytest.raises(HTTPException) as exc:
        await trigger_phase(
            request=None,  # type: ignore[arg-type]
            session_id="00000000-0000-0000-0000-000000000001",
            phase=1,
            authorization=None,
            db=None,  # type: ignore[arg-type]
        )

    assert exc.value.status_code == 422
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "jd_required"
