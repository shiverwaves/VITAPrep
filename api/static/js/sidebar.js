/* Sidebar toggle and tab switching */

(function () {
    "use strict";

    var sidebar = document.getElementById("sidebar");
    var toggleBtn = document.getElementById("sidebar-toggle-btn");

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener("click", function () {
            sidebar.classList.toggle("sidebar--collapsed");
        });
    }

    var tabs = sidebar ? sidebar.querySelectorAll(".sidebar__tab") : [];
    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            var panelName = tab.getAttribute("data-panel");

            tabs.forEach(function (t) { t.classList.remove("sidebar__tab--active"); });
            tab.classList.add("sidebar__tab--active");

            var panels = sidebar.querySelectorAll(".sidebar__panel");
            panels.forEach(function (p) { p.classList.remove("sidebar__panel--active"); });

            var target = document.getElementById("panel-" + panelName);
            if (target) target.classList.add("sidebar__panel--active");
        });
    });
})();
