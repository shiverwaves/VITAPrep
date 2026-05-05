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
            /* Marked panel state. While open, the workspace is a
             * single-slot top+bottom split: marked panel top 1/3,
             * one of (form OR a single doc) in the bottom 2/3.
             * Selecting any doc from the doc-list replaces the
             * visible thing; the X on a doc returns to the form.
             *
             * markedCache snapshots the docs visible at the moment
             * Marked opened (pre-marked docSlots). It's read-only
             * during marked mode and applied on close to rebuild
             * the prior layout. The doc visible at close gets
             * appended to the cache if the cache has room, so a
             * doc the player surfaced during marked mode promotes
             * into a pane on exit. */
            markedOpen: false,
            markedCache: [],
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
            /* Marked mode is single-slot regardless of chat. Clicking
             * a doc pill replaces whatever's in the slot (form or
             * a different doc); the previously-visible thing returns
             * via X on the doc pane or the form pill (SHOW_FORM). */
            if (state.docSlots[0] === docId) return state;
            return Object.assign({}, state, {
                panes: 1,
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
            if (state.markedOpen) {
                /* Marked mode is already single-slot (panes:1). Chat
                 * just slides into the right column — no shed needed. */
            } else if (state.panes === 3) {
                openUpdate.panes = 2;
                openUpdate.docSlots = state.docSlots.slice(0, 1);
                openUpdate.hiddenDocCache = state.docSlots[1];
            }
            return Object.assign({}, state, openUpdate);
        }

        /* Closing (prev non-null → next null). */
        var closeUpdate = { sidebarTool: null, chatOpen: false };
        if (!state.markedOpen && state.hiddenDocCache !== null) {
            closeUpdate.panes = 3;
            closeUpdate.docSlots = state.docSlots.concat([state.hiddenDocCache]);
            closeUpdate.hiddenDocCache = null;
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

    /* TOGGLE_MARKED — opens/closes the Marked panel.
     *
     * Marked mode is always single-slot: top 1/3 marked + bottom 2/3
     * containing either the form (form-only-marked) or one doc
     * (doc-only-marked). Chat is independent — when open, it takes
     * the right column without affecting the marked-mode template.
     *
     * On open: snapshot pre-marked docSlots into markedCache, then
     * clear docSlots so the form is the default visible thing.
     * Player can swap to any doc via the doc-list; X (or clicking
     * the form pill) returns to form.
     *
     * On close: rebuild docSlots from markedCache plus the doc the
     * player was viewing at close (if any).
     *   - chat closed: docSlots = cache (cap 2). If cache has room
     *     (<2) and a non-cache visible doc is set, append it.
     *   - chat open: cap is 1. If a doc is currently visible, it
     *     wins (the player explicitly surfaced it); else cache[0].
     */
    function toggleMarked(state) {
        if (state.markedOpen) {
            var cache = (state.markedCache || []).filter(function (id) {
                return id !== null && id !== undefined;
            });
            var visible = state.docSlots && state.docSlots[0]
                ? state.docSlots[0] : null;
            var newSlots;
            if (state.chatOpen) {
                /* Chat-open caps panes at 2 (form + 1 doc). Visible
                 * doc takes priority since the player explicitly
                 * surfaced it during marked mode. */
                newSlots = visible ? [visible] : (cache.length > 0 ? [cache[0]] : []);
            } else {
                /* Chat-closed: cache restores in full; visible doc
                 * appends only if cache has room and isn't already
                 * holding it. */
                newSlots = cache.slice(0, 2);
                if (visible && newSlots.length < 2 && newSlots.indexOf(visible) === -1) {
                    newSlots.push(visible);
                }
            }
            return Object.assign({}, state, {
                markedOpen: false,
                markedCache: [],
                panes: 1 + newSlots.length,
                docSlots: newSlots,
            });
        }
        /* Opening — snapshot current docs, default to form visible. */
        var preDocs = (state.docSlots || []).filter(function (id) {
            return id !== null && id !== undefined;
        });
        return Object.assign({}, state, {
            markedOpen: true,
            markedCache: preDocs,
            panes: 1,
            docSlots: [],
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

    /* SHOW_FORM — restore form visibility in marked mode. The marked-
     * mode bottom slot holds either form or one doc; SHOW_FORM
     * clears docSlots so the form takes the slot. No-op outside
     * marked mode (form is always visible there). */
    function showForm(state) {
        if (!state.markedOpen) return state;
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
