/*
 * Shared hover tooltip for the hand-drawn SVG charts across the app.
 *
 * The charts themselves stay exactly as designed — plain SVG shapes with
 * pixel geometry computed server-side (see app.py) — so the visual design
 * matches the original concept mockup exactly. This file only adds the
 * same interaction the mockup itself used: a single floating tooltip div
 * positioned on mousemove, plus a subtle hover highlight, wired up
 * generically to any element carrying data-tip-label / data-tip-value.
 */
(function () {
  "use strict";

  var tip = document.getElementById("chart-tooltip");
  if (!tip) return;

  function positionTip(evt) {
    var x = evt.clientX + 14;
    var y = evt.clientY + 14;
    var maxX = window.innerWidth - 260;
    var maxY = window.innerHeight - 100;
    if (x > maxX) x = evt.clientX - 254;
    if (y > maxY) y = evt.clientY - 90;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }

  function showTip(label, value, evt) {
    tip.innerHTML = "<b>" + label + "</b><br>" + value;
    tip.style.display = "block";
    positionTip(evt);
  }

  function hideTip() {
    tip.style.display = "none";
  }

  document.addEventListener("mousemove", function (e) {
    if (tip.style.display === "block") positionTip(e);
  });

  function wireTooltips(root) {
    (root || document).querySelectorAll("[data-tip-label]").forEach(function (el) {
      if (el._tipWired) return;
      el._tipWired = true;

      var isCircle = el.tagName.toLowerCase() === "circle";
      var baseR = isCircle ? parseFloat(el.getAttribute("r")) || 3.5 : null;

      el.addEventListener("mousemove", function (e) {
        el.classList.add("is-hovered");
        if (isCircle) el.setAttribute("r", baseR + 1.5);
        showTip(el.getAttribute("data-tip-label"), el.getAttribute("data-tip-value"), e);
      });
      el.addEventListener("mouseleave", function () {
        el.classList.remove("is-hovered");
        if (isCircle) el.setAttribute("r", baseR);
        hideTip();
      });

      var href = el.getAttribute("data-href");
      if (href) {
        el.addEventListener("click", function () {
          window.location.href = href;
        });
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireTooltips(document);
  });

  window.AsterTooltips = { wire: wireTooltips };
})();
