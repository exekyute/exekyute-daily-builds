/* Reads DATA (from data.js, one row per fiscal year, sector, county, and deal
   type) and derives every figure on this page. Money is added up in whole
   cents, so the totals match the SQL golden output in expected/deal_book.csv
   exactly; the numbers they have to hit are written out in spec.md. */

(function () {
  "use strict";

  /* ---- helpers ---- */

  function cents(row) {
    return Math.round(row.contribution * 100);
  }

  function money(c) {
    return "$" + (c / 100).toLocaleString("en-CA", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function moneyShort(c) {
    var d = c / 100;
    if (d >= 1000000) return "$" + (d / 1000000).toFixed(1) + "M";
    if (d >= 1000) return "$" + Math.round(d / 1000) + "k";
    return "$" + d.toFixed(0);
  }

  function count(n) {
    return n.toLocaleString("en-CA");
  }

  function share(partCents, wholeCents) {
    if (!wholeCents) return "0.00";
    return (Math.round(partCents * 10000 / wholeCents) / 100).toFixed(2);
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* ---- group any set of rows by one field, summing cents and deals ---- */

  function groupBy(rows, field) {
    var index = {};
    var out = [];
    rows.forEach(function (r) {
      var k = r[field];
      if (!index[k]) {
        index[k] = { name: k, cents: 0, deals: 0, geographic: true };
        out.push(index[k]);
      }
      index[k].cents += cents(r);
      index[k].deals += r.deals;
      if (field === "nsbi_county" && r.county_is_geographic === 0) {
        index[k].geographic = false;
      }
    });
    out.sort(function (a, b) {
      return b.cents - a.cents || a.name.localeCompare(b.name);
    });
    return out;
  }

  /* ---- the year axis, always the full window ---- */

  var yearIndex = {};
  var years = [];
  DATA.forEach(function (r) {
    if (!yearIndex[r.fiscal_year]) {
      yearIndex[r.fiscal_year] = {
        year: r.fiscal_year,
        start: r.fiscal_year_start,
        cents: 0,
        deals: 0,
        rows: []
      };
      years.push(yearIndex[r.fiscal_year]);
    }
    var y = yearIndex[r.fiscal_year];
    y.cents += cents(r);
    y.deals += r.deals;
    y.rows.push(r);
  });
  years.sort(function (a, b) { return a.start - b.start; });

  var ALL = "all";
  var selected = ALL;

  function activeRows() {
    return selected === ALL ? DATA : yearIndex[selected].rows;
  }

  /* ---- headline cards ---- */

  function renderHeadline() {
    var rows = activeRows();
    var totalCents = 0;
    var deals = 0;
    rows.forEach(function (r) {
      totalCents += cents(r);
      deals += r.deals;
    });

    var topSector = groupBy(rows, "nsbi_sector")[0];
    var topCounty = groupBy(rows, "nsbi_county")[0];

    var window_ = selected === ALL
      ? years[0].year + " to " + years[years.length - 1].year
      : selected;

    document.getElementById("headline").innerHTML =
      card("Total contribution", money(totalCents), window_) +
      card("Deals recorded", count(deals),
           "about " + money(Math.round(totalCents / deals)) + " per deal") +
      card("Leading sector", topSector.name,
           money(topSector.cents) + ", " + share(topSector.cents, totalCents) +
           "% of the total") +
      card("Leading county", topCounty.name,
           money(topCounty.cents) + ", " + share(topCounty.cents, totalCents) +
           "% of the total");

    document.getElementById("filter-note").textContent =
      selected === ALL
        ? "Showing all six fiscal years"
        : "Showing " + selected + " only";
  }

  function card(label, value, detail) {
    return '<div class="stat-card"><div class="label">' + escapeHtml(label) +
      '</div><div class="value">' + escapeHtml(value) +
      '</div><div class="detail">' + escapeHtml(detail) + "</div></div>";
  }

  /* ---- year filter buttons ---- */

  function renderButtons() {
    var html = '<button data-year="' + ALL + '">All years</button>';
    years.forEach(function (y) {
      html += '<button data-year="' + y.year + '">' + y.year + "</button>";
    });
    var host = document.getElementById("year-buttons");
    host.innerHTML = html;
    var buttons = host.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function () {
        select(this.getAttribute("data-year"));
      });
    }
  }

  function paintButtons() {
    var buttons = document.querySelectorAll("#year-buttons button");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].classList.toggle("on",
        buttons[i].getAttribute("data-year") === selected);
    }
  }

  /* ---- contribution by fiscal year ---- */

  function renderYearChart() {
    var W = 1040, H = 340;
    var padL = 92, padR = 24, padT = 16, padB = 52;
    var plotW = W - padL - padR;
    var plotH = H - padT - padB;

    var max = 0;
    years.forEach(function (y) { if (y.cents > max) max = y.cents; });
    var top = niceCeil(max);

    var slot = plotW / years.length;
    var barW = Math.min(slot * 0.56, 92);

    var s = '<svg viewBox="0 0 ' + W + " " + H +
      '" xmlns="http://www.w3.org/2000/svg" role="img" ' +
      'aria-label="Total contribution by fiscal year">';

    for (var g = 0; g <= 4; g++) {
      var gy = padT + plotH - (plotH * g / 4);
      s += '<line x1="' + padL + '" y1="' + gy + '" x2="' + (W - padR) +
           '" y2="' + gy + '" stroke="#e2e2ec" stroke-width="1"/>';
      s += '<text x="' + (padL - 14) + '" y="' + (gy + 4) +
           '" text-anchor="end" font-size="12" fill="#8688a8">' +
           moneyShort(top * g / 4) + "</text>";
    }

    years.forEach(function (y, i) {
      var cx = padL + slot * i + slot / 2;
      var bh = plotH * y.cents / top;
      var by = padT + plotH - bh;
      s += '<rect class="year-bar" data-year="' + y.year + '" x="' +
           (cx - barW / 2) + '" y="' + by + '" width="' + barW +
           '" height="' + bh + '" rx="5" fill="#0f8b8d"><title>' + y.year +
           ": " + money(y.cents) + "</title></rect>";
      s += '<text x="' + cx + '" y="' + (by - 10) +
           '" text-anchor="middle" font-size="12.5" font-weight="600" ' +
           'fill="#232447">' + moneyShort(y.cents) + "</text>";
      s += '<text x="' + cx + '" y="' + (H - padB + 26) +
           '" text-anchor="middle" font-size="12.5" fill="#4a4c76">' +
           y.year + "</text>";
    });

    s += "</svg>";
    document.getElementById("year-chart").innerHTML = s;

    var bars = document.querySelectorAll("#year-chart .year-bar");
    for (var b = 0; b < bars.length; b++) {
      bars[b].addEventListener("click", function () {
        var y = this.getAttribute("data-year");
        select(y === selected ? ALL : y);
      });
    }
  }

  function paintYearChart() {
    var bars = document.querySelectorAll("#year-chart .year-bar");
    for (var i = 0; i < bars.length; i++) {
      bars[i].classList.toggle("on",
        bars[i].getAttribute("data-year") === selected);
    }
  }

  function niceCeil(v) {
    if (v <= 10) return 10;
    var mag = Math.pow(10, Math.floor(Math.log10(v)));
    var step = mag / 2;
    return Math.ceil(v / step) * step;
  }

  /* ---- ranked lists ---- */

  var LIST_ROWS = 12;

  function renderRanked(elementId, field) {
    var rows = activeRows();
    var totalCents = 0;
    rows.forEach(function (r) { totalCents += cents(r); });

    var groups = groupBy(rows, field);
    var shown = groups.slice(0, LIST_ROWS);
    var max = shown.length ? shown[0].cents : 0;
    var el = document.getElementById(elementId);

    if (!shown.length) {
      el.innerHTML = '<li class="empty">No rows for this year.</li>';
      return;
    }

    el.innerHTML = shown.map(function (g) {
      var width = max > 0 ? (100 * g.cents / max) : 0;
      var tag = g.geographic === false
        ? '<span class="tag">not a county</span>' : "";
      return "<li>" +
        '<span class="name">' + escapeHtml(g.name) + tag + "</span>" +
        '<span class="num">' + money(g.cents) +
        '<span class="pct">' + share(g.cents, totalCents) + "% of total, " +
        count(g.deals) + " deals</span></span>" +
        '<span class="bar-track"><span class="bar-fill" style="width:' +
        width.toFixed(2) + '%"></span></span>' +
        "</li>";
    }).join("");

    if (groups.length > shown.length) {
      var restCents = 0;
      var restDeals = 0;
      groups.slice(LIST_ROWS).forEach(function (g) {
        restCents += g.cents;
        restDeals += g.deals;
      });
      el.innerHTML += '<li class="empty">' + (groups.length - LIST_ROWS) +
        " more, " + money(restCents) + " across " + count(restDeals) +
        " deals</li>";
    }
  }

  /* ---- deal-type mix by fiscal year ---- */

  function renderMix() {
    var allCents = 0;
    DATA.forEach(function (r) { allCents += cents(r); });
    var lead = groupBy(DATA, "deal_type")[0];
    document.getElementById("mix-lead").innerHTML =
      "Across all six years the largest single deal-type label is <strong>" +
      escapeHtml(lead.name) + "</strong>, worth " + money(lead.cents) +
      " over " + count(lead.deals) + " deals, or " +
      share(lead.cents, allCents) + " percent of every dollar in the file.";

    document.getElementById("mix-grid").innerHTML = years.map(function (y) {
      var types = groupBy(y.rows, "deal_type");
      var maxShare = types.length ? types[0].cents : 0;
      var rows = types.map(function (t) {
        var width = maxShare > 0 ? (100 * t.cents / maxShare) : 0;
        return '<div class="mix-row"><div class="top"><span>' +
          escapeHtml(t.name) + '</span><span class="share">' +
          share(t.cents, y.cents) + "% &middot; " + moneyShort(t.cents) +
          '</span></div><div class="track"><span class="fill" style="width:' +
          width.toFixed(2) + '%"></span></div></div>';
      }).join("");
      return '<div class="mix-card' + (y.year === selected ? " on" : "") +
        '"><h3>' + y.year + '</h3><div class="total">' + money(y.cents) +
        " across " + count(y.deals) + " deals</div>" + rows + "</div>";
    }).join("");
  }

  /* ---- counted classes ---- */

  function renderClasses() {
    var deals = 0, funded = 0, blank = 0, zero = 0, mappable = 0, inBounds = 0;
    var nonCountyDeals = 0, nonCountyCents = 0;
    activeRows().forEach(function (r) {
      deals += r.deals;
      funded += r.funded_deals;
      blank += r.blank_deals;
      zero += r.zero_deals;
      mappable += r.mappable_deals;
      inBounds += r.in_bounds_deals;
      if (r.county_is_geographic === 0) {
        nonCountyDeals += r.deals;
        nonCountyCents += cents(r);
      }
    });

    document.getElementById("classes").innerHTML =
      cell("Deals with a contribution value", count(funded),
           "out of " + count(deals) + " deals") +
      cell("Blank contributions", count(blank),
           "left out of every sum, never read as zero") +
      cell("Contributions of exactly zero", count(zero),
           "kept in the counts, worth nothing") +
      cell("County label is not a county", count(nonCountyDeals),
           money(nonCountyCents) + ", still in the totals") +
      cell("Deals with map coordinates", count(mappable),
           count(deals - mappable) + " without a coordinate pair") +
      cell("Coordinates inside Nova Scotia", count(inBounds),
           count(mappable - inBounds) + " point somewhere else and are flagged");
  }

  function cell(label, value, note) {
    return '<div class="cell"><div class="label">' + escapeHtml(label) +
      '</div><div class="value">' + escapeHtml(value) +
      '</div><div class="note">' + escapeHtml(note) + "</div></div>";
  }

  /* ---- wiring ---- */

  function select(year) {
    selected = year;
    paintButtons();
    paintYearChart();
    renderHeadline();
    renderRanked("sector-list", "nsbi_sector");
    renderRanked("county-list", "nsbi_county");
    renderMix();
    renderClasses();
  }

  renderButtons();
  renderYearChart();
  select(ALL);

  /* Exposed so the same derivations can be checked from the console, or read
     back and compared against expected/deal_book.csv. */
  window.DEAL_BOOK_DERIVED = function () {
    var totalCents = 0, deals = 0;
    DATA.forEach(function (r) { totalCents += cents(r); deals += r.deals; });
    return {
      totalContribution: (totalCents / 100).toFixed(2),
      deals: deals,
      sectors: groupBy(DATA, "nsbi_sector"),
      counties: groupBy(DATA, "nsbi_county"),
      dealTypes: groupBy(DATA, "deal_type"),
      byYear: years.map(function (y) {
        return { year: y.year, contribution: (y.cents / 100).toFixed(2) };
      })
    };
  };
})();
