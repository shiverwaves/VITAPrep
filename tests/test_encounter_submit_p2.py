"""Tests for Page 2 submission and grading (Phase 3-E).

End-to-end via FastAPI TestClient: generate a scenario, submit a
form post containing Page 2 inputs, and verify:

1. POST /scenarios/{id}/submit returns 200 with Page 2 inputs in the
   payload.
2. Page 2 fields (income.wages, vol.income.w2, etc.) appear in the
   per-field result feedback.
3. Unchecked checkboxes posting from the form (absent from form_data)
   are graded correctly when the answer key expects "No".
4. The "on" form-post default for checked checkboxes grades correctly
   against "Yes".
5. Notes-column entries surface as ungraded when the player fills
   them; they don't affect the score.
6. Sub-question Y/N pairs (prior-loss, short-term residence rental,
   self-employment prior loss) likewise surface as ungraded when filled.
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

    The Page 2 partial sometimes renders ``class=`` between ``name=``
    and ``value=`` (e.g. ``<input ... name="..." class="..."
    value="...">``), so the regex tolerates any attributes between
    them. type="text" inputs only — checkboxes are handled separately.
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
    """Build a "perfect submission" off the rendered page: every
    text-input value as-is + every currently-checked checkbox sent
    with value="on" (the HTML form-post default)."""
    submission = dict(_scrape_text_inputs(html))
    for name in _checkbox_names(html, only_checked=True):
        submission[name] = "on"
    return submission


def _score_from_html(body: str) -> tuple[int, int]:
    """Parse the score line from the rendered result page."""
    m = re.search(r'(\d+)/(\d+)', body)
    assert m, "could not find score in result"
    return int(m.group(1)), int(m.group(2))


# =========================================================================
# 200 + Page 2 fields surface in the result feedback
# =========================================================================


class TestSubmitReturns200:

    def test_basic_submit_succeeds(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        assert r.status_code == 200

    def test_page2_fields_appear_in_feedback(
        self, client: TestClient,
    ) -> None:
        """Per-row Page 2 fields appear in the per-field feedback
        table on the result page."""
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        body = r.text
        # At minimum the wages row (always in the answer key) shows up.
        assert "income.wages" in body
        # Volunteer column should also appear somewhere in the table.
        assert "vol.income.w2" in body


# =========================================================================
# Unchecked checkbox auto-fill semantics
# =========================================================================


class TestUncheckedCheckboxAutoFill:
    """Unchecked checkboxes don't post anything; the submit handler
    auto-fills them with "No" before grading so the strict
    _values_match still rules them correct against an answer key
    entry of "No"."""

    def test_unchecked_checkboxes_grade_as_no(
        self, client: TestClient,
    ) -> None:
        """Submit only the bare minimum (no checkboxes posted) and
        confirm that an income row whose answer is "No" still grades
        correctly. We can't easily isolate one row, so we assert that
        the score is non-zero (some "No" rows match)."""
        sid = _make_scenario(client)
        # Submit nothing — every checkbox is unchecked, every text
        # field is blank.
        r = client.post(f"/scenarios/{sid}/submit", data={})
        assert r.status_code == 200
        score, max_score = _score_from_html(r.text)
        # The auto-fill turns a blank submission into "No" for every
        # graded checkbox; many income/expense answers are "No" by
        # default, so score > 0 (typically the unchecked rows match).
        assert score > 0
        assert max_score > 0


# =========================================================================
# "on" → "Yes" equivalence (HTML form-post default for checked checkboxes)
# =========================================================================


class TestOnYesEquivalence:
    """Pre-checked checkboxes in the rendered Page 2 partial don't
    have a value= attribute, so when the player submits the form
    they post "on" — the grader's _values_match treats "on" as
    equivalent to "Yes"."""

    def test_on_grades_as_yes(self, client: TestClient) -> None:
        """If the rendered Page 2 has any pre-checked checkbox,
        confirm submitting it as "on" yields a "correct" row in the
        result feedback for that field."""
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        # Find an income.* checkbox that's pre-checked.
        income_checks = [
            n for n in _checkbox_names(page, only_checked=True)
            if n.startswith("income.")
        ]
        if not income_checks:
            pytest.skip("auto-pattern household has no pre-filled income")
        target = income_checks[0]
        submission = _full_perfect_submission(page)
        # submission[target] = "on" (already, via the helper).
        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        body = r.text
        # The target row in the result table must be classed "correct".
        m = re.search(
            rf'<tr class="(\w+)"><td>[^<]*</td><td>{re.escape(target)}',
            body,
        )
        assert m, f"{target} row missing from result table"
        assert m.group(1) == "correct", (
            f"expected correct for {target} (on→Yes broken?); got {m.group(1)}"
        )


# =========================================================================
# Notes column / ungraded sub-questions
# =========================================================================


class TestUngradedSurfacing:

    def test_filling_notes_field_appears_as_ungraded(
        self, client: TestClient,
    ) -> None:
        """Player types a wages-row note → the result UI surfaces it
        with the 'Not graded in this version' label."""
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        submission["income.note.wages"] = "saw two W-2s"

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        assert r.status_code == 200
        body = r.text
        assert "income.note.wages" in body
        assert "Not graded in this version" in body
        assert 'class="ungraded"' in body

    def test_blank_notes_does_not_appear(
        self, client: TestClient,
    ) -> None:
        """If the player leaves all notes blank, no Page 2 ungraded
        rows surface (the result UI suppresses blank-input ungraded
        entries)."""
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        # No notes fields touched.
        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        body = r.text
        # No notes-row should appear in the ungraded section.
        for row in (
            "income.note.wages",
            "income.note.retirement",
            "income.note.ss",
        ):
            # If the field appears at all, it must NOT be in an ungraded
            # row (ungraded rows only surface for non-blank submissions).
            ungraded_match = re.search(
                rf'<tr class="ungraded">[^<]*<td>[^<]*</td>'
                rf'<td>{re.escape(row)}',
                body,
            )
            assert ungraded_match is None, (
                f"{row} surfaced as ungraded despite blank submission"
            )

    def test_filling_subq_yn_appears_as_ungraded(
        self, client: TestClient,
    ) -> None:
        """Sub-question Y/N pairs (e.g. prior-loss) aren't modeled →
        they're in UNGRADED_FIELDS. Filling one surfaces it as
        ungraded in the result table."""
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        submission = _full_perfect_submission(page)
        submission["income.stock_sale.prior_loss.yes"] = "on"

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        body = r.text
        assert "income.stock_sale.prior_loss.yes" in body
        assert "Not graded in this version" in body


# =========================================================================
# Wrong answer drops the score
# =========================================================================


class TestWrongAnswerReducesScore:

    def test_wrong_w2_count_drops_score(
        self, client: TestClient,
    ) -> None:
        """If the household has at least one W-2, a wrong vol.income.w2.count
        entry drops the encounter score by 1 vs. the correct count."""
        sid = _make_scenario(client)
        page = client.get(f"/scenarios/{sid}").text
        # Locate the pre-filled W-2 count to discover the right answer.
        m = re.search(
            r'name="vol\.income\.w2\.count"[^>]*value="(\d+)"', page,
        )
        if m is None:
            pytest.skip("auto-pattern household has no W-2 count")
        right_count = m.group(1)

        right = _full_perfect_submission(page)
        right_r = client.post(f"/scenarios/{sid}/submit", data=right)
        right_score, right_max = _score_from_html(right_r.text)

        wrong = dict(right)
        # Submit a deliberately wrong count.
        wrong_count = str(int(right_count) + 5)
        wrong["vol.income.w2.count"] = wrong_count
        wrong_r = client.post(f"/scenarios/{sid}/submit", data=wrong)
        wrong_score, wrong_max = _score_from_html(wrong_r.text)

        assert wrong_max == right_max, "max_score should be identical"
        assert wrong_score == right_score - 1
