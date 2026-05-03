/* Layout system renderer for the encounter workspace.
 *
 * Single render entry point: applyState(state) mutates the DOM to
 * reflect the current state object produced by api/static/js/layout-
 * reducer.js. Everything else dispatches actions through dispatch().
 *
 * DOM contract — IDs, classes, and data-attributes this file expects:
 *
 *   #workspace                  data-layout="form-only|h2|h3|form-only-chat|h2-chat"
 *     #form-pane                always present
 *     #doc-pane-0               doc-pane container, hidden when not in use
 *       .doc-pane__tabs           tab strip (rendered by JS)
 *       .doc-pane__frame          <iframe>
 *     #doc-pane-1               doc-pane container, hidden when not in use
 *       .doc-pane__tabs
 *       .doc-pane__frame
 *   #chat-pane                  hidden when chat is closed
 *
 *   <body data-chat="open|closed">
 *
 *   #pane-cycle-btn             data-next-panes="1|2|3", disabled when chat open
 *   #chat-toggle-btn            aria-pressed="true|false"
 *   #hidden-doc-badge           hidden unless state.hiddenDocCache is set
 *
 * Event delegation listens at the document root for any element with
 * data-layout-action="cycle-panes|toggle-chat|select-doc". Doc-tab
 * elements also carry data-doc-id and live inside an ancestor with
 * data-pane-index="0|1".
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
    var workspace, formPane, docPanes, chatPane;
    var paneCycleBtn, chatToggleBtn, hiddenDocBadge;
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

    /* Drop persisted docSlots entries whose doc_ids no longer exist
     * in this scenario (e.g. the scenario was regenerated). Otherwise
     * we'd ask iframes to load 404 URLs. */
    function sanitizePersistedState(persisted) {
        if (!persisted || !persisted.docSlots) return persisted;
        var sanitized = persisted.docSlots.map(function (id) {
            return docUrls[id] ? id : null;
        });
        if (persisted.hiddenDocCache && !docUrls[persisted.hiddenDocCache]) {
            persisted.hiddenDocCache = null;
        }
        persisted.docSlots = sanitized;
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
        if (s.chatOpen) {
            return s.panes === 1 ? "form-only-chat" : "h2-chat";
        }
        if (s.panes === 1) return "form-only";
        if (s.panes === 2) return "h2";
        if (s.panes === 3) return "h3";
        return "form-only";
    }

    function applyState() {
        if (!workspace) return;
        workspace.setAttribute("data-layout", computeLayoutName(state));
        document.body.setAttribute("data-chat", state.chatOpen ? "open" : "closed");
        updateDocPane(0, state.docSlots[0] || null);
        updateDocPane(1, state.docSlots[1] || null);
        updatePaneCycleButton();
        updateChatToggleButton();
    }

    function updateDocPane(index, docId) {
        var pane = docPanes[index];
        if (!pane) return;
        if (!docId) {
            pane.hidden = true;
            return;
        }
        pane.hidden = false;
        renderDocTabs(pane, docId);
        var iframe = pane.querySelector(".doc-pane__frame");
        if (iframe) {
            var newSrc = docUrls[docId] || "";
            /* Only re-set src when it actually changed; otherwise the
             * iframe reloads on every state transition. */
            if (iframe.getAttribute("src") !== newSrc) {
                iframe.setAttribute("src", newSrc);
            }
        }
    }

    function renderDocTabs(pane, activeDocId) {
        var tabs = pane.querySelector(".doc-pane__tabs");
        if (!tabs) return;
        var parts = [];
        for (var i = 0; i < availableDocIds.length; i++) {
            var docId = availableDocIds[i];
            var label = docLabels[docId] || docId;
            var isActive = docId === activeDocId;
            parts.push(
                '<button type="button" class="doc-pane__tab' +
                (isActive ? " doc-pane__tab--active" : "") +
                '" data-layout-action="select-doc" data-doc-id="' +
                escapeAttr(docId) + '">' +
                escapeHtml(label) +
                '</button>'
            );
        }
        tabs.innerHTML = parts.join("");
    }

    function updatePaneCycleButton() {
        if (!paneCycleBtn) return;
        paneCycleBtn.disabled = !!state.chatOpen;
        paneCycleBtn.setAttribute(
            "data-next-panes",
            String(computeNextPanes(state))
        );
    }

    /* Returns the panes count the next pane-cycle click will produce.
     * Used by the icon to show "next state, not current". */
    function computeNextPanes(s) {
        if (s.chatOpen) return s.panes;
        if (s.panes === 1) return 2;
        if (s.panes === 3) return 2;
        return s.direction === "expanding" ? 3 : 1;
    }

    function updateChatToggleButton() {
        if (chatToggleBtn) {
            chatToggleBtn.setAttribute(
                "aria-pressed", state.chatOpen ? "true" : "false"
            );
        }
        if (hiddenDocBadge) {
            hiddenDocBadge.hidden = state.hiddenDocCache === null
                || state.hiddenDocCache === undefined;
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
        if (action === "cycle-panes") {
            if (state.chatOpen) return;  /* button is disabled but be safe */
            dispatch({
                type: "CYCLE_PANES",
                availableDocs: availableDocIds,
            });
        } else if (action === "toggle-chat") {
            dispatch({ type: "TOGGLE_CHAT" });
        } else if (action === "select-doc") {
            var paneEl = closest(element, "[data-pane-index]");
            if (!paneEl) return;
            var slotIndex = parseInt(
                paneEl.getAttribute("data-pane-index"), 10
            );
            var docId = element.getAttribute("data-doc-id");
            if (isNaN(slotIndex) || !docId) return;
            dispatch({
                type: "SELECT_DOC",
                slotIndex: slotIndex,
                docId: docId,
            });
        }
    }

    /* -------- Helpers -------- */
    function closest(el, selector) {
        if (el.closest) return el.closest(selector);
        var node = el;
        while (node && node.nodeType === 1) {
            if (node.matches && node.matches(selector)) return node;
            node = node.parentNode;
        }
        return null;
    }

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
        docPanes = [
            document.getElementById("doc-pane-0"),
            document.getElementById("doc-pane-1"),
        ];
        chatPane = document.getElementById("chat-pane");
        paneCycleBtn = document.getElementById("pane-cycle-btn");
        chatToggleBtn = document.getElementById("chat-toggle-btn");
        hiddenDocBadge = document.getElementById("hidden-doc-badge");

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
