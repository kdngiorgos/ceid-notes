// Anonymous, cookie-free usage counts (GoatCounter). Page views + one event per file download (pdf/zip/release asset).
(function () {
  var s = document.createElement("script");
  s.async = true;
  s.src = "https://gc.zgo.at/count.js";
  s.setAttribute("data-goatcounter", "https://kdngiorgos.goatcounter.com/count");
  document.head.appendChild(s);
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    var href = a.getAttribute("href") || "";
    if (!/\.(pdf|zip|xlsx?|docx?|pptx?)(\?|#|$)/i.test(href) && href.indexOf("/releases/") === -1) return;
    var name = decodeURIComponent(href.split("?")[0].split("/").pop() || href);
    if (window.goatcounter && window.goatcounter.count) {
      window.goatcounter.count({ path: "download/" + name, title: "Download " + name, event: true });
    }
  }, true);
})();
