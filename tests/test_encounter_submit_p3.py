"""Tests for Page 3 submission and grading (Phase 4-E).

End-to-end via FastAPI TestClient: generate a scenario, submit a
form post containing Page 3 inputs, and verify:

1. POST /scenarios/{id}/submit returns 200 with Page 3 inputs in
   the payload.
2. Page 3 fields (expense.*, vol.expense.*) appear in the per-field
   result feedback.
3. Filling a notes-column entry surfaces it as ungraded.
4. Filling an unmodeled event row (event.hsa, etc.) surfaces it as
   ungraded.
5. A wrong volunteer answer on the standard/itemized deduction
   toggle drops the score.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _make_scenario(client: TestClient) -> str:
    r = client.post(
        "/scenarios/new",
        data={
            "mode": "encounter",
            "difficulty": "easy",
            "pattern": "auto",
            "target_concepts": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    return r.headers["location"].rsplit("/", 1)[-1]


def _scrape_text_inputs(html: str) -> dict:
    """Extract every text input's name → value from rendered HTML.

    Tolerates ``class=`` (and similar) attributes appearing between
    ``name="..."`` and ``value="..."``.
    """
    return {
        m.group(1): m.group(2)
        for m in re.finditer(
            r'<input\s+type="text"\s+name="([^"]+)"[^>]*\bvalue="([^"]*)"',
            html,
        )
    }


def _checkbox_names(html: str, *, only_checked: bool = True) -> set:
    names: set[str] = set()
    pattern = r'<input type="checkbox" name="([^"]+)"([^>]*)>'
    for m in re.finditer(pattern, html):
        is_checked = "checked" in m.group(2)
        if (not only_checked) or is_checked:
            names.add(m.group(1))
    return names


def _full_perfect_submission(html: str) -> dict[str, str]:
    submission = dict(_scrape_text_inputs(html))
    for name in _checkbox_names(html, only_checked=True):
        submission[name] = "on"
    return submission


def _score_from_html(body: str) -> tuple[int, int]:
    m = re.search(r'(\d+)/(\d+)', body)
    assert m, "could not find score in result"
    return int(m.group(1)), int(m.group(2))


# =========================================================================
# 200 + Page 3 fields surface in the result feedback
# =========================================================================


class TestSubmitReturns200:

    def test_basic_submit_succeeds(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        assert r.status_code == 200

    def test_page3_fields_appear_in_feedback(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        body = r.text
        # Itemize section + standard/itemized toggle are always in
        # the answer key regardless of household state.
        assert "expense.medical" in body
        assert "vol.expense.standard_deduction" in body


# =========================================================================
# Notes / unmodeled fields surface as ungraded
# =========================================================================


class TestUngradedSurfacing:

    def test_filling_notes_field_appears_as_ungraded(
        self, client: TestClient,
    ) -> None:
        """Player types an itemize-row note → result UI surfaces it
        with the 'Not graded in this version' label."""
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        submission["expense.note.itemize"] = "client itemizes this year"

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        body = r.text
        assert "expense.note.itemize" in body
        assert "Not graded in this version" in body
        assert 'class="ungraded"' in body

    def test_filling_event_row_appears_as_ungraded(
        self, client: TestClient,
    ) -> None:
        """Tax Related Events client checkboxes aren't modeled →
        checking event.hsa surfaces it as ungraded."""
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        submission["event.hsa"] = "on"

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        body = r.text
        assert "event.hsa" in body
        # Find the event.hsa row and confirm it's ungraded.
        m = re.search(
            r'<tr class="(\w+)"><td>[^<]*</td><td>event\.hsa',
            body,
        )
        assert m, "event.hsa row missing from result table"
        assert m.group(1) == "ungraded", (
            f"expected ungraded for event.hsa; got {m.group(1)}"
        )


# =========================================================================
# Standard / Itemized deduction toggle correctness
# =========================================================================


class TestDeductionToggleScored:
    """The standard / itemized deduction checkboxes are graded against
    household.uses_standard_deduction. Toggling the wrong one drops
    the score by 2 (one for the wrong "Yes", one for the wrong "No")."""

    def test_wrong_deduction_choice_reduces_score(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)

        # Discover the pre-filled choice.
        std_pre = re.search(
            r'name="vol\.expense\.standard_deduction"\s+checked', page,
        )
        item_pre = re.search(
            r'name="vol\.expense\.itemized_deduction"\s+checked', page,
        )
        assert (std_pre is not None) != (item_pre is not None)

        right_r = client.post(f"/scenarios/{sid}/submit", data=submission)
        right_score, right_max = _score_from_html(right_r.text)

        # Flip both — uncheck the right one, check the wrong one.
        wrong = dict(submission)
        if std_pre:
            wrong.pop("vol.expense.standard_deduction", None)
            wrong["vol.expense.itemized_deduction"] = "on"
        else:
            wrong.pop("vol.expense.itemized_deduction", None)
            wrong["vol.expense.standard_deduction"] = "on"

        wrong_r = client.post(f"/scenarios/{sid}/submit", data=wrong)
        wrong_score, wrong_max = _score_from_html(wrong_r.text)

        assert wrong_max == right_max
        # Both standard_deduction and itemized_deduction graded; both
        # flipped → score drops by exactly 2.
        assert wrong_score == right_score - 2
