/* Conservative, local question matching. This file never sends form text to a model. */
(function (root) {
  "use strict";
  function norm(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
  }
  // Classify the question label only. Applicant-entered motivation text is
  // never read by ACE, including when an older Memory record exists.
  function isEmployerMotivation(question) {
    var q = norm(question);
    if (!q) return false;
    if (/\bwhy (?:this|our|the) (?:company|employer|organization|organisation|team|role|position)\b/.test(q)) return true;
    if (/\b(?:why|what|tell us why|explain why)\b/.test(q) &&
        /\b(?:want|wish|hope|choose|chose|interested|interest|excite\w*|attract\w*|motivat\w*)\b/.test(q) &&
        /\b(?:work|working|join|joining|company|employer|organization|organisation|team|us|our|here)\b/.test(q)) return true;
    if (/\bwhat (?:interests|excites|attracts|motivates) you\b/.test(q) &&
        /\b(?:about|in|to|at|with|joining|working|us|our)\b/.test(q)) return true;
    if (/\b(?:reason|reasons|motivation) for (?:applying|joining|working)\b/.test(q)) return true;
    return false;
  }
  function policy(question) {
    var q = norm(question);
    if (isEmployerMotivation(question)) return "employer_motivation";
    if (/\b(visa|sponsor(?:ship|ed|ing)?|work authori[sz]\w*|authorization to work|authorisation to work|authorized to work|authorised to work|right to work|citizen\w*|immigration|opt|cpt|practical training|f 1|h 1b|disability|veteran|ethnic\w*|race|gender|age|at least 18|18 years old|birth|criminal|felon|government|military|board of directors|export control|signature|certif\w*|attest\w*|privacy|consent\w*|acknowledg\w*|declar\w*|agree\w*|authoriz\w*|authoris\w*|salary|compensation|non compet\w*|non solicit\w*|signed|subject to any agreement|conflict of interest)\b/.test(q)) return "sensitive";
    if (/\b(ever worked|previously worked|formerly worked|been employed|currently employed|previously employed|employee of|employed at|employed with|worked at|worked for|contracted with|contractor at|contractor for|current contractor|current or former|applied to|applied for|recruiters?|agencies|referred by|our footprint|our 6 state footprint|this hybrid schedule|onsite at the office at least|family members|relatives|personal relationship|work at [a-z]|work for [a-z])\b/.test(q)) return "company";
    if (/\b(why|interest|motivat|excited|join|work for)\b/.test(q) && /\b(company|employer|us|our|team|organization|organisation)\b/.test(q)) return "company";
    if (/\b(why do you want to|why are you interested in|what makes you want to join)\b/.test(q)) return "company";
    return "reusable";
  }
  function concept(question) {
    var q = norm(question);
    if (/\b(distributed|microservice)\b/.test(q) && /\b(tradeoff|trade off|tradeoffs|trade offs)\b/.test(q) && /\b(design|architecture|system)\b/.test(q)) return "distributed_design_tradeoff";
    if (/\bpython\b/.test(q) && /\bapi|apis\b/.test(q) && /\bexperience|built|building|develop|worked\b/.test(q)) return "python_api_experience";
    if (/\b(time zones|distributed team|remote team)\b/.test(q) && /\b(collaborat|work|communicat)\b/.test(q)) return "remote_collaboration";
    return "q:" + q;
  }
  function equivalent(a, b, kindA, kindB) {
    if (kindA !== kindB || policy(a) !== "reusable" || policy(b) !== "reusable") return false;
    // A negation or a time qualifier can reverse the answer while leaving
    // the subject words unchanged. Keep these cases in Review.
    var qualifiers = /\b(not|never|without|currently|previously|former|future|minimum|maximum|at least|more than|less than)\b/g;
    if ((norm(a).match(qualifiers) || []).join("|") !== (norm(b).match(qualifiers) || []).join("|")) return false;
    var ca = concept(a), cb = concept(b);
    return ca === cb && ca !== "q:" || ca === cb && norm(a) === norm(b);
  }
  function resolve(question, kind, entries) {
    if (policy(question) !== "reusable") return null;
    var hits = (entries || []).filter(function (entry) {
      return entry.reuse_policy === "reusable" && entry.answer_type === kind &&
        equivalent(question, entry.question, kind, entry.answer_type);
    });
    return hits.length === 1 ? hits[0] : null;
  }
  root.aceMemory = { norm: norm, policy: policy, concept: concept, equivalent: equivalent, resolve: resolve, isEmployerMotivation: isEmployerMotivation };
  if (typeof module !== "undefined") module.exports = root.aceMemory;
})(typeof globalThis !== "undefined" ? globalThis : this);
