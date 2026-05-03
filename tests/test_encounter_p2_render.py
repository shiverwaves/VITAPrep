"""Tests for Page 2 rendering inside the encounter view (Phase 3-D wiring).

End-to-end via FastAPI TestClient: generate a scenario, GET the
encounter page, and confirm the new partial / its prefilled values
all reach the rendered HTML. The actual partial content is covered
by tests/test_form_populator_p2.py; this file only verifies the
*wiring* (route → template → static asset link).
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """TestClient with lifespan so app.state.engine / store are wired."""
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


def _page_2_region(html: str) -> str:
    """Slice out the page-2 sheet panel from the rendered encounter."""
    m = re.search(
        r'id="page-2"[^>]*data-page="2"[^>]*>(.*?)id="page-3"',
        html,
        re.DOTALL,
    )
    assert m, "page 2 region not found in encounter HTML"
    return m.group(1)


class TestEncounterPage2Render:

    def test_stylesheet_link_present(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        assert "/app-static/styles/form_13614c_p2.css" in html

    def test_page_two_uses_p2_marker_class(self, client: TestClient) -> None:
        """The Page 2 sheet container carries the sheet__page--p2
        modifier (drives the layout-override CSS in encounter.html)."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        assert "sheet__page--p2" in html

    def test_grid_structure_renders(self, client: TestClient) -> None:
        """The new IRS-faithful three-column grid + cell classes."""
        sid = _make_scenario(client)
        body = _page_2_region(client.get(f"/scenarios/{sid}").text)
        assert "f13c-p2-grid" in body
        assert "f13c-p2-cell--client" in body
        assert "f13c-p2-cell--volunteer" in body
        assert "f13c-p2-cell--notes" in body

    def test_new_namespace_inputs_render(self, client: TestClient) -> None:
        """All 14 row-level client checkboxes from the new namespace
        appear in Page 2's HTML."""
        sid = _make_scenario(client)
        body = _page_2_region(client.get(f"/scenarios/{sid}").text)
        for name in (
            "income.wages",
            "income.tips",
            "income.retirement",
            "income.disability",
            "income.ss",
            "income.unemployment",
            "income.state_refund",
            "income.interest_dividends",
            "income.stock_sale",
            "income.alimony",
            "income.rental",
            "income.self_employment",
            "income.gambling",
            "income.other",
        ):
            assert f'name="{name}"' in body, f"input {name!r} missing"

    def test_volunteer_column_inputs_render(self, client: TestClient) -> None:
        """The volunteer column's count / amount / Y-N entries render."""
        sid = _make_scenario(client)
        body = _page_2_region(client.get(f"/scenarios/{sid}").text)
        for name in (
            "vol.income.w2",
            "vol.income.w2.count",
            "vol.income.1099r",
            "vol.income.ssa",
            "vol.income.1099int",
            "vol.income.1099div",
            "vol.income.schedule_c",
            "vol.income.1099nec",
        ):
            assert f'name="{name}"' in body, (
                f"volunteer input {name!r} missing"
            )

    def test_notes_column_inputs_render(self, client: TestClient) -> None:
        """All 14 free-form per-row notes render with empty values."""
        sid = _make_scenario(client)
        body = _page_2_region(client.get(f"/scenarios/{sid}").text)
        for name in (
            "income.note.wages",
            "income.note.tips",
            "income.note.retirement",
            "income.note.disability",
            "income.note.ss",
            "income.note.unemployment",
            "income.note.state_refund",
            "income.note.interest_dividends",
            "income.note.stock_sale",
            "income.note.alimony",
            "income.note.rental",
            "income.note.self_employment",
            "income.note.gambling",
            "income.note.other",
        ):
            # Notes are blank by default; the populator never emits
            # values for them.
            assert f'name="{name}" class="f13c-p2-notes-input" value=""' in body

    def test_legacy_layout_markers_absent_on_page2(
        self, client: TestClient,
    ) -> None:
        """Page 2 no longer uses the notes-driven sheet__row layout."""
        sid = _make_scenario(client)
        body = _page_2_region(client.get(f"/scenarios/{sid}").text)
        assert "sheet__row" not in body
        assert "sheet__empty-page" not in body


class TestPage2PreFill:
    """The populator's output reaches the rendered HTML for households
    with non-zero income."""

    def test_wages_prefill_when_filer_has_w2(
        self, client: TestClient,
    ) -> None:
        """A scenario whose generated householder has wage income
        renders income.wages as checked + a non-empty W-2 count."""
        sid = _make_scenario(client)
        body = _page_2_region(client.get(f"/scenarios/{sid}").text)

        # If the auto pattern produced wages, both markers fire.
        # If not, neither — skip the assertion path.
        wages_checked = re.search(
            r'name="income\.wages"\s+checked', body,
        )
        if wages_checked is None:
            pytest.skip("auto-pattern household has no wage income")
        assert re.search(r'name="vol\.income\.w2"\s+checked', body)
        # W-2 count input has a non-empty value.
        m = re.search(
            r'name="vol\.income\.w2\.count"[^>]*value="(\d+)"', body,
        )
        assert m is not None, "vol.income.w2.count not populated"
        assert int(m.group(1)) >= 1


class TestPage2NotInPage1Region:
    """Smoke check: the Page 2 partial doesn't bleed into the Page 1
    region. (Helps catch a missing sheet__page wrapper bug.)"""

    def test_page1_region_has_no_page2_grid(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'id="page-1"[^>]*data-page="1"[^>]*>(.*?)id="page-2"',
            html,
            re.DOTALL,
        )
        assert m, "page 1 region not found"
        assert "f13c-p2-grid" not in m.group(1)
