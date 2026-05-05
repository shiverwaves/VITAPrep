/* Flag state machine for the marked-for-follow-up mechanic.
 *
 * Pure function. No DOM, no globals (other than the namespace export
 * at the bottom), no side effects. Returns a new state object on every
 * transition; never mutates inputs.
 *
 * Wired up by api/static/js/flags-render.js, which dispatches actions
 * and persists state to sessionStorage.
 *
 * State shape:
 *
 *     {
 *         flags: { [field_id]: Flag },
 *         tick: number,                 // monotonic counter for created_at
 *     }
 *
 * Flag shape (chain-link redesign):
 *
 *     {
 *         field_id: string,
 *         verb: "RequestInfo" | "RequestConfirmation",
 *         target: "Vida" | "Client" | null,
 *         channel: "Email" | "Message" | null,
 *         status: "draft" | "ready" | "in_progress" | "sent",
 *         created_at: number,           // tick when first flagged
 *     }
 *
 * The chain is complete when verb + target + channel are all set.
 * Confirm (status:ready) is only allowed on a complete chain;
 * Execute likewise. Send all batch-fires every ready row.
 *
 * Action types:
 *
 *     FLAG_FIELD       { field_id, verb }
 *     UNFLAG_FIELD     { field_id }                 (Discard)
 *     SET_VERB         { field_id, verb }
 *     SET_TARGET       { field_id, target }         (target may be null)
 *     SET_CHANNEL      { field_id, channel }        (channel may be null)
 *     TOGGLE_CONFIRM   { field_id }                 (draft ↔ ready)
 *     EXECUTE_FLAG     { field_id }                 (→ sent)
 *     SEND_ALL         {}                           (all ready → sent)
 */

