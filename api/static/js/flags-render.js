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
        renderMarkedPill();
    }

    /* -------- Marked panel content (chain-link redesign) -------- */
    /* Each row is a sentence chain: field + 3 pill dropdowns +
     * split-button (Confirm / Execute / Discard). State is
     * source-of-truth; clicking pills or buttons dispatches
     * SET_VERB / SET_TARGET / SET_CHANNEL / TOGGLE_CONFIRM /
     * EXECUTE_FLAG / UNFLAG_FIELD and the row re-renders. */

    var VERB_LABELS = {
        RequestInfo: "Request Information",
        RequestConfirmation: "Request Confirmation",
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

    function renderFlagsPanel() {
        var pane = document.getElementById("marked-pane");
        if (!pane) return;

        var flags = state.flags || {};
        var archive = state.archive || [];
        var activeIds = Object.keys(flags);

        if (activeIds.length === 0 && archive.length === 0) {
            pane.innerHTML =
                '<div class="flags-pane__empty">No flags yet.</div>';
            return;
        }

        /* Active rows newest-first by created_at; archive newest-
         * first by sent_at. Split into two sections separated by
         * a divider; archive is read-only history. */
        activeIds.sort(function (a, b) {
            return (flags[b].created_at || 0) - (flags[a].created_at || 0);
        });
        var sortedArchive = archive.slice().sort(function (a, b) {
            return (b.sent_at || 0) - (a.sent_at || 0);
        });

        var hasReady = activeIds.some(function (fid) {
            return flags[fid].status === "ready";
        });

        var html = '<div class="flags-pane__body">';
        activeIds.forEach(function (fid) {
            html += renderChainRow(flags[fid], false);
        });
        if (sortedArchive.length > 0) {
            html += '<div class="flags-pane__divider">Sent</div>';
            sortedArchive.forEach(function (entry, i) {
                /* Archive entries are unique by (field_id, sent_at);
                 * use index as the data-archive-index so the row's
                 * data-field-id can stay the bare field id. */
                html += renderChainRow(entry, true, i);
            });
        }
        html += '</div>';
        html += renderFooter(hasReady);
        pane.innerHTML = html;

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
        var complete = global.FlagsReducer.isChainComplete(flag);
        var isReady = !isSent && flag.status === "ready";

        var modifiers = " flags-pane__row--chain";
        if (isSent) modifiers += " flags-pane__row--sent";
        if (isReady) modifiers += " flags-pane__row--ready";

        var rowAttrs = ' data-field-id="' + escapeAttr(fieldId) + '"';
        if (isSent) {
            rowAttrs += ' data-archive-index="' + archiveIndex + '"';
        }

        var parts = [
            '<div class="flags-pane__row' + modifiers + '"' + rowAttrs + '>',
            '<div class="flags-pane__row-field">' + escapeHtml(fieldId) + '</div>',
            '<div class="flags-pane__chain">',
            renderPill(fieldId, "verb", flag.verb, VERB_LABELS, isSent),
            '<span class="flags-pane__chain-connector">from</span>',
            renderPill(fieldId, "target", flag.target, TARGET_LABELS, isSent),
            '<span class="flags-pane__chain-connector">via</span>',
            renderPill(fieldId, "channel", flag.channel, CHANNEL_LABELS, isSent),
            renderConfirm(fieldId, flag, complete, isSent),
            '</div>',
            '</div>',
        ];
        return parts.join("");
    }

    function renderPill(fieldId, pillKey, value, labelMap, isSent) {
        var label = value
            ? (labelMap[value] || value)
            : PILL_PLACEHOLDERS[pillKey];
        var classes = "flags-pane__pill";
        if (!value) classes += " flags-pane__pill--placeholder";
        if (isSent) classes += " flags-pane__pill--sent";
        var attrs = isSent
            ? ' disabled aria-disabled="true"'
            : ' data-flag-action="open-pill" data-pill="' + pillKey + '"';
        return (
            '<button type="button" class="' + classes + '"' + attrs + '>' +
            '<span class="flags-pane__pill-label">' + escapeHtml(label) + '</span>' +
            (isSent ? '' : '<span class="flags-pane__pill-chevron" aria-hidden="true">&#9662;</span>') +
            '</button>'
        );
    }

    function renderConfirm(fieldId, flag, complete, isSent) {
        if (isSent) {
            return (
                '<span class="flags-pane__sent-tag">Sent</span>'
            );
        }
        var disabled = !complete;
        var pressed = flag.status === "ready";
        var primaryClass = "flags-pane__confirm-primary";
        if (pressed) primaryClass += " flags-pane__confirm-primary--pressed";
        var primaryAttrs = disabled ? ' disabled aria-disabled="true"' : '';
        return (
            '<span class="flags-pane__confirm">' +
            '<button type="button" class="' + primaryClass + '"' +
            ' data-flag-action="toggle-confirm"' +
            ' aria-pressed="' + (pressed ? "true" : "false") + '"' +
            primaryAttrs + '>' +
            (pressed ? "Confirmed" : "Confirm") +
            '</button>' +
            '<button type="button" class="flags-pane__confirm-menu"' +
            ' data-flag-action="open-confirm-menu"' +
            ' aria-label="More actions">' +
            '<span aria-hidden="true">&#9662;</span>' +
            '</button>' +
            '</span>'
        );
    }

    function renderFooter(hasReady) {
        var disabled = !hasReady;
        var attrs = disabled ? ' disabled aria-disabled="true"' : '';
        return (
            '<div class="flags-pane__footer">' +
            '<button type="button" class="flags-pane__btn flags-pane__btn--primary"' +
            ' data-flag-action="send-all"' + attrs + '>' +
            'Send all' +
            '</button>' +
            '</div>'
        );
    }

    /* Pill dropdown popover. Created on demand inside the marked
     * pane; positioned right under the clicked pill via getBoundingClientRect. */
    function showDropdown(fieldId, pillKey) {
        hideDropdown();

        var pane = document.getElementById("marked-pane");
        if (!pane) return;
        var pillBtn = pane.querySelector(
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

        var pane = document.getElementById("marked-pane");
        if (!pane) return;
        var trigger = pane.querySelector(
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
            ' data-flag-action="execute"' + executeAttrs + '>Execute</button>' +
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
        var pane = document.getElementById("marked-pane");
        if (pane) {
            var expanded = pane.querySelectorAll('[aria-expanded="true"]');
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

    /* Update the titlebar "Marked: N" pill — both the count and the
     * "has flags" state class. The pill is always present (greyed
     * when count is 0); the .titlebar__pill--has-flags class flips
     * it to the accent-illuminated state when count > 0.
     *
     * The pill itself carries data-layout-action="toggle-sidebar-tool"
     * so clicking it opens / closes the flag panel via the layout-
     * render dispatcher. aria-pressed is managed by layout-render
     * (mirrors state.sidebarTool === "flags"). */
    function renderMarkedPill() {
        var pill = document.getElementById("marked-pill");
        if (!pill) return;
        var count = Object.keys(state.flags || {}).length;
        var countSpan = document.getElementById("marked-pill-count");
        if (countSpan) countSpan.textContent = String(count);
        pill.classList.toggle("titlebar__pill--has-flags", count > 0);
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
            /* Click outside any flag-action element — close dropdown. */
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

            case "send-all":
                dispatch({ type: "SEND_ALL" });
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
         * AND closes any open dropdown when clicking outside. */
        document.addEventListener("click", handleDocumentClick);

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
