/* Which answer belongs in which box.

   Matching is on the question a human reads, not on the field's name
   attribute, because those are generated and differ per tenant.

   Three things decide a match, and all three had to exist before real
   forms stopped being answered wrongly:

   1. The phrases that identify the question, and the phrases that rule
      it out.
   2. How specific the match was. The longest matched phrase wins, not
      the first rule in the list. A real Dell form asks "is the role you
      are applying for located in the United States?", and "state"
      matches inside "United States"; "role you are applying for" is
      longer and is the honest answer.
   3. What shape of answer the control can accept. A Yes/No pair cannot
      hold "Masters in Computer Science", so a rule whose answer is free
      text is refused there outright. On the same Dell form this alone
      stopped four wrong matches, including "are you a recent graduate
      (less than 3 years since you completed your most recent degree)?"
      being answered with a degree.

   A field ACE cannot identify is left alone and reported. Filling a box
   with the wrong answer is far worse than leaving it empty, because the
   user is about to send it to an employer. */

/* Answer shapes.

   Only "yesno" is enforced strictly, and only in one direction: a
   control offering nothing but Yes and No refuses any rule that is not
   itself a yes/no question. Everything else stays permissive, because
   a country is a text answer on one form and a dropdown on the next,
   and aceChooseOption is the real guard there. */
var ACE_YESNO = "yesno";
var ACE_CHOICE = "choice";
var ACE_TEXT = "text";

