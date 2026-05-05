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
 *       #doc-list                  sticky doc-list bar (renderer-populated)
 *     #doc-pane-0               doc-pane container, hidden when not in use
 *       .doc-pane__banner         navy title + action buttons (renderer-populated)
 *       .doc-pane__frame          <iframe>
 *     #doc-pane-1               doc-pane container, hidden when not in use
 *       .doc-pane__banner
 *       .doc-pane__frame
 *   #chat-pane                  hidden when chat is closed
 *
 *   <body data-chat="open|closed">
 *
 *   #chat-toggle-btn            aria-pressed="true|false"
 *
 * Event delegation listens at the document root for any element with
 * data-layout-action="toggle-chat|open-doc|close-doc|open-third-pane|select-doc".
 * Pills in the doc-list carry data-doc-id; doc-pane banner buttons
 * carry data-doc-id (close X) or no extra data (pane-2 toggle).
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
    var workspace, formPane, docPanes, chatPane, markedPane;
    var chatToggleBtn, markedPill;
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

    /* Drop persisted docSlots entries whose doc_ids no longer exist
     * in this scenario (e.g. the scenario was regenerated). Otherwise
     * we'd ask iframes to load 404 URLs. Also backfill paneRecency
     * and tick for sessions persisted before Phase 2 added them, and
     * migrate sidebarTool for sessions persisted before Phase D
     * added the sidebar-tool generalization. */
    function sanitizePersistedState(persisted) {
        if (!persisted) return persisted;
        if (persisted.docSlots) {
            var sanitized = persisted.docSlots.map(function (id) {
                return docUrls[id] ? id : null;
            });
            persisted.docSlots = sanitized;
        }
        if (persisted.hiddenDocCache && !docUrls[persisted.hiddenDocCache]) {
            persisted.hiddenDocCache = null;
        }
        if (!persisted.paneRecency) persisted.paneRecency = [0, 0];
        if (typeof persisted.tick !== "number") persisted.tick = 0;
        /* Phase D migration: pre-Phase-D state had only chatOpen:bool.
         * Derive sidebarTool from it. */
        if (typeof persisted.sidebarTool === "undefined") {
            persisted.sidebarTool = persisted.chatOpen ? "chat" : null;
        }
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
        /* Marked open → workspace switches to a top-1/3 marked +
         * bottom-2/3 form grid. Docs are auto-cached by the reducer
         * when Marked opens, so the layout never combines marked
         * with doc panes. Chat coexists at the .app-main level
         * (right column) and doesn't change the workspace template. */
        if (s.markedOpen) return "form-only-marked";
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
        var sidebarValue = state.sidebarTool || "closed";
        document.body.setAttribute("data-sidebar", sidebarValue);
        document.body.setAttribute(
            "data-marked", state.markedOpen ? "open" : "closed"
        );
        updateDocPane(0, state.docSlots[0] || null);
        updateDocPane(1, state.docSlots[1] || null);
        renderDocList();
        updateSidebarToggleButtons();
    }

    /* Render the sticky doc-list bar at the top of #form-pane.
     * One pill per generated doc, with three possible states:
     * - in-pane: doc is currently in slot 0 or slot 1. Pill gets
     *   the --in-pane modifier and a [2] / [3] numbered badge.
     * - cached: chatOpen and doc is in state.hiddenDocCache (shed
     *   from a 3-pane state on chat-open). Pill gets the --cached
     *   modifier and a dot badge — visually rhyming with the
     *   pane-2 banner indicator that uses the same accent dot.
     * - default: nothing visible in any pane.
     *
     * Pills carry data-layout-action="open-doc" so the central event
     * handler dispatches OPEN_DOC on click. The reducer decides
     * what happens — promote layout, replace pane, recency-target,
     * or cached↔visible swap. */
    function renderDocList() {
        if (!docList) return;
        if (availableDocIds.length === 0) {
            docList.innerHTML = "";
            return;
        }
        var slot0 = state.docSlots[0] || null;
        var slot1 = state.docSlots[1] || null;
        var cached = state.chatOpen ? (state.hiddenDocCache || null) : null;
        var parts = [];
        for (var i = 0; i < availableDocIds.length; i++) {
            var docId = availableDocIds[i];
            var label = docLabels[docId] || docId;
            var modifier = "";
            var badge = "";
            if (docId === slot0) {
                modifier = " doc-list__item--in-pane";
                badge = '<span class="doc-list__badge">2</span>';
            } else if (docId === slot1) {
                modifier = " doc-list__item--in-pane";
                badge = '<span class="doc-list__badge">3</span>';
            } else if (docId === cached) {
                modifier = " doc-list__item--cached";
                badge = '<span class="doc-list__badge doc-list__badge--cached"></span>';
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

    function updateDocPane(index, docId) {
        var pane = docPanes[index];
        if (!pane) return;
        if (!docId) {
            pane.hidden = true;
            return;
        }
        pane.hidden = false;
        renderDocBanner(pane, docId);
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

    /* Write the active doc's title + action buttons into the pane's
     * navy banner. Pane 2 (the first doc pane) carries the "open
     * pane 3" toggle when in 2-pane chat-closed mode; otherwise the
     * toggle is omitted. The close X is on the far right of every
     * doc pane's banner (Windows-style placement). */
    function renderDocBanner(pane, docId) {
        var banner = pane.querySelector(".doc-pane__banner");
        if (!banner) return;
        var paneIndex = parseInt(pane.getAttribute("data-pane-index"), 10);
        var label = docLabels[docId] || docId;
        var parts = [
            '<span class="doc-pane__banner-title">' +
            escapeHtml(label) +
            '</span>',
        ];

        /* Pane 2's "open pane 3" toggle: visible only when the
         * layout is exactly 2-pane and chat is closed. The reducer
         * guards against dispatch in other states; hiding here is
         * for visual consistency. */
        if (paneIndex === 0 && state.panes === 2 && !state.chatOpen) {
            parts.push(
                '<button type="button" class="doc-pane__banner-btn"' +
                ' data-layout-action="open-third-pane"' +
                ' aria-label="Open third pane">' +
                '<svg viewBox="0 0 18 18" fill="none"' +
                ' stroke="currentColor" stroke-width="1.5">' +
                '<rect x="2" y="2" width="14" height="6" rx="1.5"/>' +
                '<rect x="2" y="10" width="6" height="6" rx="1.5"/>' +
                '<rect x="10" y="10" width="6" height="6" rx="1.5"/>' +
                '</svg></button>'
            );
        } else if (paneIndex === 0 && state.panes === 2
                && state.chatOpen && state.hiddenDocCache) {
            /* Chat-open + 2-pane + a cached doc exists: render the
             * 3-pane icon as a non-interactive indicator (span, not
             * button) with a small filled dot overlaid. Signals
             * "there's a third pane in cache" purely visually; no
             * click action. The cached doc itself is reachable via
             * its pill in the global doc-list bar. */
            var cacheLabel = docLabels[state.hiddenDocCache] || state.hiddenDocCache;
            parts.push(
                '<span class="doc-pane__banner-indicator"' +
                ' title="' + escapeAttr("Cached: " + cacheLabel) + '">' +
                '<svg viewBox="0 0 18 18" fill="none"' +
                ' stroke="currentColor" stroke-width="1.5">' +
                '<rect x="2" y="2" width="14" height="6" rx="1.5"/>' +
                '<rect x="2" y="10" width="6" height="6" rx="1.5"/>' +
                '<rect x="10" y="10" width="6" height="6" rx="1.5"/>' +
                '</svg>' +
                '<span class="doc-pane__banner-indicator-dot"></span>' +
                '</span>'
            );
        }

        /* Close X — present on every doc pane. Carries data-doc-id
         * so the dispatcher knows which doc to close. */
        parts.push(
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
            '</svg></button>'
        );

        banner.innerHTML = parts.join("");
    }

    /* Sync aria-pressed on each sidebar-tool toggle to reflect which
     * tool is currently active. Two elements participate: the
     * chat-toggle button (icon, titlebar right) and the marked pill
     * (titlebar center, doubles as flag-panel toggle). Each reads
     * from state.sidebarTool so exactly one (or neither) shows
     * pressed. */
    function updateSidebarToggleButtons() {
        if (chatToggleBtn) {
            chatToggleBtn.setAttribute(
                "aria-pressed", state.sidebarTool === "chat" ? "true" : "false"
            );
        }
        if (markedPill) {
            /* Marked is its own axis (state.markedOpen), not a
             * sidebar tool — pill reflects the dedicated marked
             * panel state. */
            markedPill.setAttribute(
                "aria-pressed", state.markedOpen ? "true" : "false"
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
        } else if (action === "toggle-marked") {
            /* Marked panel toggle — fires from the titlebar Marked
             * pill. The reducer's TOGGLE_MARKED handler caches /
             * restores docs and updates state.markedOpen. */
            dispatch({ type: "TOGGLE_MARKED" });
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
        } else if (action === "open-doc") {
            /* Click on a pill in the global doc-list bar. Always
             * dispatches OPEN_DOC; the reducer's openDoc no-ops
             * when the clicked doc is already visible in some pane.
             * Closing a pane is intentionally a separate gesture
             * (click the close X on the pane's banner) — re-clicking
             * a visible doc's pill is a no-op, not a close. The
             * cached doc (chat-open mode) is NOT in docSlots, so
             * clicking it goes through OPEN_DOC and the reducer
             * maps that to a visible↔cached swap. */
            var openDocId = element.getAttribute("data-doc-id");
            if (!openDocId) return;
            dispatch({ type: "OPEN_DOC", docId: openDocId });
        } else if (action === "close-doc") {
            /* Click on a doc pane's banner X. The element carries the
             * doc id directly so we don't need to walk up to the pane. */
            var closeDocId = element.getAttribute("data-doc-id");
            if (!closeDocId) return;
            dispatch({ type: "CLOSE_DOC", docId: closeDocId });
        } else if (action === "open-third-pane") {
            /* Click on pane 2's "open pane 3" toggle. Reducer guards
             * against dispatch in chat-open / non-2-pane states. */
            dispatch({
                type: "OPEN_THIRD_PANE",
                availableDocs: availableDocIds,
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
        markedPane = document.getElementById("marked-pane");
        chatToggleBtn = document.getElementById("chat-toggle-btn");
        markedPill = document.getElementById("marked-pill");
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
