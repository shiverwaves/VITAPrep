/* Dropdown menu handling — hamburger and scenario menus */

(function () {
    "use strict";

    function setupDropdown(btnId, menuId, backdropId) {
        var btn = document.getElementById(btnId);
        var menu = document.getElementById(menuId);
        var backdrop = document.getElementById(backdropId);
        if (!btn || !menu) return;

        function open() {
            menu.classList.add("dropdown--open");
            if (backdrop) backdrop.classList.add("dropdown__backdrop--open");
        }

        function close() {
            menu.classList.remove("dropdown--open");
            if (backdrop) backdrop.classList.remove("dropdown__backdrop--open");
        }

        function toggle() {
            if (menu.classList.contains("dropdown--open")) {
                close();
            } else {
                open();
            }
        }

        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            toggle();
        });

        if (backdrop) {
            backdrop.addEventListener("click", close);
        }

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") close();
        });
    }

    setupDropdown("hamburger-btn", "hamburger-menu", "hamburger-backdrop");
    setupDropdown("scenario-btn", "scenario-menu", "scenario-backdrop");
})();
