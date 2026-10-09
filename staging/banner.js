/* PLAT-35: visible label for an isolated, disposable Server frontend only. */
(function () {
  "use strict";
  var banner = document.createElement("div");
  banner.id = "ai-compass-staging-label";
  banner.setAttribute("role", "status");
  banner.style.cssText = "position:fixed;top:0;left:50%;transform:translateX(-50%);z-index:999999;background:#8a2525;color:#fff;padding:8px 22px;border-radius:0 0 10px 10px;font:bold 13px system-ui;box-shadow:0 3px 18px #0005;pointer-events:none";
  banner.textContent = "STAGING · ISOLATED COPY · NOT PRODUCTION";
  document.body.appendChild(banner);
})();
