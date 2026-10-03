"""Sanitize coached interview history before compile/submit."""

from app.agent.story_interview import sanitize_interview_history


def test_sanitize_drops_complete_sentinel_and_resume_leak() -> None:
    history = [
        {"role": "interviewer", "text": "Q1"},
        {"role": "user", "text": "A1"},
        {"role": "interviewer", "text": "INTERVIEW_COMPLETE"},
        {
            "role": "interviewer",
            "text": "INTERVIEW_COMPLETE\nPROFESSIONAL SUMMARY\nFoo",
        },
        {"role": "user", "text": "A2"},
    ]
    cleaned = sanitize_interview_history(history)
    assert cleaned == [
        {"role": "interviewer", "text": "Q1"},
        {"role": "user", "text": "A1"},
        {"role": "user", "text": "A2"},
    ]
