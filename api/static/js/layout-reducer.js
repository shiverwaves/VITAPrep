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
 *         formState: { currentPage: 1..4 }
 *     }
 *
 * Layout (four combinations):
 *
 *     chat   docSlots  layout name        visual
 *     ----   --------  ----------------   ----------------------
 *      no    []        form-only          full-screen form
 *      no    [d]       h2                 form top, doc bottom
 *      yes   []        form-only-chat     form left + chat right
 *      yes   [d]       h2-chat            form/doc split + chat
 *
 * Marked (the flag review UI) is no longer part of the layout state
 * machine — it's a dropdown popover owned by flags-render.js,
 * anchored to the titlebar Marked pill. Opening / closing it doesn't
 * change the workspace.
 *
 * Action types:
 *
 *     OPEN_DOC           { docId }            set docSlots to [docId]
 *     CLOSE_DOC          { docId }            clear docSlots (X on doc pane)
 *     SHOW_FORM          {}                   clear docSlots (form pill click)
 *     TOGGLE_CHAT        {}                   flip sidebarTool null ↔ "chat"
 *     TOGGLE_SIDEBAR_TOOL { tool }            generic sidebar-tool toggle
 *     SET_FORM_PAGE      { page: 1..4 }       update form page
 */

(function (global) {
    "use strict";

    function initialState() {
        return {
            docSlots: [],
            sidebarTool: null,
            chatOpen: false,
            formState: { currentPage: 1 },
        };
    }

    /* OPEN_DOC — clicking a doc pill in the doc-list. Sets docSlots
     * to [docId], replacing whatever was there. */
    function openDoc(state, docId) {
        if (!docId) return state;
        if (state.docSlots[0] === docId) return state;
        return Object.assign({}, state, {
            docSlots: [docId],
        });
    }

    /* CLOSE_DOC — X on the doc pane banner. Clears docSlots. The
     * docId arg is accepted for symmetry but no longer used. */
    function closeDoc(state, docId) {
        if (!docId) return state;
        if (state.docSlots.length === 0) return state;
        return Object.assign({}, state, {
            docSlots: [],
        });
    }

    /* SHOW_FORM — clicking the bolded form pill in the doc-list.
     * Clears docSlots, switching the workspace from h2 (or h2-chat)
     * back to form-only (or form-only-chat). */
    function showForm(state) {
        if (state.docSlots.length === 0) return state;
        return Object.assign({}, state, {
            docSlots: [],
        });
    }

    /* setSidebarTool: single source of truth for the right column. */
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
