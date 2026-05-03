/* Layout state machine for the encounter workspace.
 *
 * Pure function. No DOM, no globals (other than the namespace export
 * at the bottom), no side effects. Returns a new state object on every
 * transition; never mutates inputs.
 *
 * Wired up by api/static/js/layout-render.js (Phase 2B). The renderer
 * dispatches actions; this module decides the next state.
 *
 * State shape:
 *
 *     {
 *         panes: 1 | 2 | 3,            (max 2 when chatOpen is true)
 *         docSlots: [doc_id | null, ...],   length = panes - 1
 *         chatOpen: boolean,
 *         hiddenDocCache: doc_id | null,    set when chat opens from panes:3
 *         formState: { currentPage: 1..4 }
 *     }
 *
 * Action types:
 *
 *     CYCLE_PANES        { availableDocs: [doc_id, ...] }
 *     TOGGLE_CHAT        {}
 *     SELECT_DOC         { slotIndex, docId }
 *     SET_FORM_PAGE      { page: 1..4 }
 *
 * Pane-cycle is a wrapping forward cycle: 1 → 2 → 3 → 1 → 2 → ...
 * Each click advances; the 3 → 1 wrap drops both docs back to a
 * clean form-only view. The action is a no-op while chatOpen is
 * true (the UI disables the button in that state; the reducer
 * guards as a safety net so a mis-fired event can't corrupt state).
 */

(function (global) {
    "use strict";

    function initialState() {
        return {
            panes: 1,
            docSlots: [],
            chatOpen: false,
            hiddenDocCache: null,
            formState: { currentPage: 1 },
        };
    }

    /* Pick the first doc_id not currently visible in any pane.
     * Falls back to the first available doc if all are visible. */
    function pickNextDoc(availableDocs, currentSlots) {
        if (!availableDocs || availableDocs.length === 0) return null;
        var visible = {};
        for (var i = 0; i < currentSlots.length; i++) {
            if (currentSlots[i] !== null && currentSlots[i] !== undefined) {
                visible[currentSlots[i]] = true;
            }
        }
        for (var j = 0; j < availableDocs.length; j++) {
            if (!visible[availableDocs[j]]) return availableDocs[j];
        }
        return availableDocs[0];
    }

    /* Wrapping cycle: 1 → 2 → 3 → 1. Single forward direction; no
     * endpoint flips, no direction tracking. The pane-cycle button
     * is one-way "next" — click again to keep going. */
    function cyclePanes(state, availableDocs) {
        if (state.chatOpen) return state;  /* disabled while chat open */

        if (state.panes === 1) {
            return Object.assign({}, state, {
                panes: 2,
                docSlots: [pickNextDoc(availableDocs, state.docSlots)],
            });
        }
        if (state.panes === 2) {
            return Object.assign({}, state, {
                panes: 3,
                docSlots: state.docSlots.concat([
                    pickNextDoc(availableDocs, state.docSlots),
                ]),
            });
        }
        if (state.panes === 3) {
            /* 3 → 1: drop both docs (the player wraps back to a clean
             * form-only view; clicking again starts the cycle over). */
            return Object.assign({}, state, {
                panes: 1,
                docSlots: [],
            });
        }
        return state;
    }

    function toggleChat(state) {
        if (!state.chatOpen) {
            /* Open. Caching is only needed when shedding from 3 panes;
             * 1- and 2-pane states keep their pane structure under chat. */
            if (state.panes === 3) {
                return Object.assign({}, state, {
                    chatOpen: true,
                    panes: 2,
                    docSlots: state.docSlots.slice(0, 1),
                    hiddenDocCache: state.docSlots[1],
                });
            }
            return Object.assign({}, state, { chatOpen: true });
        }
        /* Close. Restore the cached doc if we shed one when opening. */
        if (state.hiddenDocCache !== null) {
            return Object.assign({}, state, {
                chatOpen: false,
                panes: 3,
                docSlots: state.docSlots.concat([state.hiddenDocCache]),
                hiddenDocCache: null,
            });
        }
        return Object.assign({}, state, { chatOpen: false });
    }

    function selectDoc(state, slotIndex, docId) {
        if (slotIndex < 0 || slotIndex >= state.docSlots.length) return state;
        if (state.docSlots[slotIndex] === docId) return state;
        var newSlots = state.docSlots.slice();
        newSlots[slotIndex] = docId;
        return Object.assign({}, state, { docSlots: newSlots });
    }

    function setFormPage(state, page) {
        if (state.formState.currentPage === page) return state;
        return Object.assign({}, state, {
            formState: Object.assign({}, state.formState, { currentPage: page }),
        });
    }

    function reduce(state, action) {
        if (!action || typeof action.type !== "string") return state;
        switch (action.type) {
            case "CYCLE_PANES":
                return cyclePanes(state, action.availableDocs || []);
            case "TOGGLE_CHAT":
                return toggleChat(state);
            case "SELECT_DOC":
                return selectDoc(state, action.slotIndex, action.docId);
            case "SET_FORM_PAGE":
                return setFormPage(state, action.page);
            default:
                return state;
        }
    }

    global.LayoutReducer = {
        initialState: initialState,
        reduce: reduce,
    };
}(typeof window !== "undefined" ? window : globalThis));
