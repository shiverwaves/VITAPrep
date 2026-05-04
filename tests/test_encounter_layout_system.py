"""Tests for the encounter view's layout system (Phase 2C).

Covers the chrome and data wiring introduced by Phase 2B:

- The new workspace markup (workspace + form-pane + 2 doc-panes +
  chat-pane).
- The two new titlebar buttons (pane cycle + chat toggle) and the
  hidden-doc badge.
- The retired sidebar markup is gone.
- Data globals (SCENARIO_ID / SCENARIO_DOCS / SCENARIO_DOC_LABELS)
  are injected as parseable JSON before the layout-render.js script.
- Per-case doc-label rendering (single W-2, multiple W-2s, mixed).
- The Submit button is correctly associated with the encounter form
  (wired in 2C polish) and POSTing through the same path the form
  uses still produces a graded result (regression on Phase 1).

What's *not* covered here:

- Browser-driven UI testing (clicking the pane-cycle button,
  toggling chat, etc.). The DOM-mutating renderer code is exercised
  by manual browser passes; automating click-throughs is out of
  scope for 2C.
- Reducer behavior — the JS reducer is exercised manually via
  Node smoke-traces (Phase 2A) and during the manual browser pass.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from api.main import app


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _make_scenario(client: TestClient, pattern: str = "auto") -> str:
    """Create a scenario; return its id."""
    r = client.post(
        "/scenarios/new",
        data={
            "mode": "encounter",
            "difficulty": "easy",
            "pattern": pattern,
            "target_concepts": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, (
        f"new failed: {r.status_code} {r.text[:200]}"
    )
    return r.headers["location"].rsplit("/", 1)[-1]


def _make_scenario_with_dep(client: TestClient) -> str:
    """A scenario reliably containing dependents (and thus more docs)."""
    return _make_scenario(client, "married_couple_with_children")


# =========================================================================
# Workspace structure (Phase 2B)
# =========================================================================


class TestWorkspaceStructure:

    def test_returns_200(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        assert client.get(f"/scenarios/{sid}").status_code == 200

    def test_workspace_default_layout(self, client: TestClient) -> None:
        """Server-rendered default is form-only-full-width so the no-JS
        first paint is never half-hydrated."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert re.search(
            r'<div\s+id="workspace"\s+data-layout="form-only"', body,
        ), "workspace must default to form-only"

    def test_form_pane_contains_sheet(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        # form-pane wraps the sheet div, which contains page-tabs.
        m = re.search(
            r'id="form-pane">\s*(?:<form[^>]*>)?\s*'
            r'.*?<div\s+class="sheet"',
            body, re.DOTALL,
        )
        assert m is not None, "form-pane should wrap the sheet"

    def test_two_doc_pane_skeletons(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        for i in (0, 1):
            assert (
                f'id="doc-pane-{i}" data-pane-index="{i}"' in body
            ), f"missing doc-pane-{i} skeleton"
        # Each pane has a navy title banner and an iframe. (The
        # per-pane tab strip was removed in favor of a single global
        # doc-list bar; each pane now shows just the active doc's
        # title in its banner.)
        assert body.count('class="doc-pane__banner"') == 2
        assert body.count('class="doc-pane__frame"') == 2

    def test_doc_panes_hidden_by_default(self, client: TestClient) -> None:
        """Both doc panes start `hidden`; the renderer un-hides them as
        the player adds panes via pane-cycle."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert re.search(
            r'id="doc-pane-0"[^>]*\bhidden\b', body,
        ), "doc-pane-0 should start hidden"
        assert re.search(
            r'id="doc-pane-1"[^>]*\bhidden\b', body,
        ), "doc-pane-1 should start hidden"

    def test_chat_pane_present(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'id="chat-pane"' in body
        # MVP: three placeholder sub-tabs.
        assert 'data-panel="probes"' in body
        assert 'data-panel="flags"' in body
        assert 'data-panel="notes"' in body


# =========================================================================
# Titlebar buttons (Phase 2B)
# =========================================================================


class TestTitlebarButtons:

    def test_pane_cycle_button_present(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'<button[^>]+id="pane-cycle-btn"[^>]+'
            r'data-layout-action="cycle-panes"[^>]*'
            r'data-next-panes="(\d)"',
            body,
        )
        assert m is not None, "pane-cycle button missing or malformed"
        # Server-rendered default: form-only state, so next click adds a
        # pane → data-next-panes="2".
        assert m.group(1) == "2"

    def test_pane_cycle_has_three_svg_icons(self, client: TestClient) -> None:
        """The icon shown depends on data-next-panes; CSS picks one of
        three svg children. All three must be present in markup so the
        renderer can flip between them by attribute change alone."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        for n in (1, 2, 3):
            assert f'class="layout-btn__icon-{n}"' in body

    def test_chat_toggle_button_present(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'<button[^>]+id="chat-toggle-btn"[^>]+'
            r'data-layout-action="toggle-chat"[^>]*'
            r'aria-pressed="(true|false)"',
            body,
        )
        assert m is not None, "chat-toggle button missing or malformed"
        assert m.group(1) == "false", "chat starts closed"

    def test_hidden_doc_badge_present_and_hidden(
        self, client: TestClient,
    ) -> None:
        """The hidden-doc badge lives inside the chat-toggle button and
        starts `hidden`. The renderer un-hides it when chat is opened
        from a 3-pane state and a doc gets cached."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'<span[^>]+id="hidden-doc-badge"[^>]*\bhidden\b',
            body,
        )
        assert m is not None, "hidden-doc-badge missing or not hidden"

    def test_submit_button_wired_to_form(self, client: TestClient) -> None:
        """2C polish: the submit-btn lives in the titlebar (out of the
        form's DOM tree) but submits via the form="encounter-form"
        association."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'<button[^>]+id="submit-btn"[^>]+'
            r'type="submit"[^>]+form="encounter-form"',
            body,
        )
        assert m is not None, (
            "submit-btn must be type=submit and form=encounter-form"
        )

    def test_encounter_form_action_points_to_submit(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'<form[^>]+id="encounter-form"[^>]+method="post"[^>]+'
            r'action="(/scenarios/[^"]+/submit)"',
            body,
        )
        assert m is not None, "encounter-form action attribute missing"
        assert m.group(1) == f"/scenarios/{sid}/submit"


# =========================================================================
# Retired markup is gone (Phase 2B)
# =========================================================================


class TestRetiredMarkupGone:

    def test_no_sidebar_aside(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'id="sidebar"' not in body
        assert 'class="sidebar' not in body

    def test_no_workspace_classes(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        # The new workspace container uses id only, no class. The old
        # .workspace / .workspace__form / .workspace__doc-left etc.
        # classes are gone.
        assert 'class="workspace"' not in body
        assert 'class="workspace__' not in body

    def test_no_sidebar_script_tag(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'sidebar.js' not in body
        # Layout scripts ARE present.
        assert 'layout-reducer.js' in body
        assert 'layout-render.js' in body


# =========================================================================
# Data globals (Phase 2A + 2B)
# =========================================================================


class TestDataGlobals:

    def test_scenario_id_global(self, client: TestClient) -> None:
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'window\.SCENARIO_ID\s*=\s*"([^"]+)"',
            body,
        )
        assert m is not None
        assert m.group(1) == sid

    def test_scenario_docs_is_parseable_json(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario_with_dep(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'window\.SCENARIO_DOCS\s*=\s*(\{.*?\});',
            body, re.DOTALL,
        )
        assert m is not None
        urls = json.loads(m.group(1))
        assert len(urls) > 0, "expected docs in this scenario"
        # All values are URLs into /scenarios/{sid}/documents/...
        for doc_id, url in urls.items():
            assert url.startswith(
                f"/scenarios/{sid}/documents/"
            ), f"bad URL for {doc_id}: {url}"

    def test_scenario_doc_labels_is_parseable_json(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario_with_dep(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'window\.SCENARIO_DOC_LABELS\s*=\s*(\{.*?\});',
            body, re.DOTALL,
        )
        assert m is not None
        labels = json.loads(m.group(1))
        assert len(labels) > 0
        # Every label is a non-empty string.
        for doc_id, label in labels.items():
            assert isinstance(label, str) and label.strip(), (
                f"empty label for {doc_id}"
            )

    def test_docs_and_labels_share_keys(
        self, client: TestClient,
    ) -> None:
        """The renderer looks up URL and label by the same doc_id; the
        two maps must agree on key set."""
        sid = _make_scenario_with_dep(client)
        body = client.get(f"/scenarios/{sid}").text
        urls_match = re.search(
            r'window\.SCENARIO_DOCS\s*=\s*(\{.*?\});',
            body, re.DOTALL,
        )
        labels_match = re.search(
            r'window\.SCENARIO_DOC_LABELS\s*=\s*(\{.*?\});',
            body, re.DOTALL,
        )
        urls = json.loads(urls_match.group(1))
        labels = json.loads(labels_match.group(1))
        assert set(urls.keys()) == set(labels.keys())


# =========================================================================
# Per-case doc-label rendering (Phase 2A + 2C)
# =========================================================================


class TestDocLabelsRendering:
    """The unit-level label cases are covered exhaustively in
    tests/test_doc_labels.py. These tests confirm the labels survive
    the JSON-encode-and-render round trip into the actual HTML page."""

    def test_typical_household_emits_possessive_labels(
        self, client: TestClient,
    ) -> None:
        sid = _make_scenario_with_dep(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'window\.SCENARIO_DOC_LABELS\s*=\s*(\{.*?\});',
            body, re.DOTALL,
        )
        labels = json.loads(m.group(1))
        # Every label should be of the form "{Name}'s {Type}" since
        # the data model only has person-owned docs today.
        for doc_id, label in labels.items():
            assert "'s " in label, (
                f"expected possessive form, got {label!r} for {doc_id}"
            )

    def test_w2_label_format(self, client: TestClient) -> None:
        """W-2 labels carry the W-2 type token. (Generated householders
        have varied names, so we don't assert the name; we do assert
        the presence of the type token alongside an apostrophe-s.)"""
        sid = _make_scenario_with_dep(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'window\.SCENARIO_DOC_LABELS\s*=\s*(\{.*?\});',
            body, re.DOTALL,
        )
        labels = json.loads(m.group(1))
        w2_labels = [
            v for k, v in labels.items() if k.startswith("w2_")
        ]
        if not w2_labels:
            pytest.skip("scenario produced no W-2s")
        for label in w2_labels:
            assert "W-2" in label
            assert "'s " in label


# =========================================================================
# Submit-flow regression (Phase 1 — confirm 2B/2C didn't break it)
# =========================================================================


class TestSubmitFlowRegression:

    def test_submission_via_form_path_still_grades(
        self, client: TestClient,
    ) -> None:
        """The Submit button was wired up in 2C polish. Hitting the
        same /submit endpoint with the same shape of form data still
        produces a graded result page identical to what Phase 1
        produced."""
        sid = _make_scenario_with_dep(client)
        page = client.get(f"/scenarios/{sid}").text

        # Build a submission: pull every text-input value from the
        # rendered HTML, plus checkbox names that are currently
        # rendered with the `checked` attribute.
        submission = {
            m.group(1): m.group(2)
            for m in re.finditer(
                r'name="([^"]+)" value="([^"]*)"', page
            )
        }
        for m in re.finditer(
            r'<input type="checkbox" name="([^"]+)"([^>]*)>',
            page,
        ):
            if "checked" in m.group(2):
                submission[m.group(1)] = "on"

        r = client.post(f"/scenarios/{sid}/submit", data=submission)
        assert r.status_code == 200
        # Grade / score band rendered.
        assert re.search(r"\d+/\d+", r.text), "no score band"

    def test_action_attribute_round_trip(
        self, client: TestClient,
    ) -> None:
        """The form's action URL points to the same scenario_id-scoped
        /submit route the regression test posts to. (Trivially true,
        but worth pinning so a route rename can't silently break it.)"""
        sid = _make_scenario_with_dep(client)
        body = client.get(f"/scenarios/{sid}").text
        m = re.search(
            r'<form[^>]+id="encounter-form"[^>]+action="([^"]+)"',
            body,
        )
        assert m is not None
        assert m.group(1) == f"/scenarios/{sid}/submit"
