"""Unit tests for story verify hints."""
from app.agent.story_verify import build_verify_items, extract_spoken_companies


SEGMENTS_BRIGHTCART = [
    "I worked at Northline Health since early 2025 as a senior software engineer.",
    "Before that I was at Bright Cart from summer 2019 until February 2022 as a data engineer.",
    "I also built Shelf Mark, a side project for bookstore inventory.",
]

RESUME_BRIGHTCART = """
PROFESSIONAL SUMMARY
Senior engineer with healthcare and e-commerce experience.

EXPERIENCE
Northline Health | Senior Software Engineer | Jan 2025 – Present
• Led platform work

Bright Card | Data Engineer | Jun 2019 – Feb 2022
• Built pipelines

Shelf Mark | Personal Project | 2021 – Present
• Inventory tooling
""".strip()


def test_detects_stt_split_company_names():
    items = build_verify_items(SEGMENTS_BRIGHTCART, RESUME_BRIGHTCART)
    review = [i for i in items if i.status == "review" and i.field == "Employer / organization"]
    assert any("Bright" in i.spoken or "Bright" in i.resume for i in review)


def test_season_vs_month_date_flags_review():
    items = build_verify_items(SEGMENTS_BRIGHTCART, RESUME_BRIGHTCART)
    date_items = [i for i in items if i.field == "Dates"]
    assert any(i.status == "review" and "season" in i.message.lower() for i in date_items)


def test_extract_spoken_companies_finds_at_phrases():
    companies = extract_spoken_companies(SEGMENTS_BRIGHTCART)
    assert any("Northline" in c for c in companies)
    assert any("Bright" in c for c in companies)


SEGMENTS_STUDENT = [
    "I babysit for about five kids in my neighborhood on weekends.",
    "I volunteer at Camas Library shelving books since 2023.",
    "I tutor local shops on basic computer stuff — I'm a student at Skyridge High.",
]

RESUME_STUDENT = """
PROFESSIONAL SUMMARY
High school student interested in technology.

EXPERIENCE
Camas Library | Volunteer | 2023 – Present
• Shelved and organized materials

Skyridge High School | Student | 2022 – Present
• Coursework in computer science
""".strip()


def test_student_speech_does_not_flood_employer_reviews():
    items = build_verify_items(SEGMENTS_STUDENT, RESUME_STUDENT)
    employer_reviews = [
        i for i in items if i.field == "Employer / organization" and i.status == "review"
    ]
    assert len(employer_reviews) <= 4
    spoken_blob = " ".join(i.spoken.lower() for i in employer_reviews)
    assert "babysitting" not in spoken_blob
    assert "five kids" not in spoken_blob
