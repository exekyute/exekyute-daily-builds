/* SubList pure logic: dates, money, validation, filtering, stats.
   No DOM access in this file; tests.html imports it directly. */

const SubLogic = (() => {
  "use strict";

  const STATUSES = ["active", "trial", "review", "considering", "cancelled"];

  /* Statuses that count toward spend totals and the upcoming rail. A
     subscription under review is still being paid for, so it counts. */
  const COUNTABLE = ["active", "trial", "review"];

  const CYCLES = {
    weekly:     { label: "Weekly",        months: 0,  perYear: 52 },
    monthly:    { label: "Monthly",       months: 1,  perYear: 12 },
    quarterly:  { label: "Quarterly",     months: 3,  perYear: 4 },
    semiannual: { label: "Every 6 months", months: 6, perYear: 2 },
    yearly:     { label: "Yearly",        months: 12, perYear: 1 },
    biennial:   { label: "Every 2 years", months: 24, perYear: 0.5 }
  };

  const CATEGORIES = [
    "Communication", "Productivity", "Dev Tools", "Design", "Sales & CRM",
    "Marketing", "Finance & Accounting", "HR & Legal", "Security",
    "AI Tools", "Cloud & Storage", "Other"
  ];

  /* ---------- dates ----------
     All dates are ISO strings (YYYY-MM-DD) handled as plain calendar
     dates in UTC, so DST never shifts a renewal day. */

  function isLeap(y) {
    return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  }

  function daysInMonth(y, m) {
    const lengths = [31, isLeap(y) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return lengths[m - 1];
  }

  function isValidISO(s) {
    if (typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
    const y = Number(s.slice(0, 4));
    const m = Number(s.slice(5, 7));
    const d = Number(s.slice(8, 10));
    if (y < 1970 || y > 2200) return false;
    if (m < 1 || m > 12) return false;
    return d >= 1 && d <= daysInMonth(y, m);
  }

  function parseISO(s) {
    return {
      y: Number(s.slice(0, 4)),
      m: Number(s.slice(5, 7)),
      d: Number(s.slice(8, 10))
    };
  }

  function toISO(y, m, d) {
    const mm = String(m).padStart(2, "0");
    const dd = String(d).padStart(2, "0");
    return y + "-" + mm + "-" + dd;
  }

  function daysBetween(aISO, bISO) {
    const a = parseISO(aISO);
    const b = parseISO(bISO);
    const utcA = Date.UTC(a.y, a.m - 1, a.d);
    const utcB = Date.UTC(b.y, b.m - 1, b.d);
    return Math.round((utcB - utcA) / 86400000);
  }

  function addDays(iso, n) {
    const p = parseISO(iso);
    const t = new Date(Date.UTC(p.y, p.m - 1, p.d + n));
    return toISO(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate());
  }

  /* Month addition clamps to the shortest month but remembers the billing
     anchor day, the way card billing does: Jan 31 -> Feb 28 -> Mar 31. */
  function addMonthsAnchored(iso, n, anchorDay) {
    const p = parseISO(iso);
    const anchor = anchorDay || p.d;
    const total = (p.m - 1) + n;
    const y = p.y + Math.floor(total / 12);
    const m = ((total % 12) + 12) % 12 + 1;
    const d = Math.min(anchor, daysInMonth(y, m));
    return toISO(y, m, d);
  }

  function advanceRenewal(nextISO, cycleKey, anchorDay) {
    const cycle = CYCLES[cycleKey];
    if (cycle.months === 0) return addDays(nextISO, 7);
    return addMonthsAnchored(nextISO, cycle.months, anchorDay);
  }

  function retreatRenewal(nextISO, cycleKey, anchorDay) {
    const cycle = CYCLES[cycleKey];
    if (cycle.months === 0) return addDays(nextISO, -7);
    return addMonthsAnchored(nextISO, -cycle.months, anchorDay);
  }

  /* Roll a lapsed date forward until it lands on or after today.
     Returns the new date, how many periods were skipped, and whether the
     iteration cap cut the roll short (capped dates are still in the past). */
  function catchUp(nextISO, cycleKey, anchorDay, todayISO) {
    const behind = daysBetween(todayISO, nextISO);
    if (behind >= 0) return { date: nextISO, periods: 0, capped: false };
    if (CYCLES[cycleKey].months === 0) {
      const periods = Math.ceil(-behind / 7);
      return { date: addDays(nextISO, periods * 7), periods: periods, capped: false };
    }
    let date = nextISO;
    let periods = 0;
    while (daysBetween(todayISO, date) < 0 && periods < 5000) {
      date = advanceRenewal(date, cycleKey, anchorDay);
      periods += 1;
    }
    return { date: date, periods: periods, capped: daysBetween(todayISO, date) < 0 };
  }

  function daysUntil(iso, todayISO) {
    return daysBetween(todayISO, iso);
  }

  /* Last day to give cancellation notice before a renewal locks in. */
  function noticeDeadline(nextRenewalISO, noticeDays) {
    return addDays(nextRenewalISO, -noticeDays);
  }

  /* Fraction of the current billing period already elapsed, 0 to 1. */
  function periodProgress(nextISO, cycleKey, anchorDay, todayISO) {
    const start = retreatRenewal(nextISO, cycleKey, anchorDay);
    const length = daysBetween(start, nextISO);
    if (length <= 0) return 1;
    const elapsed = daysBetween(start, todayISO);
    return Math.min(1, Math.max(0, elapsed / length));
  }

  /* ---------- money ----------
     Prices live as integer cents. Rounding is half up at the cent. */

  function roundHalfUp(x) {
    return Math.floor(x + 0.5);
  }

  function monthlyCents(cents, cycleKey) {
    return roundHalfUp(cents * CYCLES[cycleKey].perYear / 12);
  }

  function annualCents(cents, cycleKey) {
    return roundHalfUp(cents * CYCLES[cycleKey].perYear);
  }

  const moneyFormat = new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD"
  });

  function formatMoney(cents) {
    return moneyFormat.format(cents / 100);
  }

  /* "12.99", "$12.99", "12" -> cents. Anything else -> null. */
  function parsePrice(text) {
    if (typeof text !== "string") return null;
    const cleaned = text.trim().replace(/^\$/, "");
    if (!/^\d{1,6}(\.\d{1,2})?$/.test(cleaned)) return null;
    const parts = cleaned.split(".");
    const dollars = Number(parts[0]);
    const centsPart = parts[1] ? parts[1].padEnd(2, "0") : "00";
    return dollars * 100 + Number(centsPart);
  }

  /* ---------- validation ---------- */

  function safeUrl(u) {
    return typeof u === "string" &&
      u.length <= 300 &&
      /^https:\/\/[^\s]+$/i.test(u);
  }

  function validateSub(sub) {
    const errors = [];
    if (typeof sub !== "object" || sub === null) return ["Not a subscription object."];

    if (typeof sub.name !== "string" || sub.name.trim().length === 0) {
      errors.push("Name is required.");
    } else if (sub.name.trim().length > 80) {
      errors.push("Name is longer than 80 characters.");
    }

    if (typeof sub.category !== "string" || sub.category.length > 40) {
      errors.push("Category must be text of 40 characters or fewer.");
    }

    if (!Number.isInteger(sub.priceCents) || sub.priceCents < 0 || sub.priceCents > 99999999) {
      errors.push("Price must be a whole number of cents between 0 and 99,999,999.");
    }

    if (!Number.isInteger(sub.seats) || sub.seats < 1 || sub.seats > 100000) {
      errors.push("Seats must be a whole number from 1 to 100,000.");
    }

    if (typeof sub.owner !== "string" || sub.owner.length > 60) {
      errors.push("Owner must be text of 60 characters or fewer.");
    }

    if (!Number.isInteger(sub.noticeDays) || sub.noticeDays < 0 || sub.noticeDays > 365) {
      errors.push("Notice days must be a whole number from 0 to 365.");
    }

    if (!Object.prototype.hasOwnProperty.call(CYCLES, sub.cycle)) {
      errors.push("Billing cycle must be one of: " + Object.keys(CYCLES).join(", ") + ".");
    }

    if (!isValidISO(sub.nextRenewal)) {
      errors.push("Next renewal must be a real date in YYYY-MM-DD form.");
    }

    if (!Number.isInteger(sub.anchorDay) || sub.anchorDay < 1 || sub.anchorDay > 31) {
      errors.push("Anchor day must be a whole number from 1 to 31.");
    }

    if (STATUSES.indexOf(sub.status) === -1) {
      errors.push("Status must be one of: " + STATUSES.join(", ") + ".");
    }

    if (sub.score !== null && (!Number.isInteger(sub.score) || sub.score < 1 || sub.score > 10)) {
      errors.push("Score must be empty or a whole number from 1 to 10.");
    }

    if (typeof sub.notes !== "string" || sub.notes.length > 500) {
      errors.push("Notes must be text of 500 characters or fewer.");
    }

    if (typeof sub.links !== "object" || sub.links === null) {
      errors.push("Links must be an object.");
    } else {
      ["manage", "cancel", "help"].forEach(function (key) {
        const value = sub.links[key];
        if (value !== "" && !safeUrl(value)) {
          errors.push("The " + key + " link must be empty or an https:// URL.");
        }
      });
    }

    return errors;
  }

  /* Coerce a raw imported object into the subscription shape, then validate. */
  function normalizeSub(raw, id) {
    const links = (raw && typeof raw.links === "object" && raw.links !== null) ? raw.links : {};
    const nextRenewal = (raw && typeof raw.nextRenewal === "string") ? raw.nextRenewal : "";
    let anchorDay = raw ? raw.anchorDay : null;
    if (!Number.isInteger(anchorDay) && isValidISO(nextRenewal)) {
      anchorDay = parseISO(nextRenewal).d;
    }
    const sub = {
      id: (raw && typeof raw.id === "string" && raw.id.length > 0 && raw.id.length <= 40) ? raw.id : id,
      name: (raw && typeof raw.name === "string") ? raw.name.trim() : "",
      category: (raw && typeof raw.category === "string" && raw.category.length > 0) ? raw.category : "Other",
      priceCents: raw ? raw.priceCents : null,
      seats: (raw && raw.seats !== undefined) ? raw.seats : 1,
      owner: (raw && typeof raw.owner === "string") ? raw.owner.trim() : "",
      noticeDays: (raw && raw.noticeDays !== undefined) ? raw.noticeDays : 0,
      cycle: raw ? raw.cycle : "",
      nextRenewal: nextRenewal,
      anchorDay: anchorDay,
      status: raw ? raw.status : "",
      score: (raw && raw.score !== undefined && raw.score !== "") ? raw.score : null,
      notes: (raw && typeof raw.notes === "string") ? raw.notes : "",
      links: {
        manage: typeof links.manage === "string" ? links.manage : "",
        cancel: typeof links.cancel === "string" ? links.cancel : "",
        help: typeof links.help === "string" ? links.help : ""
      }
    };
    return { sub: sub, errors: validateSub(sub) };
  }

  /* Strict import: one bad record rejects the file, so a half-broken
     backup can never silently overwrite a good list. */
  function parseImport(text) {
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return { ok: false, errors: ["Not valid JSON: " + e.message] };
    }
    const list = Array.isArray(data) ? data : (data && Array.isArray(data.subs) ? data.subs : null);
    if (list === null) {
      return { ok: false, errors: ["Expected a JSON array of subscriptions, or an object with a \"subs\" array."] };
    }
    if (list.length > 500) {
      return { ok: false, errors: ["File holds " + list.length + " records; the limit is 500."] };
    }
    const subs = [];
    const errors = [];
    list.forEach(function (raw, i) {
      const result = normalizeSub(raw, "imp-" + (i + 1));
      if (result.errors.length > 0) {
        const rawName = (raw && typeof raw.name === "string") ? raw.name.trim() : "";
        const label = rawName
          ? (rawName.length > 60 ? rawName.slice(0, 60) + "..." : rawName)
          : ("record " + (i + 1));
        errors.push(label + ": " + result.errors[0]);
      } else {
        subs.push(result.sub);
      }
    });
    if (errors.length > 0) return { ok: false, errors: errors.slice(0, 5) };
    /* Null prototype so ids like "constructor" are not false duplicates. */
    const seen = Object.create(null);
    for (let i = 0; i < subs.length; i++) {
      if (seen[subs[i].id]) subs[i].id = subs[i].id + "-" + (i + 1);
      seen[subs[i].id] = true;
    }
    return { ok: true, subs: subs };
  }

  function makeExport(subs, exportedOnISO) {
    return JSON.stringify({ app: "sublist", version: 1, exportedOn: exportedOnISO, subs: subs }, null, 2);
  }

  /* ---------- filtering, sorting, stats ---------- */

  function filterSubs(subs, opts) {
    const status = opts.status || "all";
    const category = opts.category || "all";
    const query = (opts.query || "").trim().toLowerCase();
    return subs.filter(function (s) {
      if (status !== "all" && s.status !== status) return false;
      if (category !== "all" && s.category !== category) return false;
      if (query && (s.name + " " + s.owner).toLowerCase().indexOf(query) === -1) return false;
      return true;
    });
  }

  function sortSubs(subs, key, todayISO) {
    const copy = subs.slice();
    if (key === "name") {
      copy.sort(function (a, b) { return a.name.localeCompare(b.name); });
    } else if (key === "price") {
      copy.sort(function (a, b) {
        return monthlyCents(b.priceCents * b.seats, b.cycle) - monthlyCents(a.priceCents * a.seats, a.cycle);
      });
    } else if (key === "score") {
      copy.sort(function (a, b) { return (b.score || 0) - (a.score || 0); });
    } else {
      copy.sort(function (a, b) {
        const aEnded = a.status === "cancelled" ? 1 : 0;
        const bEnded = b.status === "cancelled" ? 1 : 0;
        if (aEnded !== bEnded) return aEnded - bEnded;
        return daysUntil(a.nextRenewal, todayISO) - daysUntil(b.nextRenewal, todayISO);
      });
    }
    return copy;
  }

  function stats(subs, todayISO) {
    let monthly = 0;
    let annual = 0;
    let active = 0;
    let dueSoon = 0;
    subs.forEach(function (s) {
      if (COUNTABLE.indexOf(s.status) === -1) return;
      monthly += monthlyCents(s.priceCents * s.seats, s.cycle);
      annual += annualCents(s.priceCents * s.seats, s.cycle);
      active += 1;
      if (daysUntil(s.nextRenewal, todayISO) <= 7) dueSoon += 1;
    });
    return { monthlyCents: monthly, annualCents: annual, activeCount: active, dueSoonCount: dueSoon };
  }

  function upcoming(subs, todayISO, windowDays) {
    const window = windowDays || 30;
    return subs
      .filter(function (s) { return COUNTABLE.indexOf(s.status) !== -1; })
      .map(function (s) { return { sub: s, days: daysUntil(s.nextRenewal, todayISO) }; })
      .filter(function (item) { return item.days <= window; })
      .sort(function (a, b) { return a.days - b.days; });
  }

  function countByStatus(subs) {
    const counts = { all: subs.length };
    STATUSES.forEach(function (st) { counts[st] = 0; });
    subs.forEach(function (s) { counts[s.status] += 1; });
    return counts;
  }

  /* Deterministic hash for picking a cover tint from a name. */
  function hashString(text) {
    let h = 5381;
    for (let i = 0; i < text.length; i++) {
      h = ((h << 5) + h + text.charCodeAt(i)) >>> 0;
    }
    return h;
  }

  /* ---------- sample data ----------
     A small company's stack, dated relative to today so the demo always
     has a renewal a few days out, one past due, and a notice deadline
     coming up. Prices are per seat per cycle. All people are fictional. */

  function sampleSubs(todayISO) {
    function day(offset) { return addDays(todayISO, offset); }
    function make(id, name, category, price, seats, cycle, offset, status, score, noticeDays, owner, links, notes) {
      const next = day(offset);
      return {
        id: id, name: name, category: category, priceCents: price, seats: seats,
        owner: owner, noticeDays: noticeDays, cycle: cycle,
        nextRenewal: next, anchorDay: parseISO(next).d, status: status,
        score: score, notes: notes || "", links: links
      };
    }
    return [
      make("smp-1", "Slack Business+", "Communication", 1800, 14, "monthly", 3, "active", 8, 0, "Dana Whitfield",
        { manage: "https://my.slack.com/admin/billing", cancel: "", help: "https://slack.com/help" }),
      make("smp-2", "Google Workspace", "Productivity", 1740, 16, "monthly", 11, "active", 9, 0, "Priya Nair",
        { manage: "https://admin.google.com", cancel: "", help: "https://support.google.com/a" }),
      make("smp-3", "GitHub Team", "Dev Tools", 550, 9, "monthly", 17, "active", 8, 0, "Marcus Lee",
        { manage: "https://github.com/settings/billing", cancel: "", help: "https://docs.github.com/billing" }),
      make("smp-4", "Adobe Creative Cloud Teams", "Design", 11999, 3, "monthly", -2, "active", 7, 0, "Renee Cormier",
        { manage: "https://adminconsole.adobe.com", cancel: "", help: "https://helpx.adobe.com" },
        "Three all-apps licences for the design pod."),
      make("smp-5", "Zoom Workplace Pro", "Communication", 21990, 6, "yearly", 143, "active", 6, 30, "Dana Whitfield",
        { manage: "https://zoom.us/billing", cancel: "", help: "https://support.zoom.com" }),
      make("smp-6", "1Password Business", "Security", 1050, 20, "monthly", 5, "trial", null, 0, "Alex Trinh",
        { manage: "https://start.1password.com", cancel: "", help: "https://support.1password.com" },
        "Company-wide trial. Decide before the first charge."),
      make("smp-7", "Claude Team", "AI Tools", 4200, 5, "monthly", 30, "considering", null, 0, "Jordan Bell",
        { manage: "https://claude.ai/settings/billing", cancel: "", help: "https://support.claude.com" }),
      make("smp-8", "Salesforce Sales Cloud", "Sales & CRM", 126000, 4, "yearly", 200, "active", 7, 60, "Mo Chen",
        { manage: "https://login.salesforce.com", cancel: "", help: "https://help.salesforce.com" }),
      make("smp-9", "QuickBooks Online Plus", "Finance & Accounting", 9900, 1, "monthly", 9, "active", 8, 0, "Mo Chen",
        { manage: "https://accounts.intuit.com", cancel: "", help: "https://quickbooks.intuit.com/learn-support" }),
      make("smp-10", "DocuSign Business Pro", "HR & Legal", 84000, 2, "yearly", 35, "review", 5, 30, "Sam Okafor",
        { manage: "https://account.docusign.com", cancel: "", help: "https://support.docusign.com" },
        "Usage dropped this year. Decide before the notice deadline."),
      make("smp-11", "Mailchimp Standard", "Marketing", 6000, 1, "monthly", -20, "cancelled", 4, 0, "Jordan Bell",
        { manage: "https://admin.mailchimp.com", cancel: "", help: "https://mailchimp.com/help" }),
      make("smp-12", "SnackBox Office Pantry", "Other", 8900, 1, "weekly", 2, "active", 7, 0, "Sam Okafor",
        { manage: "", cancel: "", help: "" },
        "Weekly pantry restock for the office.")
    ];
  }

  return {
    STATUSES: STATUSES,
    COUNTABLE: COUNTABLE,
    CYCLES: CYCLES,
    CATEGORIES: CATEGORIES,
    isLeap: isLeap,
    daysInMonth: daysInMonth,
    isValidISO: isValidISO,
    parseISO: parseISO,
    toISO: toISO,
    daysBetween: daysBetween,
    addDays: addDays,
    addMonthsAnchored: addMonthsAnchored,
    advanceRenewal: advanceRenewal,
    retreatRenewal: retreatRenewal,
    catchUp: catchUp,
    daysUntil: daysUntil,
    noticeDeadline: noticeDeadline,
    periodProgress: periodProgress,
    roundHalfUp: roundHalfUp,
    monthlyCents: monthlyCents,
    annualCents: annualCents,
    formatMoney: formatMoney,
    parsePrice: parsePrice,
    safeUrl: safeUrl,
    validateSub: validateSub,
    normalizeSub: normalizeSub,
    parseImport: parseImport,
    makeExport: makeExport,
    filterSubs: filterSubs,
    sortSubs: sortSubs,
    stats: stats,
    upcoming: upcoming,
    countByStatus: countByStatus,
    hashString: hashString,
    sampleSubs: sampleSubs
  };
})();

if (typeof window !== "undefined") window.SubLogic = SubLogic;
