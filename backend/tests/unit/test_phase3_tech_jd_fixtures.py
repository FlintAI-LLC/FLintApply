"""Tailoring invariants against realistic tech JDs: no invented skills, no rewritten history."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.phase3_keyword_placement import place_evidenced_keywords
from app.agent.phase3_postprocess import canonical_skill, flatten_skill_terms
from app.agent.phase3_truthfulness import TruthfulnessContext
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput

_FIXTURES = sorted((Path(__file__).parent.parent / "fixtures" / "tech_jds").glob("*.txt"))
_MUST_HAVE_PREFIX = "MUST_HAVE:"
_MIN_SKILL_LINES = 1
_MAX_SKILL_LINES = 5

_RESUME_RAW = """
Backend engineer. Wrote Golang services exposing gRPC APIs, tuned Postgres queries,
cached hot paths in Redis, and consumed Kafka topics. Containerized with Docker,
deployed to k8s on Amazon Web Services. Python tooling, plus a React and TypeScript
admin dashboard and a small iOS companion app in Swift.
"""

# Terms genuinely present in _RESUME_RAW (directly or via a safe synonym).
_EVIDENCED = {
    "go", "grpc", "postgresql", "kubernetes", "docker", "aws", "python", "kafka",
    "react", "typescript", "swift",
}


def _keywords(path: Path) -> list[str]:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith(_MUST_HAVE_PREFIX)
    return [k.strip() for k in first[len(_MUST_HAVE_PREFIX):].split(",") if k.strip()]


def _base_output() -> TailoredResumeOutput:
    return TailoredResumeOutput(
        summary="Backend engineer.",
        skills=["Languages: Python", "Tools: Docker"],
        experience=[
            TailoredExperienceEntry(
                title="Backend Engineer",
                company="Acme",
                dates="2021 - 2024",
                bullets=["Led migration of services.", "Built payment APIs."],
            )
        ],
    )


def _terms(output: TailoredResumeOutput) -> set[str]:
    return {canonical_skill(t) for t in flatten_skill_terms(output.skills)}


def test_fixtures_are_present() -> None:
    assert {f.stem for f in _FIXTURES} == {
        "backend_go", "data_engineer", "frontend_react",
        "ml_engineer", "mobile_ios", "platform_sre",
    }


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.stem)
def test_only_evidenced_keywords_enter_skills(path: Path) -> None:
    base = _base_output()
    out = place_evidenced_keywords(
        base, _keywords(path), TruthfulnessContext(resume_raw=_RESUME_RAW)
    )
    added = _terms(out) - _terms(base)
    assert added <= _EVIDENCED, f"invented skills: {added - _EVIDENCED}"


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.stem)
def test_evidenced_keywords_are_not_missed(path: Path) -> None:
    keywords = _keywords(path)
    out = place_evidenced_keywords(
        _base_output(), keywords, TruthfulnessContext(resume_raw=_RESUME_RAW)
    )
    expected = {canonical_skill(k) for k in keywords} & _EVIDENCED
    assert expected, f"{path.stem} must overlap the resume evidence or this test is vacuous"
    assert expected <= _terms(out)


def test_swift_evidence_does_not_leak_to_swiftui() -> None:
    out = place_evidenced_keywords(
        _base_output(), ["Swift", "SwiftUI"], TruthfulnessContext(resume_raw=_RESUME_RAW)
    )
    terms = _terms(out)
    assert "swift" in terms
    assert "swiftui" not in terms


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.stem)
def test_history_is_never_rewritten(path: Path) -> None:
    base = _base_output()
    out = place_evidenced_keywords(
        base, _keywords(path), TruthfulnessContext(resume_raw=_RESUME_RAW)
    )
    assert out.experience == base.experience
    assert out.summary == base.summary


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.stem)
def test_skills_stay_within_category_line_budget(path: Path) -> None:
    out = place_evidenced_keywords(
        _base_output(), _keywords(path), TruthfulnessContext(resume_raw=_RESUME_RAW)
    )
    assert _MIN_SKILL_LINES <= len(out.skills) <= _MAX_SKILL_LINES


@pytest.mark.parametrize("path", _FIXTURES, ids=lambda p: p.stem)
def test_placement_is_idempotent(path: Path) -> None:
    ctx = TruthfulnessContext(resume_raw=_RESUME_RAW)
    once = place_evidenced_keywords(_base_output(), _keywords(path), ctx)
    twice = place_evidenced_keywords(once, _keywords(path), ctx)
    assert twice.skills == once.skills
