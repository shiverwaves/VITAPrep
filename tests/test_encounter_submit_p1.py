"""Tests for Page 1 submission and result rendering (Phase 1E).

End-to-end via FastAPI TestClient: generate a scenario, submit a
filled form, and verify:

1. POST /scenarios/{id}/submit with the new namespace returns 200.
2. The result page renders correctly.
3. UNGRADED_FIELDS the player filled in appear with the
   "Not graded in this version" label and an "ungraded" row class.
4. UNGRADED_FIELDS the player left blank do NOT appear (no clutter).
5. Scored volunteer columns (vol_income_under, vol_support,
   vol_home_cost) participate in the score.
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


def _make_scenario_with_dep(client: TestClient) -> str:
    """Create a scenario reliably containing at least one dependent.

    Uses the married-couple-with-children pattern, which always
    generates ≥1 dependent. Volunteer-column tests need a dep present
    so the grader emits answer-key entries for vol_*.
    """
    r = client.post(
        "/scenarios/new",
        data={
            "mode": "encounter",
            "difficulty": "easy",
            "pattern": "married_couple_with_children",
            "target_concepts": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    sid = r.headers["location"].rsplit("/", 1)[-1]
    page = client.get(f"/scenarios/{sid}").text
    m = re.search(r'name="dep\.0\.name" value="([^"]+)"', page)
    if m is None or not m.group(1).strip():
        pytest.skip("married_couple_with_children pattern returned no dep")
    return sid


def _scrape_text_inputs(html: str) -> dict:
    """Extract every text input's name → value from rendered HTML."""
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r'name="([^"]+)" value="([^"]*)"', html)
    }


def _checkbox_names(html: str, *, only_checked: bool = True) -> set:
    """Return the names of (checked) checkboxes in the rendered HTML."""
    names = set()
    pattern = (
        r'<input type="checkbox" name="([^"]+)"([^>]*)>'
    )
    for m in re.finditer(pattern, html):
        is_checked = "checked" in m.group(2)
        if (not only_checked) or is_checked:
            names.add(m.group(1))
    return names


class TestSubmitReturns200:

    def test_basic_submit_succeeds(self, client: TestClient) -> None:
        sid = _make_scenario_with_dep(client)
        page = client.get(f"/scenarios/{sid}").text
        # Build a minimum submission: every text-input value as-is + every
        # currently-checked checkbox sent with value="on".
        submission = dict(_scrape_text_inputs(page))
        for name in _checkbox_names(page, only_checked=True):
            submission[name] = "on"

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        assert r.status_code == 200


class TestUngradedSurfacing:
    """UNGRADED_FIELDS the player filled get a row in the result UI
    labeled 'Not graded in this version'."""

    def test_filling_vol_qc_other_appears_in_results(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario_with_dep(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = dict(_scrape_text_inputs(page))
        for name in _checkbox_names(page, only_checked=True):
            submission[name] = "on"
        # Fill an ungraded volunteer column for dep.0.
        submission["dep.0.vol_qc_other"] = "No"

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        assert r.status_code == 200
        body = r.text
        assert "dep.0.vol_qc_other" in body
        assert "Not graded in this version" in body
        # Row uses the ungraded class.
        assert 'class="ungraded"' in body

    def test_blank_ungraded_does_not_appear(
        self, client: TestClient,
    ) -> None:
        """Player leaves vol_qc_other blank → no row in results."""
        sid = _make_scenario_with_dep(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = dict(_scrape_text_inputs(page))
        for name in _checkbox_names(page, only_checked=True):
            submission[name] = "on"
        # Do NOT set dep.0.vol_qc_other.

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        assert r.status_code == 200
        # Ungraded section should be empty for this submission.
        assert 'class="ungraded"' not in r.text


class TestScoredVolunteerColumns:

    def test_vol_income_under_in_score(self, client: TestClient) -> None:
        """A correct submission for vol_income_under (Yes for a child
        with no income) increments the score; an incorrect one doesn't."""
        sid = _make_scenario_with_dep(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = dict(_scrape_text_inputs(page))
        for name in _checkbox_names(page, only_checked=True):
            submission[name] = "on"

        # Right answer: Yes (the dep is a child with no income).
        right = dict(submission)
        right["dep.0.vol_income_under"] = "Yes"
        right["dep.0.vol_support"] = "Yes"
        right["dep.0.vol_home_cost"] = "Yes"
        right_r = client.post(f"/scenarios/{sid}/submit", data=right)
        right_score = re.search(r'(\d+)/(\d+)', right_r.text)
        assert right_score, "could not find score in result"
        right_correct, right_max = (
            int(right_score.group(1)), int(right_score.group(2)),
        )

        # Now submit with the wrong answer for vol_income_under and
        # confirm the correct count drops by 1 (other answers identical).
        wrong = dict(right)
        wrong["dep.0.vol_income_under"] = "No"
        wrong_r = client.post(f"/scenarios/{sid}/submit", data=wrong)
        wrong_score = re.search(r'(\d+)/(\d+)', wrong_r.text)
        wrong_correct, wrong_max = (
            int(wrong_score.group(1)), int(wrong_score.group(2)),
        )
        assert wrong_max == right_max, "max_score should be identical"
        assert wrong_correct == right_correct - 1


class TestYYesEquivalence:

    def test_y_accepted_for_yes_answer_key(
        self, client: TestClient,
    ) -> None:
        """The pre-fill emits 'Y' for dependent Y/N cells but the answer
        key emits 'Yes'. _values_match treats them as equivalent so a
        player who keeps the pre-filled 'Y' isn't marked wrong."""
        sid = _make_scenario_with_dep(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = dict(_scrape_text_inputs(page))
        for name in _checkbox_names(page, only_checked=True):
            submission[name] = "on"
        # The submission should already contain "Y" for dep.0.us_citizen
        # (pre-filled). Confirm.
        assert submission.get("dep.0.us_citizen") == "Y", (
            "expected pre-fill to render 'Y' for dep.0.us_citizen"
        )

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        body = r.text
        # The dep.0.us_citizen row in the result table must be `correct`.
        # Look for the row containing "dep.0.us_citizen" and verify class.
        m = re.search(
            r'<tr class="(\w+)"><td>[^<]*</td><td>dep\.0\.us_citizen',
            body,
        )
        assert m, "dep.0.us_citizen row not found in result table"
        assert m.group(1) == "correct", (
            f"expected correct; got {m.group(1)} (Y/Yes equivalence broken?)"
        )