var ACE_RULES = [
  // ------------------------------------------------------------------
  // Work authorisation and immigration
  //
  // The cluster that matters most here, and the one general-purpose
  // autofill tools deliberately leave to the user because their answers
  // differ per person. This user's do not change, so ACE answers them
  // -- which makes getting the polarity right the whole job. "Are you
  // authorised to work" and "do you need sponsorship" are both Yes for
  // someone authorised to work now who will need sponsorship
  // later, and they are not the same question.
  // ------------------------------------------------------------------

  // "Future" has to be tested before the plain form or it never
  // matches, and both are now scored so the longer phrase wins anyway.
  { answer: "Need sponsorship in future", type: ACE_YESNO,
    any: ["in the future require", "future require", "future need",
          "sponsorship in the future", "now or in the future",
          "future require sponsorship", "in the future need sponsorship"] },
  { answer: "Need sponsorship now", type: ACE_YESNO,
    // "immigration sponsorship" is the wording Greenhouse actually
    // uses, and the shorter phrase alone never matched it.
    any: ["require immigration sponsorship", "need immigration sponsorship",
          "require sponsorship", "need sponsorship", "visa sponsorship",
          "require visa", "sponsorship for employment",
          "immigration benefit sponsorship", "sponsorship to work"],
    not: ["future"] },
  { answer: "Work authorisation", type: ACE_YESNO,
    any: ["authorized to work", "authorised to work", "work authorization",
          "work authorisation", "legally authorized", "legally authorised",
          "right to work", "eligible to work",
          "authorization documentation", "authorisation documentation"] },

  // On a temporary work visa is asked alongside the two above and is a
  // different fact again: student work authorisation is authorisation
  // without being one of the temporary work visas these forms mean
  // (H-1B, L-1, TN).
  { answer: "On a temporary work visa", type: ACE_YESNO,
    any: ["temporary work visa", "temporary visa", "work visa",
          "currently on a visa", "visa holder"],
    not: ["sponsorship", "require", "need"] },
  { answer: "US citizen or permanent resident", type: ACE_YESNO,
    any: ["u s citizen", "us citizen", "united states citizen",
          "citizen or permanent resident", "permanent resident",
          "green card"],
    not: ["embargo", "dual citizen", "trade"] },
  // Dell asks this one at length. It is not a citizenship question in
  // the ordinary sense and must not be answered from one.
  { answer: "Citizen of an embargoed country", type: ACE_YESNO,
    any: ["trade embargo", "embargoed country", "embargo"] },

  // ------------------------------------------------------------------
  // Background, clearance and prior employment
  // ------------------------------------------------------------------

  { answer: "Security clearance", type: ACE_YESNO,
    any: ["security clearance", "active clearance", "clearance level",
          "hold a clearance", "ts sci", "polygraph"] },
  { answer: "Employed by the federal government", type: ACE_YESNO,
    any: ["employed by the u s government", "employed by the us government",
          "employed by the federal government", "federal government",
          "u s government", "us government"],
    not: ["state or local", "state and local"] },
  { answer: "Employed by state or local government", type: ACE_YESNO,
    any: ["state or local government", "state and local government",
          "local government"] },
  { answer: "Involuntarily discharged from a job", type: ACE_YESNO,
    any: ["involuntarily discharged", "involuntarily separated",
          "discharged or separated", "terminated for cause",
          "asked to resign"] },
  { answer: "Criminal conviction", type: ACE_YESNO,
    any: ["convicted of a", "criminal conviction", "criminal record",
          "felony", "misdemeanor", "pleaded guilty", "plead guilty"] },
  { answer: "Bound by a non-compete", type: ACE_YESNO,
    // Hyphens are left alone by aceNormalise, because collapsing them
    // would turn "e-mail" into something the email rule no longer
    // matches. So both spellings are listed instead.
    any: ["non-compete", "non compete", "noncompete", "non-competition",
          "restrictive covenant", "restrict your employment",
          "preclude or restrict"] },
  { answer: "Previously employed by this company", type: ACE_YESNO,
    any: ["previously worked for", "previously been employed by",
          "ever worked for", "former employee", "worked here before",
          "previously applied"] },
  { answer: "Related to an employee here", type: ACE_YESNO,
    any: ["relatives employed", "family member employed",
          "related to any employee", "relative who works",
          "know anyone who works"] },

  // ------------------------------------------------------------------
  // Conflict of interest
  //
  // Dell asks five variations of "is your employer entangled with us".
  // They share one answer for someone with no such entanglement, and
  // they are kept separate from the question about a relative's
  // business, which is a genuinely different fact.
  // ------------------------------------------------------------------

  { answer: "Employer relationship with this company", type: ACE_YESNO,
    any: ["employer a reseller", "is your current employer a reseller",
          "reseller of", "has a relationship with",
          "relationship with dell", "delivery of services by",
          "interact with", "on site permanently",
          "regular basis at your employer"] },
  { answer: "Relative owns a competing business", type: ACE_YESNO,
    any: ["relative s own", "relatives own", "own any technology related",
          "in competition with", "competing business",
          "trading with or in competition"] },

  // ------------------------------------------------------------------
  // Consent and acknowledgement
  // ------------------------------------------------------------------

  { answer: "Consent to keep my application on file", type: ACE_YESNO,
    any: ["retain your application", "keep your application on file",
          "subsequent job opportunities", "future job opportunities",
          "consider you for other", "talent community"] },
  { answer: "Agree to the terms shown", type: ACE_YESNO,
    any: ["screenshot", "please confirm your acceptance",
          "confirm your acceptance", "hereby provide my consent",
          "acknowledge and agree", "i agree and hereby"] },

  // ------------------------------------------------------------------
  // Identity and contact
  // ------------------------------------------------------------------

  { answer: "First name", type: ACE_TEXT,
    any: ["first name", "given name", "forename"] },
  { answer: "Last name", type: ACE_TEXT,
    any: ["last name", "family name", "surname"] },
  { answer: "Full name", type: ACE_TEXT,
    any: ["full name", "your name", "legal name"], exact: ["name"] },

  { answer: "Email", type: ACE_TEXT,
    any: ["email", "e-mail"],
    // A marketing opt-in mentions email and is not an email box, and
    // so does Dell's "preferred method of communication", whose
    // options are Email, Email SMS and Email WhatsApp.
    not: ["receive communications", "opt in", "opt-in", "subscribe",
          "marketing", "sms", "preferred method", "method of communication"] },
  { answer: "Phone", type: ACE_TEXT,
    any: ["phone", "mobile number", "telephone", "cell"],
    // DoorDash asks whether you want SMS and WhatsApp updates, and
    // explains that otherwise "we will only communicate with you via
    // email and/or telephone calls". That is a yes/no about consent,
    // and it matched the phone rule on the word buried in the
    // explanation. A phone number typed into it answers nothing.
    not: ["country", "receive communications", "sms", "whatsapp",
          "data rates", "opt out", "opt-out"] },
  { answer: "Pronouns", type: ACE_CHOICE, any: ["pronoun"] },

  { answer: "LinkedIn", type: ACE_TEXT, any: ["linkedin"] },
  { answer: "GitHub", type: ACE_TEXT, any: ["github"] },
  { answer: "Portfolio", type: ACE_TEXT,
    any: ["portfolio", "personal website", "personal site", "website",
          "other website"] },

  { answer: "Postcode", type: ACE_TEXT,
    // "postal" bare is what the name attribute and the placeholder say.
    any: ["zip", "zipcode", "postal", "postal code", "postcode"] },
  { answer: "City", type: ACE_TEXT, any: ["city", "town"] },
  { answer: "State", type: ACE_TEXT,
    any: ["state", "province", "region"],
    // "United States" contains "state". Every Dell question naming the
    // country matched this rule before the guard existed.
    not: ["united states", "state or local", "state and local",
          "state government"] },
  // "country code" sits next to a phone box and wants +1, not a
  // country name, so it is left for the user.
  { answer: "Country", type: ACE_TEXT,
    any: ["country"],
    not: ["code", "embargo", "authorized to work", "authorised to work",
          "legally authorized", "requisition is posted"] },
  { answer: "Address", type: ACE_TEXT,
    any: ["street", "address line", "address"] },
  { answer: "Location", type: ACE_TEXT,
    any: ["current location", "where are you located", "location"],
    // Greenhouse labels a city box "Location (City)". The parenthetical
    // says which of the two it wants, and "location" is the longer
    // phrase, so without this it now outscores the city rule.
    not: ["role", "position", "requisition", "city"] },

  // ------------------------------------------------------------------
  // Education and experience
  // ------------------------------------------------------------------

  { answer: "University", type: ACE_TEXT,
    any: ["university", "school", "college", "institution"] },
  { answer: "Degree", type: ACE_TEXT,
    any: ["degree", "qualification"],
    not: ["recent graduate", "since you completed"] },
  { answer: "Field of study", type: ACE_TEXT,
    any: ["field of study", "major", "discipline", "course of study"] },
  { answer: "GPA", type: ACE_TEXT, any: ["gpa", "grade point"] },
  { answer: "Graduation date", type: ACE_TEXT,
    any: ["graduation", "grad date", "expected graduation"] },
  { answer: "Years of experience", type: ACE_TEXT,
    any: ["years of experience", "years experience",
          "years of relevant experience"] },
  // Asked as a Yes/No on Dell and on most new-grad programmes, and it
  // is not the graduation date restated.
  { answer: "Recent graduate", type: ACE_YESNO,
    any: ["recent graduate", "recently graduated", "new graduate",
          "graduating within", "since you completed your most recent"] },

  // ------------------------------------------------------------------
  // Logistics
  // ------------------------------------------------------------------

  { answer: "Earliest start date", type: ACE_TEXT,
    any: ["start date", "startdate", "available to start",
          "earliest start", "when can you start",
          "availability to start"] },
  { answer: "Salary expectation", type: ACE_TEXT,
    any: ["salary", "desired compensation", "compensation expectation",
          "expected pay", "pay expectation"] },
  { answer: "How did you hear about us", type: ACE_CHOICE,
    any: ["how did you hear", "referral source", "how you found",
          "how did you find", "where did you hear"] },
  { answer: "Preferred contact method", type: ACE_CHOICE,
    any: ["preferred method of communication", "method of communication",
          "preferred contact method", "how would you like to be contacted"] },
  { answer: "At least 18 years old", type: ACE_YESNO,
    any: ["at least 18", "18 years of age", "18 years old", "over 18",
          "age of 18", "legal working age"] },
  { answer: "Role is located in the US", type: ACE_YESNO,
    any: ["role you are applying for located", "role located in",
          "position located in", "job located in"] },
  { answer: "Willing to relocate", type: ACE_YESNO,
    // "relocate" bare is what a name attribute says, and a question
    // containing the word is not plausibly about anything else.
    any: ["willing to relocate", "open to relocat", "relocation required",
          "able to relocate", "relocate", "relocation"] },
  { answer: "Willing to work onsite", type: ACE_YESNO,
    any: ["willing to work from", "local office", "onsite and in person",
          "work in office", "work from the office", "commute to"] },
  { answer: "Willing to travel", type: ACE_YESNO,
    any: ["willing to travel", "able to travel", "travel requirement",
          "percentage of travel"] },
  { answer: "Driving licence", type: ACE_YESNO,
    any: ["driver s license", "drivers license", "driving licence",
          "valid license to drive"] },

  // ------------------------------------------------------------------
  // Voluntary self-identification
  //
  // Answered from the bank because the user filled it in, never
  // inferred. Transgender identity and sexual orientation are asked
  // separately from gender and must not be answered from it.
  // ------------------------------------------------------------------

  { answer: "Gender", type: ACE_CHOICE,
    any: ["gender"], not: ["transgender"] },
  { answer: "Transgender", type: ACE_CHOICE, any: ["transgender"] },
  { answer: "Sexual orientation", type: ACE_CHOICE,
    any: ["sexual orientation", "lgbtq"] },
  { answer: "Race or ethnicity", type: ACE_CHOICE,
    any: ["race", "ethnicity", "hispanic", "latino", "latinx"] },
  { answer: "Veteran status", type: ACE_CHOICE,
    any: ["veteran", "military service", "armed forces"] },
  { answer: "Disability status", type: ACE_CHOICE,
    any: ["disability", "disabled"],
    not: ["accommodation"] },
  { answer: "Needs an accommodation", type: ACE_YESNO,
    any: ["accommodation", "accommodations to participate"] },

  { answer: "Why this company", type: ACE_TEXT,
    any: ["why do you want", "why are you interested", "why this company",
          "why us", "why would you like to work"] }
];

