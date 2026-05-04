/* Flag state machine for the marked-for-follow-up mechanic.
 *
 * Pure function. No DOM, no globals (other than the namespace export
 * at the bottom), no side effects. Returns a new state object on every
 * transition; never mutates inputs.
 *
 * Wired up by api/static/js/flags-render.js, which dispatches actions
 * and persists state to sessionStorage. This module just decides the
 * next state shape.
 *
 * State shape:
 *
 *     {
 *         flags: { [field_id]: Flag },
 *         tick: number,                 // monotonic counter for created_at
 *     }
 *
 * Flag shape:
 *
 *     {
 *         field_id: string,             // duplicated from map key for convenience
 *         context: "Missing" | "Confirm" | "Other",
 *         context_text: string | null,  // required when context = "Other"
 *         action: "Email" | "Chat" | "AskVida" | "Other" | null,
 *         status: "draft" | "ready" | "sent" | "answered" | "applied" | "dismissed",
 *         created_at: number,           // tick value when first flagged
 *     }
 *
 * Action types:
 *
 *     FLAG_FIELD       { field_id, context, context_text? }
 *     UNFLAG_FIELD     { field_id }
 *     SET_CONTEXT      { field_id, context, context_text? }
 *     SET_ACTION       { field_id, action }           (action may be null to clear)
 *     CLEAR_ALL        {}
 *
 * Status lifecycle (placeholder beyond MVP):
 *
 *     draft (just flagged, no action)
 *       → ready (action chosen)
 *       → sent / answered / applied / dismissed (later sprints)
 *
 * For MVP only "draft" and "ready" actually fire; the later states are
 * reserved for when the probe-send pipeline lands.
 */

(function (global) {
    "use strict";

    var VALID_CONTEXTS = { Missing: 1, Confirm: 1, Other: 1 };
    var VALID_ACTIONS = { Email: 1, Chat: 1, AskVida: 1, Other: 1 };

    function initialState() {
        return {
            flags: {},
            tick: 0,
        };
    }

    /* Bump the monotonic tick. Returns the next tick value. */
    function nextTick(state) {
        return (state.tick || 0) + 1;
    }

    /* Add (or overwrite) a flag for field_id. Status starts at "draft".
     *
     * context_text is optional even for the "Other" context — it can
     * be supplied as a free-form descriptor when set, or left null.
     * (The MVP context menu doesn't prompt for text; a richer compose
     * flow can populate context_text later.) */
    function flagField(state, fieldId, context, contextText) {
        if (!fieldId) return state;
        if (!VALID_CONTEXTS[context]) return state;

        var tick = nextTick(state);
        var newFlags = Object.assign({}, state.flags);
        var existing = state.flags[fieldId];
        newFlags[fieldId] = {
            field_id: fieldId,
            context: context,
            context_text: contextText || null,
            /* Re-flagging an already-flagged field preserves its action
             * and status. Brand-new flags start as drafts. */
            action: existing ? existing.action : null,
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

    /* Change the context on an existing flag. No-op if the field isn't
     * flagged (use FLAG_FIELD to create). context_text is optional
     * for any context. */
    function setContext(state, fieldId, context, contextText) {
        if (!fieldId || !state.flags[fieldId]) return state;
        if (!VALID_CONTEXTS[context]) return state;

        var existing = state.flags[fieldId];
        var newText = contextText || null;
        if (existing.context === context && existing.context_text === newText) {
            return state;  /* no actual change */
        }
        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = Object.assign({}, existing, {
            context: context,
            context_text: newText,
        });
        return { flags: newFlags, tick: state.tick };
    }

    /* Set (or clear, with action=null) the action on an existing flag.
     * Status transitions draft → ready when an action is set; ready →
     * draft when cleared. */
    function setAction(state, fieldId, action) {
        if (!fieldId || !state.flags[fieldId]) return state;
        if (action !== null && !VALID_ACTIONS[action]) return state;

        var existing = state.flags[fieldId];
        if (existing.action === action) return state;  /* no change */

        var newStatus = existing.status;
        if (action === null && existing.status === "ready") {
            newStatus = "draft";
        } else if (action !== null && existing.status === "draft") {
            newStatus = "ready";
        }

        var newFlags = Object.assign({}, state.flags);
        newFlags[fieldId] = Object.assign({}, existing, {
            action: action,
            status: newStatus,
        });
        return { flags: newFlags, tick: state.tick };
    }

    function clearAll(state) {
        if (Object.keys(state.flags).length === 0) return state;
        return { flags: {}, tick: state.tick };
    }

    function reduce(state, action) {
        if (!action || typeof action.type !== "string") return state;
        switch (action.type) {
            case "FLAG_FIELD":
                return flagField(
                    state, action.field_id, action.context, action.context_text
                );
            case "UNFLAG_FIELD":
                return unflagField(state, action.field_id);
            case "SET_CONTEXT":
                return setContext(
                    state, action.field_id, action.context, action.context_text
                );
            case "SET_ACTION":
                return setAction(state, action.field_id, action.action);
            case "CLEAR_ALL":
                return clearAll(state);
            default:
                return state;
        }
    }

    global.FlagsReducer = {
        initialState: initialState,
        reduce: reduce,
    };
}(typeof window !== "undefined" ? window : globalThis));
