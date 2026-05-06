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
     * system. Three responsibilities:
     *   - field-level visual indicators (.f13c-flagged + dot)
     *   - the titlebar Marked pill count + has-flags class
     *   - the workpanel's Marked tab body */
    function applyState() {
        if (!state) return;
        renderFieldIndicators();
        renderMarkedPill();
        renderMarkedTabBody();
    }

    /* -------- Marked panel content (chain-link redesign) -------- */
    /* Each row is a sentence chain: field + 3 pill dropdowns +
     * split-button (Confirm / Execute / Discard). State is
     * source-of-truth; clicking pills or buttons dispatches
     * SET_VERB / SET_TARGET / SET_CHANNEL / TOGGLE_CONFIRM /
     * EXECUTE_FLAG / UNFLAG_FIELD and the row re-renders. */

    var VERB_LABELS = {
        RequestInfo: "Request Information",
    };
    var TARGET_LABELS = {
        Vida: "Vida",
        Client: "Client",
    };
    var CHANNEL_LABELS = {
        Email: "Email",
        Message: "Message",
    };
    var PILL_PLACEHOLDERS = {
        verb: "Choose verb",
        target: "Choose target",
        channel: "Choose channel",
    };

    /* Which pill (if any) currently has its dropdown popover open.
     * Format: { fieldId, pillKey } | null. Only ever one open at a
     * time — clicking a pill closes any other open dropdown. */
    var openDropdown = null;
    /* Which workpanel tab is active. The tab content panes are all
     * mounted server-side; this just toggles which one displays. */
    var activeWorkpanelTab = "marked";

    /* -------- Workpanel tabs -------- */
    function setActiveWorkpanelTab(tabName) {
        if (!tabName) return;
        activeWorkpanelTab = tabName;
        var tabs = document.querySelectorAll(".workpanel__tab");
        for (var i = 0; i < tabs.length; i++) {
            var match = tabs[i].id === ("workpanel-tab-" + tabName);
            tabs[i].classList.toggle("workpanel__tab--active", match);
        }
        var navBtns = document.querySelectorAll(".workpanel__nav-btn");
        for (var j = 0; j < navBtns.length; j++) {
            var btn = navBtns[j];
            var matchBtn = btn.getAttribute("data-workpanel-tab") === tabName;
            btn.classList.toggle("workpanel__nav-btn--active", matchBtn);
            btn.setAttribute("aria-pressed", matchBtn ? "true" : "false");
        }
    }

    /* Open the workpanel (chat sidebar) and switch to the Marked
     * tab. Three cases:
     *   - chat closed         → open chat + activate Marked tab
     *   - chat open, other tab → switch to Marked tab (don't close)
     *   - chat open, on Marked → close chat (toggle off)
     * Dispatched by the titlebar Marked pill. */
    function openMarkedTab() {
        if (!global.LayoutRender || !global.LayoutRender._dispatch) return;
        var layoutState = global.LayoutRender._getState();
        var chatOpen = layoutState && layoutState.chatOpen;

        if (chatOpen && activeWorkpanelTab === "marked") {
            /* Already on Marked → close the panel. */
            global.LayoutRender._dispatch({ type: "TOGGLE_CHAT" });
            return;
        }
        if (!chatOpen) {
            global.LayoutRender._dispatch({ type: "TOGGLE_CHAT" });
        }
        setActiveWorkpanelTab("marked");
    }

    function renderMarkedTabBody() {
        var body = document.getElementById("marked-tab-body");
        if (!body) return;
        /* Update the tab-title count regardless of the body's content. */
        var count = Object.keys(state.flags || {}).length;
        var countEl = document.getElementById("marked-tab-count");
        if (countEl) countEl.textContent = String(count);

        var flags = state.flags || {};
        var archive = state.archive || [];
        var activeIds = Object.keys(flags);

        if (activeIds.length === 0 && archive.length === 0) {
            body.innerHTML =
                '<div class="workpanel__empty">No flags yet. ' +
                'Right-click a form field to mark it for follow-up.</div>';
            return;
        }

        activeIds.sort(function (a, b) {
            return (flags[b].created_at || 0) - (flags[a].created_at || 0);
        });
        var sortedArchive = archive.slice().sort(function (a, b) {
            return (b.sent_at || 0) - (a.sent_at || 0);
        });

        var html = "";
        if (activeIds.length > 0) {
            html += '<div class="workpanel__section-title">Active</div>';
            activeIds.forEach(function (fid) {
                html += renderChainRow(flags[fid], false);
            });
        }
        if (sortedArchive.length > 0) {
            html += '<div class="workpanel__section-title workpanel__section-title--sent">Sent</div>';
            sortedArchive.forEach(function (entry, i) {
                html += renderChainRow(entry, true, i);
            });
        }
        body.innerHTML = html;

        if (openDropdown) {
            var stillExists = flags[openDropdown.fieldId];
            if (!stillExists) {
                openDropdown = null;
            } else {
                showDropdown(openDropdown.fieldId, openDropdown.pillKey);
            }
        }
    }

    function renderChainRow(flag, isSent, archiveIndex) {
        var fieldId = flag.field_id;

        if (isSent) {
            /* Sent rows are compact summaries — just the field id +
             * a status tag. No chain pills, no Ready button. */
            return (
                '<div class="flags-pane__row flags-pane__row--sent"' +
                ' data-field-id="' + escapeAttr(fieldId) + '"' +
                ' data-archive-index="' + archiveIndex + '">' +
                '<div class="flags-pane__row-field">' +
                escapeHtml(fieldId) +
                '</div>' +
                renderConfirm(fieldId, flag, false, true) +
                '</div>'
            );
        }

        var complete = global.FlagsReducer.isChainComplete(flag);
        var isReady = flag.status === "ready";
        var pillsLocked = isReady;
        var modifiers = " flags-pane__row--chain";
        if (isReady) modifiers += " flags-pane__row--ready";

        return (
            '<div class="flags-pane__row' + modifiers + '"' +
            ' data-field-id="' + escapeAttr(fieldId) + '">' +
            '<div class="flags-pane__row-field">' +
            escapeHtml(fieldId) +
            '</div>' +
            '<div class="flags-pane__chain">' +
            renderPill(fieldId, "verb", flag.verb, VERB_LABELS, pillsLocked) +
            '<span class="flags-pane__chain-connector">from</span>' +
            renderPill(fieldId, "target", flag.target, TARGET_LABELS, pillsLocked) +
            '<span class="flags-pane__chain-connector">via</span>' +
            renderPill(fieldId, "channel", flag.channel, CHANNEL_LABELS, pillsLocked) +
            '</div>' +
            '<div class="flags-pane__row-actions">' +
            renderConfirm(fieldId, flag, complete, false) +
            '</div>' +
            '</div>'
        );
    }

    function renderPill(fieldId, pillKey, value, labelMap, locked) {
        var label = value
            ? (labelMap[value] || value)
            : PILL_PLACEHOLDERS[pillKey];
        var classes = "flags-pane__pill";
        if (!value) classes += " flags-pane__pill--placeholder";
        if (locked) classes += " flags-pane__pill--locked";
        var attrs = locked
            ? ' disabled aria-disabled="true"'
            : ' data-flag-action="open-pill" data-pill="' + pillKey + '"';
        return (
            '<button type="button" class="' + classes + '"' + attrs + '>' +
            '<span class="flags-pane__pill-label">' + escapeHtml(label) + '</span>' +
            (locked ? '' : '<span class="flags-pane__pill-chevron" aria-hidden="true">&#9662;</span>') +
            '</button>'
        );
    }

    function renderConfirm(fieldId, flag, complete, isSent) {
        if (isSent) {
            var sentStatus = flag.status || "sent";
            var labelMap = { sent: "Sent", delivered: "Delivered", expired: "Expired" };
            return (
                '<span class="flags-pane__sent-tag flags-pane__sent-tag--' + sentStatus + '">' +
                escapeHtml(labelMap[sentStatus] || "Sent") +
                '</span>'
            );
        }
        var disabled = !complete;
        var pressed = flag.status === "ready";
        var primaryClass = "flags-pane__confirm-primary";
        if (pressed) primaryClass += " flags-pane__confirm-primary--pressed";
        var primaryAttrs = disabled ? ' disabled aria-disabled="true"' : '';
        /* Single label "Ready" for both states — pressed/unpressed is
         * conveyed by the navy fill + checkmark, not by changing the
         * word. Keeps the language separate from the "Approve" /
         * "Approve all" verbs that fire the row. */
        return (
            '<span class="flags-pane__confirm">' +
            '<button type="button" class="' + primaryClass + '"' +
            ' data-flag-action="toggle-confirm"' +
            ' aria-pressed="' + (pressed ? "true" : "false") + '"' +
            primaryAttrs + '>' +
            (pressed ? "Ready &#10003;" : "Ready") +
            '</button>' +
            '<button type="button" class="flags-pane__confirm-menu"' +
            ' data-flag-action="open-confirm-menu"' +
            ' aria-label="More actions">' +
            '<span aria-hidden="true">&#9662;</span>' +
            '</button>' +
            '</span>'
        );
    }

    /* Send-all was retired — players fire follow-ups row by row to
     * keep the chat log per-conversation. Email-channel batching is
     * a future affordance (compile multiple ready rows into one
     * email when the channel is Email). */

    /* Pill option dropdown popover. Created on demand inside the
     * Marked tab body; positioned right under the clicked pill via
     * getBoundingClientRect. */
    function showDropdown(fieldId, pillKey) {
        hideDropdown();

        var container = document.getElementById("marked-tab-body");
        if (!container) return;
        var pillBtn = container.querySelector(
            '.flags-pane__row[data-field-id="' + cssEscape(fieldId) + '"]' +
            ' .flags-pane__pill[data-pill="' + pillKey + '"]'
        );
        if (!pillBtn) return;

        var tokens, labels, currentValue;
        var flag = (state.flags || {})[fieldId];
        if (!flag) return;
        if (pillKey === "verb") {
            tokens = global.FlagsReducer.VERB_TOKENS;
            labels = VERB_LABELS;
            currentValue = flag.verb;
        } else if (pillKey === "target") {
            tokens = global.FlagsReducer.TARGET_TOKENS;
            labels = TARGET_LABELS;
            currentValue = flag.target;
        } else if (pillKey === "channel") {
            tokens = global.FlagsReducer.CHANNEL_TOKENS;
            labels = CHANNEL_LABELS;
            currentValue = flag.channel;
        } else {
            return;
        }

        var items = tokens.map(function (tok) {
            var active = tok === currentValue ? " flags-pane__dropdown-item--active" : "";
            return (
                '<button type="button" class="flags-pane__dropdown-item' + active + '"' +
                ' data-flag-action="set-pill"' +
                ' data-pill="' + pillKey + '"' +
                ' data-value="' + escapeAttr(tok) + '">' +
                escapeHtml(labels[tok] || tok) +
                '</button>'
            );
        }).join("");

        var dropdown = document.createElement("div");
        dropdown.className = "flags-pane__dropdown";
        dropdown.id = "flags-pane-dropdown";
        dropdown.innerHTML = items;
        document.body.appendChild(dropdown);

        var rect = pillBtn.getBoundingClientRect();
        dropdown.style.position = "fixed";
        dropdown.style.top = (rect.bottom + 4) + "px";
        dropdown.style.left = rect.left + "px";
        dropdown.style.minWidth = rect.width + "px";

        openDropdown = { fieldId: fieldId, pillKey: pillKey };
        pillBtn.setAttribute("aria-expanded", "true");
    }

    function showConfirmMenu(fieldId) {
        hideDropdown();

        var container = document.getElementById("marked-tab-body");
        if (!container) return;
        var trigger = container.querySelector(
            '.flags-pane__row[data-field-id="' + cssEscape(fieldId) + '"]' +
            ' .flags-pane__confirm-menu'
        );
        if (!trigger) return;

        var flag = (state.flags || {})[fieldId];
        if (!flag) return;
        var complete = global.FlagsReducer.isChainComplete(flag);
        var executeAttrs = complete ? "" : ' disabled aria-disabled="true"';

        var menu = document.createElement("div");
        menu.className = "flags-pane__dropdown";
        menu.id = "flags-pane-dropdown";
        menu.innerHTML =
            '<button type="button" class="flags-pane__dropdown-item"' +
            ' data-flag-action="execute"' + executeAttrs + '>Approve</button>' +
            '<button type="button" class="flags-pane__dropdown-item flags-pane__dropdown-item--danger"' +
            ' data-flag-action="discard">Discard</button>';
        document.body.appendChild(menu);

        var rect = trigger.getBoundingClientRect();
        menu.style.position = "fixed";
        menu.style.top = (rect.bottom + 4) + "px";
        menu.style.right = (window.innerWidth - rect.right) + "px";

        openDropdown = { fieldId: fieldId, pillKey: "_confirmMenu" };
    }

    function hideDropdown() {
        var existing = document.getElementById("flags-pane-dropdown");
        if (existing) existing.parentNode.removeChild(existing);
        var container = document.getElementById("marked-tab-body");
        if (container) {
            var expanded = container.querySelectorAll(
                '.flags-pane__pill[aria-expanded="true"]'
            );
            for (var i = 0; i < expanded.length; i++) {
                expanded[i].setAttribute("aria-expanded", "false");
            }
        }
        openDropdown = null;
    }

    /* Minimal CSS.escape polyfill — field ids contain dots that
     * break querySelector if not escaped. */
    function cssEscape(s) {
        if (window.CSS && window.CSS.escape) return window.CSS.escape(s);
        return String(s).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
    }

    /* Update the titlebar "Marked: N" pill — count + has-flags
     * state class. aria-pressed reflects whether the workpanel
     * is currently open AND showing the Marked tab. */
    function renderMarkedPill() {
        var pill = document.getElementById("marked-pill");
        if (!pill) return;
        var count = Object.keys(state.flags || {}).length;
        var countSpan = document.getElementById("marked-pill-count");
        if (countSpan) countSpan.textContent = String(count);
        pill.classList.toggle("titlebar__pill--has-flags", count > 0);
        var chatOpen = false;
        if (global.LayoutRender && global.LayoutRender._getState) {
            var ls = global.LayoutRender._getState();
            chatOpen = ls && ls.chatOpen;
        }
        var pressed = chatOpen && activeWorkpanelTab === "marked";
        pill.setAttribute("aria-pressed", pressed ? "true" : "false");
    }

    /* -------- Panel + dropdown event delegation -------- */
    /* One click handler at the document level catches:
     *   - clicks on pills / buttons (data-flag-action attributes)
     *   - clicks anywhere else (close any open dropdown)
     * The marked panel is not a self-contained capture target
     * because the dropdown is appended to <body> (so it can escape
     * the panel's overflow:auto clipping). One global handler
     * keeps the routing centralized. */
    function handleDocumentClick(e) {
        /* Workpanel nav buttons get routed first (they're outside
         * the data-flag-action namespace). */
        var navTarget = e.target;
        while (navTarget && navTarget.nodeType === 1) {
            var tabName = navTarget.getAttribute
                && navTarget.getAttribute("data-workpanel-tab");
            if (tabName) {
                e.preventDefault();
                setActiveWorkpanelTab(tabName);
                return;
            }
            navTarget = navTarget.parentNode;
        }

        var target = e.target;
        var actionEl = null;
        while (target && target.nodeType === 1) {
            if (target.getAttribute && target.getAttribute("data-flag-action")) {
                actionEl = target;
                break;
            }
            target = target.parentNode;
        }
        if (!actionEl) {
            /* Click outside any flag-action element — dismiss any
             * pill option dropdown if open. */
            if (openDropdown) hideDropdown();
            return;
        }
        if (actionEl.disabled) return;

        var rowEl = closestRow(actionEl);
        var fieldId = rowEl ? rowEl.getAttribute("data-field-id") : null;
        var action = actionEl.getAttribute("data-flag-action");

        e.preventDefault();
        e.stopPropagation();
        handlePanelAction(action, actionEl, fieldId);
    }

    function closestRow(el) {
        var node = el;
        while (node && node.nodeType === 1) {
            if (node.classList && node.classList.contains("flags-pane__row")) {
                return node;
            }
            node = node.parentNode;
        }
        return null;
    }

    function handlePanelAction(action, element, fieldId) {
        switch (action) {
            case "toggle-marked-dropdown":
                /* Marked pill click: open chat (if closed) and
                 * switch to the Marked tab. The legacy action name
                 * is kept so the pill markup didn't have to change
                 * in the same commit. */
                openMarkedTab();
                return;

            case "open-pill":
                if (!fieldId) return;
                var pillKey = element.getAttribute("data-pill");
                /* Toggle: clicking an already-open pill closes it. */
                if (openDropdown
                        && openDropdown.fieldId === fieldId
                        && openDropdown.pillKey === pillKey) {
                    hideDropdown();
                    return;
                }
                showDropdown(fieldId, pillKey);
                return;

            case "open-confirm-menu":
                if (!fieldId) return;
                if (openDropdown
                        && openDropdown.fieldId === fieldId
                        && openDropdown.pillKey === "_confirmMenu") {
                    hideDropdown();
                    return;
                }
                showConfirmMenu(fieldId);
                return;

            case "set-pill":
                /* Dropdown lives in <body>, so fieldId comes from
                 * openDropdown rather than DOM ancestor. */
                if (!openDropdown) return;
                var key = element.getAttribute("data-pill");
                var value = element.getAttribute("data-value");
                var actionType = key === "verb" ? "SET_VERB"
                    : key === "target" ? "SET_TARGET"
                    : key === "channel" ? "SET_CHANNEL"
                    : null;
                if (!actionType) return;
                var payload = { type: actionType, field_id: openDropdown.fieldId };
                payload[key] = value;
                hideDropdown();
                dispatch(payload);
                return;

            case "toggle-confirm":
                if (!fieldId) return;
                dispatch({ type: "TOGGLE_CONFIRM", field_id: fieldId });
                return;

            case "execute":
                if (!openDropdown) return;
                var execFid = openDropdown.fieldId;
                hideDropdown();
                dispatch({ type: "EXECUTE_FLAG", field_id: execFid });
                return;

            case "discard":
                if (!openDropdown) return;
                var discardFid = openDropdown.fieldId;
                hideDropdown();
                dispatch({ type: "UNFLAG_FIELD", field_id: discardFid });
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
        state = sanitizePersisted(persisted)
            || global.FlagsReducer.initialState();

        /* Document-level click handler routes flag-action attributes
         * AND workpanel-tab nav AND closes any open pill dropdown
         * on outside click. */
        document.addEventListener("click", handleDocumentClick);

        /* Escape dismisses the open pill option dropdown if any. */
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && openDropdown) {
                hideDropdown();
            }
        });

        /* Refresh the marked pill's pressed state when the layout
         * state machine fires (chat-toggle from any path, etc.). */
        document.addEventListener("vitaprep:layout-applied", function () {
            renderMarkedPill();
        });

        applyState();
    }

    /* Sanitize persisted state for shape compatibility. Drops legacy
     * flags (the pre-chain shape with `context` / `action`) and
     * splits any sent flags out into the archive (the active map
     * is now strictly draft + ready). */
    function sanitizePersisted(persisted) {
        if (!persisted || !persisted.flags) return persisted;
        var activeMap = {};
        var archive = (persisted.archive || []).slice();
        Object.keys(persisted.flags).forEach(function (fid) {
            var f = persisted.flags[fid];
            var validShape = f && typeof f.verb === "string"
                && (f.target === null || typeof f.target === "string")
                && (f.channel === null || typeof f.channel === "string");
            if (!validShape) return;  /* drop legacy entries */
            if (f.status === "sent") {
                archive.push(Object.assign({}, f, {
                    sent_at: f.sent_at || f.created_at || 0,
                }));
            } else {
                activeMap[fid] = f;
            }
        });
        return {
            flags: activeMap,
            archive: archive,
            tick: persisted.tick || 0,
        };
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
