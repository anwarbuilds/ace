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
    if (/\b(ever worked|previously worked|formerly worked|been employed|currently employed|previously employed|employee of|employed at|employed with|worked at|worked for|temporary work for|interviewed for|search agency|employment agency|recruitment agency|contracted with|contractor at|contractor for|current contractor|current or former|applied to|applied for|recruiters?|agencies|referred by|our footprint|our 6 state footprint|this hybrid schedule|onsite at the office at least|family members|relatives|personal relationship|work at [a-z]|work for [a-z])\b/.test(q)) return "company";
    if (/\b(why|interest|motivat|excited|join|work for)\b/.test(q) && /\b(company|employer|us|our|team|organization|organisation)\b/.test(q)) return "company";
    if (/\b(why do you want to|why are you interested in|what makes you want to join)\b/.test(q)) return "company";
    return "reusable";
  }
  function concept(question) {
    var q = norm(question);
    if (/\d|\b(how many|how much|number of|years of|months of|rate|rating|level)\b/.test(q)) return "q:" + canonicalQuestion(q);
    if (/\b(distributed|microservice)\b/.test(q) && /\b(tradeoff|trade off|tradeoffs|trade offs)\b/.test(q) && /\b(design|architecture|system)\b/.test(q)) return "distributed_design_tradeoff";
    if (/\bpython\b/.test(q) && /\bapi|apis\b/.test(q) && /\bexperience|built|building|develop|worked\b/.test(q)) return "python_api_experience";
    if (/\b(time zones|distributed team|remote team)\b/.test(q) && /\b(collaborat|work|communicat)\b/.test(q)) return "remote_collaboration";
    return "q:" + canonicalQuestion(q);
  }
  // Normalize only common prompt phrasing. Preserve the subject, scope,
  // numbers and qualifiers; keyword overlap alone never authorizes reuse.
  function canonicalQuestion(question) {
    return norm(question)
      .replace(/^(?:please |kindly )/, "")
      .replace(/^(?:can you |could you |would you )(?=describe |explain |share |tell us )/, "")
      .replace(/^(?:tell us about |share |explain |describe )your experience (?:with |in |using )?/, "experience ")
      .replace(/^what (?:is|has been) your experience (?:with |in |using )?/, "experience ")
      .replace(/^(?:do you have|have you had) (?:any )?experience (?:with |in |using )?/, "experience ")
      .replace(/\b(?:building|developing|implementing)\b/g, "writing")
      .replace(/\b(?:utilizing|using)\b/g, "with");
  }
  function tenantScope(context) {
    try {
      var url = new URL(context || ""), host = url.hostname.toLowerCase();
      var parts = url.pathname.split("/").filter(Boolean);
      if (/^(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io$|^jobs\.(?:(?:eu\.)?lever\.co|ashbyhq\.com|gem\.com|smartrecruiters\.com)$|^careers\.smartrecruiters\.com$|^apply\.workable\.com$/.test(host)) {
        return parts[0] ? host + "/" + parts[0].toLowerCase() : null;
      }
      if (/\.myworkdayjobs\.com$/.test(host)) {
        var sitePart = /^[a-z]{2}(?:-[a-z]{2})?$/i.test(parts[0] || "") ? 1 : 0;
        return parts[sitePart] ? host + "/" + parts[sitePart].toLowerCase() : null;
      }
      if (/\.myworkdaysite\.com$/.test(host)) {
        var recruiting = parts.indexOf('recruiting');
        return recruiting >= 0 && parts[recruiting + 2] ? host + "/" + parts.slice(recruiting, recruiting + 3).join('/').toLowerCase() : null;
      }
      if (/\.oraclecloud\.com$/.test(host)) {
        var site = parts.indexOf("sites");
        return site >= 0 && parts[site + 1] ? host + "/" + parts[site + 1].toLowerCase() : null;
      }
      // Workday tenants and employer-owned application hosts keep their host.
      if (/^(?:www\.)?(?:linkedin\.com|indeed\.com|glassdoor\.com)$/.test(host)) return null;
      if (/(?:^|\.)(?:greenhouse\.io|lever\.co|ashbyhq\.com|gem\.com|workable\.com|smartrecruiters\.com|taleo\.net)$/.test(host)) return null;
      return host || null;
    } catch (_) { return null; }
  }
  // Only these factual binary screenings have a reviewed reuse policy. Keep
  // compound status sets, country, timeframe and the complete named employer.
  // Unknown/protected questions and attestations remain per application.
  function screeningConcept(question, context) {
    var q = norm(question).replace(/\bu s\b/g, "us").replace(/\bunited states\b/g, "us")
      .replace(/\brequired\b$/g, "").trim();
    if (isEmployerMotivation(q) || /\b(not|never|without|certify|attest|agree|consent|signature|privacy|declare|confirm|acknowledge|disability|gender|race|veteran|criminal|salary|government|military)\b/.test(q)) return null;
    var topic = "", scope = "", match;
    if (/^are you (?:a )?us citizen (?:or )?(?:a )?(?:lawful )?permanent resident(?: (?:or )?(?:a )?refugee (?:or )?(?:a )?(?:person granted asylum|asylee))?$/.test(q)) {
      topic = "us-status:citizen,resident" + (/\brefugee\b/.test(q) ? ",refugee" : "") + (/\basylum|asylee\b/.test(q) ? ",asylee" : "");
      // No additional citizenship/status qualifier can silently disappear.
      if (/\b(dual|conditional|temporary|born|naturalized|only)\b/.test(q)) return null;
    } else if (/^(?:will you|do you) now or in the future (?:require|need) (?:visa sponsorship|sponsorship for employment visa status|sponsorship)(?: (?:to work|to continue working) in the us)?$/.test(q)) {
      if (/\b(canada|canadian|uk|kingdom|australia|india|germany|europe|other|outside)\b/.test(q)) return null;
      topic = "visa-sponsorship:now-or-future";
      // An unspecified country stays with the original hiring tenant. It
      // cannot turn a US decision into a decision for a foreign application.
      scope = /\bus\b/.test(q) ? "country:us" : "tenant:" + (tenantScope(context) || "");
      if (scope === "tenant:") return null;
    } else if ((match = q.match(/^have you (?:ever |previously )?(?:performed|done|undertaken) temporary work for (.+)$/))) {
      topic = /\bpreviously\b/.test(q) ? "temporary-work:previous" : "temporary-work:ever"; scope = "employer:" + match[1];
    } else if ((match = q.match(/^have you (?:ever |previously )?interviewed for (?:a position|a role|employment) (?:at|with) (.+)$/))) {
      topic = /\bpreviously\b/.test(q) ? "interview:previous" : "interview:ever"; scope = "employer:" + match[1];
    } else if ((match = q.match(/^have you or do you currently work for or with (.+)$/))) {
      topic = "work-relationship:past-or-present"; scope = "employer:" + match[1];
    } else if ((match = q.match(/^have you (?:ever |previously )?worked (?:for|at) (.+)$/))) {
      topic = /\bpreviously\b/.test(q) ? "worked:previous" : "worked:ever"; scope = "employer:" + match[1];
    } else if (/^do you have any post employment obligations to any current or former employer i e non compete non solicitation etc that may prohibit or restrict your employment for a position$/.test(q) ||
               /^are you subject to any post employment obligations to (?:a|any) current or former employer that may (?:prevent|prohibit) or restrict your employment including non compete (?:or|and) non solicitation agreements$/.test(q)) {
      topic = "employment-obligations:current-or-former:any:restrict-employment";
    } else if (/^(?:has a search agency|has an employment agency|has a recruitment agency) submitted your application for consideration within the last 12 months$/.test(q)) {
      topic = "agency-submission:last-12-months"; scope = "tenant:" + (tenantScope(context) || "");
      if (scope === "tenant:") return null;
    }
    if (!topic) return null;
    scope = scope.replace(/\bor any of (?:its|their|the) subsidiaries\b/g, "including subsidiaries");
    if (/^employer:(?:us|this company|our company|this employer|our organization|our organisation)(?: |$)/.test(scope)) {
      var tenant = tenantScope(context);
      if (!tenant) return null;
      scope = "tenant:" + tenant + ":" + scope.slice(9);
    }
    var key = "fact:v1:" + topic + (scope ? ":" + scope : "");
    return key.length <= 180 ? key : null;
  }
  function storagePolicy(question, kind, context) {
    if (/^(choice|yesno)$/.test(kind) && screeningConcept(question, context)) return "scoped";
    return policy(question) === "reusable" ? "reusable" : null;
  }
  function equivalent(a, b, kindA, kindB) {
    if (kindA !== kindB || policy(a) !== "reusable" || policy(b) !== "reusable") return false;
    // A negation or a time qualifier can reverse the answer while leaving
    // the subject words unchanged. Keep these cases in Review.
    var qualifiers = /\b(not|never|without|current|currently|previous|previously|past|former|future|minimum|maximum|at least|more than|less than)\b/g;
    if ((norm(a).match(qualifiers) || []).join("|") !== (norm(b).match(qualifiers) || []).join("|")) return false;
    var measurement = /\b(how many|how much|number of|years of|months of|rate|rating|level)\b/;
    if (measurement.test(norm(a)) !== measurement.test(norm(b))) return false;
    var ca = concept(a), cb = concept(b);
    return ca === cb && ca !== "q:";
  }
  function candidates(question, kind, entries, context) {
    var mode = storagePolicy(question, kind, context);
    if (!mode) return [];
    var key = mode === "scoped" ? screeningConcept(question, context) : null;
    var hits = (entries || []).filter(function (entry) {
      if (mode === "scoped") return entry.reuse_policy === "scoped" && entry.concept === key &&
        /^(choice|yesno)$/.test(entry.answer_type) && /^(yes|no)$/.test(norm(entry.answer)) &&
        screeningConcept(entry.question, context) === key;
      return entry.reuse_policy === "reusable" && entry.answer_type === kind &&
        equivalent(question, entry.question, kind, entry.answer_type);
    });
    return hits;
  }
  function resolve(question, kind, entries, context) {
    var hits = candidates(question, kind, entries, context);
    // Old duplicate records with the same answer are not conflicting facts.
    // Preserve them; a disagreement still requires correction in Memory.
    return hits.length && hits.every(function (entry) { return entry.answer.trim() === hits[0].answer.trim(); }) ? hits[0] : null;
  }
  root.aceMemory = { norm: norm, policy: policy, concept: concept, equivalent: equivalent, resolve: resolve, candidates: candidates,
    screeningConcept: screeningConcept, storagePolicy: storagePolicy, isEmployerMotivation: isEmployerMotivation };
  if (typeof module !== "undefined") module.exports = root.aceMemory;
})(typeof globalThis !== "undefined" ? globalThis : this);
