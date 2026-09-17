"use strict";
(function () {
  var $ = V2.$, esc = V2.esc, gbp = V2.gbp;

  function boot(DATA) {
    /* ---- headline numbers already rendered server-side; charts below ---- */
    V2.lossChart($("#lossWrap"), DATA.lossRatio.years, true);
    V2.spark($("#sparkWrap"), DATA.monthly.counts, DATA.monthly.labels);
    V2.barList($("#causeBars"), DATA.causes.map(function (c) {
      return { label: c.cause, value: c.count, display: c.count, color: c.trainable ? "var(--c1)" : "var(--c4)", bold: c.trainable };
    }), { labelWidth: 240 });
    V2.barList($("#faultBars"), DATA.fault.map(function (f, i) {
      var tot = DATA.totals.totalClaims;
      return { label: f.label, value: f.count, display: f.count + " · " + Math.round(f.count / tot * 100) + "%", color: ["var(--c1)", "#9cc4d9", "var(--c4)", "var(--cmute)"][i % 4] };
    }), { labelWidth: 170 });
    V2.donut($("#donutWrap"), $("#donutLegend"), DATA.status.map(function (s) { return { label: s.label, value: s.count }; }), ["var(--c1)", "var(--c2)", "var(--c3)", "var(--cmute)"], "claims");
    V2.weeklyLine($("#weeklyWrap"), DATA.weekly.counts, DATA.weekly.labels, { label: "Claims notified per week" });

    /* ---- register: filter / sort / paginate the real claim rows ---- */
    var F = { year: {}, status: {}, fault: {}, depot: "All depots", q: "" };
    DATA.policyYears.forEach(function (y) { F.year[y] = true; });
    var SORT = { key: "sortDate", dir: -1 }, PAGE = 1, PER = 12, OPEN = null;
    var ROWS = DATA.rows;

    function statusGroup(s) { return s.indexOf("Open") === 0 ? "Open" : (s.indexOf("Litigated") === 0 ? "Litigated" : "Closed"); }
    function filtered() {
      return ROWS.filter(function (r) {
        if (!F.year[r.policyYear]) return false;
        var sKeys = Object.keys(F.status).filter(function (k) { return F.status[k]; });
        if (sKeys.length && !F.status[statusGroup(r.status)]) return false;
        var fKeys = Object.keys(F.fault).filter(function (k) { return F.fault[k]; });
        if (fKeys.length && !F.fault[r.fault]) return false;
        if (F.depot !== "All depots" && r.depot !== F.depot) return false;
        if (F.q) {
          var hay = (r.ref + " " + r.depot + " " + r.cause + " " + r.vehicleType).toLowerCase();
          if (hay.indexOf(F.q) < 0) return false;
        }
        return true;
      });
    }
    function sortedRows(rows) {
      var k = SORT.key, d = SORT.dir;
      return rows.slice().sort(function (a, b) {
        var x = a[k], y = b[k];
        if (typeof x === "string") return d * x.localeCompare(y);
        return d * ((x || 0) - (y || 0));
      });
    }
    function buildFilters() {
      var h = "";
      h += '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><span class="cap">Policy year</span>';
      DATA.policyYears.forEach(function (y) { h += '<button class="chip" type="button" data-f="year" data-v="' + y + '" aria-pressed="' + !!F.year[y] + '">' + y + "</button>"; });
      h += "</div>";
      h += '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><span class="cap">Status</span>';
      ["Open", "Closed", "Litigated"].forEach(function (s) { h += '<button class="chip" type="button" data-f="status" data-v="' + s + '" aria-pressed="' + !!F.status[s] + '">' + s + "</button>"; });
      h += "</div>";
      h += '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><span class="cap">Liability</span>';
      DATA.faultLabels.forEach(function (s) { h += '<button class="chip" type="button" data-f="fault" data-v="' + esc(s) + '" aria-pressed="' + !!F.fault[s] + '">' + esc(s) + "</button>"; });
      h += "</div>";
      h += '<label style="display:flex;align-items:center;gap:10px"><span class="cap">Depot</span><select id="fDepot">' +
        ["All depots"].concat(DATA.depots).map(function (d) { return '<option' + (F.depot === d ? " selected" : "") + ">" + esc(d) + "</option>"; }).join("") + "</select></label>";
      h += '<span style="flex:1 1 auto"></span><div class="sm num" id="fCount"></div>';
      h += '<button class="chip" type="button" id="fReset">Reset</button>';
      $("#filters").innerHTML = h;
      $("#fDepot").addEventListener("change", function (e) { F.depot = e.target.value; PAGE = 1; drawRegister(); });
      $("#fReset").addEventListener("click", function () {
        F.year = {}; DATA.policyYears.forEach(function (y) { F.year[y] = true; });
        F.status = {}; F.fault = {}; F.depot = "All depots"; F.q = ""; $("#q").value = ""; PAGE = 1;
        buildFilters(); drawRegister();
      });
      Array.prototype.forEach.call($("#filters").querySelectorAll("[data-f]"), function (b) {
        b.addEventListener("click", function () {
          var f = b.dataset.f, v = b.dataset.v;
          F[f][v] = !F[f][v];
          b.setAttribute("aria-pressed", String(!!F[f][v]));
          PAGE = 1; drawRegister();
        });
      });
    }
    var COLS = [
      { k: "ref", label: "Claim", sort: true },
      { k: "sortDate", label: "Loss date", sort: true },
      { k: "depot", label: "Depot", sort: true },
      { k: "vehicleType", label: "Vehicle", sort: true },
      { k: "cause", label: "Cause", sort: true },
      { k: "fault", label: "Liability", sort: false },
      { k: "status", label: "Status", sort: false },
      { k: "incurred", label: "Incurred", sort: true, r: true }
    ];
    function statusColor(s) { var g = statusGroup(s); return g === "Open" ? "var(--c2)" : (g === "Litigated" ? "var(--alert)" : "var(--ink2)"); }
    function drawRegister() {
      var rows = sortedRows(filtered()), total = ROWS.length;
      var pages = Math.max(1, Math.ceil(rows.length / PER));
      if (PAGE > pages) PAGE = pages;
      var slice = rows.slice((PAGE - 1) * PER, PAGE * PER);

      var h = "<thead><tr>";
      COLS.forEach(function (c) {
        var cur = SORT.key === c.k ? (SORT.dir === 1 ? "ascending" : "descending") : null;
        h += "<th" + (cur ? ' aria-sort="' + cur + '"' : "") + (c.r ? ' class="r"' : "") + ">";
        h += c.sort ? '<button type="button" data-sort="' + c.k + '">' + esc(c.label) + (cur ? (SORT.dir === 1 ? " ↑" : " ↓") : "") + "</button>" : esc(c.label);
        h += "</th>";
      });
      h += '<th><span class="vh">Cost breakdown</span></th></tr></thead><tbody>';
      if (!slice.length) {
        h += '<tr><td colspan="9" style="padding:40px 0"><div style="background:var(--panel);border-radius:12px;padding:26px 28px;display:flex;flex-direction:column;gap:10px;align-items:flex-start"><svg width="22" height="21" style="color:var(--line2)" aria-hidden="true"><use href="#mk"></use></svg><div class="h3">No claims match these filters</div><p class="sm">Reset them, or widen the policy year.</p></div></td></tr>';
      }
      slice.forEach(function (r) {
        var open = OPEN === r.ref;
        h += "<tr>";
        h += '<td class="num" style="font-weight:' + (open ? 700 : 600) + '">' + esc(r.ref) + "</td>";
        h += '<td class="num">' + esc(r.dateLabel) + "</td>";
        h += '<td style="color:var(--ink2)">' + esc(r.depot) + "</td>";
        h += '<td style="color:var(--ink2)">' + esc(r.vehicleType || "—") + "</td>";
        h += '<td style="color:var(--ink2)">' + esc(r.cause) + "</td>";
        h += '<td style="color:var(--ink2)">' + esc(r.fault) + "</td>";
        h += '<td style="color:' + statusColor(r.status) + ';font-weight:600">' + esc(r.status) + "</td>";
        h += '<td class="num r" style="font-weight:' + (open ? 700 : 600) + '">' + gbp(r.incurred) + "</td>";
        h += '<td class="r"><button class="exp" type="button" data-open="' + esc(r.ref) + '" aria-expanded="' + open + '" aria-label="Detail for ' + esc(r.ref) + '"><svg class="ic" style="width:13px;height:13px" aria-hidden="true"><use href="#i-chev"></use></svg></button></td>';
        h += "</tr>";
        if (open) {
          var pct = r.incurred ? Math.max(0, Math.min(100, r.paid / r.incurred * 100)) : 0;
          h += '<tr><td colspan="9" style="border-bottom:0;padding:4px 0 22px"><div class="brk">';
          h += '<div><div class="h3">Reserve position</div><div style="margin-top:14px"><div class="kv"><span class="bdy" style="color:var(--ink2)">Paid to date</span><span class="bdy num" style="font-weight:600">' + gbp(r.paid) + '</span></div>' +
            '<div class="kv"><span class="bdy" style="color:var(--ink2)">Outstanding reserve</span><span class="bdy num" style="font-weight:600">' + gbp(r.reserve) + '</span></div>' +
            '<div class="kv" style="border-bottom:0;padding-top:14px"><span class="bdy" style="font-weight:700">Total incurred</span><span class="num" style="font-size:20px;font-weight:800">' + gbp(r.incurred) + "</span></div></div></div>";
          h += '<div style="display:flex;flex-direction:column;gap:22px"><div><div class="cap">Paid against reserve</div>' +
            '<div style="height:24px;background:var(--ground);border-radius:4px;display:flex;gap:2px;overflow:hidden;margin-top:12px">' +
            '<div style="width:' + pct.toFixed(1) + '%;background:var(--c1)"></div><div style="width:' + (100 - pct).toFixed(1) + '%;background:#9cc4d9"></div></div>' +
            '<div style="display:flex;justify-content:space-between;margin-top:10px"><span class="sm num">Paid ' + gbp(r.paid) + '</span><span class="sm num">Reserve ' + gbp(r.reserve) + "</span></div></div>" +
            '<div class="grid2" style="--cols:minmax(0,1fr) minmax(0,1fr);gap:18px">' +
            '<div><div class="cap">Own damage</div><div class="bdy" style="margin-top:4px">' + esc(r.ownDamage || "—") + "</div></div>" +
            '<div><div class="cap">Driver age band</div><div class="bdy num" style="margin-top:4px">' + esc(r.ageBand || "Not recorded") + "</div></div>" +
            '<div><div class="cap">Days open</div><div class="bdy num" style="margin-top:4px">' + r.daysOpen + "</div></div>" +
            '<div><div class="cap">Policy year</div><div class="bdy num" style="margin-top:4px">' + esc(r.policyYear) + "</div></div></div></div>";
          h += "</div></td></tr>";
        }
      });
      h += "</tbody>";
      $("#reg").innerHTML = h;

      var cnt = "Showing <strong style=\"color:var(--ink)\">" + rows.length + "</strong> of <strong style=\"color:var(--ink)\">" + total + "</strong>";
      if ($("#fCount")) $("#fCount").innerHTML = cnt;
      $("#regCount").textContent = rows.length ? ((PAGE - 1) * PER + 1) + "–" + Math.min(PAGE * PER, rows.length) + " of " + rows.length : "0 of " + total;
      $("#pageInfo").textContent = "Page " + PAGE + " of " + pages;

      var p = "";
      p += '<button class="chip" type="button" data-page="' + (PAGE - 1) + '"' + (PAGE === 1 ? " disabled style=\"opacity:.45;cursor:default\"" : "") + ">Previous</button>";
      var show = [1, 2, PAGE - 1, PAGE, PAGE + 1, pages - 1, pages].filter(function (n, i, a) { return n >= 1 && n <= pages && a.indexOf(n) === i; }).sort(function (a, b) { return a - b; });
      var last = 0;
      show.forEach(function (n) {
        if (n - last > 1) p += '<span class="sm num" style="padding:0 4px">…</span>';
        p += '<button class="chip num" type="button" data-page="' + n + '"' + (n === PAGE ? ' aria-current="page" style="border-color:var(--ink);background:var(--ink);color:var(--ground)"' : "") + ">" + n + "</button>";
        last = n;
      });
      p += '<button class="chip" type="button" data-page="' + (PAGE + 1) + '"' + (PAGE === pages ? " disabled style=\"opacity:.45;cursor:default\"" : "") + ">Next</button>";
      $("#pager").innerHTML = p;
    }
    document.addEventListener("click", function (e) {
      var t = e.target.closest ? e.target.closest("[data-sort],[data-page],[data-open]") : null;
      if (!t) return;
      if (t.dataset.sort) { var k = t.dataset.sort; if (SORT.key === k) SORT.dir *= -1; else { SORT.key = k; SORT.dir = (k === "incurred" || k === "sortDate") ? -1 : 1; } PAGE = 1; drawRegister(); }
      else if (t.dataset.page) { var n = +t.dataset.page; if (n >= 1) { PAGE = n; OPEN = null; drawRegister(); } }
      else if (t.dataset.open) { OPEN = OPEN === t.dataset.open ? null : t.dataset.open; drawRegister(); }
    });
    $("#q").addEventListener("input", function (e) { F.q = e.target.value.trim().toLowerCase(); PAGE = 1; drawRegister(); });

    buildFilters();
    drawRegister();
    V2.reveal(document);
  }

  window.V2ClaimsInit = boot;
})();
