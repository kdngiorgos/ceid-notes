// Optional page translation (Google Translate widget). Nothing from Google is loaded until the visitor clicks the button,
// or has chosen a language before (cookie "googtrans" set by the widget itself).
(function () {
  var LANGS = "en,de,fr,it,es,pt,tr,ar,ru,uk,zh-CN,hi,sq,bg";
  var loaded = false;

  function markNoTranslate() {
    document.querySelectorAll("pre, code, mjx-container, .arithmatex, .md-search, .md-header__source").forEach(function (el) {
      el.classList.add("notranslate");
    });
  }

  function load() {
    if (loaded) return;
    loaded = true;
    markNoTranslate();
    window.ceidTranslateInit = function () {
      new window.google.translate.TranslateElement(
        { pageLanguage: "el", includedLanguages: LANGS, layout: window.google.translate.TranslateElement.InlineLayout.SIMPLE, autoDisplay: false },
        "ceid-translate-box"
      );
    };
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://translate.google.com/translate_a/element.js?cb=ceidTranslateInit";
    document.head.appendChild(s);
  }

  function build() {
    var wrap = document.createElement("div");
    wrap.id = "ceid-translate";
    wrap.className = "notranslate";
    // inline styles: the button must stay a floating corner button even when a browser holds an older stylesheet
    wrap.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:2147483000;max-width:280px;font:12px/1.3 system-ui,sans-serif;text-align:right";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "🌐 Translate / Μετάφραση";
    btn.setAttribute("aria-label", "Translate this page");
    btn.style.cssText = "cursor:pointer;border:1px solid #888;border-radius:999px;padding:8px 14px;background:#fff;color:#222;box-shadow:0 2px 8px rgba(0,0,0,.25);font:inherit;font-size:13px";
    var box = document.createElement("div");
    box.id = "ceid-translate-box";
    var note = document.createElement("div");
    note.className = "ceid-translate-note";
    note.textContent = "Automatic translation by Google. Exam questions are in Greek; AI translation may contain errors.";
    note.hidden = true;
    note.style.cssText = "margin-top:4px;padding:4px 8px;border-radius:6px;background:#fff;color:#444;box-shadow:0 2px 8px rgba(0,0,0,.15)";
    btn.addEventListener("click", function () {
      load();
      note.hidden = false;
      btn.hidden = true;
    });
    wrap.appendChild(btn);
    wrap.appendChild(box);
    wrap.appendChild(note);
    document.body.appendChild(wrap);
    if (/(^|;\s*)googtrans=/.test(document.cookie)) {
      btn.hidden = true;
      note.hidden = false;
      load();
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