(function (global) {
    "use strict";

    /* Pill option lists. Each is the source of truth for what's a
     * legal value AND the display order in the dropdown. Adding a
     * new option is a one-line edit here. Labels live in OPTIONS
     * separately so the token (used in state) and the display
     * string can diverge. */
    var VERB_TOKENS = ["RequestInfo", "RequestConfirmation"];
    var TARGET_TOKENS = ["Vida", "Client"];
    var CHANNEL_TOKENS = ["Email", "Message"];

    var VALID_VERBS = {};
    VERB_TOKENS.forEach(function (t) { VALID_VERBS[t] = 1; });
    var VALID_TARGETS = {};
    TARGET_TOKENS.forEach(function (t) { VALID_TARGETS[t] = 1; });
    var VALID_CHANNELS = {};
    CHANNEL_TOKENS.forEach(function (t) { VALID_CHANNELS[t] = 1; });

    function initialState() {
        return {
            flags: {},
            tick: 0,
        };
    }

    function nextTick(state) {
        return (state.tick || 0) + 1;
    }

    function isChainComplete(flag) {
        return !!(flag && flag.verb && flag.target && flag.channel);
    }

    /* FLAG_FIELD — create (or re-flag) a flag with the given verb.
     * target/channel start null, status starts at draft. Re-flagging
     * preserves target/channel/status if they were already set. */
    function flagField(state, fieldId, verb) {
        if (!fieldId) return state;
        if (!VALID_VERBS[verb]) return state;

        var tick = nextTick(state);
        var existing = state.flags[fieldId];
        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = {
            field_id: fieldId,
            verb: verb,
            target: existing ? existing.target : null,
            channel: existing ? existing.channel : null,
            status: existing ? existing.status : "draft",
            created_at: existing ? existing.created_at : tick,
        };
        return { flags: newFlags, tick: tick };
    }

    function unflagField(state, fieldId) {
        if (!fieldId || !state.flags[fieldId]) return state;
        var newFlags = Object.assign({}, state.flags);
        delete newFlags[fieldId];
        return { flags: newFlags, tick: state.tick };
    }

    /* Setting any pill on a sent row is rejected — sent is immutable.
     * Setting a pill that changes the chain back to incomplete also
     * resets a "ready" row back to draft (the chain is no longer
     * confirmable, so it shouldn't be queued). */
    function setPill(state, fieldId, pillKey, value, validMap) {
        if (!fieldId || !state.flags[fieldId]) return state;
        if (value !== null && !validMap[value]) return state;

        var existing = state.flags[fieldId];
        if (existing.status === "sent" || existing.status === "in_progress") {
            return state;  /* immutable post-fire */
        }
        if (existing[pillKey] === value) return state;  /* no change */

        var update = {};
        update[pillKey] = value;
        var next = Object.assign({}, existing, update);
        /* If this change made the chain incomplete, demote ready→draft. */
        if (next.status === "ready" && !isChainComplete(next)) {
            next.status = "draft";
        }
        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = next;
        return { flags: newFlags, tick: state.tick };
    }

    /* TOGGLE_CONFIRM — flip draft ↔ ready. Only valid when the chain
     * is complete (Confirm is meaningless before that). No-op for
     * sent / in_progress rows. */
    function toggleConfirm(state, fieldId) {
        if (!fieldId || !state.flags[fieldId]) return state;
        var existing = state.flags[fieldId];
        if (existing.status === "draft" && isChainComplete(existing)) {
            var newFlags = Object.assign({}, state.flags);
            newFlags[fieldId] = Object.assign({}, existing, { status: "ready" });
            return { flags: newFlags, tick: state.tick };
        }
        if (existing.status === "ready") {
            var newFlags2 = Object.assign({}, state.flags);
            newFlags2[fieldId] = Object.assign({}, existing, { status: "draft" });
            return { flags: newFlags2, tick: state.tick };
        }
        return state;
    }

    /* EXECUTE_FLAG — fire a single row. Goes straight to "sent" for
     * Phase 1 (the in_progress flavor state lands later with its
     * animation). Only valid on a complete chain. */
    function executeFlag(state, fieldId) {
        if (!fieldId || !state.flags[fieldId]) return state;
        var existing = state.flags[fieldId];
        if (existing.status === "sent" || existing.status === "in_progress") {
            return state;
        }
        if (!isChainComplete(existing)) return state;
        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = Object.assign({}, existing, { status: "sent" });
        return { flags: newFlags, tick: state.tick };
    }

    /* SEND_ALL — every flag with status:ready transitions to sent. */
    function sendAll(state) {
        var changed = false;
        var newFlags = {};
        Object.keys(state.flags).forEach(function (fid) {
            var f = state.flags[fid];
            if (f.status === "ready") {
                newFlags[fid] = Object.assign({}, f, { status: "sent" });
                changed = true;
            } else {
                newFlags[fid] = f;
            }
        });
        if (!changed) return state;
        return { flags: newFlags, tick: state.tick };
    }

    function reduce(state, action) {
        if (!action || typeof action.type !== "string") return state;
        switch (action.type) {
            case "FLAG_FIELD":
                return flagField(state, action.field_id, action.verb);
            case "UNFLAG_FIELD":
                return unflagField(state, action.field_id);
            case "SET_VERB":
                return setPill(state, action.field_id, "verb", action.verb, VALID_VERBS);
            case "SET_TARGET":
                return setPill(state, action.field_id, "target", action.target, VALID_TARGETS);
            case "SET_CHANNEL":
                return setPill(state, action.field_id, "channel", action.channel, VALID_CHANNELS);
            case "TOGGLE_CONFIRM":
                return toggleConfirm(state, action.field_id);
            case "EXECUTE_FLAG":
                return executeFlag(state, action.field_id);
            case "SEND_ALL":
                return sendAll(state);
            default:
                return state;
        }
    }

    global.FlagsReducer = {
        initialState: initialState,
        reduce: reduce,
        VERB_TOKENS: VERB_TOKENS,
        TARGET_TOKENS: TARGET_TOKENS,
        CHANNEL_TOKENS: CHANNEL_TOKENS,
        isChainComplete: isChainComplete,
    };
}(typeof window !== "undefined" ? window : globalThis));
