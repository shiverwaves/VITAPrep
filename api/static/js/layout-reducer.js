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
 *     CYCLE_PANES        { availableDocs: [doc_id, ...] }   (legacy)
 *     TOGGLE_CHAT        {}
 *     SELECT_DOC         { slotIndex, docId }
 *     OPEN_DOC           { docId }
 *     CLOSE_DOC          { docId }
 *     OPEN_THIRD_PANE    { availableDocs: [doc_id, ...] }
 *     SET_FORM_PAGE      { page: 1..4 }
 *
 * The previous global pane-cycle button (CYCLE_PANES) was retired:
 * pane *count* is now driven by doc clicks (OPEN_DOC promotes 1→2),
 * the per-pane close X (CLOSE_DOC reduces panes by one), and the
 * pane-2-local "add pane 3" toggle (OPEN_THIRD_PANE goes 2→3).
 * CYCLE_PANES is left in the reducer for back-compat — old persisted
 * state still loads cleanly — but no UI dispatches it today.
 *
 * OPEN_DOC is dispatched by clicking a pill in the global doc-list
 * bar. It promotes the layout (1 → 2 panes) when needed, assigns
 * the doc to the least-recently-touched pane in 3-pane mode, and
 * swaps the visible/cached docs when chat is open and the clicked
 * doc is the cached one.
 *
 * CLOSE_DOC closes the pane containing the given doc. If pane 2 is
 * closed from a 3-pane layout, pane 3's doc shifts to the pane 2
 * slot (panes are always a contiguous 1→2 or 1→2→3 stack). Closing
 * the only doc pane returns to form-only.
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
            /* sidebarTool drives which tool occupies the right column
             * ("chat" | null today). chatOpen is the derived "any
             * sidebar tool open" boolean used by the layout logic
             * (3-pane shed, layout-name computation). The two stay
             * in sync via setSidebarTool. */
            sidebarTool: null,
            chatOpen: false,
            hiddenDocCache: null,
            /* Marked-for-follow-up panel state. While open, the
             * workspace shows marked top + (form + optional 1 doc)
             * bottom; chat-open + marked-open caps the bottom at a
             * single slot (form by default, doc-swappable in Phase 2).
             *
             * preMarkedSnapshot captures the pre-marked workspace
             * (panes / docSlots / hiddenDocCache) so closing Marked
             * restores the player's prior layout exactly — any
             * mid-marked doc-browsing doesn't persist. */
            markedOpen: false,
            preMarkedSnapshot: null,
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
        if (state.markedOpen) return state;

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
     * - doc already visible in some pane → no-op. Re-clicking a
     *   visible doc's pill is intentionally inert; closing a pane
     *   requires clicking the X on the pane's banner.
     * - chat-open + cached doc click → swap visible ↔ cached.
     * - panes:1 (form-only) → promote to panes:2 with the new doc
     *   in slot 0. The chat-open form-only-chat variant promotes to
     *   h2-chat (panes:2 + chatOpen) the same way.
     * - panes:2 → replace docSlots[0]. Only one doc pane exists,
     *   so the "pane count owned by close X / pane-2 toggle" rule
     *   means we don't add a second pane — we replace.
     * - panes:3 → write to the slot whose paneRecency is smaller
     *   (the least-recently-touched pane). Tiebreaker: slot 0.
     */
    function openDoc(state, docId) {
        if (!docId) return state;
        if (state.markedOpen) {
            /* Marked-mode single-slot behavior. Two sub-cases:
             *   - chat closed: bottom 2/3 is form|doc split (h2-marked).
             *     Clicking a doc pill replaces the visible doc.
             *   - chat open: bottom 2/3 is a single slot (form OR doc).
             *     Clicking a doc pill puts that doc in the slot,
             *     caching the form. The reverse (clicking form pill
             *     to restore form) goes through SHOW_FORM. */
            if (state.docSlots[0] === docId) return state;
            if (state.chatOpen) {
                return Object.assign({}, state, {
                    docSlots: [docId],
                }, bumpRecency(state, 0));
            }
            return Object.assign({}, state, {
                panes: 2,
                docSlots: [docId],
            }, bumpRecency(state, 0));
        }
        if (isDocInSlots(docId, state.docSlots)) return state;

        /* Chat-open + cached-doc click → swap. The previously-cached
         * doc becomes visible in slot 0; the previously-visible doc
         * goes to the cache. Pane count and chat state unchanged. */
        if (state.chatOpen && state.hiddenDocCache === docId
                && state.panes === 2) {
            var displaced = state.docSlots[0];
            return Object.assign({}, state, {
                docSlots: [docId],
                hiddenDocCache: displaced,
            }, bumpRecency(state, 0));
        }

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

    /* CLOSE_DOC — closes the pane containing the given doc.
     *
     * - panes:2, doc in slot 0 → return to form-only (panes:1, no docs).
     * - panes:3, doc in slot 0 (pane 2) → shift slot 1 down to slot 0
     *   and drop to panes:2. Pane 3's doc is now visible in pane 2;
     *   its pill badge updates from [3] to [2] on next render.
     * - panes:3, doc in slot 1 (pane 3) → drop slot 1 and go to panes:2.
     * - chat-open + panes:2 + doc in slot 0 + a cached doc exists →
     *   pull the cached doc into slot 0 instead of dropping panes;
     *   the user keeps both shed-from-3-pane docs reachable, one at
     *   a time, until they explicitly close again with no cache.
     * - chat-open + panes:2 + doc in slot 0 + no cache → drop to
     *   form-only-chat (panes:1).
     * - doc not in any pane → no-op. */
    function closeDoc(state, docId) {
        if (!docId) return state;
        var slotIndex = -1;
        for (var i = 0; i < state.docSlots.length; i++) {
            if (state.docSlots[i] === docId) {
                slotIndex = i;
                break;
            }
        }
        if (slotIndex === -1) return state;

        /* Marked-mode close: drop to form-only (panes:1) regardless
         * of which slot. Single-slot semantics. Snapshot is
         * untouched. */
        if (state.markedOpen) {
            return Object.assign({}, state, {
                panes: 1,
                docSlots: [],
            });
        }

        /* Closing the only doc pane (slot 0). */
        if (state.panes === 2 && slotIndex === 0) {
            /* Chat-open with a cached doc → pull the cache into the
             * visible slot instead of dropping panes. The cached
             * lifecycle is bound to having shed from 3-pane on chat
             * open; the user gets to step through the cached doc
             * before form-only-chat. Bump recency since slot 0 just
             * received a new doc. */
            if (state.chatOpen && state.hiddenDocCache !== null) {
                return Object.assign({}, state, {
                    docSlots: [state.hiddenDocCache],
                    hiddenDocCache: null,
                }, bumpRecency(state, 0));
            }
            /* Drop to form-only. Reset paneRecency since neither slot
             * will hold a doc; clear cache (no place to restore it). */
            return Object.assign({}, state, {
                panes: 1,
                docSlots: [],
                paneRecency: [0, 0],
                tick: state.tick,
                hiddenDocCache: null,
            });
        }
        /* Closing pane 3 (slot 1) from 3-pane → 2-pane. Reset slot 1
         * recency since it's no longer in use. */
        if (state.panes === 3 && slotIndex === 1) {
            var newRecency = state.paneRecency.slice();
            newRecency[1] = 0;
            return Object.assign({}, state, {
                panes: 2,
                docSlots: state.docSlots.slice(0, 1),
                paneRecency: newRecency,
            });
        }
        /* Closing pane 2 (slot 0) from 3-pane: pane 3's doc shifts
         * down. The shifted doc keeps its recency (now at slot 0). */
        if (state.panes === 3 && slotIndex === 0) {
            var shiftedRecency = [state.paneRecency[1], 0];
            return Object.assign({}, state, {
                panes: 2,
                docSlots: [state.docSlots[1]],
                paneRecency: shiftedRecency,
            });
        }
        return state;
    }

    /* OPEN_THIRD_PANE — pane-2-local toggle that adds pane 3 with
     * a default doc. No-op when chat is open (3-pane is forbidden
     * with chat) or when not in 2-pane mode. The pane-2 toggle
     * button is only visible in 2-pane chat-closed; this guard is
     * a safety net. */
    function openThirdPane(state, availableDocs) {
        if (state.chatOpen) return state;
        if (state.markedOpen) return state;
        if (state.panes !== 2) return state;
        var nextDoc = pickNextDoc(availableDocs, state.docSlots);
        if (!nextDoc) return state;
        return Object.assign({}, state, {
            panes: 3,
            docSlots: state.docSlots.concat([nextDoc]),
        }, bumpRecency(state, 1));
    }

    /* setSidebarTool is the single source of truth for "what
     * occupies the right column." Three transitions matter:
     *   - null → tool: opening. If panes:3, shed the third doc to
     *     hiddenDocCache and drop to panes:2. chatOpen becomes true.
     *   - tool → null: closing. Restore hiddenDocCache to panes:3
     *     if one was cached. chatOpen becomes false.
     *   - toolA → toolB (switching): no layout change; just swap
     *     the tool. The right column was already shrunk; the new
     *     tool takes over the same real estate.
     *
     * chatOpen tracks "any tool open" so the rest of the layout
     * logic (cyclePanes guard, openThirdPane guard, OPEN_DOC's
     * cached-swap branch) doesn't need to know about specific
     * tools. */
    function setSidebarTool(state, nextTool) {
        var prevTool = state.sidebarTool;
        if (prevTool === nextTool) return state;

        /* Switching between two tools: just swap. Right column was
         * already in occupied state; layout doesn't change. */
        if (prevTool && nextTool) {
            return Object.assign({}, state, { sidebarTool: nextTool });
        }

        /* Opening (prev null → next non-null). */
        if (!prevTool && nextTool) {
            var openUpdate = { sidebarTool: nextTool, chatOpen: true };
            if (state.markedOpen && state.panes === 2) {
                /* Marked + 1 doc → dual mode. The doc stays visible;
                 * the bottom 2/3 just collapses from form|doc split
                 * to a single slot (the doc occupies it, form is
                 * cached). Dropping panes to 1 triggers the layout
                 * switch to doc-only-marked. */
                openUpdate.panes = 1;
            } else if (state.panes === 3) {
                openUpdate.panes = 2;
                openUpdate.docSlots = state.docSlots.slice(0, 1);
                openUpdate.hiddenDocCache = state.docSlots[1];
            }
            return Object.assign({}, state, openUpdate);
        }

        /* Closing (prev non-null → next null). */
        var closeUpdate = { sidebarTool: null, chatOpen: false };
        if (state.markedOpen && state.docSlots.length > 0) {
            /* Dual mode → marked-only with the doc visible. Promote
             * panes back to 2 so layout switches from doc-only-marked
             * to h2-marked (form|doc split below marked). */
            closeUpdate.panes = 2;
        } else if (state.hiddenDocCache !== null) {
            if (state.markedOpen) {
                /* Edge case: a doc was shed to hiddenDocCache earlier
                 * (chat opened from a panes:3 state pre-marked, etc.).
                 * Restore it into the single visible slot. */
                closeUpdate.panes = 2;
                closeUpdate.docSlots = [state.hiddenDocCache];
                closeUpdate.hiddenDocCache = null;
            } else {
                closeUpdate.panes = 3;
                closeUpdate.docSlots = state.docSlots.concat([state.hiddenDocCache]);
                closeUpdate.hiddenDocCache = null;
            }
        }
        return Object.assign({}, state, closeUpdate);
    }

    /* Legacy entry point used by the chat-toggle button. Toggles the
     * "chat" sidebar tool specifically — same semantics as before
     * the multi-tool generalization. */
    function toggleChat(state) {
        var next = state.sidebarTool === "chat" ? null : "chat";
        return setSidebarTool(state, next);
    }

    /* Generic toggle for any sidebar tool. Dispatched by the new
     * Flags toggle button (and any future sidebar-tool toggles).
     * If the requested tool is already active, closes the sidebar;
     * otherwise switches to (or opens) the requested tool. */
    function toggleSidebarTool(state, tool) {
        if (!tool) return state;
        var next = state.sidebarTool === tool ? null : tool;
        return setSidebarTool(state, next);
    }

    /* TOGGLE_MARKED — opens/closes the Marked panel. Marked occupies
     * the top 1/3 of the workspace; the bottom 2/3 holds the form
     * plus optionally one doc pane (when chat is closed). When
     * chat is open AND marked is open, the bottom 2/3 has only the
     * single main slot — phase 2 wires the form-vs-doc swap there.
     *
     * Layout while marked is open:
     *   - chat closed, no docs   → panes:1 (just form below marked)
     *   - chat closed, ≥1 doc    → panes:2 (form + 1 doc below marked;
     *                              other docs reachable via the doc-list
     *                              and recoverable from preMarkedSnapshot
     *                              on close)
     *   - chat open              → panes:1 (form below marked; chat in
     *                              the right column. Phase 2 adds the
     *                              form-vs-doc swap for this combo)
     */
    /* TOGGLE_MARKED — opens/closes the Marked panel.
     *
     * On open: snapshot the pre-marked workspace (panes / docSlots /
     * hiddenDocCache) into preMarkedSnapshot. The marked-mode layout
     * is then derived from the chat state and currently-visible docs:
     *   - chat closed, ≥1 doc visible → panes:2 with the first doc
     *     kept in the slot (layout A: marked top, form|doc split).
     *   - chat closed, no docs        → panes:1 (form below marked).
     *   - chat open                   → panes:1 (form-only-marked
     *     inside the chat-narrowed workspace; Phase 2 adds the
     *     form-vs-doc swap for this combo).
     *
     * On close: restore from preMarkedSnapshot exactly. Mid-marked
     * doc browsing is ephemeral — closing Marked reverts to the
     * player's pre-marked layout. */
    function toggleMarked(state) {
        if (state.markedOpen) {
            var snap = state.preMarkedSnapshot;
            if (!snap) {
                /* Defensive fallback — shouldn't happen, but if the
                 * snapshot is somehow missing just clear the flag. */
                return Object.assign({}, state, {
                    markedOpen: false,
                    preMarkedSnapshot: null,
                });
            }
            return Object.assign({}, state, {
                markedOpen: false,
                panes: snap.panes,
                docSlots: snap.docSlots.slice(),
                hiddenDocCache: snap.hiddenDocCache,
                preMarkedSnapshot: null,
            });
        }
        /* Opening — snapshot first, then compute initial marked-mode
         * layout based on chat + docs. */
        var snapshot = {
            panes: state.panes,
            docSlots: (state.docSlots || []).slice(),
            hiddenDocCache: state.hiddenDocCache,
        };
        var visible = (state.docSlots || []).filter(function (id) {
            return id !== null && id !== undefined;
        });
        if (state.chatOpen || visible.length === 0) {
            return Object.assign({}, state, {
                markedOpen: true,
                panes: 1,
                docSlots: [],
                preMarkedSnapshot: snapshot,
            });
        }
        return Object.assign({}, state, {
            markedOpen: true,
            panes: 2,
            docSlots: [visible[0]],
            preMarkedSnapshot: snapshot,
        });
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

    /* SHOW_FORM — restore form visibility in marked+chat dual mode.
     * In that mode the bottom 2/3 has a single slot (form OR doc);
     * SHOW_FORM clears docSlots so the form takes the slot. No-op
     * outside dual mode (form is always visible there). */
    function showForm(state) {
        if (!state.markedOpen || !state.chatOpen) return state;
        if (state.docSlots.length === 0) return state;
        return Object.assign({}, state, {
            docSlots: [],
        });
    }

    function reduce(state, action) {
        if (!action || typeof action.type !== "string") return state;
        switch (action.type) {
            case "CYCLE_PANES":
                return cyclePanes(state, action.availableDocs || []);
            case "TOGGLE_CHAT":
                return toggleChat(state);
            case "TOGGLE_SIDEBAR_TOOL":
                return toggleSidebarTool(state, action.tool);
            case "TOGGLE_MARKED":
                return toggleMarked(state);
            case "SHOW_FORM":
                return showForm(state);
            case "SELECT_DOC":
                return selectDoc(state, action.slotIndex, action.docId);
            case "OPEN_DOC":
                return openDoc(state, action.docId);
            case "CLOSE_DOC":
                return closeDoc(state, action.docId);
            case "OPEN_THIRD_PANE":
                return openThirdPane(state, action.availableDocs || []);
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
