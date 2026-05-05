"""Tests for the Flag-system DOM contract (Phase F).

Two test surfaces:

1. **Render assertions** — using the FastAPI TestClient, check that
   the encounter view emits the DOM the flag JS expects (toggle
   button, sidebar pane, scripts, status bar plumbing). Mirrors
   the encounter-layout-system tests in shape.

2. **Reducer smoke** — runs api/static/js/flags-reducer.js under
   node via subprocess and asserts it behaves correctly across
   the five action types (FLAG_FIELD / UNFLAG_FIELD / SET_CONTEXT /
   SET_ACTION / CLEAR_ALL). The reducer is pure JS with no DOM
   needs, so node executes it directly.

Why subprocess + node rather than a JS test harness in-repo:
- The codebase doesn't have a JS test runner today. Adding one
  for one module is overkill.
- The reducer's been smoke-tested manually in node throughout
  development; this test formalizes that into a regression-safe
  harness.
- pytest stays the single test entry point.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app


REPO = Path(__file__).resolve().parents[1]
FLAGS_REDUCER = REPO / "api" / "static" / "js" / "flags-reducer.js"


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


# =========================================================================
# DOM contract: titlebar buttons, sidebar pane, scripts, status bar
# =========================================================================


class TestFlagSystemDom:
    """The encounter view must emit the DOM the flag JS expects."""

    def test_marked_pill_present(self, client: TestClient) -> None:
        """The titlebar carries a 'Marked: N' pill that displays the
        flag count and toggles the Marked review panel. Replaces the
        former titlebar flag icon button + corner badge.

        Wired with data-layout-action="toggle-marked" so the layout
        renderer's TOGGLE_MARKED handler picks it up. (Marked is its
        own layout axis, not a sidebar tool — it occupies the top
        1/3 of the workspace, not the right column.)"""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'id="marked-pill"' in body
        assert 'data-layout-action="toggle-marked"' in body
        # Pressed state defaults to false on initial render.
        assert 'aria-pressed="false"' in body
        # Inner count span starts at 0.
        assert 'id="marked-pill-count"' in body

    def test_flags_toggle_icon_button_retired(self, client: TestClient) -> None:
        """The standalone flag toggle icon button was retired in
        favor of the titlebar Marked pill. Pin the removal so future
        changes don't reintroduce duplicate affordances."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'id="flags-toggle-btn"' not in body

    def test_chat_toggle_still_works(self, client: TestClient) -> None:
        """Chat toggle didn't break in the sidebar-tool migration —
        it still uses its existing data-layout-action="toggle-chat"
        for back-compat."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'id="chat-toggle-btn"' in body
        assert 'data-layout-action="toggle-chat"' in body

    def test_marked_pane_present(self, client: TestClient) -> None:
        """#marked-pane is the workspace-top container the flag
        renderer populates. Replaces the former #flags-pane (which
        lived in the right column as a sidebar tool); now lives in
        the top 1/3 of the workspace grid as its own layout axis."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'id="marked-pane"' in body
        # Old flags-pane (right-column sidebar tool) is retired.
        assert 'id="flags-pane"' not in body

    def test_chat_pane_still_present(self, client: TestClient) -> None:
        """#chat-pane stays as a sibling of #flags-pane — both share
        the right-column real estate via mutual exclusion."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'id="chat-pane"' in body

    def test_flag_scripts_load_in_order(self, client: TestClient) -> None:
        """flags-reducer must load before flags-render (which
        consumes window.FlagsReducer on init)."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        reducer_pos = body.find("/app-static/js/flags-reducer.js")
        render_pos = body.find("/app-static/js/flags-render.js")
        assert reducer_pos != -1, "flags-reducer.js script tag missing"
        assert render_pos != -1, "flags-render.js script tag missing"
        assert reducer_pos < render_pos, (
            "flags-reducer must load before flags-render"
        )

    def test_contextmenu_css_loaded(self, client: TestClient) -> None:
        """The right-click context menu reuses contextmenu.css from
        base.html. Pin the dependency."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert "/app-static/styles/contextmenu.css" in body

    def test_status_bar_counters_retired(self, client: TestClient) -> None:
        """Both #status-fields and #status-flags were retired from
        the status bar — the slot is reserved for grading info on
        resumed scenarios (future). The flag count is surfaced on
        the #flags-toggle-btn badge instead."""
        sid = _make_scenario(client)
        body = client.get(f"/scenarios/{sid}").text
        assert 'id="status-fields"' not in body
        assert 'id="status-flags"' not in body


