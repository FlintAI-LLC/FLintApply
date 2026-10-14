from __future__ import annotations

from pydantic import BaseModel, Field


class ContactLink(BaseModel):
    """Labeled URL for resume header (LinkedIn, GitHub, portfolio, etc.)."""

    label: str = Field(min_length=1, max_length=40)
    url: str = Field(min_length=1, max_length=512)


__all__ = ["ContactLink"]
