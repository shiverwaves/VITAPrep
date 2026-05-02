"""
Scenario routes — generate exercises, serve documents as HTML,
present interactive encounter forms, and grade submissions server-side.

Endpoints
---------
POST /api/v1/scenarios
    Generate a new scenario and redirect to the exercise page.

GET  /scenarios/{scenario_id}
    Exercise page: links to documents + interactive encounter form.

GET  /scenarios/{scenario_id}/documents/ssn-card/{person_id}
    Render an SSN card as HTML.

GET  /scenarios/{scenario_id}/documents/photo-id/{person_id}
    Render a DL or state ID as HTML.

GET  /scenarios/{scenario_id}/documents/w2/{person_id}/{index}
    Render a W-2 as HTML.

GET  /scenarios/{scenario_id}/documents/1099-int/{person_id}/{index}
    Render a 1099-INT as HTML.

GET  /scenarios/{scenario_id}/documents/1099-div/{person_id}/{index}
    Render a 1099-DIV as HTML.

GET  /scenarios/{scenario_id}/documents/1099-r/{person_id}/{index}
    Render a 1099-R as HTML.

GET  /scenarios/{scenario_id}/documents/ssa-1099/{person_id}
    Render an SSA-1099 as HTML.

GET  /scenarios/{scenario_id}/documents/1099-nec/{person_id}/{index}
    Render a 1099-NEC as HTML.

GET  /scenarios/{scenario_id}/form
    Interactive 13614-C Part I form with <input> fields.

GET  /scenarios/{scenario_id}/form/income
    Interactive 13614-C Part II income form.

GET  /scenarios/{scenario_id}/form/expenses
    Interactive 13614-C Part III expenses form.

POST /scenarios/{scenario_id}/submit
    Grade Part I submission server-side, return results page.

POST /scenarios/{scenario_id}/submit/income
    Grade Part II income submission server-side, return results page.

POST /scenarios/{scenario_id}/submit/expenses
    Grade Part III expenses submission server-side, return results page.

GET  /api/v1/scenarios
    List existing scenarios (JSON).

GET  /api/v1/scenarios/{scenario_id}
    Get scenario metadata (JSON, no answer key).

DELETE /api/v1/scenarios/{scenario_id}
    Delete a scenario.
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from pydantic import BaseModel

from generator.models import PATTERN_METADATA
from training.exercise_engine import ConceptMissed
from training.form_fields import (
    FILING_STATUS,
    FILING_STATUS_CHOICES,
    TEXT_FIELDS,
    CHECKBOX_FIELDS,
    ALL_FIELDS,
    PART1_FIELDS,
    PART2_FIELDS,
    PART3_FIELDS,
    INCOME_CHECKBOX_FIELDS,
    INCOME_AMOUNT_FIELDS,
    INCOME_WAGES,
    INCOME_WAGES_AMOUNT,
    INCOME_INTEREST,
    INCOME_INTEREST_AMOUNT,
    INCOME_DIVIDENDS,
    INCOME_DIVIDENDS_AMOUNT,
    INCOME_SOCIAL_SECURITY,
    INCOME_SOCIAL_SECURITY_AMOUNT,
    INCOME_RETIREMENT,
    INCOME_RETIREMENT_AMOUNT,
    INCOME_SELF_EMPLOYMENT,
    INCOME_SELF_EMPLOYMENT_AMOUNT,
    INCOME_TOTAL,
    EXPENSE_MORTGAGE_INTEREST,
    EXPENSE_MORTGAGE_INTEREST_AMOUNT,
    EXPENSE_PROPERTY_TAXES,
    EXPENSE_PROPERTY_TAXES_AMOUNT,
    EXPENSE_MEDICAL,
    EXPENSE_CHARITABLE,
    EXPENSE_CHARITABLE_AMOUNT,
    EXPENSE_DEDUCTION_TYPE,
    EXPENSE_STUDENT_LOAN,
    EXPENSE_STUDENT_LOAN_AMOUNT,
    EXPENSE_CHILD_CARE,
    EXPENSE_CHILD_CARE_AMOUNT,
    EXPENSE_EDUCATOR,
    EXPENSE_EDUCATOR_AMOUNT,
    EXPENSE_IRA,
    EXPENSE_IRA_AMOUNT,
    EXPENSE_EDUCATION,
    EXPENSE_EDUCATION_AMOUNT,
    DEDUCTION_TYPE_STANDARD,
    DEDUCTION_TYPE_ITEMIZED,
    MAX_DEPENDENTS,
    dep_field,
    DEP_FIRST_NAME,
    DEP_LAST_NAME,
    DEP_DOB,
    DEP_RELATIONSHIP,
    DEP_MONTHS,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =========================================================================
# Pydantic models for JSON API requests
# =========================================================================

class GenerateRequest(BaseModel):
    """Request body for POST /api/v1/scenarios."""
    mode: str = "encounter"
    difficulty: str = "easy"
    error_count: int = 3
    pattern: Optional[str] = None
    seed: Optional[int] = None
    concepts: Optional[List[str]] = None


# =========================================================================
# JSON API endpoints (prefixed /api/v1 by convention)
# =========================================================================

@router.post("/api/v1/scenarios")
async def api_generate_scenario(
    request: Request,
    body: GenerateRequest,
) -> JSONResponse:
    """Generate a new scenario and return its metadata.

    Returns JSON with scenario_id and a redirect URL to the exercise page.
    """
    engine = request.app.state.engine
    store = request.app.state.store

    if body.concepts:
        registered = {c.name for c in engine.concept_catalog.concepts}
        invalid = set(body.concepts) - registered
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown concepts: {', '.join(sorted(invalid))}",
            )

    try:
        scenario = engine.generate_scenario(
            mode=body.mode,
            difficulty=body.difficulty,
            error_count=body.error_count,
            pattern=body.pattern,
            seed=body.seed,
            concepts=body.concepts,
        )
    except ConceptMissed as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    store.save_scenario(scenario)

    logger.info("Created scenario %s via API", scenario.scenario_id)
    return JSONResponse(
        status_code=201,
        content={
            "scenario_id": scenario.scenario_id,
            "mode": scenario.mode,
            "difficulty": scenario.difficulty,
            "pattern": scenario.household.pattern if scenario.household else "",
            "member_count": len(scenario.household.members) if scenario.household else 0,
            "concept_tags": scenario.concept_tags or [],
            "exercise_url": f"/scenarios/{scenario.scenario_id}",
        },
    )


@router.get("/api/v1/scenarios")
async def api_list_scenarios(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    mode: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> JSONResponse:
    """List existing scenarios (metadata only, no answer keys)."""
    store = request.app.state.store
    scenarios = store.list_scenarios(
        limit=limit, offset=offset, mode=mode, difficulty=difficulty,
    )
    items = []
    for s in scenarios:
        items.append({
            "scenario_id": s.scenario_id,
            "mode": s.mode,
            "difficulty": s.difficulty,
            "pattern": s.household.pattern if s.household else "",
            "member_count": len(s.household.members) if s.household else 0,
            "created_at": s.created_at,
            "exercise_url": f"/scenarios/{s.scenario_id}",
        })
    return JSONResponse(content={"scenarios": items, "count": len(items)})


@router.get("/api/v1/scenarios/{scenario_id}")
async def api_get_scenario(
    request: Request,
    scenario_id: str,
) -> JSONResponse:
    """Get scenario metadata (no answer key exposed)."""
    store = request.app.state.store
    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    hh = scenario.household
    members_info = []
    if hh:
        for p in hh.members:
            members_info.append({
                "person_id": p.person_id,
                "relationship": p.relationship.value if hasattr(p.relationship, "value") else str(p.relationship),
                "age": p.age,
                "has_ssn": bool(p.ssn),
                "has_photo_id": bool(p.id_type),
                "id_type": p.id_type,
                "w2_count": len(p.w2s),
                "form_1099_int_count": len(p.form_1099_ints),
                "form_1099_div_count": len(p.form_1099_divs),
                "form_1099_r_count": len(p.form_1099_rs),
                "has_ssa_1099": p.ssa_1099 is not None,
                "form_1099_nec_count": len(p.form_1099_necs),
                "form_1098_count": len(p.form_1098s),
                "form_1098_e_count": len(p.form_1098_es),
                "form_1098_t_count": len(p.form_1098_ts),
            })

    # Build document URLs
    doc_urls: Dict[str, str] = {}
    if hh:
        for p in hh.members:
            pid = p.person_id
            if p.ssn:
                doc_urls[f"ssn_{pid}"] = f"/scenarios/{scenario_id}/documents/ssn-card/{pid}"
            if p.id_type:
                doc_urls[f"id_{pid}"] = f"/scenarios/{scenario_id}/documents/photo-id/{pid}"
            for i in range(len(p.w2s)):
                doc_urls[f"w2_{pid}_{i}"] = f"/scenarios/{scenario_id}/documents/w2/{pid}/{i}"
            for i in range(len(p.form_1099_ints)):
                doc_urls[f"1099int_{pid}_{i}"] = f"/scenarios/{scenario_id}/documents/1099-int/{pid}/{i}"
            for i in range(len(p.form_1099_divs)):
                doc_urls[f"1099div_{pid}_{i}"] = f"/scenarios/{scenario_id}/documents/1099-div/{pid}/{i}"
            for i in range(len(p.form_1099_rs)):
                doc_urls[f"1099r_{pid}_{i}"] = f"/scenarios/{scenario_id}/documents/1099-r/{pid}/{i}"
            if p.ssa_1099 is not None:
                doc_urls[f"ssa1099_{pid}"] = f"/scenarios/{scenario_id}/documents/ssa-1099/{pid}"
            for i in range(len(p.form_1099_necs)):
                doc_urls[f"1099nec_{pid}_{i}"] = f"/scenarios/{scenario_id}/documents/1099-nec/{pid}/{i}"
            for i in range(len(p.form_1098s)):
                doc_urls[f"1098_{pid}_{i}"] = f"/scenarios/{scenario_id}/documents/1098/{pid}/{i}"
            for i in range(len(p.form_1098_es)):
                doc_urls[f"1098e_{pid}_{i}"] = f"/scenarios/{scenario_id}/documents/1098-e/{pid}/{i}"
            for i in range(len(p.form_1098_ts)):
                doc_urls[f"1098t_{pid}_{i}"] = f"/scenarios/{scenario_id}/documents/1098-t/{pid}/{i}"

    return JSONResponse(content={
        "scenario_id": scenario.scenario_id,
        "mode": scenario.mode,
        "difficulty": scenario.difficulty,
        "pattern": hh.pattern if hh else "",
        "members": members_info,
        "document_urls": doc_urls,
        "interview_notes": scenario.interview_notes or [],
        "concept_tags": scenario.concept_tags or [],
        "form_url": f"/scenarios/{scenario_id}/form",
        "exercise_url": f"/scenarios/{scenario_id}",
        "created_at": scenario.created_at,
    })


@router.delete("/api/v1/scenarios/{scenario_id}")
async def api_delete_scenario(
    request: Request,
    scenario_id: str,
) -> JSONResponse:
    """Delete a scenario and its grades."""
    store = request.app.state.store
    deleted = store.delete_scenario(scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return JSONResponse(content={"deleted": True, "scenario_id": scenario_id})


# =========================================================================
# HTML page: generate via browser form
# =========================================================================

@router.get("/scenarios/new", response_class=HTMLResponse)
async def page_new_scenario(request: Request) -> HTMLResponse:
    """Home screen — configure and launch a new scenario."""
    store = request.app.state.store
    templates = request.app.state.templates

    concept_labels = {
        "qualifying_child_residency": "Qualifying Child Residency",
        "hoh_qualifying_person": "Head of Household",
        "refundable_credit_only_filer": "Refundable Credit Only Filer",
        "self_employment_threshold": "Self-Employment Threshold",
        "social_security_taxability": "Social Security Taxability",
        "standard_vs_itemized": "Standard vs. Itemized Deduction",
        "full_time_student_dependent": "Full-Time Student Dependent",
    }

    recent = store.list_scenarios(limit=1)
    resume_id = recent[0].scenario_id if recent else None

    return templates.TemplateResponse(request, "home.html", {
        "patterns": PATTERN_METADATA,
        "concepts": concept_labels,
        "resume_id": resume_id,
    })


@router.post("/scenarios/new")
async def page_create_scenario(
    request: Request,
    mode: str = Form("encounter"),
    difficulty: str = Form("easy"),
    pattern: str = Form(""),
    concepts: Optional[List[str]] = Form(None),
) -> Response:
    """Handle the browser form POST — generate and redirect to exercise."""
    engine = request.app.state.engine
    store = request.app.state.store

    concept_list = concepts if concepts else None

    try:
        scenario = engine.generate_scenario(
            mode=mode,
            difficulty=difficulty,
            pattern=pattern or None,
            concepts=concept_list,
        )
    except ConceptMissed as exc:
        return HTMLResponse(
            content=f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Generation Failed</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #c62828; }}
.message {{ background: #ffebee; padding: 16px; border-radius: 6px; border-left: 4px solid #c62828; }}
.actions {{ margin-top: 24px; }}
.actions a {{ padding: 12px 24px; background: #1a3a5c; color: white; text-decoration: none; border-radius: 4px; }}
</style></head>
<body>
<h1>Generation Failed</h1>
<div class="message">{exc}</div>
<div class="actions"><a href="/scenarios/new">Try Again</a></div>
</body></html>""",
            status_code=422,
        )

    store.save_scenario(scenario)

    logger.info("Created scenario %s via browser", scenario.scenario_id)
    return RedirectResponse(
        url=f"/scenarios/{scenario.scenario_id}",
        status_code=303,
    )