# =========================================================================
# Reducer smoke: run flags-reducer.js under node and exercise actions
# =========================================================================


def _node_available() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _node_available(), reason="node not on PATH")
class TestFlagsReducer:
    """Smoke tests for the pure JS reducer. Run by spawning node and
    asserting on stdout. The reducer has no DOM dependencies so node
    can exercise it directly."""

    def _run(self, body: str) -> str:
        """Run a node script that loads the reducer and executes
        `body`. Body should print 'PASS' on success or assert via
        throwing. Returns stdout; test asserts on the return."""
        script = (
            f"var fs = require('fs');\n"
            f"eval(fs.readFileSync({str(FLAGS_REDUCER)!r}, 'utf8'));\n"
            f"var R = global.FlagsReducer;\n"
            f"function eq(a, b, msg) {{\n"
            f"  if (JSON.stringify(a) !== JSON.stringify(b)) {{\n"
            f"    throw new Error(msg + ': expected ' + JSON.stringify(b) + ' got ' + JSON.stringify(a));\n"
            f"  }}\n"
            f"}}\n"
            + body
            + "\nconsole.log('PASS');\n"
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"node exited {result.returncode}\nSTDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )
        return result.stdout

    def test_initial_state_empty(self) -> None:
        out = self._run("""
            var s = R.initialState();
            eq(Object.keys(s.flags).length, 0, 'initial flags should be empty');
            eq(s.tick, 0, 'initial tick should be 0');
        """)
        assert "PASS" in out

    def test_flag_field_adds_with_verb(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'income.wages', verb: 'RequestConfirmation' });
            if (!s.flags['income.wages']) throw new Error('flag not added');
            eq(s.flags['income.wages'].verb, 'RequestConfirmation', 'verb');
            eq(s.flags['income.wages'].target, null, 'target starts null');
            eq(s.flags['income.wages'].channel, null, 'channel starts null');
            eq(s.flags['income.wages'].status, 'draft', 'status starts draft');
            if (s.flags['income.wages'].created_at <= 0) throw new Error('created_at not set');
        """)
        assert "PASS" in out

    def test_flag_field_rejects_invalid_verb(self) -> None:
        out = self._run("""
            var s = R.initialState();
            var before = JSON.stringify(s);
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'x', verb: 'NotARealVerb' });
            eq(JSON.stringify(s), before, 'invalid verb should no-op');
        """)
        assert "PASS" in out

    def test_unflag_removes(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'b', verb: 'RequestConfirmation' });
            s = R.reduce(s, { type: 'UNFLAG_FIELD', field_id: 'a' });
            if (s.flags['a']) throw new Error('flag a should be removed');
            if (!s.flags['b']) throw new Error('flag b should remain');
        """)
        assert "PASS" in out

    def test_set_pill_updates_chain(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Client' });
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Email' });
            eq(s.flags['a'].target, 'Client', 'target set');
            eq(s.flags['a'].channel, 'Email', 'channel set');
            if (!R.isChainComplete(s.flags['a'])) throw new Error('chain should be complete');
        """)
        assert "PASS" in out

    def test_set_pill_no_op_for_unflagged(self) -> None:
        out = self._run("""
            var s = R.initialState();
            var before = JSON.stringify(s);
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Vida' });
            eq(JSON.stringify(s), before, 'set-pill on unflagged is no-op');
        """)
        assert "PASS" in out

    def test_set_pill_rejects_invalid_value(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            var before = JSON.stringify(s);
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Pigeon' });
            eq(JSON.stringify(s), before, 'invalid channel no-op');
        """)
        assert "PASS" in out

    def test_toggle_confirm_requires_complete_chain(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'TOGGLE_CONFIRM', field_id: 'a' });
            eq(s.flags['a'].status, 'draft', 'incomplete chain stays draft');
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Client' });
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Email' });
            s = R.reduce(s, { type: 'TOGGLE_CONFIRM', field_id: 'a' });
            eq(s.flags['a'].status, 'ready', 'complete chain → ready');
            s = R.reduce(s, { type: 'TOGGLE_CONFIRM', field_id: 'a' });
            eq(s.flags['a'].status, 'draft', 'toggle back → draft');
        """)
        assert "PASS" in out

    def test_changing_pill_demotes_ready_when_chain_breaks(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Client' });
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Email' });
            s = R.reduce(s, { type: 'TOGGLE_CONFIRM', field_id: 'a' });
            eq(s.flags['a'].status, 'ready', 'should be ready');
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: null });
            eq(s.flags['a'].status, 'draft', 'incomplete → demoted to draft');
        """)
        assert "PASS" in out

    def test_execute_moves_to_sent(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Vida' });
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Message' });
            s = R.reduce(s, { type: 'EXECUTE_FLAG', field_id: 'a' });
            eq(s.flags['a'].status, 'sent', 'executed → sent');
        """)
        assert "PASS" in out

    def test_execute_no_op_on_incomplete_chain(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            var before = JSON.stringify(s);
            s = R.reduce(s, { type: 'EXECUTE_FLAG', field_id: 'a' });
            eq(JSON.stringify(s), before, 'incomplete execute is no-op');
        """)
        assert "PASS" in out

    def test_send_all_only_sends_ready(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Client' });
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Email' });
            s = R.reduce(s, { type: 'TOGGLE_CONFIRM', field_id: 'a' });
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'b', verb: 'RequestConfirmation' });
            // b stays in draft (chain incomplete)
            s = R.reduce(s, { type: 'SEND_ALL' });
            eq(s.flags['a'].status, 'sent', 'a (ready) sent');
            eq(s.flags['b'].status, 'draft', 'b (draft) untouched');
        """)
        assert "PASS" in out

    def test_sent_row_pills_immutable(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Vida' });
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Message' });
            s = R.reduce(s, { type: 'EXECUTE_FLAG', field_id: 'a' });
            var before = JSON.stringify(s);
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Client' });
            eq(JSON.stringify(s), before, 'sent row is immutable');
        """)
        assert "PASS" in out

    def test_state_round_trips_through_json(self) -> None:
        """State must serialize cleanly so sessionStorage hydration
        round-trips without mutation surprises."""
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'b', verb: 'RequestConfirmation' });
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Client' });
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Email' });
            var json = JSON.stringify(s);
            var parsed = JSON.parse(json);
            eq(JSON.stringify(parsed), json, 'json round-trip stable');
        """)
        assert "PASS" in out

    def test_unknown_action_is_no_op(self) -> None:
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            var before = JSON.stringify(s);
            s = R.reduce(s, { type: 'NOT_A_REAL_ACTION', field_id: 'a' });
            eq(JSON.stringify(s), before, 'unknown action no-op');
        """)
        assert "PASS" in out

    def test_re_flag_preserves_pills_and_status(self) -> None:
        """Re-flagging an already-flagged field updates the verb but
        keeps the target / channel / status — so the player doesn't
        lose work when changing the why."""
        out = self._run("""
            var s = R.initialState();
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestInfo' });
            s = R.reduce(s, { type: 'SET_TARGET', field_id: 'a', target: 'Client' });
            s = R.reduce(s, { type: 'SET_CHANNEL', field_id: 'a', channel: 'Email' });
            s = R.reduce(s, { type: 'TOGGLE_CONFIRM', field_id: 'a' });
            eq(s.flags['a'].status, 'ready', 'ready before re-flag');
            s = R.reduce(s, { type: 'FLAG_FIELD', field_id: 'a', verb: 'RequestConfirmation' });
            eq(s.flags['a'].verb, 'RequestConfirmation', 'verb updated');
            eq(s.flags['a'].target, 'Client', 'target preserved');
            eq(s.flags['a'].channel, 'Email', 'channel preserved');
            eq(s.flags['a'].status, 'ready', 'status preserved');
        """)
        assert "PASS" in out
