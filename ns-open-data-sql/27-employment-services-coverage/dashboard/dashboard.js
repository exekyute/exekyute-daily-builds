/* Every figure on this page is derived here from DATA, the centre list that
   run.py exports out of the SQL pipeline. No number is written into the page;
   the derived headline must equal expected/services_coverage.csv exactly. */

(function () {
  "use strict";

  // Mirrors the CONTACT_CHANNELS constant declared in sql/00_schema.sql, in the
  // same report order. The counts below are derived, never written down.
  var CHANNELS = [
    { key: "has_email", label: "Email", note: "email address published" },
    { key: "has_web", label: "Website", note: "web address published" },
    { key: "has_facebook", label: "Facebook", note: "page published" },
    { key: "has_twitter", label: "Twitter", note: "account published" }
  ];

  var total = DATA.length;

  function distinct(key) {
    var seen = {};
    var n = 0;
    DATA.forEach(function (row) {
      var value = row[key];
      if (value === null || value === "") { return; }
      if (!Object.prototype.hasOwnProperty.call(seen, value)) {
        seen[value] = true;
        n += 1;
      }
    });
    return n;
  }

  function pct(count) {
    return (count / total * 100).toFixed(2);
  }

  /* Ranking rule, matched to the SQL: count descending, then region name
     ascending. Two regions hold the same number of centres, so the name is
     what decides the order, not the scan. */
  function byCountThenName(a, b) {
    if (b.count !== a.count) { return b.count - a.count; }
    return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0);
  }

  function countBy(key) {
    var buckets = {};
    DATA.forEach(function (row) {
      var value = row[key];
      if (!Object.prototype.hasOwnProperty.call(buckets, value)) {
        buckets[value] = { name: value, count: 0, towns: {}, providers: {} };
      }
      buckets[value].count += 1;
      buckets[value].towns[row.city_town] = true;
      buckets[value].providers[row.center_name] = true;
    });
    return Object.keys(buckets).map(function (k) {
      var b = buckets[k];
      return {
        name: b.name,
        count: b.count,
        towns: Object.keys(b.towns).length,
        providers: Object.keys(b.providers).length
      };
    }).sort(byCountThenName);
  }

  var regions = countBy("region");
  var topRegion = regions[0];
  var fullyListed = DATA.filter(function (row) {
    return row.contact_channels === CHANNELS.length;
  }).length;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined && text !== null) { node.textContent = text; }
    return node;
  }

  /* Headline cards */
  function renderHeadline() {
    var cards = [
      {
        label: "Centres",
        value: String(total),
        detail: distinct("center_name") + " service providers across " +
                distinct("city_town") + " towns"
      },
      {
        label: "Regions covered",
        value: String(regions.length),
        detail: "every region carries at least one centre"
      },
      {
        label: "Busiest region",
        value: topRegion.name,
        detail: topRegion.count + " centres, " + pct(topRegion.count) +
                "% of the province"
      },
      {
        label: "Postal areas reached",
        value: String(distinct("fsa")),
        detail: "distinct forward sortation areas"
      },
      {
        label: "All four channels",
        value: String(fullyListed),
        detail: pct(fullyListed) + "% of centres publish every contact channel"
      }
    ];
    var host = document.getElementById("headline");
    cards.forEach(function (card) {
      var node = el("div", "stat-card");
      node.appendChild(el("div", "label", card.label));
      node.appendChild(el("div", "value", card.value));
      node.appendChild(el("div", "detail", card.detail));
      host.appendChild(node);
    });
  }

  /* Shared bar row */
  function barRow(host, name, sub, count, share, widthPct, muted) {
    var row = el("div", muted ? "bar-row muted" : "bar-row");

    var label = el("div", "name", name);
    if (sub) { label.appendChild(el("span", "sub", sub)); }
    row.appendChild(label);

    var track = el("div", "bar-track");
    var fill = el("div", "bar-fill");
    fill.style.width = widthPct + "%";
    track.appendChild(fill);
    row.appendChild(track);

    var num = el("div", "num");
    var strong = el("strong", null, String(count));
    num.appendChild(strong);
    num.appendChild(document.createTextNode("  " + share + "%"));
    row.appendChild(num);

    host.appendChild(row);
  }

  function renderRegions() {
    var host = document.getElementById("region-chart");
    var widest = regions[0].count;
    regions.forEach(function (r) {
      barRow(host, r.name,
             r.towns + " towns, " + r.providers + " providers",
             r.count, pct(r.count), r.count / widest * 100, false);
    });
  }

  function renderChannels() {
    var host = document.getElementById("channel-chart");
    CHANNELS.forEach(function (channel) {
      var count = DATA.reduce(function (sum, row) {
        return sum + row[channel.key];
      }, 0);
      barRow(host, channel.label, channel.note, count, pct(count),
             count / total * 100, true);
    });
  }

  /* Directory table */
  function renderDirectory() {
    var select = document.getElementById("region-select");
    var search = document.getElementById("town-search");
    var body = document.querySelector("#directory tbody");
    var count = document.getElementById("table-count");

    var all = el("option", null, "All regions (" + total + ")");
    all.value = "";
    select.appendChild(all);
    regions.forEach(function (r) {
      var option = el("option", null, r.name + " (" + r.count + ")");
      option.value = r.name;
      select.appendChild(option);
    });

    function draw() {
      var region = select.value;
      var term = search.value.trim().toLowerCase();
      var rows = DATA.filter(function (row) {
        if (region && row.region !== region) { return false; }
        if (!term) { return true; }
        return (row.city_town + " " + row.center_name).toLowerCase()
                 .indexOf(term) !== -1;
      });

      body.innerHTML = "";
      if (rows.length === 0) {
        var blank = el("tr");
        var cell = el("td", "empty", "No centre matches that filter.");
        cell.colSpan = 8;
        blank.appendChild(cell);
        body.appendChild(blank);
      } else {
        rows.forEach(function (row) {
          var tr = el("tr");
          tr.appendChild(el("td", "region", row.region));
          tr.appendChild(el("td", null, row.city_town));
          tr.appendChild(el("td", null, row.center_name));
          tr.appendChild(el("td", null, row.street_address));
          tr.appendChild(el("td", "fsa", row.fsa));
          tr.appendChild(el("td", "num", row.latitude.toFixed(5)));
          tr.appendChild(el("td", "num", row.longitude.toFixed(5)));
          tr.appendChild(el("td", "num",
                             row.contact_channels + " of " + CHANNELS.length));
          body.appendChild(tr);
        });
      }
      count.textContent = "Showing " + rows.length + " of " + total + " centres";
    }

    select.addEventListener("change", draw);
    search.addEventListener("input", draw);
    draw();
  }

  renderHeadline();
  renderRegions();
  renderChannels();
  renderDirectory();
})();
