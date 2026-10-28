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

  // Owner decision, 2026-10-28: every answer the owner gives on an employer
  // form is saved and filled again when a later question means the same
  // thing, including authorization, sponsorship, voluntary disclosures,
  // conflicts and acknowledgements. Company motivation stays on the employer
  // form, and signatures and credentials are never saved.
  function learnable(question) {
    var q = norm(question);
    if (!q || isEmployerMotivation(question)) return false;
    return !/\b(signature|esignature|e signature|electronic(?:ally)? sign\w*|sign your name|type your (?:full |legal )?name to sign|password|passcode|captcha)\b/.test(q);
  }
  var STOP = {};
  ("a an the you your yours are is am was were be been being do does did have has had having any of to in into " +
   "for on at by with from as or and nor if then than that this these those it its will would could should can may " +
   "might must shall please kindly select choose indicate provide enter state answer below above following one each " +
   "which who whom whose what when where how our us we i me my there their they them so such also all both either " +
   "about etc eg ie e g type kind sort required optional question box field legally lawfully ever currently current " +
   "now presently present future previously previous past former formerly before prior not never no without none " +
   "last within over since time period month months year years day days describe explain share tell give briefly " +
   "example examples detail details experience experiences writing building developing implementing using utilizing " +
   "utilize use").split(" ").forEach(function (word) { STOP[word] = 1; });
  var NUMBERS = { two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11,
    twelve: 12, fifteen: 15, twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, hundred: 100 };
  var SAME = {
    authorised: "authorized", authorise: "authorized", authorize: "authorized", authorization: "authorized",
    authorisation: "authorized", eligible: "authorized", eligibility: "authorized", permitted: "authorized",
    entitled: "authorized", allowed: "authorized", sponsor: "sponsorship", sponsored: "sponsorship",
    sponsoring: "sponsorship", require: "need", requires: "need", requiring: "need", needed: "need",
    role: "opportunity", position: "opportunity", job: "opportunity", opening: "opportunity", vacancy: "opportunity",
    considered: "consider", consideration: "consider", wish: "want", like: "want", interested: "want",
    relationship: "relation", connection: "relation", link: "relation", tie: "relation", affiliation: "relation",
    relative: "family", household: "family", acknowledgement: "acknowledge", acknowledgment: "acknowledge",
    certify: "acknowledge", certification: "acknowledge", attest: "acknowledge", affirm: "acknowledge",
    confirm: "acknowledge", declare: "acknowledge", true: "accurate", correct: "accurate", complete: "accurate",
    truthful: "accurate", employed: "work", employment: "work", employee: "work", working: "work", worked: "work",
    employer: "company", organization: "company", organisation: "company", firm: "company",
    governmental: "government", disabled: "disability", sex: "gender", racial: "race", ethnicity: "race",
    ethnic: "race", relocation: "relocate", traveling: "travel", travelling: "travel", agree: "consent",
    agreement: "consent", accept: "consent", acceptance: "consent", convicted: "criminal", conviction: "criminal",
    felony: "criminal", crime: "criminal", competitor: "compete", competing: "compete", competition: "compete",
    competitive: "compete", referred: "referral", refer: "referral"
  };
  var CANONICAL = {};
  Object.keys(SAME).forEach(function (key) { CANONICAL[SAME[key]] = 1; });
  // Plural and ending forms of one word share a stem: relocate, relocating
  // and relocation all read as "relocat".
  function word(token) {
    if (token.length > 4 && /ies$/.test(token)) token = token.slice(0, -3) + "y";
    else if (token.length > 3 && /s$/.test(token) && !/ss$/.test(token)) token = token.slice(0, -1);
    if (SAME[token]) return SAME[token];
    if (CANONICAL[token]) return token;
    if (token.length >= 6 && /ing$/.test(token)) return token.slice(0, -3);
    if (token.length >= 7 && /ion$/.test(token)) return token.slice(0, -3);
    if (token.length >= 5 && /ed$/.test(token)) return token.slice(0, -2);
    if (token.length >= 5 && /e$/.test(token)) return token.slice(0, -1);
    return token;
  }
  function hostWords(context) {
    var host = "";
    try { host = new URL(context || "").hostname.toLowerCase(); } catch (_) { host = String(context || "").toLowerCase(); }
    return host.split(".").filter(function (part) {
      return part.length > 2 && !/^(www|jobs|careers|career|apply|boards|job|wd\d+|myworkdayjobs|myworkdaysite|greenhouse|lever|ashbyhq|workable|smartrecruiters|icims|taleo|oraclecloud|com|net|org|io|co)$/.test(part);
    });
  }
  // The meaning-bearing words of a question. The employer's own name is left
  // out, so the same question asked by another company still matches. Kept
  // for reuse: the card recounts every question on each change.
  var topics = {}, topicCount = 0;
  function topic(question, employerWords) {
    var cacheKey = String(question || "") + "|" + (employerWords || []).join("|");
    if (topics[cacheKey]) return topics[cacheKey];
    if (++topicCount > 4000) { topics = {}; topicCount = 1; }
    return (topics[cacheKey] = readTopic(question, employerWords));
  }
  function readTopic(question, employerWords) {
    var q = norm(question).replace(/\bu s\b/g, "us").replace(/\bunited states(?: of america)?\b/g, "us")
      .replace(/\b[a-z]+\b/g, function (token) { return NUMBERS[token] ? String(NUMBERS[token]) : token; });
    var skip = {};
    (employerWords || []).forEach(function (name) { norm(name).split(" ").forEach(function (part) { if (part) skip[part] = 1; }); });
    var tokens = [];
    q.split(" ").forEach(function (token) {
      if (!token || STOP[token] || skip[token] || /^\d+$/.test(token)) return;
      token = word(token);
      if (!STOP[token] && !skip[token] && tokens.indexOf(token) < 0) tokens.push(token);
    });
    var countries = [];
    (norm(question).match(/\b(united states|u s a|u s|usa|america|canada|mexico|united kingdom|uk|britain|england|ireland|germany|france|netherlands|spain|italy|poland|switzerland|sweden|europe|eu|india|china|singapore|japan|korea|australia|new zealand|brazil|israel|philippines)\b/g) || []).forEach(function (name) {
      name = /^(united states|u s a|u s|usa|america)$/.test(name) ? "us" : /^(united kingdom|britain|england)$/.test(name) ? "uk" : name;
      if (countries.indexOf(name) < 0) countries.push(name);
    });
    return { tokens: tokens, countries: countries.sort().join("|"),
      // A negation, timeframe or number can reverse an answer while every
      // subject word stays the same.
      negative: /\b(not|never|no longer|without|none)\b/.test(q),
      future: /\b(future|going forward)\b/.test(q),
      past: /\b(ever|previously|previous|past|former|formerly|before|prior|in the last|within the last|over the last|have you been)\b/.test(q),
      numbers: (q.match(/\d+/g) || []).join("|") };
  }
  function similarity(a, b) {
    if (a.tokens.length < 2 || b.tokens.length < 2) return 0;
    // A different country is a different question, however alike the words.
    if (a.negative !== b.negative || a.future !== b.future || a.past !== b.past || a.numbers !== b.numbers || a.countries !== b.countries) return 0;
    var shared = a.tokens.filter(function (token) { return b.tokens.indexOf(token) >= 0; }).length;
    var smaller = Math.min(a.tokens.length, b.tokens.length);
    // A short question wholly inside a long one is the same question with
    // the employer's extra explanation, once it has enough words to say so.
    return Math.max(2 * shared / (a.tokens.length + b.tokens.length), smaller >= 4 ? 0.8 * shared / smaller : 0);
  }
  // A question about the owner's own history with this employer keeps its
  // answer with this employer: worked, employed, applied, interviewed or
  // referred here. Relationship and conflict questions are about the owner.
  function employerScoped(question, employerWords) {
    var q = norm(question);
    if (/\b(referred|referral)\b/.test(q)) return true;
    if (/\b(authori[sz]ed|eligible|sponsor\w*|visa|permit)\b/.test(q)) return false;
    if (!/\b(worked|work for|work at|employed|former employee|employee of|contracted|contractor|intern|interned|internship|interviewed|applied|application to|application with)\b/.test(q)) return false;
    if (/\b(this company|our company|the company|this organization|our organization|this employer|us|our|here|subsidiar\w*|affiliate\w*)\b/.test(q) ||
        (employerWords || []).some(function (name) {
          var named = norm(name);
          return named.length > 2 && new RegExp("\\b" + named + "\\b").test(q);
        })) return true;
    // "Have you worked for Silverpine Labs?" names an organisation, where
    // "worked for a government agency" names only a kind of employer.
    var generic = "(?!(?:a|an|any|the|another|other|government|federal|state|local|public|private|us|this|our|your|their|similar|multiple|such|more|less)\\b)";
    return new RegExp("\\b(?:(?:worked|work|employed|interned|contracted) (?:for|at|by)|interviewed (?:with|at|for)|applied (?:to|at|with)|employee of) " + generic + "[a-z0-9]").test(q);
  }
  function kindClass(kind) { return kind === "text" ? "text" : "choice"; }
  function learnedScope(question, context, employerWords) {
    return employerScoped(question, employerWords) ? "@" + (tenantScope(context) || hostWords(context).join(".") || "unknown").slice(0, 80) : "";
  }
  // `bankName` is the answer-bank row this question maps to, when one does.
  // Questions that share a row share one learned answer, whatever wording.
  function learnedConcept(question, kind, context, bankName, employerWords) {
    // A reviewed screening fact keeps its exact status set, country,
    // timeframe and employer, which a broader answer-bank row would merge.
    var fact = kindClass(kind) === "choice" && screeningConcept(question, context);
    if (fact) return "learn:fact:choice:" + fact.slice(8);
    var scope = learnedScope(question, context, employerWords);
    if (bankName) return "learn:bank:" + kindClass(kind) + ":" + norm(bankName).replace(/ /g, "-") + scope;
    var words = topic(question, employerWords).tokens.slice().sort().join("-");
    return "learn:topic:" + kindClass(kind) + ":" + (words || norm(question).replace(/ /g, "-")) + scope;
  }
  function learnedParts(concept) {
    var match = /^learn:(bank|topic|fact):(text|choice):([^@]*)(@.*)?$/.exec(String(concept || ""));
    return match ? { source: match[1], kind: match[2], name: match[3], scope: match[4] || "" } : null;
  }
  // The owner's newest matching answer for this question, or null. Legacy
  // reusable and scoped records keep their original matching rules.
  function learnedMatch(question, kind, entries, context, bankName, employerWords) {
    if (!learnable(question)) return null;
    var cls = kindClass(kind), scope = learnedScope(question, context, employerWords);
    var fact = cls === "choice" ? screeningConcept(question, context) : null;
    var mine = topic(question, employerWords), bank = bankName ? norm(bankName).replace(/ /g, "-") : "";
    // Answers learned under this policy are the owner's newest decisions and
    // win over older reusable or scoped records for the same question.
    var best = null;
    (entries || []).forEach(function (entry) {
      if (!entry || !entry.answer || isEmployerMotivation(entry.question)) return;
      var score = 0;
      if (entry.reuse_policy === "learned") {
        var parts = learnedParts(entry.concept);
        if (!parts || parts.kind !== cls) return;
        if (parts.source === "fact") score = fact && "fact:v1:" + parts.name === fact ? 4 : 0;
        else if (parts.scope !== scope) return;
        // A reviewed fact question accepts a broader learned row only when
        // that answer was not itself given to a different reviewed fact.
        else if (bank && parts.source === "bank") score = parts.name === bank && !(fact && screeningConcept(entry.question, context)) ? 3 : 0;
        else if (fact) return;
        else {
          score = similarity(mine, topic(entry.question, hostWords(entry.source_host)));
          if (score < 0.72) score = 0;
        }
        if (score) score += 10;
      } else if (entry.reuse_policy === "scoped" || entry.reuse_policy === "reusable") {
        score = candidates(question, kind, [entry], context).length ? 1 : 0;
      }
      if (!score) return;
      var when = Date.parse(entry.approved_at || entry.saved_at || "") || 0;
      if (!best || score > best.score || score === best.score && when > best.when) best = { entry: entry, score: score, when: when };
    });
    return best ? best.entry : null;
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
    screeningConcept: screeningConcept, storagePolicy: storagePolicy, isEmployerMotivation: isEmployerMotivation,
    learnable: learnable, topic: topic, similarity: similarity, employerScoped: employerScoped, hostWords: hostWords,
    learnedConcept: learnedConcept, learnedParts: learnedParts, learnedMatch: learnedMatch, tenantScope: tenantScope };
  if (typeof module !== "undefined") module.exports = root.aceMemory;
})(typeof globalThis !== "undefined" ? globalThis : this);