# =========================================================================
# HTML page: encounter screen
# =========================================================================

_PAGE_TABS = [
    {"page": 1, "label": "1·Personal", "section": "encounter",
     "card_title": "Part I — Personal Information"},
    {"page": 2, "label": "2·Income", "section": "income",
     "card_title": "Part II — Income"},
    {"page": 3, "label": "3·Expenses", "section": "expenses",
     "card_title": "Part III — Expenses"},
]

_CATEGORY_PAGE: Dict[str, int] = {
    "citizenship": 1,
    "filing": 1,
    "contact": 1,
    "employment": 1,
    "dependent": 1,
    "address": 1,
    "income": 2,
    "expenses": 3,
    "credits": 3,
}

_CATEGORY_LABELS: Dict[str, str] = {
    "citizenship": "Citizenship",
    "filing": "Filing Status",
    "contact": "Contact Information",
    "employment": "Employment",
    "dependent": "Dependents",
    "address": "Address",
    "income": "Income",
    "expenses": "Expenses & Deductions",
    "credits": "Credits",
}

_CATEGORY_ORDER: Dict[str, int] = {
    "citizenship": 0, "filing": 1, "contact": 2, "employment": 3,
    "dependent": 4, "address": 5, "income": 0, "expenses": 0, "credits": 1,
}


