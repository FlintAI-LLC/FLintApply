from __future__ import annotations

from pydantic import BaseModel


class ContactInfo(BaseModel):
    name: str = ""
    email: str = ""
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    location: str | None = None
    website: str | None = None


class ExperienceEntry(BaseModel):
    title: str = ""
    company: str = ""
    dates: str = ""
    bullets: list[str] = []


class ProjectEntry(BaseModel):
    name: str = ""
    description: str | None = None
    bullets: list[str] = []
    url: str | None = None


class EducationEntry(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str | None = None
    notes: str | None = None


class AwardEntry(BaseModel):
    title: str
    issuer: str | None = None
    date: str | None = None
    description: str | None = None


class VolunteerEntry(BaseModel):
    organization: str
    role: str
    dates: str | None = None
    description: str | None = None


class LanguageEntry(BaseModel):
    language: str
    proficiency: str | None = None


class PublicationEntry(BaseModel):
    title: str
    publisher: str | None = None
    date: str | None = None
    url: str | None = None


class ParsedResume(BaseModel):
    contact: ContactInfo = ContactInfo()
    summary: str | None = None
    skills: list[str] = []
    experience: list[ExperienceEntry] = []
    projects: list[ProjectEntry] = []
    education: list[EducationEntry] = []
    certifications: list[str] = []
    awards: list[AwardEntry] = []
    volunteer: list[VolunteerEntry] = []
    languages: list[LanguageEntry] = []
    publications: list[PublicationEntry] = []
