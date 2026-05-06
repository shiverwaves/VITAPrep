/* Layout state machine for the encounter workspace.
 *
 * Pure function. No DOM, no globals (other than the namespace export
 * at the bottom), no side effects. Returns a new state object on every
 * transition; never mutates inputs.
 *
 * State shape:
 *
 *     {
 *         docSlots: [] | [doc_id],     length 0 or 1 — drives layout
 *         sidebarTool: null | "chat",  what occupies the right column
 *         chatOpen: boolean,           derived from sidebarTool, kept in sync
 *         markedOpen: boolean,         marked panel visible in top 1/3
 *         formState: { currentPage: 1..4 }
 *     }
 *
 * Layout (six combinations):
 *
 *     marked  chat  docSlots  layout name           visual
 *     -----   ----  --------  -------------------   ----------------------
 *      no      no    []       form-only             full-screen form
 *      no      no    [d]      h2                    form top, doc bottom
 *      no      yes   []       form-only-chat        form left + chat right
 *      no      yes   [d]      h2-chat               form/doc split + chat
 *      yes     any   []       form-only-marked      marked top + form bottom
 *      yes     any   [d]      doc-only-marked       marked top + doc bottom
 *                                                   (form is "cached")
 *
 * The "form cached" cue (greyed form pill in the doc-list) is a render-
 * side derivation from `markedOpen && docSlots.length > 0`. There's no
 * cache field — `docSlots` is the single source of truth for what's
 * in the bottom slot. Closing Marked never restores anything; whatever
 * was in `docSlots` at close-time stays through.
 *
 * Action types:
 *
 *     OPEN_DOC           { docId }            set docSlots to [docId]
 *     CLOSE_DOC          { docId }            clear docSlots (X on doc pane)
 *     SHOW_FORM          {}                   clear docSlots (form pill click)
 *     TOGGLE_CHAT        {}                   flip sidebarTool null ↔ "chat"
 *     TOGGLE_SIDEBAR_TOOL { tool }            generic sidebar-tool toggle
 *     TOGGLE_MARKED      {}                   flip markedOpen
 *     SET_FORM_PAGE      { page: 1..4 }       update form page
 *
 * The 3-pane workspace (form + 2 docs) was retired; the doc-list is
 * a one-click swap and two simultaneously-visible docs proved rare in
 * practice. Removing 3-pane lets the cache fields (hiddenDocCache /
 * markedCache / paneRecency / tick) all go away.
 */

(function (global) {
    "use strict";

    function initialState() {
        return {
            docSlots: [],
            sidebarTool: null,
            chatOpen: false,
            markedOpen: false,
            formState: { currentPage: 1 },
        };
    }

    /* OPEN_DOC — clicking a doc pill in the doc-list. Sets docSlots
     * to [docId], replacing whatever was there. Single-slot semantics
     * apply across every layout (h2, h2-chat, doc-only-marked). */
    function openDoc(state, docId) {
        if (!docId) return state;
        if (state.docSlots[0] === docId) return state;
        return Object.assign({}, state, {
            docSlots: [docId],
        });
    }

    /* CLOSE_DOC — X on the doc pane banner. Clears docSlots. The
     * docId arg is accepted for symmetry with the legacy contract
     * but no longer used (single-slot model). */
    function closeDoc(state, docId) {
        if (!docId) return state;
        if (state.docSlots.length === 0) return state;
        return Object.assign({}, state, {
            docSlots: [],
        });
    }

    /* SHOW_FORM — clicking the bolded form pill in the doc-list.
     * Functionally equivalent to CLOSE_DOC but doesn't require a
     * docId. Used by the form pill's handler in marked-mode where
     * the form is "cached" behind a doc. */
    function showForm(state) {
        if (state.docSlots.length === 0) return state;
        return Object.assign({}, state, {
            docSlots: [],
        });
    }

    /* setSidebarTool: single source of truth for the right column.
     * With 3-pane retired, opening / closing chat doesn't shed or
     * restore docs anymore — chat is fully orthogonal to docSlots. */
    function setSidebarTool(state, nextTool) {
        var prevTool = state.sidebarTool;
        if (prevTool === nextTool) return state;
        return Object.assign({}, state, {
            sidebarTool: nextTool,
            chatOpen: nextTool !== null,
        });
    }

    function toggleChat(state) {
        var next = state.sidebarTool === "chat" ? null : "chat";
        return setSidebarTool(state, next);
    }

    function toggleSidebarTool(state, tool) {
        if (!tool) return state;
        var next = state.sidebarTool === tool ? null : tool;
        return setSidebarTool(state, next);
    }

    /* TOGGLE_MARKED — flip the marked panel. No snapshots, no auto-
     * clear of docSlots. Whatever doc (or form) is visible at toggle
     * time stays visible across the transition. */
    function toggleMarked(state) {
        return Object.assign({}, state, {
            markedOpen: !state.markedOpen,
        });
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
            case "OPEN_DOC":
                return openDoc(state, action.docId);
            case "CLOSE_DOC":
                return closeDoc(state, action.docId);
            case "SHOW_FORM":
                return showForm(state);
            case "TOGGLE_CHAT":
                return toggleChat(state);
            case "TOGGLE_SIDEBAR_TOOL":
                return toggleSidebarTool(state, action.tool);
            case "TOGGLE_MARKED":
                return toggleMarked(state);
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
