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
     * system. Phase C fills in the field-level visual indicator
     * (.f13c-flagged class on each flagged input). Phases D/E will
     * extend this to also update the sidebar Flags panel content +
     * the toggle button count badge. */
    function applyState() {
        if (!state) return;
        renderFieldIndicators();
    }

    /* Sync .f13c-flagged class on every form input to match flag
     * state, AND inject / remove a small orange-dot indicator near
     * each flagged input's label.
     *
     * Dots are placed at the label level, not the input level —
     * the player thinks of the field as "the question" (label text),
     * not "the input element," and labels are larger / easier to
     * eyeball at a glance.
     *
     * Anchor resolution (labelAnchorFor):
     *   - Checkboxes inside labels → anchor to the label's last span
     *     (the question text), so the dot trails after the question.
     *   - Text inputs in cells → anchor to the f13c-label sibling
     *     (the field caption), so the dot trails after the caption.
     *   - Fallback → anchor to the input itself.
     *
     * Each dot carries a data-flag-for="<field_id>" attribute so we
     * can find and remove the right one without scanning all dots. */
    function renderFieldIndicators() {
        var formPane = document.getElementById("form-pane");
        if (!formPane) return;
        var flagged = state.flags || {};
        var inputs = formPane.querySelectorAll(
            "input[name], textarea[name], select[name]"
        );
        for (var i = 0; i < inputs.length; i++) {
            var input = inputs[i];
            var fieldId = input.getAttribute("name");
            var shouldBeFlagged = !!flagged[fieldId];
            input.classList.toggle("f13c-flagged", shouldBeFlagged);

            var existingDot = formPane.querySelector(
                '.f13c-flag-dot[data-flag-for="' + cssEscape(fieldId) + '"]'
            );

            if (shouldBeFlagged && !existingDot) {
                var anchor = labelAnchorFor(input);
                if (anchor && anchor.parentNode) {
                    var dot = document.createElement("span");
                    dot.className = "f13c-flag-dot";
                    dot.setAttribute("data-flag-for", fieldId);
                    dot.setAttribute("aria-hidden", "true");
                    anchor.parentNode.insertBefore(dot, anchor.nextSibling);
                }
            } else if (!shouldBeFlagged && existingDot) {
                existingDot.parentNode.removeChild(existingDot);
            }
        }
    }

    /* Pick the visual anchor for the dot — a sibling-or-near element
     * that the dot will be inserted *after* in the DOM. */
    function labelAnchorFor(input) {
        var labelEl = input.closest ? input.closest("label") : null;
        if (labelEl) {
            /* For label-wrapping form rows (most checkboxes), prefer
             * the label's last child element so the dot trails after
             * the question text rather than appearing between the
             * checkbox and its text. */
            var lastChild = labelEl.lastElementChild;
            if (lastChild) return lastChild;
            return labelEl;
        }
        /* For cell-style text inputs (Page 1 personal-info rows),
         * the f13c-label span sits next to the input in the same
         * cell. Anchor the dot just after the caption. */
        var parent = input.parentNode;
        if (parent && parent.querySelector) {
            var labelSpan = parent.querySelector(".f13c-label");
            if (labelSpan) return labelSpan;
        }
        return input;
    }

    /* CSS.escape polyfill — older browsers don't have it, and
     * field IDs contain dots / digits that need escaping in
     * attribute selectors. */
    function cssEscape(s) {
        if (typeof CSS !== "undefined" && CSS.escape) return CSS.escape(s);
        return String(s).replace(/[!"#$%&'()*+,./:;<=>?@[\\\]^`{|}~]/g, "\\$&");
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