def _group_notes_by_page(
    notes: List[dict],
) -> Dict[int, List[dict]]:
    """Group interview notes by page number, sorted by category order."""
    by_page: Dict[int, List[dict]] = {1: [], 2: [], 3: []}
    for n in notes:
        page = _CATEGORY_PAGE.get(n.get("category", ""), 1)
        by_page.setdefault(page, []).append(n)
    for page_notes in by_page.values():
        page_notes.sort(key=lambda n: _CATEGORY_ORDER.get(n.get("category", ""), 99))
    return by_page


@router.get("/scenarios/{scenario_id}", response_class=HTMLResponse)
async def page_exercise(
    request: Request,
    scenario_id: str,
) -> HTMLResponse:
    """Encounter screen — main gameplay interface."""
    store = request.app.state.store
    templates = request.app.state.templates

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    section_grades = store.get_section_grades(scenario_id)

    page_tabs = []
    for t in _PAGE_TABS:
        graded = t["section"] in section_grades
        page_tabs.append({
            **t,
            "active": t["page"] == 1,
            "complete": graded,
        })

    notes = scenario.interview_notes or []
    notes_by_page = _group_notes_by_page(notes)

    return templates.TemplateResponse(request, "encounter.html", {
        "scenario_id": scenario_id,
        "mode": scenario.mode,
        "difficulty": scenario.difficulty,
        "page_tabs": page_tabs,
        "section_grades": section_grades,
        "notes_by_page": notes_by_page,
        "category_labels": _CATEGORY_LABELS,
    })


# =========================================================================
# HTML: interview notes debug panel
# =========================================================================

