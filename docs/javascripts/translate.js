// Optional page translation (Google Translate engine, own language picker with native language names).
// Nothing from Google is loaded until a visitor picks a language (or has picked one before: cookie "googtrans").
(function () {
  var LANGS = [
    ["en", "English"], ["de", "Deutsch"], ["fr", "Français"], ["it", "Italiano"], ["es", "Español"], ["pt", "Português"],
    ["tr", "Türkçe"], ["ar", "العربية"], ["ru", "Русский"], ["uk", "Українська"], ["zh-CN", "中文"], ["hi", "हिन्दी"],
    ["sq", "Shqip"], ["bg", "Български"]
  ];
  var loaded = false;

  function current() {
    var m = document.cookie.match(/(?:^|;\s*)googtrans=\/[^/]*\/([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function setLang(code) {
    var host = location.hostname;
    var expire = "; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    // clear on every plausible scope first, then set
    document.cookie = "googtrans=" + expire + "; path=/";
    document.cookie = "googtrans=" + expire + "; path=/; domain=" + host;
    if (code) {
      document.cookie = "googtrans=/el/" + code + "; path=/";
      document.cookie = "googtrans=/el/" + code + "; path=/; domain=" + host;
    }
    location.reload();
  }

  function markNoTranslate() {
    document.querySelectorAll("pre, code, mjx-container, .arithmatex, .md-search, .md-header__source, #ceid-translate").forEach(function (el) {
      el.classList.add("notranslate");
    });
  }

  function load() {
    if (loaded) return;
    loaded = true;
    markNoTranslate();
    window.ceidTranslateInit = function () {
      new window.google.translate.TranslateElement({ pageLanguage: "el", includedLanguages: LANGS.map(function (l) { return l[0]; }).join(","), autoDisplay: false }, "ceid-translate-engine");
    };
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://translate.google.com/translate_a/element.js?cb=ceidTranslateInit&hl=en";
    document.head.appendChild(s);
  }

  function build() {
    var wrap = document.createElement("div");
    wrap.id = "ceid-translate";
    wrap.className = "notranslate";
    wrap.setAttribute("translate", "no");
    // inline styles: must stay a floating corner control even when a browser holds an older stylesheet
    wrap.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:2147483000;max-width:280px;font:13px/1.3 system-ui,sans-serif;text-align:right";

    var sel = document.createElement("select");
    sel.setAttribute("aria-label", "Language / Γλώσσα");
    sel.style.cssText = "cursor:pointer;border:1px solid #888;border-radius:999px;padding:8px 12px;background:#fff;color:#222;box-shadow:0 2px 8px rgba(0,0,0,.25);font:inherit;max-width:100%";
    var cur = current();
    var first = document.createElement("option");
    first.value = "";
    first.textContent = cur ? "Ελληνικά (original)" : "🌐 Language / Γλώσσα";
    sel.appendChild(first);
    LANGS.forEach(function (l) {
      var o = document.createElement("option");
      o.value = l[0];
      o.textContent = l[1];
      if (l[0] === cur) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener("change", function () { setLang(sel.value); });

    var note = document.createElement("div");
    note.textContent = "Automatic translation by Google. Exam questions are in Greek; translation may contain errors.";
    note.style.cssText = "margin-top:4px;padding:4px 8px;border-radius:6px;background:#fff;color:#444;box-shadow:0 2px 8px rgba(0,0,0,.15)";
    note.hidden = !cur;

    var engine = document.createElement("div");
    engine.id = "ceid-translate-engine";
    engine.style.display = "none";

    wrap.appendChild(sel);
    wrap.appendChild(note);
    wrap.appendChild(engine);
    document.body.appendChild(wrap);
    if (cur) load();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
