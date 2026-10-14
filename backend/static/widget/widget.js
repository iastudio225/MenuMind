/* RestoIA — chargeur du widget embarquable.
   Usage : <script src="https://API_ORIGIN/widget.js" data-restaurant="rest_xxx"></script>
   Chaque balise script = un widget isolé (iframe same-origin API, zéro conflit CSS/JS hôte). */
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script) return;
  var restaurantId = script.getAttribute("data-restaurant");
  if (!restaurantId) return;
  var apiOrigin;
  try {
    apiOrigin = new URL(script.src).origin;
  } catch (e) {
    return;
  }

  var iframe = document.createElement("iframe");
  iframe.src = apiOrigin + "/widget-frame.html?restaurant=" + encodeURIComponent(restaurantId);
  iframe.title = "Assistant de commande";
  iframe.setAttribute("aria-label", "Assistant de commande " + restaurantId);
  iframe.style.cssText =
    "position:fixed;bottom:20px;right:20px;width:64px;height:64px;border:0;" +
    "z-index:2147483000;box-shadow:none;background:transparent;";
  iframe.allow = "";

  window.addEventListener("message", function (event) {
    if (event.origin !== apiOrigin) return;
    var data = event.data;
    if (!data || data.type !== "restoia-widget-size") return;
    if (typeof data.width === "number" && typeof data.height === "number") {
      iframe.style.width = data.width + "px";
      iframe.style.height = data.height + "px";
    }
  });

  function mount() {
    (document.body || document.documentElement).appendChild(iframe);
  }
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();
