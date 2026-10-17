/* Greek-aware search for Material for MkDocs (lunr has no Greek): lower-case, strip tonos / dialytika (NFD), final
   sigma -> sigma. Applied to the query and to the indexed text through the messages that go to the search worker, so the
   displayed titles and pages stay untouched (titles are also appended, normalised, to the indexed text). */
(function (root) {
  "use strict";
  function norm(s) {
    return String(s == null ? "" : s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/ς/g, "σ").normalize("NFC");
  }
  root.ceidNormalizeGreek = norm;
  var W = root.Worker;
  if (!W || root.__ceidGreekSearch) return;
  root.__ceidGreekSearch = true;
  var post = W.prototype.postMessage;
  W.prototype.postMessage = function (msg) {
    try {
      if (msg && msg.type === 0 && msg.data && Array.isArray(msg.data.docs)) {          /* SEARCH_SETUP */
        msg.data.docs.forEach(function (d) { d.text = norm((d.title || "") + " " + (d.text || "")); });
      } else if (msg && msg.type === 2 && typeof msg.data === "string") {               /* SEARCH_QUERY */
        msg = { type: msg.type, data: norm(msg.data) };
      }
    } catch (e) { /* never break the search */ }
    var args = [].slice.call(arguments);
    args[0] = msg;
    return post.apply(this, args);
  };
})(typeof window !== "undefined" ? window : globalThis);
if (typeof module !== "undefined") module.exports = { norm: globalThis.ceidNormalizeGreek || (typeof window !== "undefined" && window.ceidNormalizeGreek) };
