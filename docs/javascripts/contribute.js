// Header call to action: a pulsing "Συνεισφορά" button next to the search box (all pages).
(function () {
  function add() {
    var inner = document.querySelector(".md-header__inner");
    if (!inner || inner.querySelector(".ceid-contribute")) return;
    var a = document.createElement("a");
    a.className = "ceid-contribute";
    a.href = "https://ceid.gr/contribute.html";
    a.innerHTML = "<span>Συνεισφορά</span>";
    a.title = "Ανέβασε θέματα ή διόρθωσε λάθη";
    var search = inner.querySelector(".md-search");
    inner.insertBefore(a, search || inner.querySelector(".md-header__source"));
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add); else add();
})();
