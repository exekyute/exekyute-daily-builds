/* SubList app wiring: state, localStorage, rendering, modals.
   All user-entered text reaches the page through textContent, and every
   outbound link is checked by SubLogic.safeUrl before it becomes an href. */

(function () {
  "use strict";

  const L = SubLogic;
  const STORAGE_KEY = "sublist-v2";

  const CYCLE_SHORT = {
    weekly: "/wk", monthly: "/mo", quarterly: "/qtr",
    semiannual: "/6 mo", yearly: "/yr", biennial: "/2 yr"
  };

  const STATUS_LABEL = {
    active: "Active", trial: "Trial", review: "Under review",
    considering: "Considering", cancelled: "Cancelled"
  };

  /* Cover tints stay inside the accent's violet family so the grid keeps
     the two-tone look while cards still read as distinct. */
  const COVER_TINTS = [
    ["#31279b", "#7c6cf5"],
    ["#4437c9", "#8d7ef7"],
    ["#3a2ea8", "#6a58f0"],
    ["#4c40d8", "#9a8cf8"],
    ["#2c2390", "#7466f1"]
  ];

  const state = {
    subs: [],
    filter: { status: "all", category: "all", query: "" },
    sort: "renewal",
    detailId: null,
    editId: null
  };

  function todayISO() {
    const d = new Date();
    return L.toISO(d.getFullYear(), d.getMonth() + 1, d.getDate());
  }

  function uid() {
    return "sub-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 7);
  }

  const $ = function (sel) { return document.querySelector(sel); };

  /* ---------- persistence ---------- */

  function load() {
    let raw = null;
    try { raw = localStorage.getItem(STORAGE_KEY); } catch (e) { raw = null; }
    if (raw === null) {
      state.subs = L.sampleSubs(todayISO());
      save();
      return;
    }
    try {
      const data = JSON.parse(raw);
      const list = Array.isArray(data.subs) ? data.subs : [];
      state.subs = [];
      let dropped = 0;
      list.forEach(function (item, i) {
        const result = L.normalizeSub(item, "st-" + (i + 1));
        if (result.errors.length === 0) state.subs.push(result.sub);
        else dropped += 1;
      });
      if (dropped > 0) {
        /* Never silently lose records: park the untouched original under a
           side key before any save() rewrites the main one. */
        try { localStorage.setItem(STORAGE_KEY + "-recovered", raw); } catch (e2) {}
        showToast(dropped + " saved record" + (dropped === 1 ? "" : "s") +
          " failed validation and " + (dropped === 1 ? "was" : "were") +
          " set aside. The original data was copied to the \"" + STORAGE_KEY +
          "-recovered\" browser storage key.", true);
      }
    } catch (e) {
      state.subs = [];
      showToast("Saved data could not be read and was reset.", true);
    }
  }

  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, subs: state.subs }));
    } catch (e) {
      showToast("Could not save: browser storage is unavailable.", true);
    }
  }

  function findSub(id) {
    return state.subs.find(function (s) { return s.id === id; }) || null;
  }

  /* ---------- rendering ---------- */

  function renderAll() {
    renderStats();
    renderSidebar();
    renderGrid();
    renderRail();
  }

  function renderStats() {
    const s = L.stats(state.subs, todayISO());
    $("#stat-monthly").textContent = L.formatMoney(s.monthlyCents);
    $("#stat-annual").textContent = L.formatMoney(s.annualCents);
    $("#stat-active").textContent = String(s.activeCount);
    $("#stat-due").textContent = String(s.dueSoonCount);
  }

  function renderSidebar() {
    const counts = L.countByStatus(state.subs);
    const list = $("#status-list");
    list.textContent = "";
    const entries = [["all", "All"]].concat(L.STATUSES.map(function (st) { return [st, STATUS_LABEL[st]]; }));
    entries.forEach(function (entry) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      if (state.filter.status === entry[0]) btn.classList.add("is-active");
      const label = document.createElement("span");
      label.textContent = entry[1];
      const count = document.createElement("span");
      count.className = "side-count";
      count.textContent = String(counts[entry[0]]);
      btn.appendChild(label);
      btn.appendChild(count);
      btn.addEventListener("click", function () {
        state.filter.status = entry[0];
        renderAll();
      });
      li.appendChild(btn);
      list.appendChild(li);
    });

    const catSelect = $("#category-filter");
    const used = Object.create(null);
    state.subs.forEach(function (s) { used[s.category] = true; });
    const cats = L.CATEGORIES.filter(function (c) { return used[c]; });
    Object.keys(used).sort().forEach(function (c) {
      if (L.CATEGORIES.indexOf(c) === -1) cats.push(c);
    });
    catSelect.textContent = "";
    const allOpt = document.createElement("option");
    allOpt.value = "all";
    allOpt.textContent = "All categories";
    catSelect.appendChild(allOpt);
    cats.forEach(function (c) {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      catSelect.appendChild(opt);
    });
    catSelect.value = cats.indexOf(state.filter.category) !== -1 ? state.filter.category : "all";
    state.filter.category = catSelect.value;
  }

  function coverStyle(name) {
    const tint = COVER_TINTS[L.hashString(name) % COVER_TINTS.length];
    return "linear-gradient(135deg, " + tint[0] + ", " + tint[1] + ")";
  }

  function renewText(sub, today) {
    if (sub.status === "cancelled") return { text: "Ended", due: false };
    if (sub.status === "considering") return { text: "Not subscribed yet", due: false };
    const days = L.daysUntil(sub.nextRenewal, today);
    if (days < 0) return { text: "Past due " + (-days) + (days === -1 ? " day" : " days"), due: true };
    if (days === 0) return { text: "Renews today", due: true };
    if (days === 1) return { text: "Renews tomorrow", due: false };
    return { text: "Renews in " + days + " days", due: false };
  }

  /* A looming cancellation-notice deadline outranks the renewal countdown
     on the card, since it is the date that can still change the outcome. */
  function noticeInfo(sub, today) {
    if (L.COUNTABLE.indexOf(sub.status) === -1 || sub.noticeDays === 0) return null;
    const deadline = L.noticeDeadline(sub.nextRenewal, sub.noticeDays);
    const daysLeft = L.daysUntil(deadline, today);
    if (daysLeft < 0 || daysLeft > 7) return null;
    if (daysLeft === 0) return { text: "Cancel notice due today" };
    return { text: "Cancel notice due in " + daysLeft + (daysLeft === 1 ? " day" : " days") };
  }

  function renderGrid() {
    const today = todayISO();
    const grid = $("#grid");
    grid.textContent = "";
    let subs = L.filterSubs(state.subs, state.filter);
    subs = L.sortSubs(subs, state.sort, today);

    if (subs.length === 0) {
      const note = document.createElement("div");
      note.className = "empty-note";
      note.textContent = state.subs.length === 0
        ? "Nothing tracked yet. Add a subscription or load the sample data from the sidebar."
        : "No subscriptions match the current filters.";
      grid.appendChild(note);
      return;
    }

    subs.forEach(function (sub) {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "card";
      card.setAttribute("aria-label", sub.name + ", open details");

      const cover = document.createElement("div");
      cover.className = "cover";
      cover.style.background = coverStyle(sub.name);
      cover.textContent = sub.name.charAt(0).toUpperCase();
      const coverName = document.createElement("div");
      coverName.className = "cover-name";
      coverName.textContent = sub.name;
      cover.appendChild(coverName);

      const body = document.createElement("div");
      body.className = "card-body";

      const totalCents = sub.priceCents * sub.seats;
      const price = document.createElement("div");
      price.className = "card-price";
      price.textContent = L.formatMoney(totalCents);
      const per = document.createElement("span");
      per.className = "per";
      let perText = " " + CYCLE_SHORT[sub.cycle];
      if (sub.cycle !== "monthly") {
        perText += " (" + L.formatMoney(L.monthlyCents(totalCents, sub.cycle)) + "/mo)";
      }
      per.textContent = perText;
      price.appendChild(per);

      body.appendChild(price);

      if (sub.seats > 1) {
        const seatsLine = document.createElement("div");
        seatsLine.className = "card-seats";
        seatsLine.textContent = sub.seats + " seats × " + L.formatMoney(sub.priceCents);
        body.appendChild(seatsLine);
      }

      const renew = document.createElement("div");
      renew.className = "card-renew";
      const info = renewText(sub, today);
      const notice = noticeInfo(sub, today);
      renew.textContent = notice ? notice.text : info.text;
      if (info.due || notice) renew.classList.add("is-due");

      body.appendChild(renew);

      if (L.COUNTABLE.indexOf(sub.status) !== -1) {
        const bar = document.createElement("div");
        bar.className = "bar";
        const fill = document.createElement("div");
        fill.className = "bar-fill";
        const progress = L.periodProgress(sub.nextRenewal, sub.cycle, sub.anchorDay, today);
        fill.style.width = Math.round(progress * 100) + "%";
        if (info.due) fill.classList.add("is-due");
        bar.appendChild(fill);
        body.appendChild(bar);
      }

      const foot = document.createElement("div");
      foot.className = "card-foot";
      const chip = document.createElement("span");
      chip.className = "chip";
      if (info.due) {
        chip.classList.add("chip-due");
        chip.textContent = "Due";
      } else {
        chip.classList.add("chip-" + sub.status);
        chip.textContent = STATUS_LABEL[sub.status];
      }
      foot.appendChild(chip);
      if (sub.score !== null) {
        const score = document.createElement("span");
        score.className = "score";
        score.textContent = "★ " + sub.score;
        foot.appendChild(score);
      }
      body.appendChild(foot);

      card.appendChild(cover);
      card.appendChild(body);
      card.addEventListener("click", function () { openDetail(sub.id); });
      grid.appendChild(card);
    });
  }

  function renderRail() {
    const today = todayISO();
    const box = $("#upcoming-list");
    box.textContent = "";
    const items = L.upcoming(state.subs, today, 30);
    if (items.length === 0) {
      const p = document.createElement("p");
      p.className = "rail-note";
      p.textContent = "Nothing renews in the next 30 days.";
      box.appendChild(p);
      return;
    }
    items.forEach(function (item) {
      const row = document.createElement("div");
      row.className = "up-item";

      const days = document.createElement("div");
      days.className = "up-days";
      if (item.days < 0) {
        days.textContent = "late";
        days.classList.add("is-due");
      } else if (item.days === 0) {
        days.textContent = "today";
        days.classList.add("is-due");
      } else {
        days.textContent = item.days + "d";
      }

      const info = document.createElement("div");
      info.className = "up-info";
      const name = document.createElement("div");
      name.className = "up-name";
      name.textContent = item.sub.name;
      const meta = document.createElement("div");
      meta.className = "up-meta";
      let metaText = item.sub.nextRenewal + " · " + L.formatMoney(item.sub.priceCents * item.sub.seats);
      if (item.sub.noticeDays > 0) {
        metaText += " · notice by " + L.noticeDeadline(item.sub.nextRenewal, item.sub.noticeDays);
      }
      meta.textContent = metaText;
      info.appendChild(name);
      info.appendChild(meta);

      row.appendChild(days);
      row.appendChild(info);

      const url = item.sub.links.manage || item.sub.links.help;
      if (url && L.safeUrl(url)) {
        const link = document.createElement("a");
        link.className = "up-link";
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Manage";
        link.addEventListener("click", function (e) { e.stopPropagation(); });
        row.appendChild(link);
      }
      box.appendChild(row);
    });
  }

  function renderDirectory() {
    const box = $("#directory-list");
    box.textContent = "";
    SERVICE_DIRECTORY.forEach(function (svc) {
      const row = document.createElement("div");
      row.className = "up-item";
      const info = document.createElement("div");
      info.className = "up-info";
      const name = document.createElement("div");
      name.className = "up-name";
      name.textContent = svc.name;
      const meta = document.createElement("div");
      meta.className = "up-meta";
      meta.textContent = svc.category;
      info.appendChild(name);
      info.appendChild(meta);
      row.appendChild(info);
      [["manage", "Admin"], ["help", "Help"]].forEach(function (pair) {
        const url = svc.links[pair[0]];
        if (url && L.safeUrl(url)) {
          const a = document.createElement("a");
          a.className = "up-link";
          a.href = url;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.textContent = pair[1];
          row.appendChild(a);
        }
      });
      box.appendChild(row);
    });

    const datalist = $("#service-names");
    SERVICE_DIRECTORY.forEach(function (svc) {
      const opt = document.createElement("option");
      opt.value = svc.name;
      datalist.appendChild(opt);
    });
  }

  /* ---------- modal focus handling ----------
     Both dialogs declare aria-modal, so focus moves into them on open,
     Tab cycles inside them, and closing hands focus back. */

  let lastFocus = null;

  function rememberFocus(overlaySel) {
    if ($(overlaySel).hidden) lastFocus = document.activeElement;
  }

  function restoreFocus() {
    if (lastFocus && document.body.contains(lastFocus)) lastFocus.focus();
    lastFocus = null;
  }

  function trapTab(overlay, event) {
    const nodes = overlay.querySelectorAll("button, a[href], input, select, textarea");
    const list = Array.prototype.filter.call(nodes, function (el) {
      return !el.disabled && el.offsetParent !== null;
    });
    if (list.length === 0) return;
    const first = list[0];
    const last = list[list.length - 1];
    const active = document.activeElement;
    if (!overlay.contains(active)) {
      event.preventDefault();
      first.focus();
    } else if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  /* ---------- detail modal ---------- */

  function openDetail(id) {
    const sub = findSub(id);
    if (!sub) return;
    state.detailId = id;
    rememberFocus("#detail-overlay");
    const today = todayISO();

    const totalCents = sub.priceCents * sub.seats;
    $("#detail-title").textContent = sub.name;
    $("#detail-status").value = sub.status;
    $("#detail-price").textContent = L.formatMoney(totalCents) + " " + CYCLE_SHORT[sub.cycle];
    $("#detail-monthly").textContent = L.formatMoney(L.monthlyCents(totalCents, sub.cycle)) + "/mo";
    $("#detail-seats").textContent = sub.seats === 1
      ? "1"
      : sub.seats + " × " + L.formatMoney(sub.priceCents) + " per seat";
    $("#detail-owner").textContent = sub.owner || "Not set";
    $("#detail-notice").textContent = sub.noticeDays > 0
      ? sub.noticeDays + " days (by " + L.noticeDeadline(sub.nextRenewal, sub.noticeDays) + ")"
      : "None";
    $("#detail-category").textContent = sub.category;
    $("#detail-score").textContent = sub.score === null ? "Not rated" : "★ " + sub.score + " / 10";

    const info = renewText(sub, today);
    let renewLine = sub.nextRenewal;
    if (L.COUNTABLE.indexOf(sub.status) !== -1) renewLine += " (" + info.text.toLowerCase() + ")";
    $("#detail-renewal").textContent = renewLine;

    const catchup = L.catchUp(sub.nextRenewal, sub.cycle, sub.anchorDay, today);
    const lateNote = $("#detail-late-note");
    if (catchup.periods > 1 && L.COUNTABLE.indexOf(sub.status) !== -1) {
      lateNote.hidden = false;
      lateNote.textContent = catchup.capped
        ? "This renewal date is very far in the past. Edit the date to bring it current."
        : "This renewal is " + catchup.periods +
          " periods behind. Mark renewed repeatedly, or edit the date to " + catchup.date + ".";
    } else {
      lateNote.hidden = true;
    }

    const notes = $("#detail-notes");
    if (sub.notes.trim()) {
      notes.hidden = false;
      notes.textContent = sub.notes;
    } else {
      notes.hidden = true;
    }

    const linkRow = $("#detail-links");
    linkRow.textContent = "";
    [["manage", "Manage plan"], ["cancel", "Cancel flow"], ["help", "Billing help"]].forEach(function (pair) {
      const url = sub.links[pair[0]];
      if (url && L.safeUrl(url)) {
        const a = document.createElement("a");
        a.className = "link-btn";
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = pair[1];
        linkRow.appendChild(a);
      }
    });
    if (linkRow.children.length === 0) {
      const span = document.createElement("span");
      span.className = "rail-note";
      span.textContent = "No links saved. Edit this subscription to add them.";
      linkRow.appendChild(span);
    }

    const wasHidden = $("#detail-overlay").hidden;
    $("#detail-overlay").hidden = false;
    if (wasHidden) $("#detail-close").focus();
  }

  function closeDetail() {
    $("#detail-overlay").hidden = true;
    state.detailId = null;
    restoreFocus();
  }

  function markRenewed() {
    const sub = findSub(state.detailId);
    if (!sub) return;
    sub.nextRenewal = L.advanceRenewal(sub.nextRenewal, sub.cycle, sub.anchorDay);
    save();
    renderAll();
    openDetail(sub.id);
    showToast(sub.name + " rolled forward to " + sub.nextRenewal + ".", false);
  }

  /* ---------- form modal ---------- */

  function openForm(id) {
    rememberFocus("#form-overlay");
    state.editId = id || null;
    const sub = id ? findSub(id) : null;
    $("#form-title").textContent = sub ? "Edit subscription" : "Add subscription";
    $("#form-banner").hidden = true;

    $("#f-name").value = sub ? sub.name : "";

    /* Imported subs may carry a category outside the built-in list; give it
       a temporary option so a round-trip through this form keeps it. */
    const catSelect = $("#f-category");
    while (catSelect.options.length > L.CATEGORIES.length) {
      catSelect.remove(catSelect.options.length - 1);
    }
    if (sub && L.CATEGORIES.indexOf(sub.category) === -1) {
      const custom = document.createElement("option");
      custom.value = sub.category;
      custom.textContent = sub.category;
      catSelect.appendChild(custom);
    }
    catSelect.value = sub ? sub.category : "Streaming";
    $("#f-price").value = sub ? (sub.priceCents / 100).toFixed(2) : "";
    $("#f-seats").value = sub ? String(sub.seats) : "1";
    $("#f-owner").value = sub ? sub.owner : "";
    $("#f-notice").value = sub ? String(sub.noticeDays) : "0";
    $("#f-cycle").value = sub ? sub.cycle : "monthly";
    $("#f-date").value = sub ? sub.nextRenewal : "";
    $("#f-status").value = sub ? sub.status : "active";
    $("#f-score").value = sub && sub.score !== null ? String(sub.score) : "";
    $("#f-notes").value = sub ? sub.notes : "";
    $("#f-link-manage").value = sub ? sub.links.manage : "";
    $("#f-link-cancel").value = sub ? sub.links.cancel : "";
    $("#f-link-help").value = sub ? sub.links.help : "";

    ["#f-name", "#f-price", "#f-seats", "#f-notice", "#f-date",
     "#f-link-manage", "#f-link-cancel", "#f-link-help"].forEach(function (sel) {
      $(sel).classList.remove("is-invalid");
    });
    ["#e-name", "#e-price", "#e-seats", "#e-notice", "#e-date", "#e-links"].forEach(function (sel) {
      $(sel).textContent = "";
    });

    $("#form-overlay").hidden = false;
    $("#f-name").focus();
  }

  function closeForm() {
    $("#form-overlay").hidden = true;
    state.editId = null;
    restoreFocus();
  }

  /* Pre-fill category and links when a directory name is picked. */
  function applyDirectoryMatch() {
    const name = $("#f-name").value.trim().toLowerCase();
    const match = SERVICE_DIRECTORY.find(function (svc) { return svc.name.toLowerCase() === name; });
    if (!match) return;
    $("#f-category").value = match.category;
    $("#f-link-manage").value = match.links.manage;
    $("#f-link-cancel").value = match.links.cancel;
    $("#f-link-help").value = match.links.help;
    showToast("Category and links filled from the directory.", false);
  }

  function submitForm(event) {
    event.preventDefault();
    const errors = [];

    const name = $("#f-name").value.trim();
    const priceCents = L.parsePrice($("#f-price").value);
    const date = $("#f-date").value;
    const seatsRaw = $("#f-seats").value.trim();
    const seats = /^\d+$/.test(seatsRaw) ? Number(seatsRaw) : null;
    const noticeRaw = $("#f-notice").value.trim();
    const noticeDays = noticeRaw === "" ? 0 : (/^\d+$/.test(noticeRaw) ? Number(noticeRaw) : null);

    function flag(inputSel, errorSel, message) {
      $(inputSel).classList.add("is-invalid");
      $(errorSel).textContent = message;
      errors.push(message);
    }

    ["#f-name", "#f-price", "#f-seats", "#f-notice", "#f-date",
     "#f-link-manage", "#f-link-cancel", "#f-link-help"].forEach(function (sel) {
      $(sel).classList.remove("is-invalid");
    });
    ["#e-name", "#e-price", "#e-seats", "#e-notice", "#e-date", "#e-links"].forEach(function (sel) { $(sel).textContent = ""; });

    if (!name) flag("#f-name", "#e-name", "Name is required.");
    else if (name.length > 80) flag("#f-name", "#e-name", "Name is longer than 80 characters.");

    if (priceCents === null) {
      flag("#f-price", "#e-price", "Price must be a positive amount like 12.99, up to two decimals.");
    }

    if (seats === null || seats < 1 || seats > 100000) {
      flag("#f-seats", "#e-seats", "Seats must be a whole number from 1 to 100,000.");
    }

    if (noticeDays === null || noticeDays > 365) {
      flag("#f-notice", "#e-notice", "Notice days must be a whole number from 0 to 365.");
    }

    if (!L.isValidISO(date)) {
      flag("#f-date", "#e-date", "Pick a real renewal date.");
    }

    const links = {
      manage: $("#f-link-manage").value.trim(),
      cancel: $("#f-link-cancel").value.trim(),
      help: $("#f-link-help").value.trim()
    };
    ["manage", "cancel", "help"].forEach(function (key) {
      if (links[key] !== "" && !L.safeUrl(links[key])) {
        $("#f-link-" + key).classList.add("is-invalid");
        $("#e-links").textContent = "Links must start with https:// (or be left empty).";
        errors.push("bad link");
      }
    });

    if (errors.length > 0) {
      const banner = $("#form-banner");
      banner.hidden = false;
      banner.textContent = "Fix the highlighted fields to save.";
      return;
    }

    const existing = state.editId ? findSub(state.editId) : null;
    const scoreRaw = $("#f-score").value;
    /* Keep the stored anchor when the date was not touched, so editing the
       price of a sub sitting on a clamped Feb 28 does not forget its 31st. */
    const anchorDay = (existing && existing.nextRenewal === date)
      ? existing.anchorDay
      : L.parseISO(date).d;
    const sub = {
      id: existing ? existing.id : uid(),
      name: name,
      category: $("#f-category").value,
      priceCents: priceCents,
      seats: seats,
      owner: $("#f-owner").value.trim().slice(0, 60),
      noticeDays: noticeDays,
      cycle: $("#f-cycle").value,
      nextRenewal: date,
      anchorDay: anchorDay,
      status: $("#f-status").value,
      score: scoreRaw === "" ? null : Number(scoreRaw),
      notes: $("#f-notes").value.slice(0, 500),
      links: links
    };

    const check = L.validateSub(sub);
    if (check.length > 0) {
      const banner = $("#form-banner");
      banner.hidden = false;
      banner.textContent = check[0];
      return;
    }

    if (existing) {
      const index = state.subs.indexOf(existing);
      state.subs[index] = sub;
    } else {
      state.subs.push(sub);
    }
    save();
    closeForm();
    renderAll();
    showToast(existing ? sub.name + " updated." : sub.name + " added.", false);
  }

  /* ---------- import and export ---------- */

  function doExport() {
    const text = L.makeExport(state.subs, todayISO());
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sublist-export.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Exported " + state.subs.length + " subscriptions.", false);
  }

  function doImport(file) {
    const reader = new FileReader();
    reader.onload = function () {
      const result = L.parseImport(String(reader.result));
      if (!result.ok) {
        showToast("Import rejected. " + result.errors.join(" "), true);
        return;
      }
      const message = "Replace your " + state.subs.length + " tracked subscriptions with " +
        result.subs.length + " from this file?";
      if (!window.confirm(message)) return;
      state.subs = result.subs;
      save();
      renderAll();
      showToast("Imported " + result.subs.length + " subscriptions.", false);
    };
    reader.onerror = function () {
      showToast("The file could not be read.", true);
    };
    reader.readAsText(file);
  }

  /* ---------- toast ---------- */

  let toastTimer = null;

  function showToast(message, isError) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.toggle("is-error", Boolean(isError));
    toast.hidden = false;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.hidden = true; }, isError ? 8000 : 4000);
  }

  /* ---------- events ---------- */

  function wireEvents() {
    $("#btn-add").addEventListener("click", function () { openForm(null); });
    $("#btn-export").addEventListener("click", doExport);
    $("#btn-import").addEventListener("click", function () { $("#import-file").click(); });
    $("#import-file").addEventListener("change", function (event) {
      if (event.target.files.length > 0) doImport(event.target.files[0]);
      event.target.value = "";
    });

    $("#search").addEventListener("input", function (event) {
      state.filter.query = event.target.value;
      renderGrid();
    });

    $("#category-filter").addEventListener("change", function (event) {
      state.filter.category = event.target.value;
      renderAll();
    });

    $("#sort-select").addEventListener("change", function (event) {
      state.sort = event.target.value;
      renderGrid();
    });

    $("#btn-sample").addEventListener("click", function () {
      if (state.subs.length > 0 &&
          !window.confirm("Replace the current list with the sample data?")) return;
      state.subs = L.sampleSubs(todayISO());
      save();
      renderAll();
      showToast("Sample data loaded.", false);
    });

    $("#btn-clear").addEventListener("click", function () {
      if (!window.confirm("Delete every tracked subscription? Export first if you want a backup.")) return;
      state.subs = [];
      save();
      renderAll();
      showToast("All subscriptions deleted.", false);
    });

    $("#detail-close").addEventListener("click", closeDetail);
    $("#btn-renewed").addEventListener("click", markRenewed);
    $("#btn-edit").addEventListener("click", function () {
      const id = state.detailId;
      closeDetail();
      openForm(id);
    });
    $("#btn-delete").addEventListener("click", function () {
      const sub = findSub(state.detailId);
      if (!sub) return;
      if (!window.confirm("Delete " + sub.name + "?")) return;
      state.subs = state.subs.filter(function (s) { return s.id !== sub.id; });
      save();
      closeDetail();
      renderAll();
      showToast(sub.name + " deleted.", false);
    });
    $("#detail-status").addEventListener("change", function (event) {
      const sub = findSub(state.detailId);
      if (!sub) return;
      sub.status = event.target.value;
      save();
      renderAll();
      openDetail(sub.id);
    });

    $("#form-close").addEventListener("click", closeForm);
    $("#form-cancel").addEventListener("click", closeForm);
    $("#sub-form").addEventListener("submit", submitForm);
    $("#f-name").addEventListener("change", applyDirectoryMatch);

    [["#detail-overlay", closeDetail], ["#form-overlay", closeForm]].forEach(function (pair) {
      $(pair[0]).addEventListener("mousedown", function (event) {
        if (event.target === event.currentTarget) pair[1]();
      });
    });

    document.addEventListener("keydown", function (event) {
      const openOverlay = !$("#form-overlay").hidden
        ? $("#form-overlay")
        : (!$("#detail-overlay").hidden ? $("#detail-overlay") : null);
      if (event.key === "Escape") {
        if (openOverlay === $("#form-overlay")) closeForm();
        else if (openOverlay) closeDetail();
      } else if (event.key === "Tab" && openOverlay) {
        trapTab(openOverlay, event);
      }
    });
  }

  /* ---------- boot ---------- */

  function populateStaticSelects() {
    const cycleSelect = $("#f-cycle");
    Object.keys(L.CYCLES).forEach(function (key) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = L.CYCLES[key].label;
      cycleSelect.appendChild(opt);
    });

    const statusSelects = [$("#f-status"), $("#detail-status")];
    statusSelects.forEach(function (select) {
      L.STATUSES.forEach(function (st) {
        const opt = document.createElement("option");
        opt.value = st;
        opt.textContent = STATUS_LABEL[st];
        select.appendChild(opt);
      });
    });

    const catSelect = $("#f-category");
    L.CATEGORIES.forEach(function (c) {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      catSelect.appendChild(opt);
    });

    const scoreSelect = $("#f-score");
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "Not rated";
    scoreSelect.appendChild(none);
    for (let i = 10; i >= 1; i--) {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = i + " / 10";
      scoreSelect.appendChild(opt);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    populateStaticSelects();
    renderDirectory();
    load();
    renderAll();
    wireEvents();
  });
})();