/* A control that offers a choice rather than free text.

   Radios and checkboxes are the ordinary case. Ashby renders its Yes/No
   as a pair of real <button> elements with no name attribute linking
   them and a hidden, unfocusable checkbox that is not the thing to
   click. Oracle's Candidate Experience, which Dell runs on, renders the
   same shape again, so the declared accessibility state is checked as
   well as Ashby's own attribute: a button carrying aria-pressed,
   aria-checked or role=radio is a choice however it is styled. */
function aceIsChoiceControl(field) {
  if (field.type === "radio" || field.type === "checkbox") return true;
  if (field.tagName !== "BUTTON") return false;

  return (
    field.hasAttribute("data-option") ||
    field.hasAttribute("aria-pressed") ||
    field.hasAttribute("aria-checked") ||
    field.getAttribute("role") === "radio" ||
    field.getAttribute("role") === "switch"
  );
}

/* Ashby's "How did you hear about us" and similar fields are a
   controlled autocomplete: role="combobox", its real options rendered
   only once opened, and nothing to do with a native <select>. Typing
   a raw value into it and moving on is how "Job Portal" became
   "Search Engine" on a real Applied Intuition form: the widget does
   not accept freeform text, and on an unmatched value it silently
   snapped to some option of its own choosing rather than staying
   blank. Filling it correctly needs the listbox open and a real
   option clicked, which fields.js cannot do on its own -- see
   fillOneCombobox in content.js. */
