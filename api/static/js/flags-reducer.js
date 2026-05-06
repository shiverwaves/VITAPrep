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
 *         verb: "RequestInfo",
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
 * Status lifecycle: draft → staged → sent
 *   - draft: chain may be incomplete; pills editable; no action taken.
 *   - staged: chain complete and player tapped Compose (Message) or
 *     Add to draft (Email). Pills locked. Surface depends on channel.
 *   - sent: archived, immutable.
 *
 * Action types:
 *
 *     FLAG_FIELD       { field_id, verb }
 *     UNFLAG_FIELD     { field_id }                 (Discard from any state)
 *     SET_VERB         { field_id, verb }
 *     SET_TARGET       { field_id, target }         (target may be null)
 *     SET_CHANNEL      { field_id, channel }        (channel may be null)
 *     STAGE_FLAG       { field_id }                 (draft → staged, requires complete chain)
 *     UNSTAGE_FLAG     { field_id }                 (staged → draft)
 *     SEND_FLAG        { field_id }                 (staged → sent)
 *     SEND_STAGED_BY_CHANNEL { channel, target? }   (batch staged → sent)
 *     SET_ARCHIVE_STATUS { archive_index, status }  (sent → delivered|expired)
 */

(function (global) {
    "use strict";

    /* Pill option lists. Each is the source of truth for what's a
     * legal value AND the display order in the dropdown. Adding a
     * new option is a one-line edit here. Labels live in OPTIONS
     * separately so the token (used in state) and the display
     * string can diverge. */
    var VERB_TOKENS = ["RequestInfo"];
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

    /* setPill — change a pill's value on an active flag. Pills are
     * locked once a row is staged (Compose / Add to draft was
     * clicked) — player must un-stage to edit. */
    function setPill(state, fieldId, pillKey, value, validMap) {
        if (!fieldId || !state.flags[fieldId]) return state;
        if (value !== null && !validMap[value]) return state;

        var existing = state.flags[fieldId];
        if (existing.status === "staged") return state;  /* locked */
        if (existing[pillKey] === value) return state;

        var update = {};
        update[pillKey] = value;
        var next = Object.assign({}, existing, update);
        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = next;
        return withState(state, { flags: newFlags });
    }

    /* STAGE_FLAG — moves a complete-chain row from draft → staged.
     * Channel decides what "staged" means downstream:
     *   - Message: row is composed and visible in the Messages tab;
     *     player clicks Send there to fire (SEND_FLAG).
     *   - Email:   row is queued in the Mail tab's email draft;
     *     player clicks Send Email there to batch-fire.
     * Pills lock once staged. */
    function stageFlag(state, fieldId) {
        if (!fieldId || !state.flags[fieldId]) return state;
        var existing = state.flags[fieldId];
        if (existing.status !== "draft") return state;
        if (!isChainComplete(existing)) return state;
        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = Object.assign({}, existing, { status: "staged" });
        return withState(state, { flags: newFlags });
    }

    /* UNSTAGE_FLAG — staged → draft. Lets the player re-edit pills
     * after they've staged a row but before sending. */
    function unstageFlag(state, fieldId) {
        if (!fieldId || !state.flags[fieldId]) return state;
        var existing = state.flags[fieldId];
        if (existing.status !== "staged") return state;
        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = Object.assign({}, existing, { status: "draft" });
        return withState(state, { flags: newFlags });
    }

    /* archiveOne — pop a flag from `flags` and push a sent copy
     * onto `archive`. Caller has already validated state. */
    function archiveOne(flags, archive, fieldId, sentAt) {
        var existing = flags[fieldId];
        if (!existing) return null;
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

    /* SEND_FLAG — fires a single staged row to the archive. The
     * preview surface (Messages tab for Message channel, Mail tab
     * for Email channel) calls this on its Send action. */
    function sendFlag(state, fieldId) {
        if (!fieldId) return state;
        var existing = state.flags[fieldId];
        if (!existing || existing.status !== "staged") return state;
        var tick = nextTick(state);
        var moved = archiveOne(state.flags, state.archive || [], fieldId, tick);
        if (!moved) return state;
        return withState(state, {
            flags: moved.flags,
            archive: moved.archive,
            tick: tick,
        });
    }

    /* SEND_STAGED_BY_CHANNEL — batch-fire all staged rows whose
     * channel matches the given value (and target, if provided).
     * Used by the Mail tab when the player sends a compiled email:
     * every staged Email-row to that recipient archives in one event. */
    function sendStagedByChannel(state, channel, target) {
        if (!channel) return state;
        var matchIds = Object.keys(state.flags).filter(function (fid) {
            var f = state.flags[fid];
            if (f.status !== "staged") return false;
            if (f.channel !== channel) return false;
            if (target && f.target !== target) return false;
            return true;
        });
        if (matchIds.length === 0) return state;
        var tick = nextTick(state);
        var flags = state.flags;
        var archive = state.archive || [];
        for (var i = 0; i < matchIds.length; i++) {
            var moved = archiveOne(flags, archive, matchIds[i], tick);
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
            case "STAGE_FLAG":
                return stageFlag(state, action.field_id);
            case "UNSTAGE_FLAG":
                return unstageFlag(state, action.field_id);
            case "SEND_FLAG":
                return sendFlag(state, action.field_id);
            case "SEND_STAGED_BY_CHANNEL":
                return sendStagedByChannel(state, action.channel, action.target);
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
