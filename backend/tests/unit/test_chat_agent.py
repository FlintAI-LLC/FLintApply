"""Unit tests for resume chat agent prompt assembly."""

from __future__ import annotations

import json

from app.agent.chat import _SYSTEM_PROMPT, _master_resume_context
from app.models.resume import ParsedResume, ProjectEntry
from app.models.session import Session


def test_chat_prompt_can_include_json_examples_without_format_error() -> None:
    """Prompt must not use str.format placeholders beyond resume_json/jd_text."""
    resume_json = json.dumps({"projects": []})
    jd_text = "About the role"
    rendered = (
        _SYSTEM_PROMPT.replace("{resume_json}", resume_json)
        .replace("{jd_text}", jd_text)
        .replace("{qa_context}", "")
        .replace("{master_resume_context}", "")
    )
    assert resume_json in rendered
    assert jd_text in rendered
    assert "new_project" in rendered


def test_master_resume_context_includes_project_bullets() -> None:
    session = Session(
        session_id="00000000-0000-0000-0000-000000000001",
        resume_parsed=ParsedResume(
            projects=[
                ProjectEntry(
                    name="Flint",
                    bullets=["Built real-time co-pilot.", "Shipped RAG pipeline."],
                ),
            ],
        ),
    )
    block = _master_resume_context(session)
    assert "MASTER RESUME" in block
    assert "Flint" in block
    assert "RAG pipeline" in block