function aceIsAutocomplete(field) {
  return (
    field.tagName === "INPUT" &&
    field.getAttribute("role") === "combobox"
  );
}

/* What shape of answer this control can hold.

   Only the strict case is worth naming: a group whose every option is
   an unambiguous yes or no, with at least one of each, cannot hold
   anything else. Everything else is left permissive. */
function aceFieldKind(field, optionTexts) {
  if (!aceIsChoiceControl(field)) {
    if (field.tagName === "SELECT") return ACE_CHOICE;
    return ACE_TEXT;
  }

  if (optionTexts && aceLooksYesNo(optionTexts)) return ACE_YESNO;

  return ACE_CHOICE;
}

function aceLooksYesNo(texts) {
  if (!texts || texts.length < 2) return false;

  var yes = 0;
  var no = 0;

  for (var i = 0; i < texts.length; i++) {
    var intent = aceIntent(texts[i]);
    if (intent === "yes") yes += 1;
    else if (intent === "no") no += 1;
    else return false;
  }

  return yes >= 1 && no >= 1;
}

/* Whether an answer of this declared shape may fill a control of that
   observed kind. Strict in one direction only. */
function aceShapeFits(answerType, fieldKind) {
  if (!fieldKind || fieldKind !== ACE_YESNO) return true;

  return answerType === ACE_YESNO;
}

