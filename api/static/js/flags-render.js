/* Flag system renderer + persistence.
 *
 * Single render entry point: applyState() mutates the DOM to reflect
 * the current flag state produced by api/static/js/flags-reducer.js.
 * Everything else dispatches actions through dispatch().
 *
 * Phase B (this file's initial scope) sets up:
 *   - The state container + dispatch + sessionStorage hydration / save
 *   - applyState() as a placeholder that does nothing visible yet
 *   - The public dispatch() entry point so other modules can fire
 *     flag actions (right-click menu lands in Phase C, panel content
 *     in Phase E)
 *
 * Phases C and E fill in applyState() with real DOM mutations
 * (visual indicators on flagged fields; flag-list content in the
 * sidebar panel).
 *
 * Window-globals consumed:
 *   window.FlagsReducer        from flags-reducer.js
 *   window.SCENARIO_ID         string (set in encounter.html)
 */

(function (global) {
    "use strict";

    /* -------- State container -------- */
    var state = null;
    var scenarioId = "";
    var storageKey = "";

    /* -------- Persistence -------- */
    /* Storage key per scenario so flags don't bleed across cases. */
    function storageKeyFor(sid) {
        return "flags-" + (sid || "default");
    }

    function loadPersistedState() {
        if (!storageKey) return null;
        try {
            var raw = sessionStorage.getItem(storageKey);
            if (!raw) return null;
            var parsed = JSON.parse(raw);
            /* Quick shape sanity-check; reject anything that doesn't
             * look like our expected state. */
            if (parsed && typeof parsed === "object"
                    && parsed.flags && typeof parsed.flags === "object"
                    && typeof parsed.tick === "number") {
                return parsed;
            }
            return null;
        } catch (e) {
            return null;
        }
    }

    function persistState() {
        if (!storageKey) return;
        try {
            sessionStorage.setItem(storageKey, JSON.stringify(state));
        } catch (e) {
            /* Quota exceeded or storage disabled — silently drop. The
             * flag mechanic still works in-memory; just won't persist
             * across reloads. */
        }
    }

    /* -------- Action dispatch -------- */
    function dispatch(action) {
        if (!global.FlagsReducer) return;
        var next = global.FlagsReducer.reduce(state, action);
        if (next === state) return;  /* no-op, skip render */
        state = next;
        persistState();
        applyState();
    }

    /* -------- Render -------- */
    /* applyState is the single DOM mutation entry point for the flag
     * system. Two responsibilities:
     *   - field-level visual indicators (Phase C: .f13c-flagged class +
     *     dot in the field's wrapper)
     *   - sidebar Flags panel content + count badge on the toggle
     *     (Phase E: list view, per-row detail submenu, batch actions) */
    function applyState() {
        if (!state) return;
        renderFieldIndicators();
        renderFlagsPanel();
        renderMarkedPill();
    }

    /* -------- Marked panel content -------- */
    /* Bare list of flagged field names. Header / footer / per-row
     * detail submenu / clear-all / send-all were retired — the
     * marked panel is now display-only while we redesign the
     * follow-up workflow. The list still updates live as flags
     * are added or removed elsewhere. */
    function renderFlagsPanel() {
        var pane = document.getElementById("marked-pane");
        if (!pane) return;

        var flags = state.flags || {};
        var fieldIds = Object.keys(flags);

        if (fieldIds.length === 0) {
            pane.innerHTML =
                '<div class="flags-pane__empty">No flags yet.</div>';
            return;
        }

        /* Sort by created_at so flags appear in flag-order. */
        fieldIds.sort(function (a, b) {
            return (flags[a].created_at || 0) - (flags[b].created_at || 0);
        });

        var rows = fieldIds.map(function (fieldId) {
            return (
                '<div class="flags-pane__row flags-pane__row--static">' +
                '<span class="flags-pane__row-field">' +
                escapeHtml(fieldId) +
                '</span>' +
                '</div>'
            );
        }).join("");

        pane.innerHTML = '<div class="flags-pane__body">' + rows + '</div>';
    }

    /* Update the titlebar "Marked: N" pill — both the count and the
     * "has flags" state class. The pill is always present (greyed
     * when count is 0); the .titlebar__pill--has-flags class flips
     * it to the accent-illuminated state when count > 0.
     *
     * The pill itself carries data-layout-action="toggle-sidebar-tool"
     * so clicking it opens / closes the flag panel via the layout-
     * render dispatcher. aria-pressed is managed by layout-render
     * (mirrors state.sidebarTool === "flags"). */
    function renderMarkedPill() {
        var pill = document.getElementById("marked-pill");
        if (!pill) return;
        var count = Object.keys(state.flags || {}).length;
        var countSpan = document.getElementById("marked-pill-count");
        if (countSpan) countSpan.textContent = String(count);
        pill.classList.toggle("titlebar__pill--has-flags", count > 0);
    }

    /* Sync .f13c-flagged class on every form input to match flag
     * state, AND maintain the absolute-positioned orange dot in
     * the top-right corner of each flagged field's wrapper.
     *
     * Wrapper resolution (flagWrapperFor): walk up from the input
     * to the smallest ancestor that contains exactly one named
     * input. That's the same "field's local label area" the
     * right-click handler treats as the field's interactive zone.
     * Examples:
     *   - Checkbox in label → wrapper IS the label
     *   - Text input in f13c-cell → wrapper is the cell
     *   - Page 2/3 sub-question text input → wrapper is f13c-p2-subq
     *
     * The wrapper gets:
     *   - .f13c-flagged-label class (sets position: relative)
     *   - The dot appended as a child <span class="f13c-flag-dot">
     * The dot is positioned absolute top-right via CSS.
     *
     * Two-pass: first wipe all existing flagged-label classes and
     * dots from the form pane; then add fresh ones for currently-
     * flagged fields. Slightly more DOM churn than surgical updates
     * but trivial at our scale (~200 inputs, a few flags) and
     * dramatically simpler. */
    function renderFieldIndicators() {
        var formPane = document.getElementById("form-pane");
        if (!formPane) return;
        var flagged = state.flags || {};

        /* Pass 1: wipe existing dots and wrapper classes. */
        var existingDots = formPane.querySelectorAll(".f13c-flag-dot");
        for (var i = 0; i < existingDots.length; i++) {
            existingDots[i].parentNode.removeChild(existingDots[i]);
        }
        var existingWrappers = formPane.querySelectorAll(".f13c-flagged-label");
        for (var j = 0; j < existingWrappers.length; j++) {
            existingWrappers[j].classList.remove("f13c-flagged-label");
        }

        /* Pass 2: re-mark currently-flagged fields. Always inject a
         * dot somewhere visible — primary path is the wrapper found
         * by flagWrapperFor; fallback is the input's immediate
         * parent so we never silently fail to show the indicator. */
        var inputs = formPane.querySelectorAll(
            "input[name], textarea[name], select[name]"
        );
        for (var k = 0; k < inputs.length; k++) {
            var input = inputs[k];
            var fieldId = input.getAttribute("name");
            var shouldBeFlagged = !!flagged[fieldId];
            input.classList.toggle("f13c-flagged", shouldBeFlagged);
            if (!shouldBeFlagged) continue;

            var wrapper = flagWrapperFor(input, formPane);
            if (!wrapper) {
                /* Fallback: input's immediate parent always exists. */
                wrapper = input.parentNode;
            }
            if (!wrapper) continue;  /* truly broken — bail */
            wrapper.classList.add("f13c-flagged-label");
            var dot = document.createElement("span");
            dot.className = "f13c-flag-dot";
            dot.setAttribute("data-flag-for", fieldId);
            dot.setAttribute("aria-hidden", "true");
            wrapper.appendChild(dot);
        }
    }

    /* Smallest ancestor of `input` (inclusive of immediate parent)
     * that contains exactly one named form input. Mirrors the logic
     * in encounter.js's findFormInput so right-click and dot use
     * the same wrapper. */
    function flagWrapperFor(input, formPane) {
        var cursor = input.parentNode;
        while (cursor && cursor !== formPane && cursor.nodeType === 1) {
            if (cursor.querySelectorAll) {
                var found = cursor.querySelectorAll(
                    "input[name], textarea[name], select[name]"
                );
                if (found.length === 1) return cursor;
                if (found.length > 1) return null;
            }
            cursor = cursor.parentNode;
        }
        return null;
    }

    /* -------- Init -------- */
    function init() {
        if (!global.FlagsReducer) return;

        scenarioId = global.SCENARIO_ID || "";
        storageKey = storageKeyFor(scenarioId);

        var persisted = loadPersistedState();
        state = persisted || global.FlagsReducer.initialState();

        applyState();
    }

    /* -------- Helpers -------- */
    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                "\"": "&quot;",
                "'": "&#39;",
            }[c];
        });
    }

    /* -------- Public surface -------- */
    /* Other modules dispatch through this. The state itself stays
     * private (no external module has a reference; no risk of
     * accidental mutation). */
    global.Flags = {
        dispatch: dispatch,
        /* Read-only snapshot for renderers that need to introspect
         * state without dispatching. Returned object is the live
         * state — callers must treat it as immutable. */
        getState: function () { return state; },
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}(typeof window !== "undefined" ? window : globalThis));
