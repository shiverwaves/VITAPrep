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
        var prev = state;
        var next = global.FlagsReducer.reduce(state, action);
        if (next === state) return;  /* no-op, skip render */
        state = next;
        persistState();
        applyState();
        /* Side effect: marking a NEW field opens the workpanel
         * to the Marked tab so the player can fill the chain
         * immediately. Re-flagging an existing field doesn't
         * trigger this — the row is already there. */
        if (action.type === "FLAG_FIELD"
                && action.field_id
                && !prev.flags[action.field_id]
                && next.flags[action.field_id]) {
            openMarkedTab();
        }
    }

    /* -------- Render -------- */
    /* applyState is the single DOM mutation entry point for the flag
     * system. Four responsibilities:
     *   - field-level visual indicators (.f13c-flagged + dot)
     *   - the titlebar Marked pill count + has-flags class
     *   - the workpanel's Marked tab body
     *   - the workpanel's Messages tab body (staged Message previews) */
    function applyState() {
        if (!state) return;
        renderFieldIndicators();
        renderMarkedPill();
        renderMarkedTabBody();
        renderMessagesTabBody();
    }

    /* -------- Marked panel content (chain-link redesign) -------- */
    /* Each row is a sentence chain: field + 3 pill dropdowns +
     * split-button (Confirm / Execute / Discard). State is
     * source-of-truth; clicking pills or buttons dispatches
     * SET_VERB / SET_TARGET / SET_CHANNEL / TOGGLE_CONFIRM /
     * EXECUTE_FLAG / UNFLAG_FIELD and the row re-renders. */

    var VERB_LABELS = {
        RequestInfo: "Request Information",
        ClarifyInfo: "Clarify Information",
    };
    var TARGET_LABELS = {
        Vida: "Vida",
        Client: "Client",
    };
    var CHANNEL_LABELS = {
        Email: "Email",
        Message: "Message",
    };
    /* Drawer-row data: each option has a title (the canonical
     * label), an optional subtitle (description that teaches the
     * schema), and for targets, an avatar string (initials). The
     * subtitle is what makes the drawer richer than a flat enum
     * picker. Adding a new option = one entry. */
    var VERB_OPTIONS = {
        RequestInfo: { title: "Request Information", subtitle: "Get a value you don't have yet" },
        ClarifyInfo: { title: "Clarify Information", subtitle: "Verify a value that seems off or unclear" },
    };
    var TARGET_OPTIONS = {
        Vida: { title: "Vida Reyes", subtitle: "Senior preparer", initials: "VR" },
        Client: { title: "Client", subtitle: "The taxpayer you're helping", initials: "CL" },
    };
    var CHANNEL_OPTIONS = {
        Email: { title: "Email", subtitle: "Sent as an email" },
        Message: { title: "Message", subtitle: "In-app chat message" },
    };
    var DRAWER_TITLES = {
        verb: "Verb",
        target: "Send to",
        channel: "Channel",
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
     * mounted server-side; this just toggles which one displays.
     * Default is "messages" — the Marked pill or marking a field
     * is the only way to land on the Marked tab automatically. */
    var activeWorkpanelTab = "messages";

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
             * a status tag. No chain pills, no action button. */
            return (
                '<div class="flags-pane__row flags-pane__row--sent"' +
                ' data-field-id="' + escapeAttr(fieldId) + '"' +
                ' data-archive-index="' + archiveIndex + '">' +
                '<div class="flags-pane__row-field">' +
                escapeHtml(fieldId) +
                '</div>' +
                renderSentTag(flag) +
                '</div>'
            );
        }

        var complete = global.FlagsReducer.isChainComplete(flag);
        var isStaged = flag.status === "staged";
        var pillsLocked = isStaged;
        var modifiers = " flags-pane__row--chain";
        if (isStaged) modifiers += " flags-pane__row--staged";

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
            renderRowAction(fieldId, flag, complete, isStaged) +
            '</div>'
        );
    }

    /* renderSentTag — small status chip on archived rows. Color
     * varies with the archive sub-status (sent / delivered / expired). */
    function renderSentTag(flag) {
        var sentStatus = flag.status || "sent";
        var labelMap = { sent: "Sent", delivered: "Delivered", expired: "Expired" };
        return (
            '<span class="flags-pane__sent-tag flags-pane__sent-tag--' + sentStatus + '">' +
            escapeHtml(labelMap[sentStatus] || "Sent") +
            '</span>'
        );
    }

    /* Per-row action button. Channel decides the verb:
     *   - Message → "Compose" (stages the row; tab jumps to Messages
     *     where the player previews and clicks Send).
     *   - Email   → "Add to draft" (queues the row in the Mail tab's
     *     email draft for that recipient; player sends from there).
     *   - Chain incomplete → disabled generic "Stage".
     * Staged rows show "Discard" + "Edit" affordances instead. */
    function renderRowAction(fieldId, flag, complete, isStaged) {
        if (isStaged) {
            var stagedLabel = flag.channel === "Email"
                ? "Queued in mail" : "Composed in messages";
            return (
                '<div class="flags-pane__row-actions flags-pane__row-actions--staged">' +
                '<span class="flags-pane__staged-tag">' +
                escapeHtml(stagedLabel) +
                '</span>' +
                '<button type="button" class="flags-pane__row-btn flags-pane__row-btn--ghost"' +
                ' data-flag-action="unstage">Edit</button>' +
                '<button type="button" class="flags-pane__row-btn flags-pane__row-btn--danger"' +
                ' data-flag-action="discard">Discard</button>' +
                '</div>'
            );
        }
        var label = "Stage";
        if (flag.channel === "Message") label = "Compose";
        else if (flag.channel === "Email") label = "Add to draft";
        var disabled = !complete;
        var attrs = disabled ? ' disabled aria-disabled="true"' : '';
        return (
            '<div class="flags-pane__row-actions">' +
            '<button type="button" class="flags-pane__row-btn flags-pane__row-btn--ghost"' +
            ' data-flag-action="discard">Discard</button>' +
            '<button type="button" class="flags-pane__row-btn flags-pane__row-btn--primary"' +
            ' data-flag-action="stage"' + attrs + '>' +
            escapeHtml(label) +
            '</button>' +
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

    /* renderConfirm + the Approve/Discard split-button menu were
     * retired alongside the Ready toggle. Each row now has a
     * direct channel-aware button — see renderRowAction. */

    /* Generate the message body text for a staged row. This is the
     * preview content the player sees in the Messages tab — auto-
     * composed from the chain (verb + target + field). Future
     * iterations may let the player edit this; for now it's
     * derived. */
    function composeMessageText(flag) {
        var verbText = (VERB_LABELS[flag.verb] || flag.verb || "").toLowerCase();
        var targetText = TARGET_LABELS[flag.target] || flag.target || "";
        var fieldText = flag.field_id || "the field";
        return "Hi " + targetText + ", I need to " + verbText +
            " for " + fieldText + ". Could you help me with this?";
    }

    /* Render the Messages tab body — shows each staged Message-
     * channel row as a composed preview with a Send button. Empty
     * state when no Message rows are staged. */
    function renderMessagesTabBody() {
        var body = document.getElementById("messages-tab-body");
        if (!body) return;

        var flags = state.flags || {};
        var stagedMessageIds = Object.keys(flags).filter(function (fid) {
            return flags[fid].status === "staged"
                && flags[fid].channel === "Message";
        });

        if (stagedMessageIds.length === 0) {
            body.innerHTML =
                '<div class="workpanel__empty">No messages staged. ' +
                'Compose a Marked row with channel "Message" to start one.</div>';
            return;
        }

        /* Newest first by created_at. */
        stagedMessageIds.sort(function (a, b) {
            return (flags[b].created_at || 0) - (flags[a].created_at || 0);
        });

        var html = "";
        stagedMessageIds.forEach(function (fid) {
            var flag = flags[fid];
            var target = TARGET_LABELS[flag.target] || flag.target || "";
            var initials = (TARGET_OPTIONS[flag.target] || {}).initials || "?";
            html +=
                '<div class="message-preview" data-field-id="' +
                escapeAttr(fid) + '">' +
                '<div class="message-preview__header">' +
                    '<span class="message-preview__avatar">' +
                    escapeHtml(initials) + '</span>' +
                    '<span class="message-preview__target">' +
                    escapeHtml(target) + '</span>' +
                    '<span class="message-preview__field">' +
                    escapeHtml(fid) + '</span>' +
                '</div>' +
                '<div class="message-preview__body">' +
                    escapeHtml(composeMessageText(flag)) +
                '</div>' +
                '<div class="message-preview__actions">' +
                    '<button type="button" class="flags-pane__row-btn flags-pane__row-btn--ghost"' +
                        ' data-flag-action="unstage">Edit</button>' +
                    '<button type="button" class="flags-pane__row-btn flags-pane__row-btn--primary"' +
                        ' data-flag-action="send">Send</button>' +
                '</div>' +
                '</div>';
        });
        body.innerHTML = html;
    }

    /* Pill option drawer. Slides up from the bottom of the workpanel
     * content area when a pill is tapped. Mobile-app action-sheet
     * pattern. The pill being edited gets an orange ring
     * (.flags-pane__pill--editing) so the connection between pill
     * and drawer is unambiguous. */
    function showDropdown(fieldId, pillKey) {
        hideDropdown();

        var content = document.querySelector(
            "#workpanel-tab-marked .workpanel__body"
        );
        if (!content) return;
        var pillBtn = content.querySelector(
            '.flags-pane__row[data-field-id="' + cssEscape(fieldId) + '"]' +
            ' .flags-pane__pill[data-pill="' + pillKey + '"]'
        );
        if (!pillBtn) return;

        var flag = (state.flags || {})[fieldId];
        if (!flag) return;

        var tokens, options, currentValue;
        if (pillKey === "verb") {
            tokens = global.FlagsReducer.VERB_TOKENS;
            options = VERB_OPTIONS;
            currentValue = flag.verb;
        } else if (pillKey === "target") {
            tokens = global.FlagsReducer.TARGET_TOKENS;
            options = TARGET_OPTIONS;
            currentValue = flag.target;
        } else if (pillKey === "channel") {
            tokens = global.FlagsReducer.CHANNEL_TOKENS;
            options = CHANNEL_OPTIONS;
            currentValue = flag.channel;
        } else {
            return;
        }

        var items = tokens.map(function (tok) {
            var opt = options[tok] || { title: tok };
            var isActive = tok === currentValue;
            var classes = "workpanel__drawer-item"
                + (isActive ? " workpanel__drawer-item--active" : "");
            var avatar = opt.initials
                ? '<span class="workpanel__drawer-item-avatar">' +
                    escapeHtml(opt.initials) + '</span>'
                : "";
            var subtitle = opt.subtitle
                ? '<span class="workpanel__drawer-item-subtitle">' +
                    escapeHtml(opt.subtitle) + '</span>'
                : "";
            return (
                '<button type="button" class="' + classes + '"' +
                ' data-flag-action="set-pill"' +
                ' data-pill="' + pillKey + '"' +
                ' data-value="' + escapeAttr(tok) + '">' +
                avatar +
                '<span class="workpanel__drawer-item-text">' +
                    '<span class="workpanel__drawer-item-title">' +
                    escapeHtml(opt.title || tok) + '</span>' +
                    subtitle +
                '</span>' +
                '<span class="workpanel__drawer-item-check" aria-hidden="true">' +
                    '&#10003;' +
                '</span>' +
                '</button>'
            );
        }).join("");

        /* Backdrop + drawer share a wrapper so they can be removed
         * together. The wrapper is positioned absolute inside the
         * .workpanel__body scroll container (sits above content,
         * below the bottom nav). */
        var wrapper = document.createElement("div");
        wrapper.className = "workpanel__drawer-host";
        wrapper.id = "workpanel-drawer-host";
        wrapper.innerHTML =
            '<div class="workpanel__drawer-backdrop"' +
                ' data-flag-action="dismiss-drawer"></div>' +
            '<div class="workpanel__drawer">' +
                '<div class="workpanel__drawer-handle" aria-hidden="true"></div>' +
                '<div class="workpanel__drawer-title">' +
                    escapeHtml(DRAWER_TITLES[pillKey] || "") +
                '</div>' +
                '<div class="workpanel__drawer-list">' + items + '</div>' +
            '</div>';
        content.appendChild(wrapper);

        /* Trigger the slide-in animation in the next frame. */
        requestAnimationFrame(function () {
            wrapper.classList.add("workpanel__drawer-host--open");
        });

        pillBtn.classList.add("flags-pane__pill--editing");
        pillBtn.setAttribute("aria-expanded", "true");
        openDropdown = { fieldId: fieldId, pillKey: pillKey };
    }

    function hideDropdown() {
        var drawerHost = document.getElementById("workpanel-drawer-host");
        if (drawerHost && drawerHost.parentNode) {
            drawerHost.parentNode.removeChild(drawerHost);
        }
        /* Also clean up the legacy popover wrapper if any persists
         * from an older render path. */
        var legacy = document.getElementById("flags-pane-dropdown");
        if (legacy && legacy.parentNode) legacy.parentNode.removeChild(legacy);

        var container = document.getElementById("marked-tab-body");
        if (container) {
            var expanded = container.querySelectorAll(
                '.flags-pane__pill[aria-expanded="true"]'
            );
            for (var i = 0; i < expanded.length; i++) {
                expanded[i].setAttribute("aria-expanded", "false");
                expanded[i].classList.remove("flags-pane__pill--editing");
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
            if (node.getAttribute && node.getAttribute("data-field-id")) {
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

            case "dismiss-drawer":
                /* Backdrop click — close the open pill drawer. */
                hideDropdown();
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

            case "stage":
                /* Compose / Add to draft button on a chain row.
                 * Stages the row; for Message channel, switches the
                 * tab to Messages so the player sees the composed
                 * preview. */
                if (!fieldId) return;
                var flag = (state.flags || {})[fieldId];
                dispatch({ type: "STAGE_FLAG", field_id: fieldId });
                if (flag && flag.channel === "Message") {
                    setActiveWorkpanelTab("messages");
                }
                return;

            case "unstage":
                /* Edit button on a staged row — back to draft so the
                 * player can re-edit the chain pills. */
                if (!fieldId) return;
                dispatch({ type: "UNSTAGE_FLAG", field_id: fieldId });
                return;

            case "send":
                /* Send button on a staged Message preview in the
                 * Messages tab. Fires the row to archive. */
                if (!fieldId) return;
                dispatch({ type: "SEND_FLAG", field_id: fieldId });
                return;

            case "discard":
                /* Discard button on a row (any state). Removes the
                 * flag entirely. */
                if (!fieldId) return;
                dispatch({ type: "UNFLAG_FIELD", field_id: fieldId });
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
