"use strict";
/* Shared drawing helpers for the Aster* v2 concept pages — ported from the
   Aster-concept.html mockup, but generalised to draw from real data passed
   in from Flask (server-computed aggregates), rather than a client-side
   fake dataset. Scales are computed from the data instead of hardcoded. */
var V2 = (function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var gbp = function (n) { return "£" + Math.round(n).toLocaleString("en-GB"); };
  var gbpK = function (n) { return "£" + Math.round(n / 1000) + "k"; };
  var RM = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function svg(vb, w, h, body, label) {
    return '<svg viewBox="' + vb + '" width="' + w + '" height="' + h + '" role="img" aria-label="' + esc(label) + '" style="display:block;max-width:100%">' + body + "</svg>";
  }
  function niceMax(v) {
    if (v <= 0) return 1;
    var mag = Math.pow(10, Math.floor(Math.log(v) / Math.LN10));
    var n = v / mag;
    var step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
    return step * mag;
  }

  /* ---------- five-spoke mark (radial risk breakdown) ---------- */
  function spokePts(cx, cy, ang, L, hw, tw) {
    var a = ang * Math.PI / 180, ux = Math.sin(a), uy = -Math.cos(a), px = uy, py = -ux;
    var p = [[cx + px * hw, cy + py * hw], [cx + ux * L + px * tw, cy + uy * L + py * tw], [cx + ux * L - px * tw, cy + uy * L - py * tw], [cx - px * hw, cy - py * hw]];
    return p.map(function (q) { return q[0].toFixed(1) + "," + q[1].toFixed(1); }).join(" ");
  }
  function tipXY(cx, cy, ang, L) { var a = ang * Math.PI / 180; return [cx + Math.sin(a) * L, cy - Math.cos(a) * L]; }
  function renderMark(el, domains, maxAbs) {
    var cx = 230, cy = 130, MAX = 104, HUB = 16, hw = 5.5, tw = 13, s = "";
    var med = domains.map(function (d) { var L = HUB + (MAX - HUB) * Math.abs(d.med) / maxAbs; return tipXY(cx, cy, d.ang, L); });
    s += '<polygon fill="none" stroke="var(--ink3)" stroke-width="1.3" stroke-dasharray="5 4" points="' +
      med.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ") + '"></polygon>';
    domains.forEach(function (d) {
      var L = HUB + (MAX - HUB) * Math.abs(d.pts) / maxAbs;
      s += '<polygon class="' + d.cls + '" points="' + spokePts(cx, cy, d.ang, L, hw, tw) + '"><title>' + esc(d.label) + " " + (d.pts > 0 ? "+" : "−") + Math.abs(Math.round(d.pts)) + ' points</title></polygon>';
    });
    s += '<circle cx="230" cy="130" r="4.5" fill="var(--ink)" stroke="var(--gap)" stroke-width="2"></circle>';
    domains.forEach(function (d) {
      var L = HUB + (MAX - HUB) * Math.abs(d.pts) / maxAbs, t = tipXY(cx, cy, d.ang, L + 20);
      var anch = d.ang === 0 ? "middle" : (d.ang < 180 ? "start" : "end");
      s += '<text x="' + t[0].toFixed(1) + '" y="' + t[1].toFixed(1) + '" text-anchor="' + anch + '" font-size="13" font-weight="600" fill="var(--ink)">' +
        esc(d.label) + ' <tspan fill="var(--ink3)" style="font-variant-numeric:tabular-nums">' + (d.pts > 0 ? "+" : "−") + Math.abs(Math.round(d.pts)) + '</tspan></text>';
    });
    el.innerHTML = '<svg viewBox="-70 10 600 240" style="width:100%;height:auto" role="img" aria-label="Radial risk breakdown">' + s + "</svg>";
  }
  function glyph(values, cls, maxAbs, size) {
    size = size || 60;
    var c = size / 2, MAX = size * 0.4375, HUB = size * 0.073, hw = size * 0.0333, tw = size * 0.0875, s = "";
    values.forEach(function (v, i) {
      if (!v) return;
      var L = HUB + (MAX - HUB) * Math.abs(v) / maxAbs;
      s += '<polygon class="' + cls[i] + '" points="' + spokePts(c, c, [0, 72, 144, 216, 288][i], L, hw, tw) + '"></polygon>';
    });
    return '<svg class="mini" viewBox="0 0 ' + size + ' ' + size + '" width="60" height="60" aria-hidden="true">' + s + "</svg>";
  }

  /* ---------- growable bars ---------- */
  function reveal(root) {
    Array.prototype.forEach.call(root.querySelectorAll(".drawn"), function (elx) { elx.classList.add("go"); });
    Array.prototype.forEach.call(root.querySelectorAll(".growy"), function (elx, i) { setTimeout(function () { elx.classList.add("go"); }, i * 30); });
    Array.prototype.forEach.call(root.querySelectorAll(".growx"), function (elx, i) {
      var w = elx.dataset.w; setTimeout(function () { elx.firstElementChild.style.width = w; }, i * 35);
    });
  }

  /* ---------- generic horizontal bar list (cause / fault breakdowns) ---------- */
  function barList(el, rows, opts) {
    opts = opts || {};
    var mx = niceMax(Math.max.apply(null, rows.map(function (r) { return r.value; })));
    var h = "";
    rows.forEach(function (r) {
      var w = (r.value / mx * 100).toFixed(1) + "%";
      h += '<div style="display:flex;align-items:center;gap:14px">' +
        '<div class="bdy" style="flex:0 0 ' + (opts.labelWidth || 202) + 'px;font-weight:' + (r.bold === false ? 400 : 600) + ';color:' + (r.muted ? "var(--ink3)" : "var(--ink)") + '">' + esc(r.label) + "</div>" +
        '<div class="trk growx" data-w="' + w + '"><i style="background:' + r.color + '"><span class="vh">' + r.value + "</span></i></div>" +
        '<div class="bdy num" style="flex:0 0 40px;text-align:right;font-weight:700">' + r.display + "</div></div>";
    });
    el.innerHTML = h;
  }

  /* ---------- donut ---------- */
  function donut(elChart, elLegend, rows, colors, centreLabel) {
    var total = rows.reduce(function (a, r) { return a + r.value; }, 0) || 1;
    var r = 58, C = 2 * Math.PI * r, off = 0, b = "";
    b += '<g transform="rotate(-90 100 100)" fill="none" stroke-width="18">';
    rows.forEach(function (row, i) {
      var seg = C * row.value / total;
      b += '<circle cx="100" cy="100" r="' + r + '" stroke="' + colors[i % colors.length] + '" stroke-dasharray="' + Math.max(0, seg - (rows.length > 1 ? 3 : 0)).toFixed(1) + " " + (C - seg + 3).toFixed(1) + '" stroke-dashoffset="' + (-off).toFixed(1) + '"><title>' + esc(row.label) + " — " + row.value + '</title></circle>';
      off += seg;
    });
    b += "</g>";
    b += '<text x="100" y="97" text-anchor="middle" font-size="34" font-weight="800" fill="var(--ink)" style="font-variant-numeric:tabular-nums">' + total + "</text>";
    b += '<text class="axis" x="100" y="118" text-anchor="middle" font-size="13" font-weight="600">' + esc(centreLabel || "total") + "</text>";
    elChart.innerHTML = svg("0 0 200 200", 180, 180, b, "Donut breakdown");
    if (elLegend) {
      var l = "";
      rows.forEach(function (row, i) {
        l += '<div style="display:flex;align-items:center;gap:10px"><span class="sw" style="width:13px;height:13px;border-radius:3px;background:' + colors[i % colors.length] + '"></span><span class="bdy" style="flex:1 1 auto">' + esc(row.label) + '</span><span class="bdy num" style="font-weight:700">' + row.value + "</span></div>";
      });
      elLegend.innerHTML = l;
    }
  }

  /* ---------- loss ratio bar chart, policy years, dashed part-year ---------- */
  function lossChart(el, years, currentIsPartYear) {
    var maxv = niceMax(Math.max.apply(null, years.map(function (y) { return Math.max(y.premium, y.incurred); })) * 1.15);
    var x0 = 64, x1 = 690, yb = 176, yt = 40, b = "";
    [0, 0.33, 0.67, 1].forEach(function (f) {
      var v = maxv * f, y = yb - (yb - yt) * f;
      b += '<line class="gridln" x1="' + x0 + '" y1="' + y + '" x2="' + x1 + '" y2="' + y + '"></line>';
      b += '<text class="axis" x="54" y="' + (y + 4) + '" text-anchor="end">' + (v ? "£" + (v / 1e6).toFixed(1) + "m" : "£0") + "</text>";
    });
    var gw = (x1 - x0) / years.length;
    years.forEach(function (y, i) {
      var gx = x0 + i * gw, bw = Math.min(52, gw / 2 - 8), h1 = (yb - yt) * y.premium / maxv, h2 = (yb - yt) * y.incurred / maxv;
      var isPart = currentIsPartYear && i === years.length - 1;
      var dash = isPart ? ' fill-opacity=".5" stroke-width="1.5" stroke-dasharray="4 3"' : "";
      b += '<rect class="growy" x="' + (gx + gw / 2 - bw - 4) + '" y="' + (yb - h1) + '" width="' + bw + '" height="' + h1 + '" rx="4" fill="var(--c4)"' + (isPart ? ' stroke="var(--c4)"' + dash : "") + '><title>' + y.label + " earned premium " + gbp(y.premium) + "</title></rect>";
      b += '<rect class="growy" x="' + (gx + gw / 2 + 4) + '" y="' + (yb - h2) + '" width="' + bw + '" height="' + h2 + '" rx="4" fill="var(--c1)"' + (isPart ? ' stroke="var(--c1)"' + dash : "") + '><title>' + y.label + " incurred " + gbp(y.incurred) + "</title></rect>";
      b += '<text x="' + (gx + gw / 2 - 4) + '" y="' + (yb - Math.max(h1, h2) - 12) + '" text-anchor="middle" font-size="16" font-weight="700" fill="' + (y.lr >= y.target ? "var(--ink)" : "var(--ink2)") + '">' + y.lr.toFixed(1) + "%</text>";
      b += '<text x="' + (gx + gw / 2 - 4) + '" y="196" text-anchor="middle" font-size="13" font-weight="600" fill="var(--ink)">' + y.label + "</text>";
      if (isPart) b += '<text class="axis" x="' + (gx + gw / 2 - 4) + '" y="211" text-anchor="middle" font-size="11">part year, earned pro rata</text>';
    });
    b += '<g transform="translate(64 220)"><rect x="0" y="0" width="15" height="10" rx="2" fill="var(--c4)"></rect><text class="axis" x="22" y="9">Earned premium</text>' +
      '<rect x="140" y="0" width="15" height="10" rx="2" fill="var(--c1)"></rect><text class="axis" x="162" y="9">Incurred</text>' +
      (currentIsPartYear ? '<text class="axis" x="248" y="9">Dashed bars are the part year</text>' : "") + '</g>';
    el.innerHTML = svg("0 0 708 232", 708, 232, b, "Loss ratio by policy year");
  }

  /* ---------- monthly sparkline ---------- */
  function spark(el, values, labels, color) {
    var mx = niceMax(Math.max.apply(null, values));
    var x0 = 4, x1 = 296, yb = 60, yt = 10, b = "";
    var pts = values.map(function (v, i) { return [x0 + i * (x1 - x0) / (values.length - 1), yb - (yb - yt) * v / mx]; });
    b += '<line class="gridln" x1="0" y1="60" x2="300" y2="60"></line>';
    b += '<polyline class="drawn" style="--len:420" points="' + pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ") + '" fill="none" stroke="' + (color || "var(--c1)") + '" stroke-width="2" stroke-linejoin="round"></polyline>';
    var last = pts[pts.length - 1];
    b += '<circle cx="' + last[0].toFixed(1) + '" cy="' + last[1].toFixed(1) + '" r="4" fill="var(--ink)"><title>' + labels[labels.length - 1] + " — " + values[values.length - 1] + '</title></circle>';
    el.innerHTML = svg("0 0 300 70", "100%", 70, b, "Monthly trend");
  }

  /* ---------- weekly line, with an optional highlighted band ---------- */
  function weeklyLine(el, values, labels, opts) {
    opts = opts || {};
    var lo = Math.min.apply(null, values), hi = Math.max.apply(null, values);
    var pad = Math.max(1, (hi - lo) * 0.25); lo = Math.max(0, Math.floor(lo - pad)); hi = Math.ceil(hi + pad);
    var x0 = 54, x1 = 1082, yb = 166, yt = 28, b = "";
    var Y = function (v) { return yb - (yb - yt) * (v - lo) / (hi - lo || 1); };
    var steps = 5, stepv = niceMax((hi - lo) / steps) || 1;
    for (var v = Math.ceil(lo / stepv) * stepv; v <= hi; v += stepv) {
      b += '<line class="gridln" x1="54" y1="' + Y(v).toFixed(1) + '" x2="1082" y2="' + Y(v).toFixed(1) + '"></line>';
      b += '<text class="axis" x="44" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end">' + Math.round(v) + "</text>";
    }
    var pts = values.map(function (val, i) { return [x0 + i * (x1 - x0) / (values.length - 1), Y(val)]; });
    b += '<polyline class="drawn" style="--len:1300" points="' + pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ") + '" fill="none" stroke="var(--c1)" stroke-width="2.5" stroke-linejoin="round"></polyline>';
    pts.forEach(function (p, i) {
      if (i === pts.length - 1) return;
      b += '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="4" fill="var(--ground)" stroke="var(--c1)" stroke-width="2"><title>' + esc(labels[i]) + " — " + values[i] + '</title></circle>';
    });
    var lastp = pts[pts.length - 1];
    b += '<circle cx="' + lastp[0].toFixed(1) + '" cy="' + lastp[1].toFixed(1) + '" r="5.5" fill="var(--ink)" stroke="var(--ground)" stroke-width="2"><title>' + esc(labels[labels.length - 1]) + " — " + values[values.length - 1] + '</title></circle>';
    b += '<text x="' + lastp[0].toFixed(1) + '" y="' + (lastp[1] - 14).toFixed(1) + '" text-anchor="end" font-size="15" font-weight="800" fill="var(--ink)">' + values[values.length - 1] + "</text>";
    var everyN = Math.ceil(labels.length / 6);
    labels.forEach(function (lab, i) { if (i % everyN === 0 || i === labels.length - 1) b += '<text class="axis" x="' + pts[i][0].toFixed(1) + '" y="190" text-anchor="middle">' + esc(lab) + "</text>"; });
    el.innerHTML = svg("0 0 1100 214", "100%", 214, b, opts.label || "Weekly trend");
  }

  /* ---------- schematic GB map, real depots ---------- */
  var GB_OUTLINE = "M95.9,4.8 L59.2,9.6 L42.3,4.8 L31,24 L19.7,52.8 L22.6,67.2 L16.9,91.2 L14.1,100.8 L19.7,129.6 L25.4,163.2 L42.3,177.6 L45.1,182.4 L81.8,187.2 L93.1,216 L95.9,235.2 L93.1,254.4 L53.6,259.2 L50.8,278.4 L67.7,302.4 L33.9,326.4 L56.4,340.8 L87.5,350.4 L98.7,360 L64.9,360 L39.5,398.4 L22.6,412.8 L42.3,408 L67.7,393.6 L87.5,388.8 L101.6,384 L129.8,379.2 L152.4,379.2 L174.9,374.4 L200.3,374.4 L222.9,364.8 L222.9,350.4 L211.6,331.2 L217.2,321.6 L231.4,297.6 L211.6,278.4 L191.9,273.6 L186.2,259.2 L180.6,244.8 L180.6,220.8 L163.6,201.6 L143.9,177.6 L135.4,148.8 L110,129.6 L98.7,124.8 L104.4,110.4 L112.9,96 L124.1,72 L127,48 L98.7,48 L95.9,28.8 Z";
  var GB_NODES = {
    "Glasgow": [63.5, 96.3], "Newcastle": [128, 172], "Leeds": [139.7, 235.2],
    "Manchester": [120.2, 250.6], "Birmingham": [129.8, 298.6], "Bristol": [110.3, 348]
  };
  function ukMap(elMap, elTable, depotAgg) {
    var maxClaims = Math.max.apply(null, depotAgg.map(function (d) { return d.claims; }));
    var hub = depotAgg.slice().sort(function (a, b) { return b.claims - a.claims; })[0];
    var b = '<path d="' + GB_OUTLINE + '" fill="none" stroke="var(--link)" stroke-opacity=".38" stroke-width="1.15"></path>';
    b += '<g fill="none" stroke="var(--link)" stroke-opacity=".26" stroke-width="1.15" stroke-dasharray="5 5">';
    depotAgg.forEach(function (d) {
      if (d.depot === hub.depot || !GB_NODES[d.depot] || !GB_NODES[hub.depot]) return;
      var p0 = GB_NODES[hub.depot], p1 = GB_NODES[d.depot];
      var mx = (p0[0] + p1[0]) / 2 - (p1[1] - p0[1]) * 0.12, my = (p0[1] + p1[1]) / 2 + (p1[0] - p0[0]) * 0.12;
      b += '<path class="drawn" style="--len:180" d="M' + p0[0] + ',' + p0[1] + ' Q' + mx.toFixed(1) + ',' + my.toFixed(1) + ' ' + p1[0] + ',' + p1[1] + '"></path>';
    });
    b += "</g>";
    depotAgg.forEach(function (d) {
      var xy = GB_NODES[d.depot]; if (!xy) return;
      var r = 15 * Math.sqrt(d.claims / maxClaims);
      b += '<circle cx="' + xy[0] + '" cy="' + xy[1] + '" r="' + r.toFixed(1) + '" fill="var(--c1)"><title>' + esc(d.depot) + " — " + d.claims + " claims, " + gbpK(d.incurred) + " incurred</title></circle>";
      b += '<text x="' + xy[0] + '" y="' + (xy[1] + 4) + '" text-anchor="middle" font-size="11" font-weight="700" fill="var(--ground)" style="font-variant-numeric:tabular-nums">' + d.claims + "</text>";
    });
    elMap.innerHTML = svg("-8 -8 256 440", 330, 567, b, "Schematic map of six depots sized by claim count");
    if (elTable) {
      var h = '<thead><tr><th>Depot</th><th class="r">Claims</th><th class="r">Incurred</th><th class="r">Per 100 vehicles</th></tr></thead><tbody>';
      var top2 = depotAgg.slice().sort(function (a, b) { return b.claims - a.claims; }).slice(0, 2).map(function (d) { return d.depot; });
      depotAgg.slice().sort(function (a, b) { return b.claims - a.claims; }).forEach(function (d) {
        var w = top2.indexOf(d.depot) >= 0 ? "700" : "400";
        var per100 = d.vehicles ? (d.claims / d.vehicles * 100).toFixed(1) : "—";
        h += '<tr><td style="font-weight:' + w + '">' + esc(d.depot) + '</td><td class="num r" style="font-weight:' + w + '">' + d.claims + '</td><td class="num r" style="font-weight:' + w + '">' + gbpK(d.incurred) + '</td><td class="num r" style="font-weight:' + w + '">' + per100 + "</td></tr>";
      });
      elTable.innerHTML = h + "</tbody>";
    }
  }

  return {
    $: $, esc: esc, gbp: gbp, gbpK: gbpK, RM: RM, svg: svg, niceMax: niceMax,
    spokePts: spokePts, tipXY: tipXY, renderMark: renderMark, glyph: glyph, reveal: reveal,
    barList: barList, donut: donut, lossChart: lossChart, spark: spark, weeklyLine: weeklyLine, ukMap: ukMap
  };
})();
