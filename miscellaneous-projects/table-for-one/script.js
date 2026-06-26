/* ============================================================
   Table for One - progressive enhancements
   ------------------------------------------------------------
   With JavaScript off, every entry is present in the HTML and the
   page reads fine. This script adds, in order:

     1. Theme toggle (light / dark), remembered in localStorage.
     2. Newest-first date sort, so HTML order never matters.
     3. A two-tier archive (year, then month) built from the dates.
     4. Text search across all entries.
     5. Per-entry permalinks with copy-to-clipboard.

   Archive scope, search, and the scale-friendly default all run
   through one applyFilters(), so they compose instead of fighting.
   No build step, no dependencies.
   ============================================================ */
(function () {
  "use strict";

  setupTheme();

  var page = document.querySelector(".page");
  if (!page) return;

  var entries = Array.prototype.slice.call(page.querySelectorAll(".entry"));
  if (!entries.length) return;

  /* ---------- 2. date sort (newest first, stable) ---------- */
  function isoOf(entry) {
    var t = entry.querySelector("time[datetime]");
    return (t && t.getAttribute("datetime")) || "";
  }
  entries.sort(function (a, b) {
    var ia = isoOf(a), ib = isoOf(b);
    return ia < ib ? 1 : ia > ib ? -1 : 0;
  });
  // Re-append in order; the .controls and .archive stay ahead of them.
  entries.forEach(function (e) { page.appendChild(e); });

  /* ---------- index: months, ids, search text, permalinks ---------- */
  var monthName = new Intl.DateTimeFormat("en", { month: "long" });
  var years = {};      // "2026" -> { count, months: {"2026-04": {label,count}}, order: [] }
  var yearOrder = [];

  entries.forEach(function (entry) {
    var iso = isoOf(entry);
    var ym = iso.slice(0, 7);
    var y = iso.slice(0, 4);
    entry.dataset.month = ym;
    entry.dataset.year = y;

    if (!years[y]) {
      years[y] = { count: 0, months: {}, order: [] };
      yearOrder.push(y);
    }
    years[y].count += 1;
    if (!years[y].months[ym]) {
      var d = new Date(iso + "T12:00:00");
      years[y].months[ym] = { label: monthName.format(d), count: 0 };
      years[y].order.push(ym);
    }
    years[y].months[ym].count += 1;

    // stable id (honor a static one, else derive; dedupe just in case)
    if (!entry.id) entry.id = "entry-" + iso;
    var id = entry.id, n = 2, clash;
    while ((clash = document.getElementById(id)) && clash !== entry) {
      id = entry.id + "-" + n++;
    }
    entry.id = id;

    // searchable text snapshot (title + body + place + date) before we add the "#"
    entry._search = (entry.textContent || "").toLowerCase();

    // permalink affordance on the date line
    var dateEl = entry.querySelector(".entry__date");
    if (dateEl) {
      var link = document.createElement("a");
      link.className = "entry__permalink";
      link.href = "#" + entry.id;
      link.textContent = "#";
      link.setAttribute("aria-label", "Copy link to this entry");
      link.addEventListener("click", onPermalinkClick);
      dateEl.appendChild(link);
    }
  });

  yearOrder.sort().reverse();
  yearOrder.forEach(function (y) { years[y].order.sort().reverse(); });

  /* ---------- 3. archive UI ---------- */
  var nav = page.querySelector(".archive");
  var yearsRow, monthsRow;

  function makeItem(value, label, count) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "archive__item";
    btn.dataset.value = value;
    btn.setAttribute("aria-pressed", "false");
    var l = document.createElement("span");
    l.className = "archive__label";
    l.textContent = label;
    btn.appendChild(l);
    if (count != null) {
      var c = document.createElement("span");
      c.className = "archive__count";
      c.textContent = count;
      btn.appendChild(c);
    }
    return btn;
  }

  if (nav) {
    yearsRow = document.createElement("div");
    yearsRow.className = "archive__row archive__years";
    var title = document.createElement("span");
    title.className = "archive__title";
    title.textContent = "Archive";
    yearsRow.appendChild(title);
    yearsRow.appendChild(makeItem("all", "All", entries.length));
    yearOrder.forEach(function (y) {
      yearsRow.appendChild(makeItem(y, y, years[y].count));
    });

    monthsRow = document.createElement("div");
    monthsRow.className = "archive__row archive__months";
    monthsRow.hidden = true;

    nav.appendChild(yearsRow);
    nav.appendChild(monthsRow);
    nav.hidden = false;

    nav.addEventListener("click", function (e) {
      var btn = e.target.closest(".archive__item");
      if (!btn) return;
      if (searchInput) searchInput.value = "";
      state.query = "";
      state.scope = btn.dataset.value;
      applyFilters();
    });
  }

  function setActive(row, value) {
    if (!row) return;
    Array.prototype.forEach.call(row.querySelectorAll(".archive__item"), function (btn) {
      var active = btn.dataset.value === value;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function buildMonths(year) {
    if (!monthsRow) return;
    monthsRow.innerHTML = "";
    var Y = years[year];
    if (!Y) return;
    Y.order.forEach(function (ym) {
      monthsRow.appendChild(makeItem(ym, Y.months[ym].label, Y.months[ym].count));
    });
  }

  /* ---------- 4. search UI ---------- */
  var controls = page.querySelector(".controls");
  var searchInput, searchClear, statusEl;

  if (controls) {
    var wrap = document.createElement("div");
    wrap.className = "search";

    searchInput = document.createElement("input");
    searchInput.type = "search";
    searchInput.className = "search__input";
    searchInput.placeholder = "Search the entries";
    searchInput.setAttribute("aria-label", "Search the entries");

    searchClear = document.createElement("button");
    searchClear.type = "button";
    searchClear.className = "search__clear";
    searchClear.innerHTML = "&times;";
    searchClear.setAttribute("aria-label", "Clear search");
    searchClear.hidden = true;

    wrap.appendChild(searchInput);
    wrap.appendChild(searchClear);

    statusEl = document.createElement("p");
    statusEl.className = "controls__status";
    statusEl.setAttribute("role", "status");
    statusEl.setAttribute("aria-live", "polite");
    statusEl.hidden = true;

    controls.appendChild(wrap);
    controls.appendChild(statusEl);
    controls.hidden = false;

    searchInput.addEventListener("input", debounce(function () {
      state.query = searchInput.value.trim();
      applyFilters();
    }, 120));

    searchClear.addEventListener("click", function () {
      searchInput.value = "";
      state.query = "";
      applyFilters();
      searchInput.focus();
    });
  }

  /* ---------- unified filter model ---------- */
  var state = { scope: "all", query: "" };

  function setHash(hash) {
    if (location.hash !== hash) {
      history.replaceState(null, "", hash || location.pathname + location.search);
    }
  }

  function applyScope(value) {
    if (value === "all" || !value) {
      entries.forEach(function (e) { e.hidden = false; });
      setActive(yearsRow, "all");
      if (monthsRow) { monthsRow.hidden = true; monthsRow.innerHTML = ""; }
      setHash("");
      return;
    }
    var isMonth = value.length === 7;
    var year = value.slice(0, 4);
    entries.forEach(function (e) {
      e.hidden = isMonth ? e.dataset.month !== value : e.dataset.year !== year;
    });
    setActive(yearsRow, year);
    buildMonths(year);
    if (monthsRow) monthsRow.hidden = false;
    setActive(monthsRow, isMonth ? value : "");
    setHash("#" + value);
  }

  function applyFilters() {
    var q = state.query.toLowerCase();

    if (q) {
      var matches = 0;
      entries.forEach(function (e) {
        var show = e._search.indexOf(q) !== -1;
        e.hidden = !show;
        if (show) matches += 1;
      });
      setActive(yearsRow, " ");           // clear all archive highlights
      if (monthsRow) { monthsRow.hidden = true; monthsRow.innerHTML = ""; }
      if (searchClear) searchClear.hidden = false;
      if (statusEl) {
        statusEl.hidden = false;
        statusEl.innerHTML = matches
          ? "Showing <em>" + matches + "</em> " + (matches === 1 ? "entry" : "entries") +
            " for “" + escapeHtml(state.query) + "”"
          : "No entries for “" + escapeHtml(state.query) + "”";
      }
      setHash("");
      return;
    }

    if (searchClear) searchClear.hidden = true;
    if (statusEl) { statusEl.hidden = true; statusEl.textContent = ""; }
    applyScope(state.scope);
  }

  /* ---------- 5. permalink behavior ---------- */
  function onPermalinkClick(e) {
    e.preventDefault();
    var a = e.currentTarget;
    var id = a.getAttribute("href").slice(1);
    history.replaceState(null, "", "#" + id);
    copyText(location.href);
    a.classList.add("is-copied");
    setTimeout(function () { a.classList.remove("is-copied"); }, 1300);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () { fallbackCopy(text); });
    } else {
      fallbackCopy(text);
    }
  }
  function fallbackCopy(text) {
    try {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    } catch (e) {}
  }

  /* ---------- hash routing ---------- */
  function parseHash() {
    var h = location.hash.slice(1);
    if (!h) return null;
    if (h.indexOf("entry-") === 0 && document.getElementById(h)) {
      return { type: "entry", value: h };
    }
    if (/^\d{4}$/.test(h) && years[h]) return { type: "scope", value: h };
    if (/^\d{4}-\d{2}$/.test(h) && years[h.slice(0, 4)] && years[h.slice(0, 4)].months[h]) {
      return { type: "scope", value: h };
    }
    return null;
  }

  function goTo(parsed, scroll) {
    if (parsed && parsed.type === "entry") {
      if (searchInput) searchInput.value = "";
      state.query = "";
      state.scope = "all";       // make sure the linked entry is visible
      applyFilters();
      var el = document.getElementById(parsed.value);
      if (el && scroll) el.scrollIntoView({ block: "start" });
    } else if (parsed && parsed.type === "scope") {
      if (searchInput) searchInput.value = "";
      state.query = "";
      state.scope = parsed.value;
      applyFilters();
    }
  }

  window.addEventListener("hashchange", function () {
    var parsed = parseHash();
    if (parsed) goTo(parsed, true);
  });

  /* ---------- initial state ----------
     permalink  >  archive hash  >  scale-friendly default (latest month) */
  var initial = parseHash();
  if (initial) {
    goTo(initial, true);
  } else {
    state.scope = entries[0].dataset.month || "all"; // newest month
    applyFilters();
  }

  /* ============================================================
     helpers
     ============================================================ */
  function setupTheme() {
    var root = document.documentElement;
    var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

    function effective() {
      var attr = root.getAttribute("data-theme");
      if (attr === "dark" || attr === "light") return attr;
      return mq && mq.matches ? "dark" : "light";
    }

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "theme-toggle";

    function render() {
      var dark = effective() === "dark";
      btn.textContent = dark ? "☀" : "☾";   // sun in dark mode, moon in light
      btn.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
      btn.setAttribute("aria-pressed", dark ? "true" : "false");
    }

    btn.addEventListener("click", function () {
      var next = effective() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
      render();
    });

    if (mq && mq.addEventListener) {
      mq.addEventListener("change", function () {
        if (!root.getAttribute("data-theme")) render();
      });
    }

    render();
    document.body.appendChild(btn);
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }
})();
