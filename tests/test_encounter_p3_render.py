"""Tests for Page 3 rendering inside the encounter view (Phase 4-D wiring).

End-to-end via FastAPI TestClient: generate a scenario, GET the
encounter page, and confirm the new partial / its prefilled values
all reach the rendered HTML.
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
    assert r.status_code == 303, f"new failed: {r.status_code} {r.text[:300]}"
    return r.headers["location"].rsplit("/", 1)[-1]


def _page_3_region(html: str) -> str:
    """Slice out the page-3 sheet panel from the rendered encounter.

    Page 3 is currently followed by Page 4 in _PAGE_TABS, so we can
    use ``id="page-4"`` as the boundary; if Page 4 ever disappears,
    fall back to the sheet footer.
    """
    m = re.search(
        r'id="page-3"[^>]*data-page="3"[^>]*>(.*?)(?:id="page-4"|sheet__footer)',
        html,
        re.DOTALL,
    )
    assert m, "page 3 region not found in encounter HTML"
    return m.group(1)


class TestEncounterPage3Render:

    def test_stylesheet_link_present(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        assert "/app-static/styles/form_13614c_p3.css" in html

    def test_page_three_uses_p3_marker_class(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        assert "sheet__page--p3" in html

    def test_partial_marker_present(self, client: TestClient) -> None:
        """The v=phase-4 marker comment is in the partial; if it's
        missing, the legacy code path is being hit instead."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        assert "f13c-p3-partial v=phase-4" in html

    def test_section_headers_render(self, client: TestClient) -> None:
        """All three section banners appear inline inside the first
        cells of each section (3 sections × 3 cell-headers)."""
        sid = _make_scenario(client)
        body = _page_3_region(client.get(f"/scenarios/{sid}").text)
        assert body.count("f13c-p3-cell-header") == 9

    def test_itemize_section_inputs_render(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = _page_3_region(client.get(f"/scenarios/{sid}").text)
        for name in (
            "expense.mortgage_interest",
            "expense.taxes",
            "expense.medical",
            "expense.charitable",
            "vol.expense.1098",
            "vol.expense.standard_deduction",
            "vol.expense.itemized_deduction",
        ):
            assert f'name="{name}"' in body, f"input {name!r} missing"

    def test_other_expenses_section_inputs_render(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario(client)
        body = _page_3_region(client.get(f"/scenarios/{sid}").text)
        for name in (
            "expense.student_loan",
            "expense.child_care",
            "expense.retirement_contrib",
            "expense.educator",
            "expense.alimony_paid",
            "vol.expense.1098e",
            "vol.expense.child_care_credit",
            "vol.expense.ira",
            "vol.expense.educator",
            "vol.expense.alimony_paid",
        ):
            assert f'name="{name}"' in body, f"input {name!r} missing"

    def test_event_section_inputs_render(self, client: TestClient) -> None:
        """All 12 Tax Related Events client checkboxes render."""
        sid = _make_scenario(client)
        body = _page_3_region(client.get(f"/scenarios/{sid}").text)
        for name in (
            "event.education",
            "event.sell_home",
            "event.hsa",
            "event.marketplace",
            "event.energy_home",
            "event.other_purchase",
            "event.debt_cancelled",
            "event.disaster_loss",
            "event.credit_disallowed",
            "event.irs_letter",
            "event.estimated_payments",
            "event.brought_prior_return",
        ):
            assert f'name="{name}"' in body, f"event input {name!r} missing"

    def test_event_volunteer_inputs_render(self, client: TestClient) -> None:
        """The volunteer column for Tax Related Events renders the
        document-receipt checkboxes (1098-T, 1099-S, 1095-A, 1099-C,
        1099-A) and the special inputs (year/reason/VIN)."""
        sid = _make_scenario(client)
        body = _page_3_region(client.get(f"/scenarios/{sid}").text)
        for name in (
            "vol.event.1098t",
            "vol.event.1099s",
            "vol.event.1095a",
            "vol.event.1099c",
            "vol.event.1099a",
            "vol.event.hsa_contributions",
            "vol.event.hsa_distributions",
            "vol.event.energy_credit",
            "vol.event.education_credit",
            "vol.event.taxable_scholarship",
            "vol.event.litc_referral",
            "vol.event.disaster_relief_impacts",
            "vol.event.credit_disallowed",
            "vol.event.credit_disallowed.year",
            "vol.event.credit_disallowed.reason",
            "vol.event.other_purchase.vin",
            "vol.event.estimated_payments",
            "vol.event.estimated_payments.amount",
            "vol.event.prior_refund_applied",
            "vol.event.prior_refund_applied.amount",
            "vol.event.prior_return_available",
        ):
            assert f'name="{name}"' in body, f"event vol input {name!r} missing"

    def test_notes_column_inputs_render(self, client: TestClient) -> None:
        """All 18 free-form per-row notes render with empty values."""
        sid = _make_scenario(client)
        body = _page_3_region(client.get(f"/scenarios/{sid}").text)
        for name in (
            "expense.note.itemize",
            "expense.note.student_loan",
            "expense.note.child_care",
            "expense.note.retirement_contrib",
            "expense.note.educator",
            "expense.note.alimony_paid",
            "event.note.education",
            "event.note.sell_home",
            "event.note.hsa",
            "event.note.marketplace",
            "event.note.energy_home",
            "event.note.other_purchase",
            "event.note.debt_cancelled",
            "event.note.disaster_loss",
            "event.note.credit_disallowed",
            "event.note.irs_letter",
            "event.note.estimated_payments",
            "event.note.brought_prior_return",
        ):
            assert (
                f'name="{name}" class="f13c-p3-notes-input" value=""' in body
            ), f"note input {name!r} missing or pre-filled"


class TestPage3PreFill:
    """The populator's output reaches the rendered HTML."""

    def test_standard_deduction_default(self, client: TestClient) -> None:
        """uses_standard_deduction defaults to True on most generated
        scenarios → the volunteer standard_deduction checkbox renders
        as checked, itemized_deduction as unchecked."""
        sid = _make_scenario(client)
        body = _page_3_region(client.get(f"/scenarios/{sid}").text)
        # Either standard or itemized gets checked, never both.
        std_checked = re.search(
            r'name="vol\.expense\.standard_deduction"\s+checked', body,
        )
        item_checked = re.search(
            r'name="vol\.expense\.itemized_deduction"\s+checked', body,
        )
        assert (std_checked is not None) != (item_checked is not None), (
            "standard/itemized deduction must be exactly one of checked"
        )
