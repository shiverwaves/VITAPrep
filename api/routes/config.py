"""
Config endpoints — available states, household patterns, difficulty levels.

These are read-only reference data endpoints that help the client (or a
future frontend) populate dropdowns and understand what options are available.
"""

import logging
from typing import List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from generator.models import PATTERN_METADATA

logger = logging.getLogger(__name__)
router = APIRouter(tags=["config"])


@router.get("/config/patterns")
async def get_patterns() -> JSONResponse:
    """Return available household patterns and their metadata."""
    patterns = {}
    for name, meta in PATTERN_METADATA.items():
        patterns[name] = {
            "description": meta["description"],
            "complexity": meta.get("complexity", "medium"),
            "expected_adults": meta.get("expected_adults"),
            "expected_children": meta.get("expected_children"),
        }
    return JSONResponse(content={"patterns": patterns})


@router.get("/config/difficulty")
async def get_difficulty_levels() -> JSONResponse:
    """Return available difficulty levels and their descriptions."""
    return JSONResponse(content={
        "levels": {
            "easy": {
                "description": "All client facts provided upfront",
                "client_facts": "all",
            },
            "medium": {
                "description": "Required facts only — student must notice gaps",
                "client_facts": "required_only",
            },
            "hard": {
                "description": "Minimal facts — student must identify what to ask",
                "client_facts": "minimal",
            },
        },
    })


@router.get("/config/modes")
async def get_modes() -> JSONResponse:
    """Return available exercise modes and their descriptions."""
    return JSONResponse(content={
        "modes": {
            "intake": {
                "description": "Fill a blank 13614-C Part I from source documents",
                "student_action": "Fill form fields",
            },
            "verify": {
                "description": "Find errors in a pre-filled form by comparing against documents",
                "student_action": "Flag incorrect fields",
            },
        },
    })
