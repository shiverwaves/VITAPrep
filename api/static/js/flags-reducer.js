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
 *         flags: { [field_id]: ActiveFlag },   // draft + ready only
 *         archive: [SentFlag, ...],            // immutable log, append-only
 *         tick: number,                        // monotonic counter
 *     }
 *
 * Active flag shape (chain-link):
 *
 *     {
 *         field_id: string,
 *         verb: "RequestInfo" | "RequestConfirmation",
 *         target: "Vida" | "Client" | null,
 *         channel: "Email" | "Message" | null,
 *         status: "draft" | "ready",
 *         created_at: number,
 *     }
 *
 * Sent flag (in archive) shape — same as active plus `sent_at`,
 * with `status` ∈ { "sent" | "delivered" | "expired" }:
 *
 *   - sent       fired, no response yet (default on Execute / Send all)
 *   - delivered  client received & responded
 *   - expired    client never responded / message timed out
 *
 * The transition sent → delivered/expired is currently driven only
 * by the SET_ARCHIVE_STATUS action; future scenario events (or a
 * client-response simulation) will dispatch it automatically.
 *
 * Once a flag fires, it's removed from `flags` and pushed to
 * `archive`. The form-side dot + .f13c-flagged class clear
 * automatically because they read from `flags` only. The field
 * can then be re-flagged, producing a fresh active entry while
 * the archived entry remains in the panel as history.
 *
 * The chain is complete when verb + target + channel are all set.
 * Confirm (status:ready) is only allowed on a complete chain;
 * Execute likewise. Send all fires every active row in ready state.
 *
 * Action types:
 *
 *     FLAG_FIELD       { field_id, verb }
 *     UNFLAG_FIELD     { field_id }                 (Discard)
 *     SET_VERB         { field_id, verb }
 *     SET_TARGET       { field_id, target }         (target may be null)
 *     SET_CHANNEL      { field_id, channel }        (channel may be null)
 *     TOGGLE_CONFIRM   { field_id }                 (draft ↔ ready)
 *     EXECUTE_FLAG     { field_id }                 (→ archive, status:sent)
 *     SEND_ALL         {}                           (all ready → archive)
 *     SET_ARCHIVE_STATUS { archive_index, status }  (sent → delivered|expired)
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
    var ARCHIVE_STATUSES = { sent: 1, delivered: 1, expired: 1 };

    var VALID_VERBS = {};
    VERB_TOKENS.forEach(function (t) { VALID_VERBS[t] = 1; });
    var VALID_TARGETS = {};
    TARGET_TOKENS.forEach(function (t) { VALID_TARGETS[t] = 1; });
    var VALID_CHANNELS = {};
    CHANNEL_TOKENS.forEach(function (t) { VALID_CHANNELS[t] = 1; });

    function initialState() {
        return {
            flags: {},
            archive: [],
            tick: 0,
        };
    }

    function nextTick(state) {
        return (state.tick || 0) + 1;
    }

    function isChainComplete(flag) {
        return !!(flag && flag.verb && flag.target && flag.channel);
    }

    /* withState — convenience that copies state and overlays updates,
     * always preserving the archive unless explicitly replaced. */
    function withState(state, updates) {
        return Object.assign({}, state, updates);
    }

    /* FLAG_FIELD — create (or re-flag) a flag with the given verb.
     * target/channel start null, status starts at draft. Re-flagging
     * an active flag preserves target/channel/status. The archive is
     * never consulted — re-flagging a previously-sent field always
     * starts fresh. */
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
        return withState(state, { flags: newFlags, tick: tick });
    }

    function unflagField(state, fieldId) {
        if (!fieldId || !state.flags[fieldId]) return state;
        var newFlags = Object.assign({}, state.flags);
        delete newFlags[fieldId];
        return withState(state, { flags: newFlags });
    }

    /* setPill — change a pill's value on an active flag. If the
     * change makes the chain incomplete, ready demotes to draft. */
    function setPill(state, fieldId, pillKey, value, validMap) {
        if (!fieldId || !state.flags[fieldId]) return state;
        if (value !== null && !validMap[value]) return state;

        var existing = state.flags[fieldId];
        if (existing[pillKey] === value) return state;

        var update = {};
        update[pillKey] = value;
        var next = Object.assign({}, existing, update);
        if (next.status === "ready" && !isChainComplete(next)) {
            next.status = "draft";
        }
        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = next;
        return withState(state, { flags: newFlags });
    }

    /* TOGGLE_CONFIRM — flip draft ↔ ready. Confirm requires a
     * complete chain; toggling off is always allowed. */
    function toggleConfirm(state, fieldId) {
        if (!fieldId || !state.flags[fieldId]) return state;
        var existing = state.flags[fieldId];
        if (existing.status === "draft" && isChainComplete(existing)) {
            var newFlags = Object.assign({}, state.flags);
            newFlags[fieldId] = Object.assign({}, existing, { status: "ready" });
            return withState(state, { flags: newFlags });
        }
        if (existing.status === "ready") {
            var newFlags2 = Object.assign({}, state.flags);
            newFlags2[fieldId] = Object.assign({}, existing, { status: "draft" });
            return withState(state, { flags: newFlags2 });
        }
        return state;
    }

    /* archiveOne — pop a flag from `flags` and push a sent copy
     * onto `archive`. Returns updated { flags, archive } or null
     * if the flag wasn't eligible to fire (incomplete chain). */
    function archiveOne(flags, archive, fieldId, sentAt) {
        var existing = flags[fieldId];
        if (!existing) return null;
        if (!isChainComplete(existing)) return null;
        var newFlags = Object.assign({}, flags);
        delete newFlags[fieldId];
        var sentEntry = Object.assign({}, existing, {
            status: "sent",
            sent_at: sentAt,
        });
        return {
            flags: newFlags,
            archive: archive.concat([sentEntry]),
        };
    }

    /* EXECUTE_FLAG — fire a single row. Removes from flags, appends
     * to archive. No-op on incomplete chain or unknown field. */
    function executeFlag(state, fieldId) {
        if (!fieldId) return state;
        var tick = nextTick(state);
        var moved = archiveOne(state.flags, state.archive || [], fieldId, tick);
        if (!moved) return state;
        return withState(state, {
            flags: moved.flags,
            archive: moved.archive,
            tick: tick,
        });
    }

    /* SEND_ALL — every active flag with status:ready fires; each
     * one moves from flags → archive. Single shared sent_at tick
     * for the batch so the archive reads as one event. */
    function sendAll(state) {
        var readyIds = Object.keys(state.flags).filter(function (fid) {
            return state.flags[fid].status === "ready";
        });
        if (readyIds.length === 0) return state;
        var tick = nextTick(state);
        var flags = state.flags;
        var archive = state.archive || [];
        for (var i = 0; i < readyIds.length; i++) {
            var moved = archiveOne(flags, archive, readyIds[i], tick);
            if (!moved) continue;
            flags = moved.flags;
            archive = moved.archive;
        }
        return withState(state, {
            flags: flags,
            archive: archive,
            tick: tick,
        });
    }

    /* SET_ARCHIVE_STATUS — transition an archive entry's status
     * (sent → delivered | expired). Identified by archive_index
     * since (field_id, sent_at) isn't a unique key — same field
     * may appear multiple times. */
    function setArchiveStatus(state, archiveIndex, status) {
        var archive = state.archive || [];
        if (archiveIndex < 0 || archiveIndex >= archive.length) return state;
        if (!ARCHIVE_STATUSES[status]) return state;
        var existing = archive[archiveIndex];
        if (existing.status === status) return state;
        var newArchive = archive.slice();
        newArchive[archiveIndex] = Object.assign({}, existing, { status: status });
        return withState(state, { archive: newArchive });
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
            case "SET_ARCHIVE_STATUS":
                return setArchiveStatus(state, action.archive_index, action.status);
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
