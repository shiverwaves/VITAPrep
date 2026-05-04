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
 *         paneRecency: [number, number],    monotonic-counter timestamps
 *         tick: number,                     increments on each pane touch
 *         formState: { currentPage: 1..4 }
 *     }
 *
 * Action types:
 *
 *     CYCLE_PANES        { availableDocs: [doc_id, ...] }
 *     TOGGLE_CHAT        {}
 *     SELECT_DOC         { slotIndex, docId }
 *     OPEN_DOC           { docId }
 *     SET_FORM_PAGE      { page: 1..4 }
 *
 * Pane-cycle is a wrapping forward cycle: 1 → 2 → 3 → 1 → 2 → ...
 * Each click advances; the 3 → 1 wrap drops both docs back to a
 * clean form-only view. The action is a no-op while chatOpen is
 * true (the UI disables the button in that state; the reducer
 * guards as a safety net so a mis-fired event can't corrupt state).
 *
 * OPEN_DOC is dispatched by clicking a pill in the global doc-list
 * bar. It promotes the layout (1 → 2 panes) when needed and assigns
 * the doc to the least-recently-touched pane in 3-pane mode.
 * Pane *count* is owned exclusively by CYCLE_PANES (and the chat
 * toggle); OPEN_DOC only changes pane *contents* — except it may
 * promote 1 → 2 when there's no doc pane to put the new doc in.
 *
 * paneRecency tracks last-touched ticks per slot index. Any action
 * that writes to docSlots[i] bumps the global tick counter and
 * stamps paneRecency[i] with the new tick; the OPEN_DOC handler in
 * 3-pane mode picks the slot with the smaller (older) recency value.
 */

(function (global) {
    "use strict";

    function initialState() {
        return {
            panes: 1,
            docSlots: [],
            chatOpen: false,
            hiddenDocCache: null,
            paneRecency: [0, 0],
            tick: 0,
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

    /* Bump the monotonic tick and stamp paneRecency[slotIndex] with
     * the new tick. Returns a partial state ({ tick, paneRecency })
     * to merge into the next state via Object.assign. */
    function bumpRecency(state, slotIndex) {
        var newTick = (state.tick || 0) + 1;
        var newRecency = (state.paneRecency || [0, 0]).slice();
        newRecency[slotIndex] = newTick;
        return { tick: newTick, paneRecency: newRecency };
    }

    /* Pick the slot with the smaller (older) recency timestamp.
     * Ties resolve to slot 0. Used by OPEN_DOC in 3-pane mode. */
    function pickRecencyTarget(paneRecency) {
        if (!paneRecency) return 0;
        return paneRecency[0] <= paneRecency[1] ? 0 : 1;
    }

    /* Linear scan of docSlots for an exact match. */
    function isDocInSlots(docId, docSlots) {
        for (var i = 0; i < docSlots.length; i++) {
            if (docSlots[i] === docId) return true;
        }
        return false;
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
            }, bumpRecency(state, 0));
        }
        if (state.panes === 2) {
            return Object.assign({}, state, {
                panes: 3,
                docSlots: state.docSlots.concat([
                    pickNextDoc(availableDocs, state.docSlots),
                ]),
            }, bumpRecency(state, 1));
        }
        if (state.panes === 3) {
            /* 3 → 1: drop both docs (the player wraps back to a clean
             * form-only view; clicking again starts the cycle over).
             * No recency bump — we're not assigning a doc, just
             * clearing both slots. */
            return Object.assign({}, state, {
                panes: 1,
                docSlots: [],
            });
        }
        return state;
    }

    /* OPEN_DOC — clicking a pill in the global doc-list bar.
     *
     * Behavior by current layout:
     * - doc already visible in some pane → no-op (focus pulse is
     *   strictly visual, handled by the renderer).
     * - panes:1 (form-only) → promote to panes:2 with the new doc
     *   in slot 0. The chat-open form-only-chat variant promotes to
     *   h2-chat (panes:2 + chatOpen) the same way.
     * - panes:2 → replace docSlots[0]. Only one doc pane exists,
     *   so the "pane count owned by the layout toggle" rule means
     *   we don't add a second pane — we replace.
     * - panes:3 → write to the slot whose paneRecency is smaller
     *   (the least-recently-touched pane). Tiebreaker: slot 0.
     */
    function openDoc(state, docId) {
        if (!docId) return state;
        if (isDocInSlots(docId, state.docSlots)) return state;

        if (state.panes === 1) {
            return Object.assign({}, state, {
                panes: 2,
                docSlots: [docId],
            }, bumpRecency(state, 0));
        }
        if (state.panes === 2) {
            var newSlots2 = state.docSlots.slice();
            newSlots2[0] = docId;
            return Object.assign({}, state, {
                docSlots: newSlots2,
            }, bumpRecency(state, 0));
        }
        if (state.panes === 3) {
            var target = pickRecencyTarget(state.paneRecency);
            var newSlots3 = state.docSlots.slice();
            newSlots3[target] = docId;
            return Object.assign({}, state, {
                docSlots: newSlots3,
            }, bumpRecency(state, target));
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

    /* SELECT_DOC — direct slot-targeted assignment, dispatched by
     * the per-pane dropdown (Phase 4). Bumps paneRecency for the
     * touched slot so the OPEN_DOC alternation in 3-pane mode
     * correctly treats this pane as the most-recently-touched one. */
    function selectDoc(state, slotIndex, docId) {
        if (slotIndex < 0 || slotIndex >= state.docSlots.length) return state;
        if (!docId) return state;
        if (state.docSlots[slotIndex] === docId) return state;
        var newSlots = state.docSlots.slice();
        newSlots[slotIndex] = docId;
        return Object.assign({}, state, {
            docSlots: newSlots,
        }, bumpRecency(state, slotIndex));
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
            case "OPEN_DOC":
                return openDoc(state, action.docId);
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
