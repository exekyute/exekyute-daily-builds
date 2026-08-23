/* Every figure on the page is derived here from the DATA rows in data.js.
   Nothing is written in by hand, so the totals shown are the same totals the
   SQL pipeline proves in expected/ed_closures.csv.

   Hours are reported to one decimal place, so all arithmetic runs on tenths of
   an hour as integers. Summing 0.1 values as floats drifts; summing them as
   integers does not, and the page has to tie to the cent-equivalent. */

(function () {
  "use strict";

  var ZONE_SHADES = ["#14454e", "#1f6f6a", "#3d938c", "#74b6b0", "#b3d5d1"];

  /* ---------- exact arithmetic and formatting ---------- */

  function tenths(hours) {
    return Math.round(hours * 10);
  }

  function fmtHours(t) {
    var neg = t < 0;
    var abs = Math.abs(t);
    var whole = Math.floor(abs / 10);
    var frac = abs % 10;
    var grouped = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return (neg ? "-" : "") + grouped + "." + frac;
  }

  function fmtInt(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  /* Temporary share uses the reported total as the denominator, guarded so the
     denominator is above zero. That guard is the same rule the SQL applies. */
  function sharePct(tempT, totalT) {
    if (totalT <= 0) {
      return null;
    }
    return Math.round((100 * tempT / totalT) * 100) / 100;
  }

  function fmtPct(p) {
    return p === null ? "n/a" : p.toFixed(2) + "%";
  }

  function zoneLabel(code) {
    return /^\d+$/.test(code) ? "Zone " + code : code;
  }

  /* ---------- aggregation ---------- */

  function blank() {
    return { total: 0, temp: 0, sched: 0, siteYears: 0, zeroYears: 0 };
  }

  function add(acc, row) {
    acc.total += tenths(row.total_hours);
    acc.temp += tenths(row.temporary_hours);
    acc.sched += tenths(row.scheduled_hours);
    acc.siteYears += 1;
    if (tenths(row.total_hours) === 0) {
      acc.zeroYears += 1;
    }
    return acc;
  }

  function groupBy(rows, keyOf) {
    var map = {};
    for (var i = 0; i < rows.length; i++) {
      var key = keyOf(rows[i]);
      if (!map[key]) {
        map[key] = blank();
      }
      add(map[key], rows[i]);
    }
    return map;
  }

  function totalsOf(rows) {
    var acc = blank();
    for (var i = 0; i < rows.length; i++) {
      add(acc, rows[i]);
    }
    return acc;
  }

  function distinctSorted(rows, field) {
    var seen = {};
    var out = [];
    for (var i = 0; i < rows.length; i++) {
      var v = rows[i][field];
      if (!seen[v]) {
        seen[v] = true;
        out.push(v);
      }
    }
    out.sort();
    return out;
  }

  /* Ranked breakdown: dollars-style sort, highest total first, ties broken by
     the label so the order never depends on insertion order. */
  function ranked(map) {
    var out = [];
    for (var key in map) {
      if (Object.prototype.hasOwnProperty.call(map, key)) {
        out.push({ key: key, agg: map[key] });
      }
    }
    out.sort(function (a, b) {
      if (b.agg.total !== a.agg.total) {
        return b.agg.total - a.agg.total;
      }
      return a.key < b.key ? -1 : a.key > b.key ? 1 : 0;
    });
    return out;
  }

  /* ---------- headline cards ---------- */

  function renderHeadline(rows) {
    var all = totalsOf(rows);
    var sites = distinctSorted(rows, "site").length;
    var years = distinctSorted(rows, "fiscal_year").length;

    var cards = [
      {
        label: "Total closure hours",
        value: fmtHours(all.total),
        detail: fmtInt(years) + " fiscal years, " + fmtInt(sites) + " sites"
      },
      {
        label: "Temporary closure hours",
        value: fmtHours(all.temp),
        detail: fmtPct(sharePct(all.temp, all.total)) + " of all closure hours"
      },
      {
        label: "Scheduled closure hours",
        value: fmtHours(all.sched),
        detail: fmtPct(sharePct(all.sched, all.total)) + " of all closure hours",
        ink: true
      },
      {
        label: "Site-years with no closures",
        value: fmtInt(all.zeroYears),
        detail: "of " + fmtInt(all.siteYears) + " site-years reported",
        ink: true
      }
    ];

    var html = "";
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      html += '<div class="stat-card' + (c.ink ? " ink-top" : "") + '">' +
        '<div class="label">' + c.label + "</div>" +
        '<div class="value">' + c.value + "</div>" +
        '<div class="detail">' + c.detail + "</div></div>";
    }
    document.getElementById("headline").innerHTML = html;
  }

  /* ---------- stacked chart: zone by fiscal year ---------- */

  function niceScale(maxHours) {
    if (maxHours <= 0) {
      return { step: 1, top: 1 };
    }
    var raw = maxHours / 4;
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var norm = raw / mag;
    var step;
    if (norm <= 1) {
      step = 1;
    } else if (norm <= 2) {
      step = 2;
    } else if (norm <= 2.5) {
      step = 2.5;
    } else if (norm <= 5) {
      step = 5;
    } else {
      step = 10;
    }
    step = step * mag;
    return { step: step, top: Math.ceil(maxHours / step) * step };
  }

  function svgEl(name, attrs) {
    var el = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (var k in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, k)) {
        el.setAttribute(k, attrs[k]);
      }
    }
    return el;
  }

  function renderZoneChart(rows, zones, shadeOf) {
    var years = distinctSorted(rows, "fiscal_year");
    var cell = groupBy(rows, function (r) {
      return r.fiscal_year + "|" + r.zone;
    });
    var perYear = groupBy(rows, function (r) {
      return r.fiscal_year;
    });

    var maxYear = 0;
    for (var y = 0; y < years.length; y++) {
      if (perYear[years[y]].total > maxYear) {
        maxYear = perYear[years[y]].total;
      }
    }

    var scale = niceScale(maxYear / 10);
    var topT = tenths(scale.top);

    var W = 980, H = 420;
    var mL = 78, mR = 24, mT = 18, mB = 58;
    var plotW = W - mL - mR;
    var plotH = H - mT - mB;
    var band = plotW / years.length;
    var barW = Math.min(52, band * 0.62);

    var svg = svgEl("svg", {
      viewBox: "0 0 " + W + " " + H,
      role: "img",
      "aria-label": "Closure hours by zone for each fiscal year"
    });

    var gridCount = Math.round(scale.top / scale.step);
    for (var g = 0; g <= gridCount; g++) {
      var vHours = scale.step * g;
      var yPos = mT + plotH - (tenths(vHours) / topT) * plotH;
      svg.appendChild(svgEl("line", {
        x1: mL, x2: mL + plotW, y1: yPos, y2: yPos, "class": "grid-line"
      }));
      var lbl = svgEl("text", {
        x: mL - 12, y: yPos + 4, "text-anchor": "end", "class": "axis-text"
      });
      lbl.textContent = fmtInt(Math.round(vHours));
      svg.appendChild(lbl);
    }

    for (var i = 0; i < years.length; i++) {
      var year = years[i];
      var x = mL + band * i + (band - barW) / 2;
      var stackT = 0;
      for (var z = 0; z < zones.length; z++) {
        var agg = cell[year + "|" + zones[z]];
        if (!agg || agg.total === 0) {
          continue;
        }
        var segH = (agg.total / topT) * plotH;
        var yTop = mT + plotH - ((stackT + agg.total) / topT) * plotH;
        var rect = svgEl("rect", {
          x: x, y: yTop, width: barW, height: segH,
          fill: shadeOf[zones[z]], "class": "seg"
        });
        var title = svgEl("title", {});
        title.textContent = zoneLabel(zones[z]) + ", " + year + ": " +
          fmtHours(agg.total) + " hours";
        rect.appendChild(title);
        svg.appendChild(rect);
        stackT += agg.total;
      }
      var yearLbl = svgEl("text", {
        x: x + barW / 2, y: mT + plotH + 24,
        "text-anchor": "middle", "class": "axis-text year"
      });
      yearLbl.textContent = year;
      svg.appendChild(yearLbl);

      var totalLbl = svgEl("text", {
        x: x + barW / 2, y: mT + plotH + 44,
        "text-anchor": "middle", "class": "axis-text"
      });
      totalLbl.textContent = fmtInt(Math.round(perYear[year].total / 10));
      svg.appendChild(totalLbl);
    }

    svg.appendChild(svgEl("line", {
      x1: mL, x2: mL + plotW, y1: mT + plotH, y2: mT + plotH, "class": "grid-line"
    }));

    var host = document.getElementById("zone-chart");
    host.innerHTML = "";
    host.appendChild(svg);
  }

  function renderZoneLegend(zones, shadeOf) {
    var html = "";
    for (var i = 0; i < zones.length; i++) {
      html += '<span class="key"><span class="swatch" style="background:' +
        shadeOf[zones[i]] + '"></span>' + zoneLabel(zones[i]) + "</span>";
    }
    document.getElementById("zone-legend").innerHTML = html;
  }

  /* ---------- temporary and scheduled split ---------- */

  function splitBarHtml(agg) {
    if (agg.total <= 0) {
      return '<div class="split-bar"></div>';
    }
    var tempPct = 100 * agg.temp / agg.total;
    return '<div class="split-bar">' +
      '<div class="part temp" style="width:' + tempPct + '%"></div>' +
      '<div class="part sched" style="width:' + (100 - tempPct) + '%"></div>' +
      "</div>";
  }

  function renderOverallSplit(rows) {
    var all = totalsOf(rows);
    document.getElementById("split-overall").innerHTML =
      splitBarHtml(all) +
      '<div class="split-caption"><span>Temporary ' + fmtHours(all.temp) +
      " h, " + fmtPct(sharePct(all.temp, all.total)) + "</span>" +
      "<span>Scheduled " + fmtHours(all.sched) + " h, " +
      fmtPct(sharePct(all.sched, all.total)) + "</span></div>";
  }

  function renderSplitList(hostId, entries, nameOf) {
    var html = "";
    for (var i = 0; i < entries.length; i++) {
      var agg = entries[i].agg;
      var empty = agg.total <= 0;
      html += '<div class="row' + (empty ? " empty" : "") + '">' +
        '<div class="row-head"><span class="name">' + nameOf(entries[i].key) +
        '</span><span class="figure">' + fmtHours(agg.total) + " h, " +
        fmtPct(sharePct(agg.temp, agg.total)) + " temporary</span></div>" +
        splitBarHtml(agg) + "</div>";
    }
    document.getElementById(hostId).innerHTML = html;
  }

  /* ---------- ranked site table ---------- */

  function renderSiteTable(rows) {
    var zonePick = document.getElementById("zone-filter").value;
    var yearPick = document.getElementById("year-filter").value;

    var kept = [];
    for (var i = 0; i < rows.length; i++) {
      if (zonePick !== "*" && rows[i].zone !== zonePick) {
        continue;
      }
      if (yearPick !== "*" && rows[i].fiscal_year !== yearPick) {
        continue;
      }
      kept.push(rows[i]);
    }

    var body = document.getElementById("site-rows");
    var note = document.getElementById("filter-note");

    if (kept.length === 0) {
      body.innerHTML = '<tr><td colspan="9" class="empty-note">' +
        "No site-years match that combination.</td></tr>";
      note.textContent = "";
      return;
    }

    /* The facility type shown is the one reported in the latest fiscal year
       still in the filter, which with no filter is the site's most recent
       reported type, the same rule the SQL uses. */
    var latestType = {};
    var latestYear = {};
    var zoneOf = {};
    for (var j = 0; j < kept.length; j++) {
      var r = kept[j];
      zoneOf[r.site] = r.zone;
      if (!(r.site in latestYear) || r.fiscal_year_start > latestYear[r.site]) {
        latestYear[r.site] = r.fiscal_year_start;
        latestType[r.site] = r.facility_type;
      }
    }

    var entries = ranked(groupBy(kept, function (row) {
      return row.site;
    }));
    var all = totalsOf(kept);

    var html = "";
    for (var k = 0; k < entries.length; k++) {
      var site = entries[k].key;
      var agg = entries[k].agg;
      var zero = agg.total === 0;
      var width = all.total > 0 ? (100 * agg.total / all.total) : 0;
      html += '<tr class="' + (zero ? "zero" : "") + '">' +
        '<td class="num">' + (k + 1) + "</td>" +
        '<td class="site">' + escapeHtml(site) + "</td>" +
        "<td>" + zoneLabel(zoneOf[site]) + "</td>" +
        '<td><span class="tag">' + latestType[site] + "</span></td>" +
        '<td class="num">' + fmtHours(agg.total) + "</td>" +
        '<td class="num">' + fmtHours(agg.temp) + "</td>" +
        '<td class="num">' + fmtHours(agg.sched) + "</td>" +
        '<td class="num">' + fmtPct(sharePct(agg.temp, agg.total)) + "</td>" +
        '<td><div class="row-bar"><div class="fill" style="width:' +
        width + '%"></div></div></td></tr>';
    }
    body.innerHTML = html;

    note.textContent = fmtInt(entries.length) +
      (entries.length === 1 ? " site, " : " sites, ") +
      fmtHours(all.total) + " hours, " + fmtInt(all.zeroYears) + " of " +
      fmtInt(all.siteYears) + " site-years with no closures";
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function fillSelect(id, values, allLabel, labelOf) {
    var sel = document.getElementById(id);
    var html = '<option value="*">' + allLabel + "</option>";
    for (var i = 0; i < values.length; i++) {
      html += '<option value="' + values[i] + '">' +
        labelOf(values[i]) + "</option>";
    }
    sel.innerHTML = html;
  }

  /* ---------- boot ---------- */

  function main() {
    var rows = DATA;
    var zones = distinctSorted(rows, "zone");
    var shadeOf = {};
    for (var i = 0; i < zones.length; i++) {
      shadeOf[zones[i]] = ZONE_SHADES[i % ZONE_SHADES.length];
    }

    renderHeadline(rows);
    renderZoneLegend(zones, shadeOf);
    renderZoneChart(rows, zones, shadeOf);
    renderOverallSplit(rows);
    renderSplitList("split-by-zone",
      ranked(groupBy(rows, function (r) { return r.zone; })), zoneLabel);
    renderSplitList("type-list",
      ranked(groupBy(rows, function (r) { return r.facility_type; })),
      function (t) { return t; });

    fillSelect("zone-filter", zones, "All zones", zoneLabel);
    fillSelect("year-filter", distinctSorted(rows, "fiscal_year"),
      "All years", function (y) { return y; });

    document.getElementById("zone-filter").addEventListener("change",
      function () { renderSiteTable(rows); });
    document.getElementById("year-filter").addEventListener("change",
      function () { renderSiteTable(rows); });

    renderSiteTable(rows);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }
})();
