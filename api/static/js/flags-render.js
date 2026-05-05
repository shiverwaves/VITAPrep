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
        renderFlagsCountBadge();
    }

    /* -------- Sidebar Flags panel -------- */
    /* Internal panel UI state — NOT persisted, NOT in flag-state.
     * Just transient view-model for which subview the user is in. */
    var panelView = "list";          /* "list" | "detail" */
    var panelDetailFieldId = null;   /* the row being edited in detail view */

    var CONTEXT_LABELS = {
        Missing: "Missing Information",
        Confirm: "Needs Confirmation",
        Other: "Other",
    };
    var ACTION_LABELS = {
        Email: "Email",
        Chat: "Chat",
        AskVida: "Ask Vida",
        Other: "Other",
    };
    var CONTEXTS = ["Missing", "Confirm", "Other"];
    var ACTIONS = ["Email", "Chat", "AskVida", "Other"];

    /* Render the entire #flags-pane content based on flag-state +
     * panelView. Always renders (even when the pane is hidden via
     * body[data-sidebar]) so opening the pane shows fresh content. */
    function renderFlagsPanel() {
        var pane = document.getElementById("flags-pane");
        if (!pane) return;

        var flags = state.flags || {};
        var fieldIds = Object.keys(flags);

        /* If we were in detail view but the field got dismissed
         * elsewhere, fall back to the list. */
        if (panelView === "detail" && !flags[panelDetailFieldId]) {
            panelView = "list";
            panelDetailFieldId = null;
        }

        if (fieldIds.length === 0) {
            pane.innerHTML =
                '<div class="flags-pane__empty">No flags yet.<br>' +
                'Right-click any form field to flag it for follow-up.</div>';
            return;
        }

        if (panelView === "detail" && flags[panelDetailFieldId]) {
            pane.innerHTML = renderDetailView(panelDetailFieldId, flags[panelDetailFieldId]);
        } else {
            pane.innerHTML = renderListView(fieldIds, flags);
        }
    }

    function renderListView(fieldIds, flags) {
        /* Sort by created_at so flags appear in flag-order. */
        fieldIds.sort(function (a, b) {
            return (flags[a].created_at || 0) - (flags[b].created_at || 0);
        });

        var rows = fieldIds.map(function (fieldId) {
            var f = flags[fieldId];
            var contextBadge = '<span class="flags-pane__badge flags-pane__badge--context">' +
                escapeHtml(CONTEXT_LABELS[f.context] || f.context) + '</span>';
            var actionBadge = f.action
                ? '<span class="flags-pane__badge flags-pane__badge--action">' +
                  escapeHtml(ACTION_LABELS[f.action] || f.action) + '</span>'
                : '<span class="flags-pane__badge flags-pane__badge--placeholder">No action</span>';
            return (
                '<button type="button" class="flags-pane__row"' +
                ' data-flag-action="open-detail" data-field-id="' + escapeAttr(fieldId) + '">' +
                '<span class="flags-pane__row-field">' + escapeHtml(fieldId) + '</span>' +
                '<span class="flags-pane__row-meta">' + contextBadge + actionBadge + '</span>' +
                '</button>'
            );
        }).join("");

        return (
            '<div class="flags-pane__header">' +
                '<span class="flags-pane__title">Marked for Follow Up</span>' +
                '<span class="flags-pane__count">' + fieldIds.length + '</span>' +
            '</div>' +
            '<div class="flags-pane__body">' + rows + '</div>' +
            '<div class="flags-pane__footer">' +
                '<button type="button" class="flags-pane__btn"' +
                ' data-flag-action="clear-all">Clear all</button>' +
                /* Send all is a placeholder for now — wired when the
                 * probe-send pipeline lands. */
                '<button type="button" class="flags-pane__btn flags-pane__btn--primary"' +
                ' data-flag-action="send-all" disabled' +
                ' title="Coming soon — probe sending lands in a future sprint">' +
                'Send all</button>' +
            '</div>'
        );
    }

    function renderDetailView(fieldId, flag) {
        var contextOptions = CONTEXTS.map(function (ctx) {
            var isActive = flag.context === ctx;
            return (
                '<button type="button" class="flags-pane__option' +
                (isActive ? " flags-pane__option--active" : "") + '"' +
                ' data-flag-action="set-context" data-context="' + ctx + '">' +
                escapeHtml(CONTEXT_LABELS[ctx]) +
                '</button>'
            );
        }).join("");

        var actionOptions = ACTIONS.map(function (act) {
            var isActive = flag.action === act;
            return (
                '<button type="button" class="flags-pane__option' +
                (isActive ? " flags-pane__option--active" : "") + '"' +
                ' data-flag-action="set-action" data-action="' + act + '">' +
                escapeHtml(ACTION_LABELS[act]) +
                '</button>'
            );
        }).join("");
        /* Allow clearing the action — sets status back to draft. */
        actionOptions +=
            '<button type="button" class="flags-pane__option flags-pane__option--clear"' +
            ' data-flag-action="clear-action">No action yet</button>';

        return (
            '<div class="flags-pane__header">' +
                '<button type="button" class="flags-pane__back"' +
                ' data-flag-action="back-to-list" aria-label="Back to list">' +
                '&#8592;</button>' +
                '<span class="flags-pane__title">' + escapeHtml(fieldId) + '</span>' +
            '</div>' +
            '<div class="flags-pane__body">' +
                '<div class="flags-pane__section">' +
                    '<div class="flags-pane__section-title">Context</div>' +
                    contextOptions +
                '</div>' +
                '<div class="flags-pane__section">' +
                    '<div class="flags-pane__section-title">Action</div>' +
                    actionOptions +
                '</div>' +
            '</div>' +
            '<div class="flags-pane__footer">' +
                '<button type="button" class="flags-pane__btn flags-pane__btn--danger"' +
                ' data-flag-action="dismiss" data-field-id="' + escapeAttr(fieldId) + '">' +
                'Dismiss flag</button>' +
            '</div>'
        );
    }

    /* Update the count badge on the Flags toggle button. Hidden when
     * count is 0. */
    function renderFlagsCountBadge() {
        var btn = document.getElementById("flags-toggle-btn");
        if (!btn) return;
        var count = Object.keys(state.flags || {}).length;
        var badge = btn.querySelector(".flags-toggle-badge");
        if (count === 0) {
            if (badge) badge.parentNode.removeChild(badge);
            return;
        }
        if (!badge) {
            badge = document.createElement("span");
            badge.className = "flags-toggle-badge";
            btn.appendChild(badge);
        }
        badge.textContent = String(count);
    }

    /* -------- Panel event delegation -------- */
    /* One click listener on #flags-pane. Each interactive element
     * carries data-flag-action; the dispatcher routes accordingly. */
    function handlePanelClick(e) {
        var target = e.target;
        while (target && target.nodeType === 1) {
            var action = target.getAttribute("data-flag-action");
            if (action) {
                e.preventDefault();
                handlePanelAction(action, target);
                return;
            }
            target = target.parentNode;
        }
    }

    function handlePanelAction(action, element) {
        var fieldId;
        switch (action) {
            case "open-detail":
                fieldId = element.getAttribute("data-field-id");
                if (!fieldId) return;
                panelView = "detail";
                panelDetailFieldId = fieldId;
                renderFlagsPanel();
                return;

            case "back-to-list":
                panelView = "list";
                panelDetailFieldId = null;
                renderFlagsPanel();
                return;

            case "set-context":
                if (!panelDetailFieldId) return;
                var ctx = element.getAttribute("data-context");
                dispatch({
                    type: "SET_CONTEXT",
                    field_id: panelDetailFieldId,
                    context: ctx,
                });
                return;

            case "set-action":
                if (!panelDetailFieldId) return;
                var act = element.getAttribute("data-action");
                dispatch({
                    type: "SET_ACTION",
                    field_id: panelDetailFieldId,
                    action: act,
                });
                return;

            case "clear-action":
                if (!panelDetailFieldId) return;
                dispatch({
                    type: "SET_ACTION",
                    field_id: panelDetailFieldId,
                    action: null,
                });
                return;

            case "dismiss":
                fieldId = element.getAttribute("data-field-id") || panelDetailFieldId;
                if (!fieldId) return;
                dispatch({ type: "UNFLAG_FIELD", field_id: fieldId });
                /* Bounce back to list since the detail target is gone. */
                panelView = "list";
                panelDetailFieldId = null;
                renderFlagsPanel();
                return;

            case "clear-all":
                if (window.confirm("Remove all flags? This cannot be undone.")) {
                    dispatch({ type: "CLEAR_ALL" });
                    panelView = "list";
                    panelDetailFieldId = null;
                }
                return;

            case "send-all":
                /* Placeholder — probe-send pipeline hasn't landed yet. */
                return;
        }
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

        /* Wire one click listener on the flags pane for panel
         * interactions. Outside the pane, no flag-action attributes
         * exist so clicks fall through to other handlers. */
        var pane = document.getElementById("flags-pane");
        if (pane) pane.addEventListener("click", handlePanelClick);

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

    function escapeAttr(s) {
        /* Same character set as escapeHtml — attribute values need
         * the same escapes. */
        return escapeHtml(s);
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
