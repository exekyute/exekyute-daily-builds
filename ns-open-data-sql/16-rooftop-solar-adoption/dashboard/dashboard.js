/* Reads DATA (from data.js, one row per FSA and year) and derives every figure
   on the page. The derived provincial totals must equal the SQL golden output
   in expected/solar_adoption.csv; see spec.md for the exact numbers. */

(function () {
  "use strict";

  function round2(x) {
    return Math.round(x * 100) / 100;
  }

  function fmtInt(n) {
    return n.toLocaleString("en-CA");
  }

  function fmtKw(n) {
    return round2(n).toLocaleString("en-CA", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  /* ---- Aggregations, all re-derived from DATA ---- */

  var years = [];
  var byYear = {};        // year -> {installs, kw}
  var byFsa = {};         // fsa  -> {installs, kw}
  var byYearFsa = {};     // year -> [{fsa, installs, kw}]

  DATA.forEach(function (r) {
    if (!byYear[r.year]) {
      byYear[r.year] = { installs: 0, kw: 0 };
      years.push(r.year);
      byYearFsa[r.year] = [];
    }
    byYear[r.year].installs += r.installs;
    byYear[r.year].kw += r.installed_kw;
    byYearFsa[r.year].push(r);

    if (!byFsa[r.fsa]) {
      byFsa[r.fsa] = { fsa: r.fsa, installs: 0, kw: 0 };
    }
    byFsa[r.fsa].installs += r.installs;
    byFsa[r.fsa].kw += r.installed_kw;
  });

  years.sort(function (a, b) { return a - b; });

  var cumulative = [];
  var runInstalls = 0;
  var runKw = 0;
  years.forEach(function (y) {
    runInstalls += byYear[y].installs;
    runKw += byYear[y].kw;
    cumulative.push({
      year: y,
      installs: byYear[y].installs,
      kw: round2(byYear[y].kw),
      cumInstalls: runInstalls,
      cumKw: round2(runKw)
    });
  });

  var totalInstalls = runInstalls;
  var totalKw = round2(runKw);

  var fsaList = Object.keys(byFsa).map(function (k) { return byFsa[k]; });
  var topByInstalls = fsaList.slice().sort(function (a, b) {
    return b.installs - a.installs || a.fsa.localeCompare(b.fsa);
  });
  var topByKw = fsaList.slice().sort(function (a, b) {
    return b.kw - a.kw || a.fsa.localeCompare(b.fsa);
  });

  /* ---- Headline cards ---- */

  var leader = topByInstalls[0];
  var headline = document.getElementById("headline");
  headline.innerHTML =
    card("Total installations", fmtInt(totalInstalls),
         years[0] + " to " + years[years.length - 1]) +
    card("Total installed capacity", fmtKw(totalKw) + " kW",
         "about " + fmtKw(totalKw / totalInstalls) + " kW per install") +
    card("Leading region", leader.fsa,
         fmtInt(leader.installs) + " installs, " + fmtKw(leader.kw) + " kW") +
    card("Regions with installs", fmtInt(fsaList.length),
         "forward sortation areas");

  function card(label, value, detail) {
    return '<div class="stat-card"><div class="label">' + label +
      '</div><div class="value">' + value +
      '</div><div class="detail">' + detail + "</div></div>";
  }

  /* ---- Growth chart (SVG built by hand, no libraries) ---- */

  function buildChart() {
    var W = 1000, H = 380;
    var padL = 64, padR = 72, padT = 20, padB = 44;
    var plotW = W - padL - padR;
    var plotH = H - padT - padB;

    var maxYearly = 0, maxCum = 0;
    cumulative.forEach(function (d) {
      if (d.installs > maxYearly) maxYearly = d.installs;
      if (d.cumInstalls > maxCum) maxCum = d.cumInstalls;
    });
    maxYearly = niceCeil(maxYearly);
    maxCum = niceCeil(maxCum);

    var n = cumulative.length;
    var slot = plotW / n;
    var barW = Math.min(slot * 0.62, 70);

    var s = '<svg viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Installs per year and cumulative installs">';

    // horizontal gridlines against the yearly scale
    for (var g = 0; g <= 4; g++) {
      var gy = padT + plotH - (plotH * g / 4);
      var gv = Math.round(maxYearly * g / 4);
      s += '<line x1="' + padL + '" y1="' + gy + '" x2="' + (W - padR) + '" y2="' + gy +
           '" stroke="#e4e0d7" stroke-width="1"/>';
      s += '<text x="' + (padL - 10) + '" y="' + (gy + 4) +
           '" text-anchor="end" font-size="12" fill="#8b97a8">' + fmtInt(gv) + "</text>";
    }
    // right axis labels against the cumulative scale
    for (var g2 = 0; g2 <= 4; g2++) {
      var gy2 = padT + plotH - (plotH * g2 / 4);
      var gv2 = Math.round(maxCum * g2 / 4);
      s += '<text x="' + (W - padR + 10) + '" y="' + (gy2 + 4) +
           '" text-anchor="start" font-size="12" fill="#8b97a8">' + fmtInt(gv2) + "</text>";
    }

    // bars
    cumulative.forEach(function (d, i) {
      var cx = padL + slot * i + slot / 2;
      var bh = plotH * d.installs / maxYearly;
      var bx = cx - barW / 2;
      var by = padT + plotH - bh;
      s += '<rect class="year-bar" data-year="' + d.year + '" x="' + bx + '" y="' + by +
           '" width="' + barW + '" height="' + bh + '" rx="4" fill="#e89b1c">' +
           "<title>" + d.year + ": " + fmtInt(d.installs) + " installs</title></rect>";
      s += '<text x="' + cx + '" y="' + (H - padB + 24) +
           '" text-anchor="middle" font-size="12" fill="#3d4f68">' + d.year + "</text>";
    });

    // cumulative line
    var pts = cumulative.map(function (d, i) {
      var cx = padL + slot * i + slot / 2;
      var cy = padT + plotH - (plotH * d.cumInstalls / maxCum);
      return [cx, cy];
    });
    var path = pts.map(function (p, i) {
      return (i === 0 ? "M" : "L") + p[0].toFixed(1) + " " + p[1].toFixed(1);
    }).join(" ");
    s += '<path d="' + path + '" fill="none" stroke="#1b2a41" stroke-width="2.5"/>';
    pts.forEach(function (p, i) {
      s += '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) +
           '" r="4" fill="#1b2a41"><title>' + cumulative[i].year + ": " +
           fmtInt(cumulative[i].cumInstalls) + ' cumulative</title></circle>';
    });

    s += "</svg>";
    document.getElementById("growth-chart").innerHTML = s;

    var bars = document.querySelectorAll("#growth-chart .year-bar");
    for (var b = 0; b < bars.length; b++) {
      bars[b].addEventListener("click", function () {
        selectYear(parseInt(this.getAttribute("data-year"), 10));
      });
    }
  }

  function niceCeil(v) {
    if (v <= 10) return 10;
    var mag = Math.pow(10, Math.floor(Math.log10(v)));
    var step = mag / 2;
    return Math.ceil(v / step) * step;
  }

  /* ---- Top-FSA ranked lists ---- */

  function renderRankList(el, rows, key, fmt) {
    var max = rows[0][key];
    el.innerHTML = rows.map(function (r, i) {
      var pct = max > 0 ? (100 * r[key] / max) : 0;
      return "<li>" +
        '<span class="fsa">' + (i + 1) + ". " + r.fsa + "</span>" +
        '<span class="bar-track"><span class="bar-fill" style="width:' +
        pct.toFixed(1) + '%"></span></span>' +
        '<span class="num">' + fmt(r[key]) + "</span></li>";
    }).join("");
  }

  renderRankList(document.getElementById("top-installs"),
                 topByInstalls.slice(0, 10), "installs", fmtInt);
  renderRankList(document.getElementById("top-kw"),
                 topByKw.slice(0, 10), "kw", fmtKw);

  /* ---- Year detail ---- */

  var sel = document.getElementById("year-select");
  sel.innerHTML = years.map(function (y) {
    return '<option value="' + y + '">' + y + "</option>";
  }).join("");
  sel.addEventListener("change", function () {
    selectYear(parseInt(sel.value, 10));
  });

  function selectYear(year) {
    sel.value = String(year);

    var bars = document.querySelectorAll("#growth-chart .year-bar");
    for (var b = 0; b < bars.length; b++) {
      bars[b].classList.toggle("selected",
        parseInt(bars[b].getAttribute("data-year"), 10) === year);
    }

    var idx = years.indexOf(year);
    var d = cumulative[idx];
    var prev = idx > 0 ? cumulative[idx - 1] : null;
    var yoy = prev ? d.installs - prev.installs : null;
    var yoyPct = prev && prev.installs > 0
      ? (100 * (d.installs - prev.installs) / prev.installs) : null;

    var cells =
      dcell("Installs in " + year, fmtInt(d.installs)) +
      dcell("kW installed", fmtKw(d.kw)) +
      dcell("Cumulative installs", fmtInt(d.cumInstalls)) +
      dcell("Cumulative kW", fmtKw(d.cumKw)) +
      dcell("Change vs prior year", prev === null ? "first year"
        : (yoy >= 0 ? "+" : "") + fmtInt(yoy) +
          (yoyPct === null ? "" : " (" + (yoyPct >= 0 ? "+" : "") + yoyPct.toFixed(1) + "%)"));
    document.getElementById("year-stats").innerHTML = cells;

    var top5 = byYearFsa[year].slice().sort(function (a, b) {
      return b.installs - a.installs || a.fsa.localeCompare(b.fsa);
    }).slice(0, 5);
    document.getElementById("year-top").innerHTML =
      "<h3>Busiest regions in " + year + "</h3>" +
      '<ol class="rank-list" id="year-top-list"></ol>';
    renderRankList(document.getElementById("year-top-list"), top5, "installs", fmtInt);
  }

  function dcell(label, value) {
    return '<div class="cell"><div class="label">' + label +
      '</div><div class="value">' + value + "</div></div>";
  }

  buildChart();
  selectYear(years[years.length - 1]);

  /* Exposed for verification: run the same derivations from the console. */
  window.SOLAR_DERIVED = {
    totalInstalls: totalInstalls,
    totalKw: totalKw,
    topFsa: leader.fsa,
    yearly: cumulative
  };
})();
