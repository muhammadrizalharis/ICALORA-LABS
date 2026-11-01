"""Katalog 13 fitur ICALORA-LABS (sumber tunggal untuk sidebar frontend)."""

from fastapi import APIRouter

router = APIRouter(tags=["features"])

FEATURES: list[dict] = [
    {"slug": "ai-chat", "name": "AI Chat", "group": "ringan", "phase": 1, "status": "planned"},
    {
        "slug": "grammar-checker",
        "name": "Grammar Checker",
        "group": "ringan",
        "phase": 1,
        "status": "active",
    },
    {
        "slug": "paraphraser",
        "name": "Paraphraser",
        "group": "ringan",
        "phase": 1,
        "status": "active",
    },
    {
        "slug": "ai-rewriter",
        "name": "AI Rewriter",
        "group": "ringan",
        "phase": 1,
        "status": "planned",
    },
    {"slug": "humanizer", "name": "Humanizer", "group": "ringan", "phase": 1, "status": "active"},
    {"slug": "ai-grader", "name": "AI Grader", "group": "ringan", "phase": 1, "status": "planned"},
    {
        "slug": "word-count",
        "name": "Word Count",
        "group": "ringan",
        "phase": 1,
        "status": "active",
    },
    {
        "slug": "citation-finder",
        "name": "Citation Finder",
        "group": "api",
        "phase": 2,
        "status": "planned",
    },
    {
        "slug": "reader-reactions",
        "name": "Reader Reactions",
        "group": "ringan",
        "phase": 1,
        "status": "planned",
    },
    {
        "slug": "resume-builder",
        "name": "Resume Builder",
        "group": "ringan",
        "phase": 1,
        "status": "planned",
    },
    {
        "slug": "ai-detector",
        "name": "AI Detector",
        "group": "berat",
        "phase": 4,
        "status": "planned",
    },
    {"slug": "authorship", "name": "Authorship", "group": "berat", "phase": 4, "status": "planned"},
    {
        "slug": "plagiarism-checker",
        "name": "Plagiarism Checker",
        "group": "berat",
        "phase": 3,
        "status": "active",
    },
]


@router.get("/features")
def list_features() -> dict:
    return {"count": len(FEATURES), "features": FEATURES}
