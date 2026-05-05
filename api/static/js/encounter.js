/* Encounter screen — right-click context menu for the Flag mechanic.
 *
 * Listens for `contextmenu` on #form-pane. When the click target is a
 * form input, prevents the browser's default menu and shows a custom
 * menu offering Flag / Change-context / Unflag actions. Menu items
 * dispatch through window.Flags.dispatch (set up in flags-render.js).
 *
 * Outside of #form-pane (titlebar, doc panes, chat), the browser's
 * default context menu fires unchanged.
 */

(function (global) {
    "use strict";

    /* Single menu DOM lazily inserted on first use. The CSS skeleton
     * in api/static/styles/contextmenu.css does the visual lifting. */
    var menu = null;
    var backdrop = null;
    var formPane = null;

    function init() {
        formPane = document.getElementById("form-pane");
        if (!formPane) return;
        ensureMenuDom();

        formPane.addEventListener("contextmenu", handleContextMenu);
        backdrop.addEventListener("click", closeMenu);
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") closeMenu();
        });
    }

    function ensureMenuDom() {
        backdrop = document.createElement("div");
        backdrop.className = "contextmenu__backdrop";
        document.body.appendChild(backdrop);

        menu = document.createElement("div");
        menu.className = "contextmenu";
        menu.id = "field-contextmenu";
        document.body.appendChild(menu);
    }

    function handleContextMenu(e) {
        var input = findFormInput(e.target);
        if (!input) return;  /* let the browser default fire */
        var fieldId = input.getAttribute("name");
        if (!fieldId) return;

        e.preventDefault();
        openMenu(e.clientX, e.clientY, fieldId);
    }

    /* Locate the form input associated with a click target.
     *
     * Input-only rule: the custom Flag menu fires when the click
     * target IS (or descends from) a form input — text input,
     * textarea, checkbox, radio, select. Right-click on a label,
     * caption, cell padding, or any other surrounding wrapper
     * lets the browser's default menu fire instead.
     *
     * Crystal clear discoverability: "right-click the input itself
     * to flag it." No walk-up to ambiguous wrappers, no shared
     * heading edge cases, no need to think about which labels are
     * flag-clickable. Trade-off is loss of browser-default
     * right-click on text inputs (paste, spell-check), which is a
     * minor cost for this app's data-from-documents workflow.
     *
     * Walks up the ancestor chain rather than just checking the
     * click target directly, in case the click landed on a child
     * node of an input (e.g., text node inside a textarea). */
    function findFormInput(node) {
        var cursor = node;
        while (cursor && cursor !== formPane) {
            var tag = cursor.tagName;
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
                return cursor;
            }
            cursor = cursor.parentNode;
        }
        return null;
    }

    function openMenu(x, y, fieldId) {
        var existing = currentFlag(fieldId);
        menu.innerHTML = renderMenuItems(fieldId, existing);

        /* Wire each menu item's click before positioning, since
         * positioning measures the menu's bounding rect after layout. */
        var items = menu.querySelectorAll("[data-flag-action]");
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            (function (el) {
                el.addEventListener("click", function () {
                    handleMenuAction(el.getAttribute("data-flag-action"), fieldId);
                    closeMenu();
                });
            })(item);
        }

        menu.style.left = x + "px";
        menu.style.top = y + "px";
        menu.classList.add("contextmenu--open");
        backdrop.classList.add("contextmenu__backdrop--open");

        /* Re-anchor if the menu spills off-screen (edges of doc panes,
         * close to the chat-pane border, etc.). */
        var rect = menu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            menu.style.left = (window.innerWidth - rect.width - 4) + "px";
        }
        if (rect.bottom > window.innerHeight) {
            menu.style.top = (window.innerHeight - rect.height - 4) + "px";
        }
    }

    function closeMenu() {
        if (!menu) return;
        menu.classList.remove("contextmenu--open");
        backdrop.classList.remove("contextmenu__backdrop--open");
    }

    function currentFlag(fieldId) {
        if (!global.Flags) return null;
        var s = global.Flags.getState();
        return s && s.flags ? s.flags[fieldId] || null : null;
    }

    /* Display labels per context — natural-language, easier to read
     * than the raw enum values. The reducer / state still use the
     * canonical "Missing" / "Confirm" / "Other" tokens; this map is
     * presentation-only. */
    var CONTEXT_LABELS = {
        Missing: "Missing Information",
        Confirm: "Needs Confirmation",
        Other: "Other",
    };

    /* Render the menu HTML for the right-clicked field. Two cases:
     *   - Unflagged: show three Flag-as items (one per context).
     *   - Flagged: show current context, change-context options
     *     (excluding the current one), and an Unflag (danger) item.
     *
     * The header row shows the raw field id for now; a human-label
     * registry is a future polish item. */
    function renderMenuItems(fieldId, existing) {
        var parts = [];
        parts.push(
            '<div class="contextmenu__header">' +
            escapeHtml(fieldId) +
            '</div>'
        );

        var contexts = ["Missing", "Confirm", "Other"];

        if (existing) {
            parts.push(
                '<div class="contextmenu__header" style="text-transform:none;color:var(--color-accent)">' +
                'Flagged: ' + escapeHtml(CONTEXT_LABELS[existing.context] || existing.context) +
                '</div>'
            );
            contexts.forEach(function (ctx) {
                if (ctx !== existing.context) {
                    parts.push(
                        '<button type="button" class="contextmenu__item"' +
                        ' data-flag-action="set-context:' + ctx + '">' +
                        escapeHtml(CONTEXT_LABELS[ctx]) +
                        '</button>'
                    );
                }
            });
            parts.push('<div class="contextmenu__separator"></div>');
            parts.push(
                '<button type="button" class="contextmenu__item contextmenu__item--danger"' +
                ' data-flag-action="unflag">Unflag</button>'
            );
        } else {
            contexts.forEach(function (ctx) {
                parts.push(
                    '<button type="button" class="contextmenu__item"' +
                    ' data-flag-action="flag:' + ctx + '">' +
                    escapeHtml(CONTEXT_LABELS[ctx]) +
                    '</button>'
                );
            });
        }
        return parts.join("");
    }

    function handleMenuAction(action, fieldId) {
        if (!global.Flags) return;

        if (action === "unflag") {
            global.Flags.dispatch({
                type: "UNFLAG_FIELD",
                field_id: fieldId,
            });
            return;
        }

        var actionType, ctx;
        if (action.indexOf("flag:") === 0) {
            actionType = "FLAG_FIELD";
            ctx = action.slice(5);
        } else if (action.indexOf("set-context:") === 0) {
            actionType = "SET_CONTEXT";
            ctx = action.slice(12);
        } else {
            return;
        }

        global.Flags.dispatch({
            type: actionType,
            field_id: fieldId,
            context: ctx,
        });
    }

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

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}(typeof window !== "undefined" ? window : globalThis));
