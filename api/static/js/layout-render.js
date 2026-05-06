/* Layout system renderer for the encounter workspace.
 *
 * Single render entry point: applyState(state) mutates the DOM to
 * reflect the current state object produced by api/static/js/layout-
 * reducer.js. Everything else dispatches actions through dispatch().
 *
 * DOM contract — IDs, classes, and data-attributes this file expects:
 *
 *   #workspace           data-layout="form-only|h2|form-only-chat|h2-chat|
 *                                     form-only-marked|doc-only-marked"
 *   #form-pane           always present (hidden by CSS in doc-only-marked)
 *   #doc-list            workspace-level pill strip (renderer-populated)
 *   #doc-pane-0          single doc pane, hidden when no doc visible
 *     .doc-pane__banner  navy title + close X (renderer-populated)
 *     .doc-pane__frame   <iframe>
 *   #chat-pane           hidden when chat is closed
 *   #marked-pane         hidden when marked is closed
 *
 *   <body data-sidebar="chat|closed">  <body data-marked="open|closed">
 *
 * Event delegation listens at the document root for any element with
 * data-layout-action="toggle-chat|toggle-marked|open-doc|close-doc|show-form".
 * Pills in the doc-list carry data-doc-id; the doc-pane close X carries
 * data-doc-id.
 *
 * Window-globals consumed:
 *   window.LayoutReducer        from layout-reducer.js
 *   window.SCENARIO_ID          string (set in encounter.html)
 *   window.SCENARIO_DOCS        {doc_id: url}
 *   window.SCENARIO_DOC_LABELS  {doc_id: label}
 *
 * Persistence: every state change writes JSON to
 * sessionStorage["vitaprep:layout:" + scenarioId]. On DOMContentLoaded
 * the renderer hydrates from that key if present, else uses
 * LayoutReducer.initialState() (which produces form-only and matches
 * the server-rendered default — so the no-JS first paint is never
 * inconsistent with what the JS produces).
 */

