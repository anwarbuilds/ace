/* Which answer belongs in which box.

   Matching is on the question a human reads, not on the field's name
   attribute, because those are generated and differ per tenant. Each
   rule lists phrases that identify the question and, where two
   questions read almost alike, the phrases that rule it out. Order
   matters: the first rule that matches wins, so the narrower questions
   sit above the broader ones they would otherwise be swallowed by.

   A field ACE cannot identify is left alone and reported. Filling a box
   with the wrong answer is far worse than leaving it empty, because the
   user is about to send it to an employer. */

var ACE_RULES = [
  // Sponsorship reads as two near-identical questions. "Future" has to
  // be tested before the plain form or it never matches.
  { answer: "Need sponsorship in future",
    any: ["in the future require", "future require", "future need",
          "sponsorship in the future", "now or in the future"] },
  { answer: "Need sponsorship now",
    // "immigration sponsorship" is the wording Greenhouse actually
    // uses, and the shorter phrase alone never matched it.
    any: ["require immigration sponsorship", "need immigration sponsorship",
          "require sponsorship", "need sponsorship", "visa sponsorship",
          "require visa", "sponsorship for employment"],
    not: ["future"] },
  { answer: "Work authorisation",
    any: ["authorized to work", "authorised to work", "work authorization",
          "work authorisation", "legally authorized", "legally authorised",
          "right to work", "eligible to work"] },

  { answer: "First name", any: ["first name", "given name", "forename"] },
  { answer: "Last name", any: ["last name", "family name", "surname"] },
  { answer: "Full name",
    any: ["full name", "your name", "legal name"], exact: ["name"] },

  { answer: "Email",
    any: ["email", "e-mail"],
    // A marketing opt-in mentions email and is not an email box.
    not: ["receive communications", "opt in", "opt-in", "subscribe",
          "marketing", "sms"] },
  { answer: "Phone",
    any: ["phone", "mobile number", "telephone", "cell"],
    not: ["country"] },
  { answer: "Pronouns", any: ["pronoun"] },

  { answer: "LinkedIn", any: ["linkedin"] },
  { answer: "GitHub", any: ["github"] },
  { answer: "Portfolio",
    any: ["portfolio", "personal website", "personal site", "website",
          "other website"] },

  { answer: "Postcode", any: ["zip", "postal code", "postcode"] },
  { answer: "City", any: ["city", "town"] },
  { answer: "State", any: ["state", "province", "region"] },
  { answer: "Country", any: ["country"] },
  { answer: "Address", any: ["street", "address line", "address"] },
  { answer: "Location",
    any: ["current location", "where are you located", "location"] },

  { answer: "University",
    any: ["university", "school", "college", "institution"] },
  { answer: "Degree", any: ["degree", "qualification"] },
  { answer: "Graduation date",
    any: ["graduation", "grad date", "expected graduation"] },
  { answer: "Years of experience",
    any: ["years of experience", "years experience"] },

  { answer: "Earliest start date",
    any: ["start date", "available to start", "earliest start",
          "when can you start"] },
  { answer: "Salary expectation",
    any: ["salary", "desired compensation", "compensation expectation",
          "expected pay"] },
  { answer: "How did you hear about us",
    any: ["how did you hear", "referral source", "how you found"] },

  // Transgender identity is asked separately and has no row in the
  // bank, so it is left for the user rather than answered from Gender.
  { answer: "Gender", any: ["gender"], not: ["transgender"] },
  { answer: "Race or ethnicity",
    any: ["race", "ethnicity", "hispanic", "latino"] },
  { answer: "Veteran status", any: ["veteran", "military service"] },
  { answer: "Disability status", any: ["disability", "disabled"] },

  { answer: "Why this company",
    any: ["why do you want", "why are you interested", "why this company",
          "why us", "why would you like to work"] }
];

function aceNormalise(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .replace(/[‘’]/g, "'")
    .toLowerCase()
    .trim();
}

/* The question a person reads next to the box.

   The first source that yields text wins, rather than joining them all.
   Joining looked thorough and was actively wrong: on a real Greenhouse
   form the container around the sponsorship question also holds the
   preceding "legally authorized to work" question, so every sponsorship
   field matched work authorisation instead. The narrowest source that
   has an answer is the trustworthy one. */
/* For a radio or checkbox, the box's own label is the option, not the
   question: "He/Him", "Male", "Asian (not Hispanic or Latino)". The
   question sits on the group.

   Reading the option instead was actively dangerous. On a real Ashby
   form the "How did you hear about this opportunity" group has an
   option reading "LinkedIn", which matched the LinkedIn profile rule,
   so a stored profile URL would have ticked a referral-source box. */
function aceGroupQuestion(field) {
  // The declared group first. Ashby marks one up with a fieldset whose
  // first label is the question, and climbing from the control instead
  // finds the option's own text on the way past.
  var declared = field.closest("fieldset, [role=radiogroup], [role=group]");

  if (declared) {
    var named = aceHeadingIn(declared, field);
    if (named) return named;
  }

  // Lever declares no group, so the question is whatever heading sits
  // nearest above that is not itself one of the options.
  var node = field.parentElement;

  for (var depth = 0; node && depth < 8; depth++) {
    var found = aceHeadingIn(node, field);
    if (found) return found;
    node = node.parentElement;
  }

  return "";
}