@router.get(
    "/scenarios/{scenario_id}/debug/notes",
    response_class=HTMLResponse,
)
async def page_debug_notes(
    request: Request,
    scenario_id: str,
) -> HTMLResponse:
    """Debug view: raw interview notes table for ground-truth inspection."""
    store = request.app.state.store
    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    notes = scenario.interview_notes or []

    rows = ""
    for n in notes:
        slot = n.get("source_slot", "") or ""
        rows += (
            f"<tr>"
            f"<td>{n['category']}</td>"
            f"<td>{n['question']}</td>"
            f"<td><strong>{n['answer']}</strong></td>"
            f"<td class=\"slot\">{slot}</td>"
            f"</tr>\n"
        )

    empty_msg = "" if notes else '<p class="empty">No interview notes for this scenario.</p>'

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Interview Notes — Scenario {scenario_id[:12]}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #1a3a5c; font-size: 20px; }}
.meta {{ font-size: 13px; color: #666; margin-bottom: 16px; }}
.meta span {{ margin-right: 20px; }}
.back-link {{ display: inline-block; margin-bottom: 16px; color: #2c5f8a; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
th {{ background: #f0f4f8; font-size: 11px; text-transform: uppercase; padding: 8px 10px;
      text-align: left; border: 1px solid #ddd; }}
td {{ border: 1px solid #ddd; padding: 6px 10px; font-size: 13px; }}
td.slot {{ font-size: 11px; color: #999; font-family: monospace; }}
.empty {{ color: #999; font-style: italic; }}
.count {{ font-size: 13px; color: #666; margin-bottom: 8px; }}
</style>
</head>
<body>
<a class="back-link" href="/scenarios/{scenario_id}">&larr; Back to scenario</a>
<h1>Interview Notes — Debug View</h1>
<div class="meta">
    <span><strong>Scenario:</strong> {scenario_id[:12]}</span>
    <span><strong>Mode:</strong> {scenario.mode}</span>
    <span><strong>Difficulty:</strong> {scenario.difficulty}</span>
</div>
<p class="count">{len(notes)} notes</p>
{empty_msg}
<table>
<thead>
<tr><th>Category</th><th>Question</th><th>Answer</th><th>Source Slot</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>"""
    return HTMLResponse(content=html)


# =========================================================================
# HTML: individual document renders
# =========================================================================

@router.get(
    "/scenarios/{scenario_id}/documents/ssn-card/{person_id}",
    response_class=HTMLResponse,
)
async def page_ssn_card(
    request: Request,
    scenario_id: str,
    person_id: str,
) -> HTMLResponse:
    """Render a person's SSN card as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    html = renderer.render_ssn_card_html(person)
    # Rewrite the base.css link to use the static mount
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/documents/photo-id/{person_id}",
    response_class=HTMLResponse,
)
async def page_photo_id(
    request: Request,
    scenario_id: str,
    person_id: str,
) -> HTMLResponse:
    """Render a person's photo ID (DL or state ID) as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if not person.id_type:
        raise HTTPException(status_code=404, detail="Person has no photo ID")

    html = renderer.render_photo_id_html(person)
    if html is None:
        raise HTTPException(status_code=404, detail="Could not render photo ID")

    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


# =========================================================================
# HTML: income document renders
# =========================================================================


@router.get(
    "/scenarios/{scenario_id}/documents/w2/{person_id}/{index}",
    response_class=HTMLResponse,
)
async def page_w2(
    request: Request,
    scenario_id: str,
    person_id: str,
    index: int,
) -> HTMLResponse:
    """Render a person's W-2 as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if index < 0 or index >= len(person.w2s):
        raise HTTPException(status_code=404, detail="W-2 index out of range")

    html = renderer.render_w2_html(person, person.w2s[index])
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/documents/1099-int/{person_id}/{index}",
    response_class=HTMLResponse,
)
async def page_1099_int(
    request: Request,
    scenario_id: str,
    person_id: str,
    index: int,
) -> HTMLResponse:
    """Render a person's 1099-INT as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if index < 0 or index >= len(person.form_1099_ints):
        raise HTTPException(status_code=404, detail="1099-INT index out of range")

    html = renderer.render_1099_int_html(person, person.form_1099_ints[index])
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/documents/1099-div/{person_id}/{index}",
    response_class=HTMLResponse,
)
async def page_1099_div(
    request: Request,
    scenario_id: str,
    person_id: str,
    index: int,
) -> HTMLResponse:
    """Render a person's 1099-DIV as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if index < 0 or index >= len(person.form_1099_divs):
        raise HTTPException(status_code=404, detail="1099-DIV index out of range")

    html = renderer.render_1099_div_html(person, person.form_1099_divs[index])
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/documents/1099-r/{person_id}/{index}",
    response_class=HTMLResponse,
)
async def page_1099_r(
    request: Request,
    scenario_id: str,
    person_id: str,
    index: int,
) -> HTMLResponse:
    """Render a person's 1099-R as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if index < 0 or index >= len(person.form_1099_rs):
        raise HTTPException(status_code=404, detail="1099-R index out of range")

    html = renderer.render_1099_r_html(person, person.form_1099_rs[index])
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/documents/ssa-1099/{person_id}",
    response_class=HTMLResponse,
)
async def page_ssa_1099(
    request: Request,
    scenario_id: str,
    person_id: str,
) -> HTMLResponse:
    """Render a person's SSA-1099 as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if person.ssa_1099 is None:
        raise HTTPException(status_code=404, detail="Person has no SSA-1099")

    html = renderer.render_ssa_1099_html(person, person.ssa_1099)
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/documents/1099-nec/{person_id}/{index}",
    response_class=HTMLResponse,
)
async def page_1099_nec(
    request: Request,
    scenario_id: str,
    person_id: str,
    index: int,
) -> HTMLResponse:
    """Render a person's 1099-NEC as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if index < 0 or index >= len(person.form_1099_necs):
        raise HTTPException(status_code=404, detail="1099-NEC index out of range")

    html = renderer.render_1099_nec_html(person, person.form_1099_necs[index])
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


# =========================================================================
# HTML: expense document renders
# =========================================================================


@router.get(
    "/scenarios/{scenario_id}/documents/1098/{person_id}/{index}",
    response_class=HTMLResponse,
)
async def page_1098(
    request: Request,
    scenario_id: str,
    person_id: str,
    index: int,
) -> HTMLResponse:
    """Render a Form 1098 (Mortgage Interest Statement) as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if index < 0 or index >= len(person.form_1098s):
        raise HTTPException(status_code=404, detail="Form 1098 index out of range")

    html = renderer.render_1098_html(person, person.form_1098s[index])
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/documents/1098-e/{person_id}/{index}",
    response_class=HTMLResponse,
)
async def page_1098e(
    request: Request,
    scenario_id: str,
    person_id: str,
    index: int,
) -> HTMLResponse:
    """Render a Form 1098-E (Student Loan Interest) as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if index < 0 or index >= len(person.form_1098_es):
        raise HTTPException(status_code=404, detail="Form 1098-E index out of range")

    html = renderer.render_1098e_html(person, person.form_1098_es[index])
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/documents/1098-t/{person_id}/{index}",
    response_class=HTMLResponse,
)
async def page_1098t(
    request: Request,
    scenario_id: str,
    person_id: str,
    index: int,
) -> HTMLResponse:
    """Render a Form 1098-T (Tuition Statement) as HTML."""
    store = request.app.state.store
    renderer = request.app.state.renderer

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    person = _find_person(scenario, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in scenario")

    if index < 0 or index >= len(person.form_1098_ts):
        raise HTTPException(status_code=404, detail="Form 1098-T index out of range")

    html = renderer.render_1098t_html(person, person.form_1098_ts[index])
    html = html.replace('href="base.css"', 'href="/static/base.css"')
    return HTMLResponse(content=html)


# =========================================================================
# HTML: interactive encounter form
# =========================================================================

@router.get(
    "/scenarios/{scenario_id}/form",
    response_class=HTMLResponse,
)
async def page_encounter_form(
    request: Request,
    scenario_id: str,
) -> HTMLResponse:
    """Interactive 13614-C Part I form with input fields."""
    store = request.app.state.store
    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    hh = scenario.household
    prefill: Dict[str, str] = {}

    # In verify mode, pre-fill the form (may contain injected errors)
    if scenario.mode == "verify" and hh:
        from training.form_populator import build_field_values
        prefill = build_field_values(hh)

    html = _build_encounter_form_html(scenario_id, scenario.mode, prefill)
    return HTMLResponse(content=html)


# =========================================================================
# HTML: Part II income form
# =========================================================================

@router.get(
    "/scenarios/{scenario_id}/form/income",
    response_class=HTMLResponse,
)
async def page_income_form(
    request: Request,
    scenario_id: str,
) -> HTMLResponse:
    """Interactive 13614-C Part II income form."""
    store = request.app.state.store
    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    hh = scenario.household
    prefill: Dict[str, str] = {}

    if scenario.mode == "verify" and hh:
        from training.form_populator import build_field_values
        prefill = build_field_values(hh)

    html = _build_income_form_html(scenario_id, scenario.mode, prefill)
    return HTMLResponse(content=html)


# =========================================================================
# Form submission + grading
# =========================================================================

@router.post(
    "/scenarios/{scenario_id}/submit",
    response_class=HTMLResponse,
)
async def page_submit(
    request: Request,
    scenario_id: str,
) -> HTMLResponse:
    """Grade the submitted Part I form and show results."""
    store = request.app.state.store
    grader = request.app.state.grader

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if scenario.mode != "verify" and scenario.ground_truth is None:
        raise HTTPException(
            status_code=422,
            detail="Scenario has no ground truth. Regenerate the scenario.",
        )

    # Parse form data — Part I fields only
    form_data = await request.form()
    submission: Dict[str, str] = {}
    for field_name in PART1_FIELDS:
        val = form_data.get(field_name, "")
        if isinstance(val, str) and val.strip():
            submission[field_name] = val.strip()

    # Grade based on mode
    if scenario.mode == "verify":
        flagged = []
        for key, val in form_data.items():
            if key.startswith("flag_") and val:
                field_name = key[5:]  # strip "flag_" prefix
                flagged.append({
                    "field": field_name,
                    "description": form_data.get(f"desc_{field_name}", ""),
                })
        result = grader.grade_verification(flagged, scenario.injected_errors)
    else:
        result = grader.grade_encounter(
            submission, scenario.ground_truth, fields=PART1_FIELDS,
        )

    # Save grade with section tag
    store.save_grade(scenario_id, result, section="encounter")

    logger.info(
        "Graded Part I for scenario %s: %d/%d (%.0f%%)",
        scenario_id, result.score, result.max_score, result.accuracy * 100,
    )

    html = _build_results_html(
        scenario_id, scenario.mode, result, section="encounter",
        concept_tags=scenario.concept_tags,
    )
    return HTMLResponse(content=html)


@router.post(
    "/scenarios/{scenario_id}/submit/income",
    response_class=HTMLResponse,
)
async def page_submit_income(
    request: Request,
    scenario_id: str,
) -> HTMLResponse:
    """Grade Part II income submission."""
    store = request.app.state.store
    grader = request.app.state.grader

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if scenario.ground_truth is None:
        raise HTTPException(
            status_code=422,
            detail="Scenario has no ground truth. Regenerate the scenario.",
        )

    form_data = await request.form()
    submission: Dict[str, str] = {}

    for field_name in PART2_FIELDS:
        val = form_data.get(field_name, "")
        if isinstance(val, str) and val.strip():
            submission[field_name] = val.strip()

    result = grader.grade_encounter(
        submission, scenario.ground_truth, fields=PART2_FIELDS,
    )

    store.save_grade(scenario_id, result, section="income")

    logger.info(
        "Graded income for scenario %s: %d/%d (%.0f%%)",
        scenario_id, result.score, result.max_score, result.accuracy * 100,
    )

    html = _build_results_html(
        scenario_id, scenario.mode, result, section="income",
        concept_tags=scenario.concept_tags,
    )
    return HTMLResponse(content=html)


# =========================================================================
# HTML: Part III expenses form
# =========================================================================

@router.get(
    "/scenarios/{scenario_id}/form/expenses",
    response_class=HTMLResponse,
)
async def page_expense_form(
    request: Request,
    scenario_id: str,
) -> HTMLResponse:
    """Interactive 13614-C Part III expenses form."""
    store = request.app.state.store
    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    hh = scenario.household
    prefill: Dict[str, str] = {}

    if scenario.mode == "verify" and hh:
        from training.form_populator import build_field_values
        prefill = build_field_values(hh)

    html = _build_expense_form_html(scenario_id, scenario.mode, prefill)
    return HTMLResponse(content=html)


@router.post(
    "/scenarios/{scenario_id}/submit/expenses",
    response_class=HTMLResponse,
)
async def page_submit_expenses(
    request: Request,
    scenario_id: str,
) -> HTMLResponse:
    """Grade Part III expenses submission."""
    store = request.app.state.store
    grader = request.app.state.grader

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if scenario.ground_truth is None:
        raise HTTPException(
            status_code=422,
            detail="Scenario has no ground truth. Regenerate the scenario.",
        )

    form_data = await request.form()
    submission: Dict[str, str] = {}

    for field_name in PART3_FIELDS:
        val = form_data.get(field_name, "")
        if isinstance(val, str) and val.strip():
            submission[field_name] = val.strip()

    result = grader.grade_encounter(
        submission, scenario.ground_truth, fields=PART3_FIELDS,
    )

    store.save_grade(scenario_id, result, section="expenses")

    logger.info(
        "Graded expenses for scenario %s: %d/%d (%.0f%%)",
        scenario_id, result.score, result.max_score, result.accuracy * 100,
    )

    html = _build_results_html(
        scenario_id, scenario.mode, result, section="expenses",
        concept_tags=scenario.concept_tags,
    )
    return HTMLResponse(content=html)


@router.get(
    "/scenarios/{scenario_id}/results",
    response_class=HTMLResponse,
)
async def page_results(
    request: Request,
    scenario_id: str,
    section: str = "",
) -> HTMLResponse:
    """Show the most recent grading results for a scenario."""
    store = request.app.state.store

    scenario = store.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if section:
        section_grades = store.get_section_grades(scenario_id)
        result = section_grades.get(section)
        if result is None:
            raise HTTPException(status_code=404, detail="No grades found for this section")
    else:
        grades = store.get_grades(scenario_id)
        if not grades:
            raise HTTPException(status_code=404, detail="No grades found for this scenario")
        result = grades[-1]

    html = _build_results_html(
        scenario_id, scenario.mode, result, section=section or "encounter",
        concept_tags=scenario.concept_tags,
    )
    return HTMLResponse(content=html)


# =========================================================================
# Helpers
# =========================================================================

def _find_person(scenario, person_id: str):
    """Find a Person in a scenario by person_id."""
    if scenario.household is None:
        return None
    for p in scenario.household.members:
        if p.person_id == person_id:
            return p
    return None


def _build_encounter_form_html(
    scenario_id: str,
    mode: str,
    prefill: Dict[str, str],
) -> str:
    """Build the interactive 13614-C Part I HTML form.

    Args:
        scenario_id: Scenario identifier.
        mode: Exercise mode ("encounter" or "verify").
        prefill: Pre-filled field values (empty for encounter mode).

    Returns:
        Complete HTML page string.
    """

    def _input(name: str, label: str, size: str = "") -> str:
        val = prefill.get(name, "")
        width = f' style="width:{size}"' if size else ""
        return (
            f'<div class="field">'
            f'<label for="{name}">{label}</label>'
            f'<input type="text" id="{name}" name="{name}" value="{val}"{width}>'
            f'</div>'
        )

    def _radio(name: str, value: str, label: str) -> str:
        checked = ' checked' if prefill.get(name) == value else ""
        return (
            f'<label class="radio">'
            f'<input type="radio" name="{name}" value="{value}"{checked}> {label}'
            f'</label>'
        )

    # Build dependent rows
    dep_rows = ""
    for i in range(MAX_DEPENDENTS):
        fn = dep_field(i, DEP_FIRST_NAME)
        ln = dep_field(i, DEP_LAST_NAME)
        dob = dep_field(i, DEP_DOB)
        rel = dep_field(i, DEP_RELATIONSHIP)
        months = dep_field(i, DEP_MONTHS)
        dep_rows += f"""\
<tr>
    <td><input type="text" name="{fn}" value="{prefill.get(fn, "")}"></td>
    <td><input type="text" name="{ln}" value="{prefill.get(ln, "")}"></td>
    <td><input type="text" name="{dob}" value="{prefill.get(dob, "")}" placeholder="MM/DD/YYYY"></td>
    <td><input type="text" name="{rel}" value="{prefill.get(rel, "")}"></td>
    <td><input type="text" name="{months}" value="{prefill.get(months, "")}" style="width:60px"></td>
</tr>
"""

    mode_label = "Fill in the form from the source documents." if mode == "encounter" else "Review the pre-filled form and correct any errors."

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Encounter Form — Scenario {scenario_id[:12]}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #1a3a5c; font-size: 22px; }}
h2 {{ color: #2c5f8a; font-size: 16px; margin-top: 28px; border-bottom: 2px solid #ddd; padding-bottom: 6px; }}
.instructions {{ background: #fff3cd; padding: 12px 16px; border-radius: 6px; margin-bottom: 24px;
                 border-left: 4px solid #ffc107; }}
.field {{ margin-bottom: 12px; }}
.field label {{ display: block; font-size: 12px; font-weight: bold; color: #555;
                text-transform: uppercase; margin-bottom: 2px; }}
.field input[type="text"] {{ padding: 8px; border: 1px solid #ccc; border-radius: 3px;
                             font-size: 14px; width: 100%; box-sizing: border-box; }}
.row {{ display: flex; gap: 16px; }}
.row .field {{ flex: 1; }}
.radio {{ display: inline-block; margin-right: 16px; font-size: 14px; cursor: pointer; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
th {{ background: #f0f4f8; font-size: 11px; text-transform: uppercase; padding: 6px 8px;
      text-align: left; }}
td {{ padding: 4px; }}
td input {{ width: 100%; padding: 6px; border: 1px solid #ccc; border-radius: 3px;
            font-size: 13px; box-sizing: border-box; }}
.submit-bar {{ margin-top: 32px; text-align: center; }}
.submit-bar button {{ padding: 14px 40px; background: #1a3a5c; color: white; border: none;
                      cursor: pointer; font-size: 16px; border-radius: 4px; }}
.submit-bar button:hover {{ background: #2c5f8a; }}
.back-link {{ display: inline-block; margin-bottom: 16px; color: #2c5f8a; }}
.section-nav {{ display: flex; gap: 0; margin-bottom: 24px; border-bottom: 3px solid #1a3a5c; }}
.section-nav a {{ padding: 10px 20px; text-decoration: none; color: #555; font-weight: bold;
                   font-size: 14px; border: 1px solid #ddd; border-bottom: none; border-radius: 6px 6px 0 0;
                   background: #f0f4f8; margin-right: 4px; }}
.section-nav a.active {{ background: #1a3a5c; color: white; border-color: #1a3a5c; }}
.section-nav a:hover:not(.active) {{ background: #e0e7ef; }}
</style>
</head>
<body>
<a class="back-link" href="/scenarios/{scenario_id}">&larr; Back to scenario</a>
<nav class="section-nav">
    <a href="/scenarios/{scenario_id}/form" class="active">Part I — Personal Info</a>
    <a href="/scenarios/{scenario_id}/form/income">Part II — Income</a>
    <a href="/scenarios/{scenario_id}/form/expenses">Part III — Expenses</a>
</nav>
<h1>Form 13614-C — Part I: Your Personal Information</h1>
<div class="instructions">{mode_label}</div>

<form method="post" action="/scenarios/{scenario_id}/submit">

<h2>Section A: About You</h2>
<div class="row">
    {_input("you.first_name", "First Name")}
    {_input("you.middle_initial", "M.I.", "60px")}
    {_input("you.last_name", "Last Name")}
</div>
<div class="row">
    {_input("you.dob", "Date of Birth (MM/DD/YYYY)")}
    {_input("you.ssn", "Social Security Number")}
</div>
<div class="row">
    {_input("you.phone", "Daytime Phone")}
    {_input("you.email", "Email Address")}
</div>

<h2>Section B: Mailing Address</h2>
<div class="row">
    {_input("addr.street", "Street Address")}
    {_input("addr.apt", "Apt/Unit", "120px")}
</div>
<div class="row">
    {_input("addr.city", "City")}
    {_input("addr.state", "State", "80px")}
    {_input("addr.zip", "ZIP Code", "120px")}
</div>

<h2>Section C: About Your Spouse</h2>
<div class="row">
    {_input("spouse.first_name", "Spouse First Name")}
    {_input("spouse.middle_initial", "M.I.", "60px")}
    {_input("spouse.last_name", "Spouse Last Name")}
</div>
<div class="row">
    {_input("spouse.dob", "Spouse DOB (MM/DD/YYYY)")}
    {_input("spouse.ssn", "Spouse SSN")}
</div>

<h2>Section D: Filing Status</h2>
<div style="margin-bottom: 16px;">
    {_radio("filing_status", "single", "Single")}
    {_radio("filing_status", "married_filing_jointly", "Married Filing Jointly")}
    {_radio("filing_status", "married_filing_separately", "Married Filing Separately")}
    {_radio("filing_status", "head_of_household", "Head of Household")}
    {_radio("filing_status", "qualifying_surviving_spouse", "Qualifying Surviving Spouse")}
</div>

<h2>Section E: Dependents</h2>
<table>
<thead>
<tr><th>First Name</th><th>Last Name</th><th>DOB</th><th>Relationship</th><th>Months</th></tr>
</thead>
<tbody>
{dep_rows}
</tbody>
</table>

<div class="submit-bar">
    <button type="submit">Submit for Grading</button>
</div>
</form>
</body>
</html>"""


_INCOME_ROWS = [
    (INCOME_WAGES, INCOME_WAGES_AMOUNT, "Wages, salaries, tips (W-2)"),
    (INCOME_INTEREST, INCOME_INTEREST_AMOUNT, "Interest income (1099-INT)"),
    (INCOME_DIVIDENDS, INCOME_DIVIDENDS_AMOUNT, "Dividend income (1099-DIV)"),
    (INCOME_SOCIAL_SECURITY, INCOME_SOCIAL_SECURITY_AMOUNT, "Social Security benefits (SSA-1099)"),
    (INCOME_RETIREMENT, INCOME_RETIREMENT_AMOUNT, "Retirement, pension, annuity (1099-R)"),
    (INCOME_SELF_EMPLOYMENT, INCOME_SELF_EMPLOYMENT_AMOUNT, "Self-employment / contract (1099-NEC)"),
]


def _build_income_form_html(
    scenario_id: str,
    mode: str,
    prefill: Dict[str, str],
) -> str:
    """Build the interactive 13614-C Part II income form.

    Args:
        scenario_id: Scenario identifier.
        mode: Exercise mode ("encounter" or "verify").
        prefill: Pre-filled field values (empty for encounter mode).

    Returns:
        Complete HTML page string.
    """
    income_rows = ""
    for cb_field, amt_field, label in _INCOME_ROWS:
        checked = ' checked' if prefill.get(cb_field) == "Yes" else ""
        amt_val = prefill.get(amt_field, "")
        income_rows += f"""\
<tr>
    <td class="cb-cell">
        <input type="checkbox" name="{cb_field}" value="Yes"{checked}>
    </td>
    <td class="source-label">{label}</td>
    <td class="amt-cell">
        <input type="text" name="{amt_field}" value="{amt_val}"
               placeholder="$0" inputmode="numeric">
    </td>
</tr>
"""

    total_val = prefill.get(INCOME_TOTAL, "")
    mode_label = (
        "Using the income documents provided, check each income source "
        "that applies and enter the total amount."
        if mode == "encounter"
        else "Review the pre-filled income fields and correct any errors."
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Income Form — Scenario {scenario_id[:12]}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #1a3a5c; font-size: 22px; }}
.instructions {{ background: #fff3cd; padding: 12px 16px; border-radius: 6px; margin-bottom: 24px;
                 border-left: 4px solid #ffc107; }}
.back-link {{ display: inline-block; margin-bottom: 16px; color: #2c5f8a; }}
.section-nav {{ display: flex; gap: 0; margin-bottom: 24px; border-bottom: 3px solid #1a3a5c; }}
.section-nav a {{ padding: 10px 20px; text-decoration: none; color: #555; font-weight: bold;
                   font-size: 14px; border: 1px solid #ddd; border-bottom: none; border-radius: 6px 6px 0 0;
                   background: #f0f4f8; margin-right: 4px; }}
.section-nav a.active {{ background: #1a3a5c; color: white; border-color: #1a3a5c; }}
.section-nav a:hover:not(.active) {{ background: #e0e7ef; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
th {{ background: #f0f4f8; font-size: 11px; text-transform: uppercase; padding: 8px 12px;
      text-align: left; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
.cb-cell {{ width: 40px; text-align: center; }}
.cb-cell input {{ transform: scale(1.3); }}
.source-label {{ font-size: 14px; }}
.amt-cell {{ width: 160px; }}
.amt-cell input {{ width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 3px;
                    font-size: 14px; box-sizing: border-box; text-align: right; }}
.total-row {{ border-top: 3px solid #1a3a5c; font-weight: bold; }}
.total-row td {{ padding-top: 12px; }}
.submit-bar {{ margin-top: 32px; text-align: center; }}
.submit-bar button {{ padding: 14px 40px; background: #1a3a5c; color: white; border: none;
                      cursor: pointer; font-size: 16px; border-radius: 4px; }}
.submit-bar button:hover {{ background: #2c5f8a; }}
</style>
</head>
<body>
<a class="back-link" href="/scenarios/{scenario_id}">&larr; Back to scenario</a>
<nav class="section-nav">
    <a href="/scenarios/{scenario_id}/form">Part I — Personal Info</a>
    <a href="/scenarios/{scenario_id}/form/income" class="active">Part II — Income</a>
    <a href="/scenarios/{scenario_id}/form/expenses">Part III — Expenses</a>
</nav>
<h1>Form 13614-C — Part II: Income</h1>
<div class="instructions">{mode_label}</div>

<form method="post" action="/scenarios/{scenario_id}/submit/income">

<table>
<thead>
<tr>
    <th>Received?</th>
    <th>Income Source</th>
    <th>Amount</th>
</tr>
</thead>
<tbody>
{income_rows}
<tr class="total-row">
    <td></td>
    <td>Total Income</td>
    <td class="amt-cell">
        <input type="text" name="{INCOME_TOTAL}" value="{total_val}"
               placeholder="$0" inputmode="numeric">
    </td>
</tr>
</tbody>
</table>

<div class="submit-bar">
    <button type="submit">Submit for Grading</button>
</div>
</form>
</body>
</html>"""


_EXPENSE_ROWS = [
    (EXPENSE_MORTGAGE_INTEREST, EXPENSE_MORTGAGE_INTEREST_AMOUNT, "Mortgage interest (Form 1098)"),
    (EXPENSE_PROPERTY_TAXES, EXPENSE_PROPERTY_TAXES_AMOUNT, "Property taxes"),
    (EXPENSE_CHARITABLE, EXPENSE_CHARITABLE_AMOUNT, "Charitable contributions"),
    (EXPENSE_STUDENT_LOAN, EXPENSE_STUDENT_LOAN_AMOUNT, "Student loan interest (Form 1098-E)"),
    (EXPENSE_EDUCATOR, EXPENSE_EDUCATOR_AMOUNT, "Educator expenses"),
    (EXPENSE_IRA, EXPENSE_IRA_AMOUNT, "IRA contributions"),
    (EXPENSE_CHILD_CARE, EXPENSE_CHILD_CARE_AMOUNT, "Child/dependent care"),
    (EXPENSE_EDUCATION, EXPENSE_EDUCATION_AMOUNT, "Education expenses (Form 1098-T)"),
]

_EXPENSE_CHECKBOX_ONLY_ROWS = [
    (EXPENSE_MEDICAL, "Unreimbursed medical/dental expenses"),
]


def _build_expense_form_html(
    scenario_id: str,
    mode: str,
    prefill: Dict[str, str],
) -> str:
    """Build the interactive 13614-C Part III expenses form."""
    expense_rows = ""
    for cb_field, amt_field, label in _EXPENSE_ROWS:
        checked = ' checked' if prefill.get(cb_field) == "Yes" else ""
        amt_val = prefill.get(amt_field, "")
        expense_rows += f"""\
<tr>
    <td class="cb-cell">
        <input type="checkbox" name="{cb_field}" value="Yes"{checked}>
    </td>
    <td class="source-label">{label}</td>
    <td class="amt-cell">
        <input type="text" name="{amt_field}" value="{amt_val}"
               placeholder="$0" inputmode="numeric">
    </td>
</tr>
"""

    for cb_field, label in _EXPENSE_CHECKBOX_ONLY_ROWS:
        checked = ' checked' if prefill.get(cb_field) == "Yes" else ""
        expense_rows += f"""\
<tr>
    <td class="cb-cell">
        <input type="checkbox" name="{cb_field}" value="Yes"{checked}>
    </td>
    <td class="source-label" colspan="2">{label}</td>
</tr>
"""

    deduction_val = prefill.get(EXPENSE_DEDUCTION_TYPE, "")
    std_checked = ' checked' if deduction_val == DEDUCTION_TYPE_STANDARD else ""
    item_checked = ' checked' if deduction_val == DEDUCTION_TYPE_ITEMIZED else ""

    mode_label = (
        "Using the expense documents and client interview notes, check each "
        "expense that applies and enter the amounts. Then choose Standard or "
        "Itemized deduction."
        if mode == "encounter"
        else "Review the pre-filled expense fields and correct any errors."
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Expenses Form — Scenario {scenario_id[:12]}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #1a3a5c; font-size: 22px; }}
h2 {{ color: #2c5f8a; margin-top: 28px; font-size: 18px; }}
.instructions {{ background: #fff3cd; padding: 12px 16px; border-radius: 6px; margin-bottom: 24px;
                 border-left: 4px solid #ffc107; }}
.back-link {{ display: inline-block; margin-bottom: 16px; color: #2c5f8a; }}
.section-nav {{ display: flex; gap: 0; margin-bottom: 24px; border-bottom: 3px solid #1a3a5c; }}
.section-nav a {{ padding: 10px 20px; text-decoration: none; color: #555; font-weight: bold;
                   font-size: 14px; border: 1px solid #ddd; border-bottom: none; border-radius: 6px 6px 0 0;
                   background: #f0f4f8; margin-right: 4px; }}
.section-nav a.active {{ background: #1a3a5c; color: white; border-color: #1a3a5c; }}
.section-nav a:hover:not(.active) {{ background: #e0e7ef; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
th {{ background: #f0f4f8; font-size: 11px; text-transform: uppercase; padding: 8px 12px;
      text-align: left; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
.cb-cell {{ width: 40px; text-align: center; }}
.cb-cell input {{ transform: scale(1.3); }}
.source-label {{ font-size: 14px; }}
.amt-cell {{ width: 160px; }}
.amt-cell input {{ width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 3px;
                    font-size: 14px; box-sizing: border-box; text-align: right; }}
.deduction-choice {{ margin-top: 28px; padding: 20px; background: #f0f4f8; border-radius: 8px; }}
.deduction-choice label {{ font-size: 15px; margin-right: 32px; cursor: pointer; }}
.deduction-choice input {{ transform: scale(1.3); margin-right: 6px; }}
.submit-bar {{ margin-top: 32px; text-align: center; }}
.submit-bar button {{ padding: 14px 40px; background: #1a3a5c; color: white; border: none;
                      cursor: pointer; font-size: 16px; border-radius: 4px; }}
.submit-bar button:hover {{ background: #2c5f8a; }}
</style>
</head>
<body>
<a class="back-link" href="/scenarios/{scenario_id}">&larr; Back to scenario</a>
<nav class="section-nav">
    <a href="/scenarios/{scenario_id}/form">Part I — Personal Info</a>
    <a href="/scenarios/{scenario_id}/form/income">Part II — Income</a>
    <a href="/scenarios/{scenario_id}/form/expenses" class="active">Part III — Expenses</a>
</nav>
<h1>Form 13614-C — Part III: Expenses &amp; Deductions</h1>
<div class="instructions">{mode_label}</div>

<form method="post" action="/scenarios/{scenario_id}/submit/expenses">

<table>
<thead>
<tr>
    <th>Applies?</th>
    <th>Expense / Deduction</th>
    <th>Amount</th>
</tr>
</thead>
<tbody>
{expense_rows}
</tbody>
</table>

<div class="deduction-choice">
    <h2>Deduction Type</h2>
    <label>
        <input type="radio" name="{EXPENSE_DEDUCTION_TYPE}"
               value="{DEDUCTION_TYPE_STANDARD}"{std_checked}>
        Standard Deduction
    </label>
    <label>
        <input type="radio" name="{EXPENSE_DEDUCTION_TYPE}"
               value="{DEDUCTION_TYPE_ITEMIZED}"{item_checked}>
        Itemized Deduction
    </label>
</div>

<div class="submit-bar">
    <button type="submit">Submit for Grading</button>
</div>
</form>
</body>
</html>"""


def _build_results_html(
    scenario_id: str, mode: str, result, section: str = "encounter",
    concept_tags: Optional[List[str]] = None,
) -> str:
    """Build the grading results HTML page.

    Args:
        scenario_id: Scenario identifier.
        mode: Exercise mode.
        result: GradingResult object.
        section: Which form section ("encounter" or "income").

    Returns:
        Complete HTML page string.
    """
    # Score color
    if result.accuracy >= 0.9:
        score_color = "#4caf50"
    elif result.accuracy >= 0.7:
        score_color = "#ff9800"
    else:
        score_color = "#f44336"

    # Per-field feedback table
    field_rows = ""
    if result.field_feedback:
        for fb in result.field_feedback:
            status = fb.get("status", "")
            field = fb.get("field", "")
            if status == "correct":
                icon = "&#10004;"
                row_class = "correct"
                detail = ""
            else:
                icon = "&#10008;"
                row_class = "incorrect"
                expected = fb.get("expected", "")
                submitted = fb.get("submitted", "")
                detail = f'Expected: <strong>{expected}</strong>, You entered: <strong>{submitted}</strong>'
            field_rows += f'<tr class="{row_class}"><td>{icon}</td><td>{field}</td><td>{detail}</td></tr>\n'

    # Verification mode: missed/false flags
    flags_html = ""
    if mode == "verify":
        if result.missed_flags:
            missed_items = "\n".join(
                f'<li><strong>{m["field"]}</strong>: {m.get("explanation", "")}</li>'
                for m in result.missed_flags
            )
            flags_html += f'<h3>Missed Errors</h3><ul>{missed_items}</ul>'
        if result.false_flags:
            false_items = "\n".join(
                f'<li><strong>{m["field"]}</strong>: {m.get("description", "Not an error")}</li>'
                for m in result.false_flags
            )
            flags_html += f'<h3>False Flags</h3><ul>{false_items}</ul>'
        if result.correct_flags:
            correct_items = "\n".join(
                f'<li><strong>{m["field"]}</strong></li>'
                for m in result.correct_flags
            )
            flags_html += f'<h3>Correctly Identified</h3><ul>{correct_items}</ul>'

    field_table = ""
    if field_rows:
        field_table = f"""\
<h2>Per-Field Feedback</h2>
<table>
<thead><tr><th></th><th>Field</th><th>Detail</th></tr></thead>
<tbody>{field_rows}</tbody>
</table>"""

    concepts_html = ""
    if concept_tags:
        tag_labels = {
            "qualifying_child_residency": "Qualifying Child Residency",
            "hoh_qualifying_person": "Head of Household",
            "refundable_credit_only_filer": "Refundable Credit Only Filer",
            "self_employment_threshold": "Self-Employment Threshold",
            "social_security_taxability": "Social Security Taxability",
            "standard_vs_itemized": "Standard vs. Itemized Deduction",
        }
        items = ", ".join(tag_labels.get(t, t) for t in concept_tags)
        concepts_html = (
            f'<div class="concepts"><strong>Concepts tested:</strong> {items}</div>'
        )

    section_labels = {
        "encounter": "Part I — Personal Info",
        "income": "Part II — Income",
        "expenses": "Part III — Expenses",
    }
    section_label = section_labels.get(section, f"Section: {section}")

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Results — Scenario {scenario_id[:12]}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #1a3a5c; }}
h2 {{ color: #2c5f8a; margin-top: 28px; }}
h3 {{ color: #555; margin-top: 20px; }}
.section-tag {{ color: #555; font-size: 14px; font-weight: normal; }}
.score-box {{ text-align: center; padding: 32px; background: #f0f4f8; border-radius: 8px;
              margin-bottom: 24px; }}
.score-number {{ font-size: 48px; font-weight: bold; color: {score_color}; }}
.score-label {{ font-size: 18px; color: #555; margin-top: 8px; }}
.feedback {{ background: #f8f9fa; padding: 16px; border-radius: 6px; margin-bottom: 24px;
             border-left: 4px solid {score_color}; font-size: 15px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #f0f4f8; }}
tr.correct td {{ background: #e8f5e9; }}
tr.incorrect td {{ background: #ffebee; }}
ul {{ line-height: 1.8; }}
.actions {{ margin-top: 32px; text-align: center; }}
.actions a {{ display: inline-block; margin: 0 8px; padding: 12px 24px;
              background: #1a3a5c; color: white; text-decoration: none;
              border-radius: 4px; }}
.actions a:hover {{ background: #2c5f8a; }}
.actions a.secondary {{ background: #6c757d; }}
.concepts {{ background: #e8edf3; padding: 12px 16px; border-radius: 6px; margin-top: 24px;
             font-size: 14px; color: #333; }}
</style>
</head>
<body>
<h1>Grading Results <span class="section-tag">— {section_label}</span></h1>
<div class="score-box">
    <div class="score-number">{result.score}/{result.max_score}</div>
    <div class="score-label">{result.accuracy:.0%} accuracy</div>
</div>
<div class="feedback">{result.feedback}</div>
{field_table}
{flags_html}
{concepts_html}
<div class="actions">
    <a href="/scenarios/{scenario_id}">Back to Scenario</a>
    <a href="/scenarios/{scenario_id}/form{"/income" if section == "income" else ""}" class="secondary">Try Again</a>
    <a href="/scenarios/new" class="secondary">New Scenario</a>
</div>
</body>
</html>"""
