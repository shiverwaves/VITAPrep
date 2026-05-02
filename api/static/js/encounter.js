/* Encounter screen — page tab switching and status bar updates */

(function () {
    "use strict";

    var tabStrip = document.getElementById("page-tabs");
    if (!tabStrip) return;

    var tabs = tabStrip.querySelectorAll(".sheet__tab");
    var pages = document.querySelectorAll(".sheet__page");
    var statusPage = document.getElementById("status-page");

    var PAGE_LABELS = { 1: "Page 1", 2: "Page 2", 3: "Page 3", 4: "Page 4" };

    function switchTab(pageNum) {
        tabs.forEach(function (t) {
            var isTarget = t.getAttribute("data-page") === String(pageNum);
            t.classList.toggle("sheet__tab--active", isTarget);
        });

        pages.forEach(function (p) {
            var isTarget = p.getAttribute("data-page") === String(pageNum);
            p.classList.toggle("sheet__page--active", isTarget);
        });

        if (statusPage) {
            statusPage.textContent = PAGE_LABELS[pageNum] || "Page " + pageNum;
        }

        var url = new URL(window.location);
        url.searchParams.set("page", pageNum);
        history.replaceState(null, "", url);
    }

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            var pageNum = parseInt(tab.getAttribute("data-page"), 10);
            switchTab(pageNum);
        });
    });

    /* Set initial tab from URL parameter or default to 1 */
    var params = new URLSearchParams(window.location.search);
    var initialPage = parseInt(params.get("page"), 10) || 1;
    switchTab(initialPage);
})();