function aceNormalise(text) {
  return String(text || "")
    // A real Handshake form asked "now, or in the future, require
    // sponsorship", and the comma between "future" and "require"
    // broke a phrase match written as one contiguous string. Light
    // punctuation is replaced with a space rather than dropped, so
    // "future,require" cannot collapse into one word either.
    .replace(/[,;:]/g, " ")
    // Dell writes "U.S. Government" and "driver's license". Splitting
    // on the punctuation is what lets one written phrase match both
    // "u s government" and "us government".
    .replace(/[.'’`]/g, " ")
    // A field whose label is not associated with it falls back to its
    // name attribute, and those are written first_name, last_name,
    // start_date. No rule phrase contains an underscore, so turning
    // them into spaces costs nothing and recovers every such field.
    // Hyphens are deliberately left alone: collapsing them would stop
    // "e-mail" matching the email rule.
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
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

/* Real questions run long. Dell's consent and trade-embargo questions
   are each over four hundred characters, and a limit of three hundred
   discarded them and fell through to the field's generated name. The
   cap is a guard against grabbing a whole page section, so it is
   raised rather than removed. */
var ACE_MAX_QUESTION = 520;

/* The heading nearest above this control that is not one of its options.

   Nearest, not first. Taking the first was right only while a block
   held one question: on a repeating work-history block it holds
   several, and a "Current Employer" radio group read its question as
   "Employer" -- the label of the employer box higher up the same
   block. Every radio then looked like another employer field, and the
   form came out as one block per radio.

   Real headings are included as candidates too. A form writes "Current
   Employer" and "Start Date" as an h4 or a bold div, not as a label,
   because they name a group rather than one input. */
function aceHeadingIn(block, field) {
  var candidates = Array.prototype.filter.call(
    block.querySelectorAll(
      "legend, label, h1, h2, h3, h4, h5, h6, " +
      "[class*='heading'], [class*='label'], [class*='question']"
    ),
    function (node) {
      // A heading that wraps a control is an option, not the question.
      // Lever puts each choice in its own label, so without this the
      // group's question reads as "he/him" or "female".
      if (node.querySelector("input, select, textarea")) return false;
      if (node.contains(field)) return false;

      return !!aceNormalise(aceTextWithoutControls(node));
    }
  );

  if (!candidates.length) return "";

  // Document order, so the last one before the control is the nearest
  // above it. A label placed after its control still counts, but only
  // when nothing precedes it.
  var best = null;

  for (var i = 0; i < candidates.length; i++) {
    var where = candidates[i].compareDocumentPosition(field);

    if (where & Node.DOCUMENT_POSITION_FOLLOWING) {
      best = candidates[i];
    } else if (best === null) {
      best = candidates[i];
      break;
    }
  }

  if (best === null) best = candidates[0];

  return aceNormalise(
    aceTextWithoutControls(best)
  ).slice(0, ACE_MAX_QUESTION);
}

/* A block's wording with its own controls taken out.

   A select carries every option in its text, so the block around a
   Lever gender select reads "gender select male female decline to
   self-identify" and the question is lost in its own answers. */
function aceTextWithoutControls(block) {
  if (!block.querySelector("select, option, input, textarea, button")) {
    return block.textContent;
  }

  var clone = block.cloneNode(true);

  Array.prototype.forEach.call(
    clone.querySelectorAll("select, option, input, textarea, button"),
    function (node) {
      node.remove();
    }
  );

  return clone.textContent;
}

/* An option's text as written, for showing the user.

   aceOptionText normalises for comparison, which lower-cases and
   collapses the text. Showing that in the preview turned "He/Him" into
   "he/him" and printed a whole EEO definition paragraph. */
function aceOptionLabel(field) {
  var raw = aceOptionRaw(field);
  var text = raw.replace(/\s+/g, " ").trim();

  return text.length > 54 ? text.slice(0, 51).trim() + "..." : text;
}

function aceOptionRaw(field) {
  // A button carries its own option text and no wrapping label, and
  // climbing to one would find the question instead.
  if (field.tagName === "BUTTON") {
    return field.textContent || field.value || "";
  }

  var wrapping = field.closest("label");
  if (wrapping) return wrapping.textContent;

  if (field.id) {
    var labelled = document.querySelector(
      'label[for="' + CSS.escape(field.id) + '"]'
    );
    if (labelled) return labelled.textContent;
  }

  var option = field.closest("[class*='option']");
  if (option) return option.textContent;

  return field.value || "";
}

/* What this one option says, for checking against the stored answer. */
function aceOptionText(field) {
  return aceNormalise(aceOptionRaw(field));
}

function aceQuestionFor(field) {
  if (aceIsChoiceControl(field)) {
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
    if (text && text.length <= ACE_MAX_QUESTION) return text;
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

/* The declared shape of one bank answer, for callers that hold a name
   and need to know what can accept it. */
function aceAnswerTypeFor(name) {
  for (var i = 0; i < ACE_RULES.length; i++) {
    if (ACE_RULES[i].answer === name) return ACE_RULES[i].type;
  }

  return null;
}

/* Which stored answer this question is asking for, or null.

   `kind` is what the control can hold, from aceFieldKind. Passing it is
   what stops a free-text answer reaching a Yes/No pair. Omitting it
   matches on wording alone.

   The best match wins rather than the first. Before scoring, a rule
   listed earlier won on a phrase of any length, so "state" beat "role
   you are applying for located" on a real Dell question about where the
   role is. Ties keep list order, so the narrow rules still sit above
   the broad ones they would otherwise be swallowed by. */
function aceAnswerNameFor(question, kind) {
  if (!question) return null;

  var best = null;
  var bestScore = 0;

  for (var i = 0; i < ACE_RULES.length; i++) {
    var rule = ACE_RULES[i];

    if (!aceShapeFits(rule.type, kind)) continue;

    if (rule.not && rule.not.some(function (word) {
      return acePhraseIn(question, word);
    })) continue;

    var score = 0;

    (rule.any || []).forEach(function (phrase) {
      if (acePhraseIn(question, phrase) && phrase.length > score) {
        score = phrase.length;
      }
    });

    if (!score && rule.exact) {
      rule.exact.forEach(function (phrase) {
        if (question === phrase && phrase.length > score) {
          score = phrase.length;
        }
      });
    }

    if (score > bestScore) {
      bestScore = score;
      best = rule.answer;
    }
  }

  return best;
}


/* Choosing between the options a form offers.

   The stored answers are short, and real forms are not: "Yes" has to
   reach "Yes, I am authorized to work in the United States", and
   "I do not have any disability" has to reach "No, I don't have a
   disability, or have not had one in the past". Substring matching
   both fails that and misfires: "no" appears inside "I do not know".

   Four rules, strongest first, and every one of them refuses to answer
   when two options fit equally well. A wrong EEO answer, or a
   sponsorship answer inverted, is worse than a blank the user fills
   themselves. */

/* Consent controls say "I Agree" rather than "Yes", and Dell's decline
   option is a paragraph beginning "I Do Not Agree". Both shapes have to
   read as an intent or a consent question cannot be answered at all. */
var ACE_AFFIRMATIVE =
  /^(yes|y|true|i am|i do|i have|i agree|agree|i accept|accept|i consent|consent|i acknowledge|acknowledge|i certify|certify|confirm|authorized|authorised)\b/;
var ACE_NEGATIVE =
  /^(no|n|false|i am not|i do not|i don't|i dont|not |none|never|disagree|i disagree|decline|i decline)\b/;

// Words carrying no distinguishing meaning, so overlap is scored on
// what the options actually differ by.
var ACE_STOPWORDS = {
  i:1, a:1, an:1, the:1, of:1, to:1, in:1, on:1, at:1, or:1, and:1, is:1,
  am:1, are:1, be:1, do:1, does:1, did:1, have:1, has:1, had:1, my:1,
  me:1, you:1, your:1, for:1, with:1, that:1, this:1, it:1, as:1, by:1,
  not:1, any:1, one:1, past:1, been:1, will:1, would:1, currently:1
};

function aceWords(text) {
  return aceNormalise(text)
    .replace(/[^a-z0-9 ]/g, " ")
    .split(/\s+/)
    .filter(function (word) { return word && !ACE_STOPWORDS[word]; });
}

function aceIntent(text) {
  var value = aceNormalise(text).replace(/[^a-z0-9' ]/g, "");
  if (ACE_NEGATIVE.test(value)) return "no";
  if (ACE_AFFIRMATIVE.test(value)) return "yes";
  return null;
}

/* Return the index of the option that answers, or -1.

   `options` is a list of the visible texts, in order. */
/* `aliases` is the other wordings ACE ships for this same answer.

   Forms name the same thing differently and none of them is wrong: a
   stored "Job board" matches nothing on a Dell form whose option reads
   "Job Board (e.g., LinkedIn, Indeed, Glassdoor)", and nothing at all
   on one offering only "Indeed".

   An earlier attempt had the user type the synonyms themselves, which
   was the wrong half of the problem to solve: knowing that a job board
   and a job portal are the same thing is ACE's job. They now come from
   the catalogue the answers page picked from, so the user chooses a
   concept once and never a wording.

   Each is tried in turn, and the answer's own text always goes first.
   The refusal to pick between two equally good options is unchanged, so
   this widens what can be recognised without widening what can be
   guessed. */
function aceChooseOption(options, answer, aliases) {
  if (aliases && aliases.length) {
    var tried = [answer].concat(aliases);

    for (var a = 0; a < tried.length; a++) {
      var found = aceChooseOption(options, tried[a]);
      if (found >= 0) return found;
    }

    return -1;
  }

  var wanted = aceNormalise(answer);
  if (!wanted) return -1;

  var texts = options.map(aceNormalise);

  function only(matches) {
    // Exactly one candidate, or nothing. Two equally good options mean
    // the answer does not distinguish them and ACE must not pick.
    return matches.length === 1 ? matches[0] : -1;
  }

  function indices(test) {
    var found = [];
    texts.forEach(function (text, index) {
      if (text && test(text)) found.push(index);
    });
    return found;
  }

  var exact = indices(function (text) { return text === wanted; });
  if (exact.length) return exact[0];

  var contained = indices(function (text) {
    return acePhraseIn(text, wanted) || acePhraseIn(wanted, text);
  });
  if (contained.length === 1) return contained[0];

  // "I do not have any disability" against "No, I don't have a
  // disability, or have not had one in the past": the shape of the
  // answer decides, then the words settle which of the negatives.
  var intent = aceIntent(answer);
  if (intent) {
    var sameIntent = indices(function (text) {
      return aceIntent(text) === intent;
    });

    if (sameIntent.length === 1) return sameIntent[0];

    if (sameIntent.length > 1) {
      var narrowed = aceBestOverlap(texts, answer, sameIntent);
      if (narrowed >= 0) return narrowed;
    }
  }

  if (contained.length > 1) {
    var settled = aceBestOverlap(texts, answer, contained);
    if (settled >= 0) return settled;
  }

  return only(contained);
}

/* The candidate sharing the most meaningful words with the answer.

   Requires a clear winner: a tie means the answer does not choose
   between them, and a single shared word is coincidence rather than
   agreement. */
function aceBestOverlap(texts, answer, candidates) {
  var wanted = aceWords(answer);
  if (!wanted.length) return -1;

  var best = -1;
  var bestScore = 0;
  var tied = false;

  candidates.forEach(function (index) {
    var words = aceWords(texts[index]);
    var score = 0;
    wanted.forEach(function (word) {
      if (words.indexOf(word) >= 0) score += 1;
    });

    if (score > bestScore) {
      bestScore = score;
      best = index;
      tied = false;
    } else if (score === bestScore && score > 0) {
      tied = true;
    }
  });

  return (!tied && bestScore >= 1) ? best : -1;
}


/* ----------------------------------------------------------------------
   Repeating blocks: work history and education

   A form asks these as one block repeated: employer, title, a Yes/No
   for whether it is current, four date dropdowns, a description, then a
   Remove link and another identical block underneath. Real Workday and
   Oracle forms ask for three or four.

   Nothing above can fill them, and the reason is structural rather than
   a missing rule. The answer bank is one value per question, so "what is
   your employer" has one answer, and a second block asking the same
   question would get the same answer again. These need the Nth block to
   be filled from the Nth job.

   So the fields are identified by role within a block, the blocks are
   found and put in document order, and the entries are handed out one
   per block.
   ---------------------------------------------------------------------- */

/* What one field is, inside a history block. Deliberately separate from
   ACE_RULES: "employer" and "job title" are broad enough to swallow
   unrelated questions, and they are only trustworthy once a block has
   already been established around them. */
var ACE_HISTORY_ROLES = [
  { role: "employer",
    any: ["employer", "company name", "company", "organisation",
          "organization", "school", "university", "institution"] },
  { role: "jobTitle",
    any: ["job title", "title", "position title", "your role", "degree",
          "qualification"] },
  { role: "isCurrent",
    any: ["current employer", "currently work", "current position",
          "is this your current", "currently attend", "current school"] },
  { role: "startMonth",
    any: ["start date month", "from month", "start month"] },
  { role: "startYear",
    any: ["start date year", "from year", "start year"] },
  { role: "endMonth",
    any: ["end date month", "to month", "end month"] },
  { role: "endYear",
    any: ["end date year", "to year", "end year"] },
  { role: "description",
    any: ["job description", "description", "responsibilities",
          "what did you do", "achievements"] },
  { role: "location",
    any: ["employer location", "company location", "job location",
          "work location"] }
];

var ACE_MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

/* The role of one field inside a block, or null.

   Dates are the awkward part. A form labels the four dropdowns "Month"
   and "Year" twice over, and which pair is the start and which the end
   is said once, in a heading above them, that no label associates with
   any control. So the heading is looked for first, and the plain
   "Month" or "Year" is then resolved by which half of the block it sits
   in rather than by its own words. */
function aceHistoryRole(field, question) {
  // Longest matched phrase wins, for the same reason the answer rules
  // score rather than take the first hit: "Current Employer" contains
  // "employer", so a first-match rule read the Yes/No beside the dates
  // as another employer box. That made every radio its own block, and
  // the form came out as four blocks of one field each.
  var best = null;
  var bestScore = 0;

  for (var i = 0; i < ACE_HISTORY_ROLES.length; i++) {
    var rule = ACE_HISTORY_ROLES[i];

    rule.any.forEach(function (phrase) {
      if (acePhraseIn(question, phrase) && phrase.length > bestScore) {
        bestScore = phrase.length;
        best = rule.role;
      }
    });
  }

  if (best) return best;

  // A bare "Month" or "Year", which is what these actually say.
  if (acePhraseIn(question, "month")) return "month";
  if (acePhraseIn(question, "year")) return "year";

  return null;
}

/* Whether a bare Month/Year dropdown belongs to the start or the end.

   Read off the nearest preceding text that says one or the other,
   because that is where the form says it: a "Start Date" heading over
   the first pair and "End Date" over the second. Falls back to document
   order within the block, where the first pair is the start. */
function aceDateSide(field, block) {
  // Read backwards through the block in document order, which is how a
  // person reads it: the nearest heading above a dropdown is the one
  // that names it.
  //
  // Climbing the ancestors instead found nothing, because on a real
  // form the four dropdowns and both headings are siblings. Every
  // ancestor holds "Start Date" and "End Date" together and so says
  // neither, and the dates were left unassigned on every block.
  var nodes = Array.prototype.slice.call(
    block.querySelectorAll("*")
  );

  var at = nodes.indexOf(field);
  if (at < 0) return null;

  for (var i = at - 1; i >= 0; i--) {
    var node = nodes[i];
    var tag = node.tagName;

    // A control is not a heading, and an option's text would otherwise
    // be read as one.
    if (
      tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" ||
      tag === "BUTTON" || tag === "OPTION"
    ) continue;

    // A container holds both headings and so names neither. Only a
    // short piece of text can be the one that names this dropdown.
    if (node.querySelector("input, select, textarea, button")) continue;

    var text = aceNormalise(node.textContent || "");
    if (!text || text.length > 40) continue;

    if (acePhraseIn(text, "end date") || text === "to") return "end";
    if (acePhraseIn(text, "start date") || text === "from") return "start";
  }

  return null;
}

/* The month a stored number names, as a form writes it. */
function aceMonthName(month) {
  var index = Number(month) - 1;

  return (index >= 0 && index < 12) ? ACE_MONTHS[index] : "";
}

/* What to put in each field of a block, given one stored entry.

   Returns null where the entry says nothing, so the field is left alone
   rather than filled with a blank. */
function aceHistoryValue(entry, role) {
  if (!entry) return null;

  if (role === "employer") return entry.employer || null;
  if (role === "jobTitle") return entry.job_title || null;
  if (role === "location") return entry.location || null;
  if (role === "description") return entry.description || null;
  if (role === "isCurrent") return entry.is_current ? "Yes" : "No";

  if (role === "startMonth") return aceMonthName(entry.start_month) || null;
  if (role === "endMonth") return aceMonthName(entry.end_month) || null;

  if (role === "startYear") {
    return entry.start_year ? String(entry.start_year) : null;
  }

  if (role === "endYear") {
    return entry.end_year ? String(entry.end_year) : null;
  }

  return null;
}
