/* Bibliotheca Dantalian client script: theme, spoiler prefs, search. */
(function () {
  "use strict";

  var root = document.documentElement;

  /* Collapse the nav fold by default on narrow screens. */
  var fold = document.querySelector(".nav-fold");
  if (fold && matchMedia("(max-width: 900px)").matches) {
    fold.removeAttribute("open");
  }

  /* ------------------------------------------------------------- theme */

  var themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try {
        localStorage.setItem("dantalian-theme", next);
      } catch (e) {}
    });
  }

  /* ----------------------------------------------------------- spoilers */

  function spoilerPrefs() {
    try {
      return JSON.parse(localStorage.getItem("dantalian-spoilers") || "{}");
    } catch (e) {
      return {};
    }
  }

  var prefBoxes = document.querySelectorAll(".spoil-pref");

  function globalOn(scope) {
    return root.getAttribute("data-spoil-" + scope) === "on";
  }

  function applySpoilers(prefs) {
    prefBoxes.forEach(function (cb) {
      var scope = cb.dataset.scope;
      if (prefs[scope]) root.setAttribute("data-spoil-" + scope, "on");
      else root.removeAttribute("data-spoil-" + scope);
    });
  }

  function boxOpen(box) {
    if (box.classList.contains("user-hidden")) return false;
    return box.classList.contains("revealed") || globalOn(box.dataset.scope);
  }

  function syncButtons() {
    document.querySelectorAll(".spoiler").forEach(function (box) {
      var btn = box.querySelector(".spoiler-btn");
      if (btn) btn.textContent = boxOpen(box) ? "Hide" : "Show";
    });
  }

  if (prefBoxes.length) {
    var prefs = spoilerPrefs();
    prefBoxes.forEach(function (cb) {
      cb.checked = !!prefs[cb.dataset.scope];
    });
    var save = function () {
      var p = {};
      prefBoxes.forEach(function (cb) {
        p[cb.dataset.scope] = cb.checked;
      });
      applySpoilers(p);
      // a global change resets any per-box overrides for predictability
      document.querySelectorAll(".spoiler").forEach(function (box) {
        box.classList.remove("revealed", "user-hidden");
      });
      syncButtons();
      try {
        localStorage.setItem("dantalian-spoilers", JSON.stringify(p));
      } catch (e) {}
    };
    prefBoxes.forEach(function (cb) {
      cb.addEventListener("change", save);
    });
  }

  document.querySelectorAll(".spoiler-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var box = btn.closest(".spoiler");
      if (boxOpen(box)) {
        box.classList.remove("revealed");
        box.classList.add("user-hidden");
      } else {
        box.classList.remove("user-hidden");
        box.classList.add("revealed");
      }
      btn.textContent = boxOpen(box) ? "Hide" : "Show";
    });
  });

  syncButtons();

  /* ------------------------------------------------------------- search */

  var input = document.getElementById("search");
  var results = document.getElementById("search-results");
  if (!input || !results) return;

  var active = -1;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function score(page, q) {
    var t = page.t.toLowerCase();
    var s = 0;
    if (t === q) s += 100;
    else if (t.indexOf(q) === 0) s += 60;
    else if (t.indexOf(q) >= 0) s += 40;
    if ((page.c || "").toLowerCase().indexOf(q) >= 0) s += 12;
    if ((page.h || "").toLowerCase().indexOf(q) >= 0) s += 10;
    if ((page.d || "").toLowerCase().indexOf(q) >= 0) s += 8;
    return s;
  }

  function render(q) {
    var index = window.SEARCH_INDEX || [];
    q = q.trim().toLowerCase();
    if (!q) {
      results.hidden = true;
      results.innerHTML = "";
      active = -1;
      return;
    }
    var hits = index
      .map(function (p) { return [score(p, q), p]; })
      .filter(function (x) { return x[0] > 0; })
      .sort(function (a, b) { return b[0] - a[0]; })
      .slice(0, 8);

    if (!hits.length) {
      results.innerHTML = '<div class="r-none">No pages match. Try another spelling.</div>';
      results.hidden = false;
      active = -1;
      return;
    }
    results.innerHTML = hits
      .map(function (x) {
        var p = x[1];
        return (
          '<a href="' + esc(p.s) + '.html">' +
          '<span class="r-type">' + esc(p.y) + "</span>" +
          "<strong>" + esc(p.t) + "</strong>" +
          '<span class="r-sum">' + esc(p.d) + "</span></a>"
        );
      })
      .join("");
    results.hidden = false;
    active = -1;
  }

  input.addEventListener("input", function () { render(input.value); });
  input.addEventListener("focus", function () { render(input.value); });

  input.addEventListener("keydown", function (e) {
    var links = results.querySelectorAll("a");
    if (e.key === "ArrowDown" && links.length) {
      e.preventDefault();
      active = (active + 1) % links.length;
    } else if (e.key === "ArrowUp" && links.length) {
      e.preventDefault();
      active = (active - 1 + links.length) % links.length;
    } else if (e.key === "Enter" && links.length) {
      e.preventDefault();
      links[active >= 0 ? active : 0].click();
      return;
    } else if (e.key === "Escape") {
      results.hidden = true;
      input.blur();
      return;
    } else {
      return;
    }
    links.forEach(function (a, i) {
      a.classList.toggle("active", i === active);
    });
  });

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".search-wrap")) results.hidden = true;
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && document.activeElement !== input) {
      var tag = (document.activeElement.tagName || "").toLowerCase();
      if (tag !== "input" && tag !== "textarea") {
        e.preventDefault();
        input.focus();
      }
    }
  });
})();