/* The first heading inside a block that is not one of its options. */
function aceHeadingIn(block, field) {
  var candidates = block.querySelectorAll(
    "legend, label, [class*='heading'], [class*='label']"
  );

  for (var i = 0; i < candidates.length; i++) {
    // A heading that wraps a control is an option, not the question.
    // Lever puts each choice in its own label, so without this the
    // group's question reads as "he/him" or "female".
    if (candidates[i].querySelector("input, select, textarea")) continue;
    if (candidates[i].contains(field)) continue;

    var text = aceNormalise(
      aceTextWithoutControls(candidates[i])
    );
    if (text) return text.slice(0, 300);
  }

  return "";
}

/* A block's wording with its own controls taken out.

   A select carries every option in its text, so the block around a
   Lever gender select reads "gender select male female decline to
   self-identify" and the question is lost in its own answers. */
function aceTextWithoutControls(block) {
  if (!block.querySelector("select, option, input, textarea")) {
    return block.textContent;
  }

  var clone = block.cloneNode(true);

  Array.prototype.forEach.call(
    clone.querySelectorAll("select, option, input, textarea"),
    function (node) {
      node.remove();
    }
  );

  return clone.textContent;
}

/* What this one option says, for checking against the stored answer. */
function aceOptionText(field) {
  var wrapping = field.closest("label");
  if (wrapping) return aceNormalise(wrapping.textContent);

  if (field.id) {
    var labelled = document.querySelector(
      'label[for="' + CSS.escape(field.id) + '"]'
    );
    if (labelled) return aceNormalise(labelled.textContent);
  }

  var option = field.closest("[class*='option']");
  if (option) return aceNormalise(option.textContent);

  return aceNormalise(field.value);
}

function aceQuestionFor(field) {
  if (field.type === "radio" || field.type === "checkbox") {
    return aceGroupQuestion(field);
  }

  var sources = [];

  if (field.id) {
    var labelled = document.querySelector(
      'label[for="' + CSS.escape(field.id) + '"]'
    );
    if (labelled) sources.push(aceTextWithoutControls(labelled));
  }

  // Stripped, because a label wrapping a select carries every option:
  // Lever's gender label reads "gender select male female decline to
  // self-identify", where the question runs straight into its answers.
  var wrapping = field.closest("label");
  if (wrapping) sources.push(aceTextWithoutControls(wrapping));

  sources.push(field.getAttribute("aria-label"));

  var describedBy = field.getAttribute("aria-labelledby");
  if (describedBy) {
    var joined = describedBy.split(/\s+/).map(function (id) {
      var node = document.getElementById(id);
      return node ? node.textContent : "";
    }).join(" ");
    sources.push(joined);
  }

  // Only consulted when nothing above named the field. Greenhouse gives
  // its custom selects no label at all, so their question lives in the
  // surrounding markup and this is the only place it can be read.
  var group = aceOwnGroup(field);
  if (group) sources.push(aceTextWithoutControls(group));

  sources.push(field.getAttribute("placeholder"));
  sources.push(field.getAttribute("name"));
  sources.push(field.id);

  for (var i = 0; i < sources.length; i++) {
    var text = aceNormalise(sources[i]);
    if (text && text.length <= 300) return text;
  }

  return "";
}

/* The smallest block that holds this control and no other.

   Taking the first label inside any ancestor matched the wrong
   question whenever a container held several: on a real form every
   sponsorship field read as "legally authorized to work", the question
   printed above it. Climbing only while the block still contains one
   control keeps the question and its box together. */
function aceOwnGroup(field) {
  var node = field.parentElement;
  var best = null;

  for (var depth = 0; node && depth < 6; depth++) {
    var controls = node.querySelectorAll(
      "input:not([type=hidden]), select, textarea"
    );

    if (controls.length > 1) break;

    best = node;
    node = node.parentElement;
  }

  return best;
}

/* Boxes that are not questions. A search field sits inside the page
   chrome and matched "phone" through its ancestors, and filling a
   captcha or a consent box is never wanted. */
function aceShouldSkip(field) {
  if (field.type === "search") return true;

  var name = aceNormalise(
    (field.getAttribute("name") || "") + " " + (field.id || "")
  );

  return /recaptcha|captcha|csrf|honeypot|^q$|search/.test(name);
}

/* Whole words only. "ethnicity" contains "city", and matching on a
   raw substring sent a stored city into an ethnicity question on a
   real Lever form. */
function acePhraseIn(question, phrase) {
  var escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  // A trailing "s" still counts: forms write "pronouns" and the rule
  // says "pronoun". Anything else after the phrase is a different word.
  return new RegExp(
    "(^|[^a-z0-9])" + escaped + "s?(?![a-z0-9])"
  ).test(question);
}

function aceAnswerNameFor(question) {
  if (!question) return null;

  for (var i = 0; i < ACE_RULES.length; i++) {
    var rule = ACE_RULES[i];

    if (rule.not && rule.not.some(function (word) {
      return acePhraseIn(question, word);
    })) continue;

    var hit = (rule.any || []).some(function (phrase) {
      return acePhraseIn(question, phrase);
    });

    if (!hit && rule.exact) {
      hit = rule.exact.some(function (phrase) {
        return question === phrase;
      });
    }

    if (hit) return rule.answer;
  }

  return null;
}
