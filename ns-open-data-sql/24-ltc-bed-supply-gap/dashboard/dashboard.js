/* Reads DATA (from data.js, one row per facility per bed type) and derives every
   figure on the page. The derived totals must equal the SQL golden output in
   expected/ltc_bed_supply.csv; see spec.md for the exact numbers.

   The bed definition, applied here exactly as in sql/03_analysis.sql:
       total beds = nursing beds + residential beds   (the is_core_bed = 1 rows)
   Respite bed types are summed and shown, never folded into that total. */

(function () {
  "use strict";

  var CORE_TYPES = ["nursing", "residential"];
  var BED_LABELS = {
    nursing: "Nursing home beds",
    residential: "Residential care beds",
    nursing_respite: "Nursing home respite beds",
    residential_respite: "Residential care respite beds"
  };
  var BED_ORDER = ["nursing", "residential", "nursing_respite", "residential_respite"];
  var SEA_YES = "Y";

  function fmtInt(n) {
    return n.toLocaleString("en-CA");
  }

  function fmt2(n) {
    return n.toLocaleString("en-CA", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function round2(x) {
    return Math.round(x * 100) / 100;
  }

  /* The continuous median, matching DuckDB's MEDIAN / QUANTILE_CONT(x, 0.5):
     with an even count it averages the two middle values. */
  function medianCont(values) {
    var v = values.slice().sort(function (a, b) { return a - b; });
    if (v.length === 0) return 0;
    var pos = (v.length - 1) / 2;
    var lo = Math.floor(pos);
    var hi = Math.ceil(pos);
    return lo === hi ? v[lo] : v[lo] + (v[hi] - v[lo]) * (pos - lo);
  }

  /* ---- Fold the long rows back into facilities ---- */

  var facilityById = {};
  var facilityList = [];
  var bedTypeTotals = {};
  var bedTypeFacilities = {};

  BED_ORDER.forEach(function (t) {
    bedTypeTotals[t] = 0;
    bedTypeFacilities[t] = 0;
  });

  DATA.forEach(function (r) {
    var f = facilityById[r.facility_id];
    if (!f) {
      f = {
        facility_id: r.facility_id,
        facility_name: r.facility_name,
        town: r.town,
        zone: r.zone,
        facility_type: r.facility_type,
        sea_participating: r.sea_participating,
        beds: {},
        total_beds: 0,
        respite_beds: 0
      };
      BED_ORDER.forEach(function (t) { f.beds[t] = 0; });
      facilityById[r.facility_id] = f;
      facilityList.push(f);
    }
    f.beds[r.bed_type] += r.beds;
    if (r.is_core_bed === 1) {
      f.total_beds += r.beds;
    } else {
      f.respite_beds += r.beds;
    }

    bedTypeTotals[r.bed_type] += r.beds;
    if (r.beds > 0) bedTypeFacilities[r.bed_type] += 1;
  });

  var totalBeds = CORE_TYPES.reduce(function (a, t) { return a + bedTypeTotals[t]; }, 0);
  var facilityCount = facilityList.length;
  var seaCount = facilityList.filter(function (f) {
    return f.sea_participating === SEA_YES;
  }).length;
  var allTotals = facilityList.map(function (f) { return f.total_beds; });
  var avgBeds = round2(totalBeds / facilityCount);
  var medBeds = round2(medianCont(allTotals));

  var largest = facilityList.slice().sort(function (a, b) {
    return b.total_beds - a.total_beds || a.facility_id.localeCompare(b.facility_id);
  })[0];

  /* ---- Zone rollup ---- */

  var zoneMap = {};
  facilityList.forEach(function (f) {
    var z = zoneMap[f.zone];
    if (!z) {
      z = { zone: f.zone, facilities: 0, total_beds: 0, totals: [] };
      BED_ORDER.forEach(function (t) { z[t] = 0; });
      zoneMap[f.zone] = z;
    }
    z.facilities += 1;
    z.total_beds += f.total_beds;
    z.totals.push(f.total_beds);
    BED_ORDER.forEach(function (t) { z[t] += f.beds[t]; });
  });

  var zones = Object.keys(zoneMap).map(function (k) { return zoneMap[k]; });
  zones.forEach(function (z) {
    z.share_pct = round2(100 * z.total_beds / totalBeds);
    z.avg_beds = round2(z.total_beds / z.facilities);
    z.median_beds = round2(medianCont(z.totals));
  });
  zones.sort(function (a, b) {
    return b.total_beds - a.total_beds || a.zone.localeCompare(b.zone);
  });

  /* ---- Headline cards ---- */

  function card(label, value, detail) {
    return '<div class="stat-card"><div class="label">' + label +
      '</div><div class="value">' + value +
      '</div><div class="detail">' + detail + "</div></div>";
  }

  document.getElementById("headline").innerHTML =
    card("Total beds", fmtInt(totalBeds),
         fmtInt(bedTypeTotals.nursing) + " nursing, " +
         fmtInt(bedTypeTotals.residential) + " residential care") +
    card("Facilities", fmtInt(facilityCount),
         zones.length + " zones, " + fmtInt(seaCount) +
         " in single entry access") +
    card("Beds per facility", fmt2(avgBeds) + " average",
         fmt2(medBeds) + " median") +
    card("Largest facility", fmtInt(largest.total_beds) + " beds",
         largest.facility_name + ", " + largest.town) +
    card("Respite beds", fmtInt(bedTypeTotals.nursing_respite +
         bedTypeTotals.residential_respite),
         "reported separately, outside the total");

  /* ---- Zone bars and zone table ---- */

  var maxZoneBeds = zones.reduce(function (m, z) {
    return Math.max(m, z.total_beds);
  }, 0);

  document.getElementById("zone-bars").innerHTML = zones.map(function (z) {
    var span = 100 * z.total_beds / maxZoneBeds;
    var nursingPct = 100 * z.nursing / z.total_beds;
    var residentialPct = 100 - nursingPct;
    return '<div class="zone-row">' +
      '<span class="name">' + z.zone + "</span>" +
      '<span class="track" style="width:' + span.toFixed(2) + '%">' +
        '<span class="seg nursing" style="width:' + nursingPct.toFixed(2) + '%" ' +
        'title="' + fmtInt(z.nursing) + ' nursing home beds"></span>' +
        '<span class="seg residential" style="width:' + residentialPct.toFixed(2) + '%" ' +
        'title="' + fmtInt(z.residential) + ' residential care beds"></span>' +
      "</span>" +
      '<span class="num">' + fmtInt(z.total_beds) + " beds</span>" +
      "</div>";
  }).join("");

  document.getElementById("zone-table").innerHTML =
    "<thead><tr>" +
      '<th class="text">Zone</th><th>Facilities</th><th>Nursing</th>' +
      "<th>Residential</th><th>Total beds</th><th>Share</th>" +
      "<th>Average</th><th>Median</th><th>Respite</th>" +
    "</tr></thead><tbody>" +
    zones.map(function (z) {
      return "<tr>" +
        '<td class="text">' + z.zone + "</td>" +
        "<td>" + fmtInt(z.facilities) + "</td>" +
        "<td>" + fmtInt(z.nursing) + "</td>" +
        "<td>" + fmtInt(z.residential) + "</td>" +
        "<td>" + fmtInt(z.total_beds) + "</td>" +
        "<td>" + fmt2(z.share_pct) + "%</td>" +
        "<td>" + fmt2(z.avg_beds) + "</td>" +
        "<td>" + fmt2(z.median_beds) + "</td>" +
        "<td>" + fmtInt(z.nursing_respite + z.residential_respite) + "</td>" +
      "</tr>";
    }).join("") +
    "</tbody><tfoot><tr>" +
      '<td class="text">All zones</td>' +
      "<td>" + fmtInt(facilityCount) + "</td>" +
      "<td>" + fmtInt(bedTypeTotals.nursing) + "</td>" +
      "<td>" + fmtInt(bedTypeTotals.residential) + "</td>" +
      "<td>" + fmtInt(totalBeds) + "</td>" +
      "<td>100.00%</td>" +
      "<td>" + fmt2(avgBeds) + "</td>" +
      "<td>" + fmt2(medBeds) + "</td>" +
      "<td>" + fmtInt(bedTypeTotals.nursing_respite +
                      bedTypeTotals.residential_respite) + "</td>" +
    "</tr></tfoot>";

  /* ---- Nursing versus residential split ---- */

  var nursingShare = round2(100 * bedTypeTotals.nursing / totalBeds);
  var residentialShare = round2(100 * bedTypeTotals.residential / totalBeds);

  document.getElementById("split-bar").innerHTML =
    '<div class="split-track">' +
      '<span class="seg nursing" style="width:' + nursingShare + '%">' +
        fmtInt(bedTypeTotals.nursing) + " nursing (" + fmt2(nursingShare) + "%)</span>" +
      '<span class="seg residential" style="width:' + residentialShare + '%">' +
        fmt2(residentialShare) + "%</span>" +
    "</div>";

  function splitCell(label, value, note) {
    return '<div class="cell"><div class="label">' + label +
      '</div><div class="value">' + value +
      '</div><div class="note">' + note + "</div></div>";
  }

  document.getElementById("split-cards").innerHTML =
    splitCell("Nursing home beds", fmtInt(bedTypeTotals.nursing),
              fmt2(nursingShare) + "% of total beds, " +
              fmtInt(bedTypeFacilities.nursing) + " facilities") +
    splitCell("Residential care beds", fmtInt(bedTypeTotals.residential),
              fmt2(residentialShare) + "% of total beds, " +
              fmtInt(bedTypeFacilities.residential) + " facilities") +
    splitCell("Total beds", fmtInt(totalBeds),
              "the two above, and nothing else");

  document.getElementById("bed-type-table").innerHTML =
    "<thead><tr>" +
      '<th class="text">Bed type</th><th>Beds</th>' +
      "<th>Facilities with any</th><th>Share of total beds</th>" +
    "</tr></thead><tbody>" +
    BED_ORDER.map(function (t) {
      var core = CORE_TYPES.indexOf(t) >= 0;
      var share = core
        ? fmt2(round2(100 * bedTypeTotals[t] / totalBeds)) + "%"
        : "excluded from total";
      return '<tr class="' + (core ? "" : "excluded") + '">' +
        '<td class="text">' + BED_LABELS[t] + "</td>" +
        "<td>" + fmtInt(bedTypeTotals[t]) + "</td>" +
        "<td>" + fmtInt(bedTypeFacilities[t]) + "</td>" +
        "<td>" + share + "</td>" +
      "</tr>";
    }).join("") +
    "</tbody>";

  /* ---- Sortable facility table ---- */

  var COLUMNS = [
    { key: "facility_name", label: "Facility", text: true },
    { key: "town", label: "Town", text: true },
    { key: "zone", label: "Zone", text: true },
    { key: "facility_type", label: "Type", text: true },
    { key: "nursing", label: "Nursing", text: false },
    { key: "residential", label: "Residential", text: false },
    { key: "total_beds", label: "Total beds", text: false },
    { key: "respite_beds", label: "Respite", text: false }
  ];

  var rows = facilityList.map(function (f) {
    return {
      facility_id: f.facility_id,
      facility_name: f.facility_name,
      town: f.town,
      zone: f.zone,
      facility_type: f.facility_type,
      nursing: f.beds.nursing,
      residential: f.beds.residential,
      total_beds: f.total_beds,
      respite_beds: f.respite_beds
    };
  });

  var sortKey = "total_beds";
  var sortDesc = true;

  var zoneFilter = document.getElementById("zone-filter");
  var typeFilter = document.getElementById("type-filter");

  function distinct(key) {
    var seen = {};
    rows.forEach(function (r) { seen[r[key]] = true; });
    return Object.keys(seen).sort();
  }

  function fillFilter(el, key, allLabel) {
    el.innerHTML = '<option value="">' + allLabel + "</option>" +
      distinct(key).map(function (v) {
        return '<option value="' + v + '">' + v + "</option>";
      }).join("");
  }

  fillFilter(zoneFilter, "zone", "All zones");
  fillFilter(typeFilter, "facility_type", "All types");

  function visibleRows() {
    var z = zoneFilter.value;
    var t = typeFilter.value;
    return rows.filter(function (r) {
      return (z === "" || r.zone === z) && (t === "" || r.facility_type === t);
    });
  }

  function renderTable() {
    var data = visibleRows().sort(function (a, b) {
      var av = a[sortKey];
      var bv = b[sortKey];
      var cmp;
      if (typeof av === "number") {
        cmp = av - bv;
      } else {
        cmp = String(av).localeCompare(String(bv));
      }
      if (cmp === 0) {
        cmp = a.facility_id.localeCompare(b.facility_id);
        return sortDesc ? -cmp : cmp;
      }
      return sortDesc ? -cmp : cmp;
    });

    var head = "<thead><tr>" + COLUMNS.map(function (c) {
      var arrow = c.key === sortKey
        ? '<span class="arrow">' + (sortDesc ? "▼" : "▲") + "</span>"
        : "";
      return '<th data-key="' + c.key + '"' + (c.text ? ' class="text"' : "") +
        ">" + c.label + arrow + "</th>";
    }).join("") + "</tr></thead>";

    var body = "<tbody>" + data.map(function (r) {
      return "<tr>" + COLUMNS.map(function (c) {
        var v = r[c.key];
        return "<td" + (c.text ? ' class="text"' : "") + ">" +
          (typeof v === "number" ? fmtInt(v) : v) + "</td>";
      }).join("") + "</tr>";
    }).join("") + "</tbody>";

    var sum = data.reduce(function (a, r) { return a + r.total_beds; }, 0);
    var foot = "<tfoot><tr>" +
      '<td class="text" colspan="4">' + fmtInt(data.length) + " facilities shown</td>" +
      "<td>" + fmtInt(data.reduce(function (a, r) { return a + r.nursing; }, 0)) + "</td>" +
      "<td>" + fmtInt(data.reduce(function (a, r) { return a + r.residential; }, 0)) + "</td>" +
      "<td>" + fmtInt(sum) + "</td>" +
      "<td>" + fmtInt(data.reduce(function (a, r) { return a + r.respite_beds; }, 0)) + "</td>" +
      "</tr></tfoot>";

    var table = document.getElementById("facility-table");
    table.innerHTML = head + body + foot;

    document.getElementById("table-count").textContent =
      fmtInt(data.length) + " of " + fmtInt(rows.length) + " facilities, " +
      fmtInt(sum) + " beds";

    var ths = table.querySelectorAll("thead th");
    for (var i = 0; i < ths.length; i++) {
      ths[i].addEventListener("click", function () {
        var key = this.getAttribute("data-key");
        if (key === sortKey) {
          sortDesc = !sortDesc;
        } else {
          sortKey = key;
          sortDesc = typeof rows[0][key] === "number";
        }
        renderTable();
      });
    }
  }

  zoneFilter.addEventListener("change", renderTable);
  typeFilter.addEventListener("change", renderTable);
  renderTable();

  /* Exposed so the derivation can be checked from the console or a headless run
     against expected/ltc_bed_supply.csv. */
  window.LTC_DERIVED = {
    facilities: facilityCount,
    totalBeds: totalBeds,
    nursingBeds: bedTypeTotals.nursing,
    residentialBeds: bedTypeTotals.residential,
    nursingRespiteBeds: bedTypeTotals.nursing_respite,
    residentialRespiteBeds: bedTypeTotals.residential_respite,
    seaFacilities: seaCount,
    avgBeds: avgBeds,
    medianBeds: medBeds,
    largest: { name: largest.facility_name, beds: largest.total_beds },
    zones: zones.map(function (z) {
      return {
        zone: z.zone,
        facilities: z.facilities,
        nursing: z.nursing,
        residential: z.residential,
        totalBeds: z.total_beds,
        sharePct: z.share_pct,
        avgBeds: z.avg_beds,
        medianBeds: z.median_beds
      };
    })
  };
})();
