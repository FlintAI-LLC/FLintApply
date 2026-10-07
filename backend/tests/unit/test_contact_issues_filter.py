"""Unit tests for Phase 2 contact_issues false-positive filter."""

from __future__ import annotations

from app.agent.contact_issues_filter import (
    filter_contact_export_strings,
    filter_contact_issues,
)

_NAME_MISMATCH_MSG = (
    "Email local part 'alireza@zanganehai.com' does not match the resume name "
    "'Ali Barzin' — use a full-name professional address (e.g. ali.barzin@domain.com)"
)

_FORMAT_MSG = (
    "Email address is not clearly labeled with 'Email:' and the LinkedIn/GitHub "
    "entries are plain text labels without URLs — add full clickable URLs."
)


def test_drops_name_mismatch_for_firstname_on_custom_domain() -> None:
    out = filter_contact_issues(
        [_NAME_MISMATCH_MSG],
        resume_name="Ali Barzin",
        contact_email="alireza@zanganehai.com",
    )
    assert out == []


def test_keeps_nickname_email_warning() -> None:
    out = filter_contact_issues(
        ["Email uses nickname 'kittykat99' — use a professional address."],
        resume_name="Jane Doe",
        contact_email="kittykat99@gmail.com",
    )
    assert len(out) == 1


def test_drops_formatting_preferences() -> None:
    out = filter_contact_issues(
        [_FORMAT_MSG],
        resume_name="Ali Barzin",
        contact_email="alireza@zanganehai.com",
    )
    assert out == []


def test_keeps_first_last_pattern_mismatch_when_truly_unrelated() -> None:
    out = filter_contact_issues(
        [
            "Email local part 'randomuser' does not match the resume name 'Ali Barzin' "
            "— use a full-name professional address."
        ],
        resume_name="Ali Barzin",
        contact_email="randomuser@gmail.com",
    )
    assert len(out) == 1


def test_export_filter_drops_name_based_email_action() -> None:
    actions = filter_contact_export_strings(
        [
            "Switch to a professional name-based email address",
            "Replace broken metric placeholder 'CI eval gate (1, tests)'",
        ],
        resume_name="Ali Barzin",
        contact_email="alireza@zanganehai.com",
    )
    assert actions == [
        "Replace broken metric placeholder 'CI eval gate (1, tests)'",
    ]