(function (global) {
    "use strict";

    /* -------- Module state (initialized in init()) -------- */
    var workspace, formPane, docPane, chatPane;
    var chatToggleBtn;
    var docList;
    var scenarioId = "";
    var docUrls = {};
    var docLabels = {};
    var availableDocIds = [];
    var state = null;

    /* -------- Persistence -------- */
    function storageKey() {
        return "vitaprep:layout:" + scenarioId;
    }

    function persistState(s) {
        try {
            sessionStorage.setItem(storageKey(), JSON.stringify(s));
        } catch (e) {
            /* sessionStorage may be disabled / quota-exceeded; ignore. */
        }
    }

    function loadPersistedState() {
        try {
            var raw = sessionStorage.getItem(storageKey());
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    /* Strip retired persisted-state fields (panes, hiddenDocCache,
     * markedCache, paneRecency, tick, markedOpen) and validate
     * docSlots ids against the current scenario. */
    function sanitizePersistedState(persisted) {
        if (!persisted) return persisted;
        if (Array.isArray(persisted.docSlots)) {
            persisted.docSlots = persisted.docSlots.filter(function (id) {
                return id && docUrls[id];
            });
            if (persisted.docSlots.length > 1) {
                persisted.docSlots = persisted.docSlots.slice(0, 1);
            }
        } else {
            persisted.docSlots = [];
        }
        if (typeof persisted.sidebarTool === "undefined") {
            persisted.sidebarTool = persisted.chatOpen ? "chat" : null;
        }
        persisted.chatOpen = persisted.sidebarTool !== null;
        if (!persisted.formState) {
            persisted.formState = { currentPage: 1 };
        }
        /* Drop retired fields. */
        delete persisted.panes;
        delete persisted.hiddenDocCache;
        delete persisted.markedCache;
        delete persisted.preMarkedSnapshot;
        delete persisted.paneRecency;
        delete persisted.tick;
        delete persisted.markedOpen;
        return persisted;
    }

    /* -------- Action dispatch -------- */
    function dispatch(action) {
        if (!global.LayoutReducer) return;
        var next = global.LayoutReducer.reduce(state, action);
        if (next === state) return;  /* no-op, skip render */
        state = next;
        applyState();
        persistState(state);
    }

    /* -------- Render -------- */
    function computeLayoutName(s) {
        var hasDoc = s.docSlots.length > 0;
        if (s.chatOpen) {
            return hasDoc ? "h2-chat" : "form-only-chat";
        }
        return hasDoc ? "h2" : "form-only";
    }

    function applyState() {
        if (!workspace) return;
        workspace.setAttribute("data-layout", computeLayoutName(state));
        var sidebarValue = state.sidebarTool || "closed";
        document.body.setAttribute("data-sidebar", sidebarValue);
        updateDocPane(state.docSlots[0] || null);
        renderDocList();
        updateSidebarToggleButtons();
        /* Notify listeners (flags-render) so external surfaces like
         * the titlebar Marked pill can refresh their pressed state
         * when chat opens/closes through any path. */
        try {
            document.dispatchEvent(new CustomEvent("vitaprep:layout-applied"));
        } catch (_) { /* IE11 / very old browsers; fall through. */ }
    }

    /* Render the doc-list pill strip. The form pill is pinned at
     * position 0 (bolded, distinct styling). Each doc pill is in
     * one of three states:
     *   - in-pane: doc is currently in the slot (badge "[2]")
     *   - default: not visible
     * The form pill is "cached" iff markedOpen && a doc is visible
     * (form is hidden behind the doc). No other cache concept. */
    function renderDocList() {
        if (!docList) return;
        var slot0 = state.docSlots[0] || null;

        /* Form pill — bolded, position 0. Always shown as in-pane;
         * clicking dispatches SHOW_FORM which clears any visible doc
         * (returns the workspace to form-only). When the slot is
         * already empty (form-only / form-only-chat), clicking is
         * a no-op handled by the reducer. */
        var formPillClasses =
            "doc-list__item doc-list__item--form doc-list__item--in-pane";
        var parts = [
            '<button type="button" class="' + formPillClasses + '"' +
            ' data-layout-action="show-form">' +
            'Form 13614-C' +
            '</button>',
        ];

        for (var i = 0; i < availableDocIds.length; i++) {
            var docId = availableDocIds[i];
            var label = docLabels[docId] || docId;
            var modifier = "";
            var badge = "";
            if (docId === slot0) {
                modifier = " doc-list__item--in-pane";
                badge = '<span class="doc-list__badge">2</span>';
            }
            parts.push(
                '<button type="button" class="doc-list__item' + modifier +
                '" data-layout-action="open-doc"' +
                ' data-doc-id="' + escapeAttr(docId) + '">' +
                escapeHtml(label) + badge +
                '</button>'
            );
        }
        docList.innerHTML = parts.join("");
    }

    function updateDocPane(docId) {
        if (!docPane) return;
        if (!docId) {
            docPane.hidden = true;
            return;
        }
        docPane.hidden = false;
        renderDocBanner(docPane, docId);
        var iframe = docPane.querySelector(".doc-pane__frame");
        if (iframe) {
            var newSrc = docUrls[docId] || "";
            /* Only re-set src when it actually changed; otherwise the
             * iframe reloads on every state transition. */
            if (iframe.getAttribute("src") !== newSrc) {
                iframe.setAttribute("src", newSrc);
            }
        }
    }

    /* Write the active doc's title + close X into the pane's navy
     * banner. The banner has no other actions in single-slot model. */
    function renderDocBanner(pane, docId) {
        var banner = pane.querySelector(".doc-pane__banner");
        if (!banner) return;
        var label = docLabels[docId] || docId;
        banner.innerHTML =
            '<span class="doc-pane__banner-title">' +
            escapeHtml(label) +
            '</span>' +
            '<button type="button"' +
            ' class="doc-pane__banner-btn doc-pane__banner-btn--close"' +
            ' data-layout-action="close-doc"' +
            ' data-doc-id="' + escapeAttr(docId) + '"' +
            ' aria-label="Close ' + escapeAttr(label) + '">' +
            '<svg viewBox="0 0 18 18" fill="none"' +
            ' stroke="currentColor" stroke-width="1.5"' +
            ' stroke-linecap="round">' +
            '<line x1="4" y1="4" x2="14" y2="14"/>' +
            '<line x1="14" y1="4" x2="4" y2="14"/>' +
            '</svg></button>';
    }

    /* Sync aria-pressed on the chat toggle. The marked pill is
     * managed by flags-render.js since marked is a flag-system UI. */
    function updateSidebarToggleButtons() {
        if (chatToggleBtn) {
            chatToggleBtn.setAttribute(
                "aria-pressed", state.sidebarTool === "chat" ? "true" : "false"
            );
        }
    }

    /* -------- Event delegation -------- */
    function handleClick(e) {
        var target = e.target;
        while (target && target.nodeType === 1) {
            var action = target.getAttribute("data-layout-action");
            if (action) {
                e.preventDefault();
                handleAction(action, target);
                return;
            }
            target = target.parentNode;
        }
    }

    function handleAction(action, element) {
        if (action === "toggle-chat") {
            dispatch({ type: "TOGGLE_CHAT" });
        } else if (action === "show-form") {
            /* Form pill click — clears docSlots so the form takes
             * the workspace alone. No-op when no doc is visible. */
            dispatch({ type: "SHOW_FORM" });
        } else if (action === "open-doc") {
            var openDocId = element.getAttribute("data-doc-id");
            if (!openDocId) return;
            dispatch({ type: "OPEN_DOC", docId: openDocId });
        } else if (action === "close-doc") {
            var closeDocId = element.getAttribute("data-doc-id");
            if (!closeDocId) return;
            dispatch({ type: "CLOSE_DOC", docId: closeDocId });
        }
    }

    /* -------- Helpers -------- */
    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {
                "&": "&amp;", "<": "&lt;", ">": "&gt;",
                '"': "&quot;", "'": "&#39;",
            }[c];
        });
    }

    function escapeAttr(s) {
        return escapeHtml(s);
    }

    /* -------- Init -------- */
    function init() {
        workspace = document.getElementById("workspace");
        if (!workspace) return;  /* not on an encounter page */

        formPane = document.getElementById("form-pane");
        docPane = document.getElementById("doc-pane-0");
        chatPane = document.getElementById("chat-pane");
        chatToggleBtn = document.getElementById("chat-toggle-btn");
        docList = document.getElementById("doc-list");

        scenarioId = global.SCENARIO_ID || "";
        docUrls = global.SCENARIO_DOCS || {};
        docLabels = global.SCENARIO_DOC_LABELS || {};
        availableDocIds = Object.keys(docUrls);

        var persisted = sanitizePersistedState(loadPersistedState());
        if (persisted) {
            state = persisted;
        } else {
            state = global.LayoutReducer.initialState();
        }

        document.addEventListener("click", handleClick);
        applyState();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    /* Expose for testing / debugging only — not part of the API. */
    global.LayoutRender = {
        _dispatch: dispatch,
        _getState: function () { return state; },
        _applyState: applyState,
    };
}(typeof window !== "undefined" ? window : globalThis));
