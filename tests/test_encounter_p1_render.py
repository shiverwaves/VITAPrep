"""Tests for Page 1 rendering inside the encounter view (Phase 1D).

End-to-end via FastAPI TestClient: generate a scenario, GET the
encounter page, and confirm the new partial / its prefilled values /
its ungraded markers all reach the rendered HTML. The actual partial
content is covered by tests/test_form_populator_p1.py; this file only
verifies the *wiring*.
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
    """Create a fresh encounter-mode scenario; return its scenario_id."""
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


class TestEncounterPage1Render:

    def test_encounter_returns_200(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        r = client.get(f"/scenarios/{sid}")
        assert r.status_code == 200

    def test_partial_wrapper_present(self, client: TestClient) -> None:
        """f13c-form-shell wraps the rendered partial."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        assert "f13c-form-shell" in html
        assert "f13c-form" in html

    def test_stylesheet_link_present(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        assert "/app-static/styles/form_13614c_p1.css" in html

    def test_page_one_uses_p1_marker_class(
        self, client: TestClient,
    ) -> None:
        """The Page 1 sheet container carries the sheet__page--p1 modifier
        (drives padding strip in encounter.html)."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        assert "sheet__page--p1" in html

    def test_filer_first_name_input_present(
        self, client: TestClient,
    ) -> None:
        """The new namespace's filer.first_name input renders with a
        non-empty value (pre-filled from the generated householder)."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        m = re.search(r'name="filer\.first_name" value="([^"]+)"', html)
        assert m is not None, "filer.first_name input missing or empty"
        assert m.group(1).strip(), "filer.first_name pre-fill is empty"

    def test_dependent_rows_template_exists(
        self, client: TestClient,
    ) -> None:
        """The {% for i in range(4) %} loop renders all 4 dep slots —
        including blank rows for households with fewer dependents."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        for i in range(4):
            assert f'name="dep.{i}.name"' in html

    def test_ungraded_marker_class_on_two_columns(
        self, client: TestClient,
    ) -> None:
        """vol_qc_other and vol_self_support headers + cells carry the
        f13c-vol-col-ungraded class so the result UI / form headers
        surface them as not graded."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        # Both header and cells use the class — at minimum we should
        # see it appearing 1 (header) + 4 (cells) = 5 times per
        # ungraded column. Check once for presence rather than
        # counting (count depends on layout details).
        assert "f13c-vol-col-ungraded" in html
        assert "Not graded" in html

    def test_page_2_keeps_legacy_layout(self, client: TestClient) -> None:
        """Pages 2-4 still use the existing notes-driven sheet__row
        layout — Phase 1D scope is Page 1 only."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        # Find page-2 region; require sheet__row to live inside it.
        page2_region = re.search(
            r'id="page-2"[^>]*data-page="2"[^>]*>(.*?)id="page-3"',
            html,
            re.DOTALL,
        )
        assert page2_region, "page 2 region not found"
        # At least one sheet__row OR a sheet__empty-page placeholder
        # must be present (means we're on the legacy code path).
        body = page2_region.group(1)
        legacy_marker = "sheet__row" in body or "sheet__empty-page" in body
        assert legacy_marker, "page 2 not using legacy layout"

    def test_no_legacy_you_namespace_in_page1(
        self, client: TestClient,
    ) -> None:
        """The new partial uses filer.* names; no `name="you.*"` should
        appear inside the Page 1 region."""
        sid = _make_scenario(client)
        html = client.get(f"/scenarios/{sid}").text
        # Extract the Page 1 region.
        region = re.search(
            r'sheet__page--p1[^>]*>(.*?)<div class="sheet__page',
            html,
            re.DOTALL,
        )
        if region is None:
            # Page 1 might be the last sheet page in the loop; try EOL.
            region = re.search(
                r'sheet__page--p1[^>]*>(.*?)Catalog Number',
                html,
                re.DOTALL,
            )
        assert region, "could not isolate Page 1 region"
        body = region.group(1)
        assert 'name="you.first_name"' not in body
        assert 'name="you.dob"' not in body
