from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CoachMessage(BaseModel):
    role: Literal["coach", "user"]
    text: str = Field(..., min_length=1, max_length=2000)


class CoachRequest(BaseModel):
    coach_mode: Literal["segment", "whole_story"] = Field(
        default="segment",
        description="segment = per-segment Q&A (subscribers); whole_story = one feedback pass (free/credit).",
    )
    segment_text: str = Field(
        default="",
        max_length=5000,
        description="Transcript of the segment being coached (segment mode).",
    )
    segments: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="All story segments for whole_story mode.",
    )
    history: list[CoachMessage] = Field(
        default_factory=list,
        description="Prior coach/user exchanges in this session (max 3 coach turns).",
    )
    session_id: str | None = Field(
        default=None,
        description="Story build session ID — scopes the single coach credit per resume build.",
    )

    @model_validator(mode="after")
    def validate_exchange_count(self) -> "CoachRequest":
        if self.coach_mode == "whole_story":
            if self.history:
                raise ValueError("whole_story coach does not support conversation history.")
            total_chars = sum(len((s or "").strip()) for s in self.segments)
            if total_chars < 10:
                raise ValueError("At least one non-empty story segment is required.")
            return self

        if len(self.segment_text.strip()) < 10:
            raise ValueError("segment_text must be at least 10 characters.")
        coach_turns = sum(1 for m in self.history if m.role == "coach")
        if coach_turns > 3:
            raise ValueError("Maximum 3 coaching exchanges per segment session.")
        return self


# Long voice/typed answers (skills lists, project catalogs) must fit one turn.
_INTERVIEW_TURN_MAX_CHARS = 20_000


class InterviewMessage(BaseModel):
    """One turn in a coached interview session."""
    role: Literal["interviewer", "user"]
    text: str = Field(..., min_length=1, max_length=_INTERVIEW_TURN_MAX_CHARS)


class InterviewNextRequest(BaseModel):
    """Request the next interview question given current conversation history."""
    history: list[InterviewMessage] = Field(
        default_factory=list,
        description="Full conversation so far (interviewer + user turns).",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID for audit / credit-dedup.",
    )
    extra_question_blocks: int = Field(
        default=0,
        ge=0,
        le=1,
        description="0 = 15-question cap; 1 = user opted into +5 more (20 total).",
    )

    @model_validator(mode="after")
    def validate_question_count(self) -> "InterviewNextRequest":
        from app.agent.story_interview import resolve_interview_question_cap

        cap = resolve_interview_question_cap(self.extra_question_blocks)
        interviewer_turns = sum(1 for m in self.history if m.role == "interviewer")
        if interviewer_turns >= cap:
            raise ValueError(
                f"Maximum {cap} interview questions reached. "
                "Submit your answers to generate the resume."
            )
        return self


class InterviewSubmitRequest(BaseModel):
    """Submit completed interview Q&A to generate a resume."""
    history: list[InterviewMessage] = Field(
        ...,
        min_length=2,
        description="Full conversation (must have at least one Q and one A).",
    )
    whisper_path: bool = Field(
        default=False,
        description="True when Whisper transcription was used for any answer.",
    )

    @model_validator(mode="after")
    def validate_has_user_content(self) -> "InterviewSubmitRequest":
        user_words = sum(
            len(m.text.split()) for m in self.history if m.role == "user"
        )
        if user_words < 30:
            raise ValueError(
                "Interview answers are too short. Please answer at least a few questions "
                "before generating your resume."
            )
        return self


class PolishResumeRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Current resume draft text.")
    instruction: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Plain-English editing instruction, e.g. 'make the summary more senior'.",
    )


class StoryToResumeRequest(BaseModel):
    segments: list[str] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Transcript text per segment, in recording order.",
    )
    whisper_path: bool = Field(
        default=False,
        description="True when the Whisper transcription path was used (Firefox/Safari). "
                    "Used for credit routing.",
    )

    @model_validator(mode="after")
    def validate_content(self) -> "StoryToResumeRequest":
        total_words = sum(len(s.split()) for s in self.segments)
        if total_words < 50:
            raise ValueError(
                "Story is too short. Please record at least 50 words across all segments."
            )
        return self


class StoryVerifyRequest(BaseModel):
    segments: list[str] = Field(..., min_length=1, max_length=30)
    resume_text: str = Field(..., min_length=50, max_length=80_000)


class StorySaveRequest(BaseModel):
    resume_text: str = Field(..., min_length=50, max_length=80_000)
    segments: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="Original story segments for audit (optional).",
    )
    attestation_confirmed: bool = Field(
        ...,
        description="User confirmed names, dates, skills, and employers are accurate.",
    )
    whisper_path: bool = False

    @model_validator(mode="after")
    def validate_attestation(self) -> "StorySaveRequest":
        if not self.attestation_confirmed:
            raise ValueError(
                "You must confirm names, dates, and employers before saving to your profile."
            )
        return self
