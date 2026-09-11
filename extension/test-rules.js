/* Rule checks for the field matcher: node test-rules.js

   Every case here came from a real Greenhouse, Ashby or Lever form.
   Half of them are questions that must NOT be answered, because a
   wrong answer in a form about to be sent to an employer is worse
   than a blank one, and each of those was a bug first. */

global.document = { querySelector: function () { return null; } };
global.CSS = { escape: function (value) { return value; } };

eval(require("fs").readFileSync(__dirname + "/fields.js", "utf8"));

var CASES = [
  // Sponsorship reads as two near-identical questions, and Greenhouse
  // says "immigration sponsorship", which the first rules missed.
  ["will you now require immigration sponsorship by our company",
   "Need sponsorship now"],
  ["will you in the future require immigration sponsorship by our company",
   "Need sponsorship in future"],
  ["will you now or in the future require notion to sponsor",
   "Need sponsorship in future"],
  ["are you legally authorized to work in the united states?",
   "Work authorisation"],

  ["first name*", "First name"],
  ["last name*", "Last name"],
  ["full name", "Full name"],
  ["email*", "Email"],
  ["phone*", "Phone"],
  ["country*", "Country"],
  ["location (city)*", "City"],
  ["school", "University"],
  ["degree", "Degree"],
  ["linkedin profile*", "LinkedIn"],
  ["github url", "GitHub"],
  ["other website url", "Portfolio"],

  // Plural. The form writes "pronouns", the rule says "pronoun".
  ["pronouns", "Pronouns"],
  ["what pronouns would you like our team to use when addressing you?",
   "Pronouns"],

  ["gender", "Gender"],
  ["what gender do you identify as?", "Gender"],
  ["race", "Race or ethnicity"],
  ["are you hispanic or latinx?", "Race or ethnicity"],
  ["veteran status", "Veteran status"],
  ["disability status", "Disability status"],
  ["how did you hear about this opportunity? (select all that apply)",
   "How did you hear about us"],

  // "ethnicity" contains "city". A raw substring test put a stored
  // city into this question on a real Lever form.
  ["i identify my ethnicity as...select all that apply",
   "Race or ethnicity"],

  // Asked separately from gender, and must never be answered from it.
  // It has its own row now, so it reaches that rather than nothing;
  // an unfilled row still leaves the field alone and reports it.
  ["do you identify as transgender?", "Transgender"],

  // Must stay empty.
  ["would you like to receive communications via sms and email", null],
  ["have you worked at doordash?*", null],
  ["applicant privacy acknowledgement *", null],
  ["what is your age range?", null],
  ["current company", null],
  ["video link url", null],
  ["we work from our offices on mondays, tuesdays, and thursdays", null],

  // Found on a real Handshake application form.
  ["are you willing to relocate for this position if required?",
   "Willing to relocate"],
  ["this role is onsite and in person. are you willing to work "
   + "from our local office monday-friday?", "Willing to work onsite"],

  // The comma between "future" and "require" broke a phrase match
  // written as one contiguous string on the real form's own wording.
  ["will you now, or in the future, require sponsorship for "
   + "employment visa status?", "Need sponsorship in future"]
];

/* Every question on one real Dell application, which runs on Oracle's
   Candidate Experience and asks twenty-two of them as Yes/No pairs.

   Before these, the matcher recognised four and mis-routed five: the
   "United States" in three separate questions matched the rule for a
   postal state, and "are you a recent graduate (less than 3 years
   since you completed your most recent degree)" matched the rule for a
   degree. Both are the shape of bug that fills a box with something
   the user never said.

   The second element is the field kind, which is what the page's own
   options say the control can hold. */
var DELL_CASES = [
  ["is your current employer a reseller of dell technologies "
   + "(including dell, dell emc and affiliated companies), products, "
   + "services or technologies?", "yesno",
   "Employer relationship with this company"],
  ["are you a recent graduate (less than 3 years since you completed "
   + "your most recent degree)?", "yesno", "Recent graduate"],
  ["as part of the candidate verification process, we may be taking "
   + "screenshot(s) in between and/or at the start of the interview "
   + "process. for this purpose, please confirm your acceptance to "
   + "the following statement", "yesno", "Agree to the terms shown"],
  ["are you a foreign national and / or citizen (or dual citizen) of "
   + "a country with which the united states has a trade embargo",
   "yesno", "Citizen of an embargoed country"],
  ["i am currently or have been employed by the u.s. government?",
   "yesno", "Employed by the federal government"],
  ["are you legally authorized to work in the country where this "
   + "requisition is posted?", "yesno", "Work authorisation"],
  ["are you subject to a non-compete agreement with your current or "
   + "previous employer", "yesno", "Bound by a non-compete"],
  ["are you eligible to work and have the proper work authorization "
   + "documentation for united states?", "yesno", "Work authorisation"],
  ["are you on a temporary work visa?", "yesno",
   "On a temporary work visa"],
  ["do you now or in the future require immigration benefit "
   + "sponsorship from dell in order to retain or extend your "
   + "authorization to work in the united states?", "yesno",
   "Need sponsorship in future"],
  ["please confirm your preferred method of communication during the "
   + "recruitment process", "choice", "Preferred contact method"],
  ["is the role you are applying for located in the united states?",
   "yesno", "Role is located in the US"],
  ["i am currently or have been employed by state or local "
   + "government?", "yesno", "Employed by state or local government"],
  ["have you ever been involuntarily discharged or separated from a "
   + "job?", "yesno", "Involuntarily discharged from a job"],
  ["by selecting yes, you are granting dell technologies permission "
   + "to retain your application information for subsequent job "
   + "opportunities:", "yesno", "Consent to keep my application on file"],
  ["are you at least 18 years old?", "yesno", "At least 18 years old"],
  ["do you or your relative(s) own any technology related companies "
   + "or any businesses that are trading with or in competition with "
   + "dell's business?", "yesno", "Relative owns a competing business"],
  ["are dell technologies personnel on site permanently or on a "
   + "regular basis at your employer's facilities?", "yesno",
   "Employer relationship with this company"],

  // A label not associated with its input leaves only the name
  // attribute, and those are written with underscores or run together.
  // A whole JazzHR form filled nothing but email and phone before
  // aceNormalise split on the underscore.
  ["first_name", "text", "First name"],
  ["last_name", "text", "Last name"],
  ["start_date", "text", "Earliest start date"],
  ["startdate", "text", "Earliest start date"],
  ["relocate", "yesno", "Willing to relocate"],
  ["felony", "yesno", "Criminal conviction"],

  // Hyphens stay, or "e-mail" stops reaching the email rule.
  ["e-mail", "text", "Email"],

  // What the kind is for. The same wording offered as a Yes/No pair
  // must not reach an answer that is free text, whatever it matches.
  ["what is your current state?", "yesno", null],
  ["highest degree completed", "yesno", null],
  ["what is your current state?", "text", "State"]
];

/* Choosing between the options a form offers. The stored answers are
   short and real options are sentences, so every one of these was a
   miss or a misfire before the matcher scored intent and overlap. */
var OPTION_CASES = [
  // A city written shorter than the list writes it.
  [["Seattle, Washington, United States", "Boston, Massachusetts, United States"],
   "Seattle WA", 0],
  [["Bothell, Washington, United States", "Boston, Massachusetts, United States"],
   "Bothell", 0],
  // "bothell" does not start "boston", so nothing is chosen.
  [["Boston, Massachusetts, United States"], "Bothell", -1],
  // A shortened form that fits two options has chosen neither.
  [["San Francisco, California, United States",
    "San Fransisco de Macoris, Dominican Republic"], "San Fr", -1],
  // Still matched outright when the answer is a whole leading word:
  // "No" is the first word of the option, which is containment, not
  // a shortening, and that tier runs first.
  [["No, I do not have a disability", "Not applicable"], "No", 0],

  // A phone widget prints the dial code beside the country name. With
  // it attached nothing matched, so MongoDB's required Country stayed
  // empty and took the phone number down with it.
  [["United States +1", "United Kingdom +44", "India +91"],
   "United States Of America", 0],
  // The long name must not be dragged off by the short one sharing
  // its opening words.
  [["United States Minor Outlying Islands +1", "United States +1"],
   "United States Of America", 1],
  [["India +91", "United States +1"], "India", 0],
  // Nothing here carries a dial code, so the stripping must not fire
  // and must not invent a match.
  [["Yes", "No"], "United States Of America", -1],

  [["Yes", "No"], "Yes", 0],
  [["Yes, I am authorized to work in the United States",
    "No, I am not authorized"], "Yes", 0],
  [["Yes, I will require sponsorship",
    "No, I will not require sponsorship"], "No", 1],

  // The case that failed on a real Lever form: the user's wording
  // shares no phrase with the option, only its negative shape.
  [["Yes, I have a disability, or have had one in the past",
    "No, I do not have a disability, or have not had one in the past",
    "I do not wish to answer"],
   "I do not have any disability", 1],

  [["I identify as one or more of the classifications of a protected veteran",
    "I am not a protected veteran",
    "I decline to self-identify"], "I am not a protected veteran", 1],

  // "male" is inside "female", which ticked both boxes on a real form.
  [["Male", "Female", "Decline to self-identify"], "Male", 0],
  [["Asian (not Hispanic or Latino)", "White (not Hispanic or Latino)",
    "Two or more races"], "Asian", 0],
  [["He/Him", "She/Her", "They/Them", "Prefer not to say"], "He/Him", 0],

  // "no" is inside "know".
  [["I do not know", "Yes", "No"], "No", 2],

  // Refusing is the right answer when nothing fits, or when two fit
  // equally well.
  [["Bachelors degree", "Masters degree"], "PhD", -1],
  [["Option A", "Option B"], "Something else", -1]
];

/* The same stored answer against forms that word it differently.

   ACE ships these wordings, so the user picks "Job board" once and
   never has to predict that Dell writes it one way and Ashby another.
   [options, answer, aliases, expected index] */
var ALIAS_CASES = [
  [["Job Board (e.g., LinkedIn, Indeed, Glassdoor)", "Employee Referral",
    "Search Engine"],
   "Job board", ["job board", "job portal", "indeed", "glassdoor"], 0],

  // The same answer on a board that never uses the phrase at all.
  [["AngelList", "Conference", "Indeed", "Other"],
   "Job board", ["job board", "job portal", "indeed", "glassdoor"], 2],

  // A consent control saying I Agree rather than Yes.
  [["I Agree", "I Do Not Agree (Please note that appearing for the "
    + "interview will be deemed as consent)"],
   "Yes", ["yes", "i agree", "agree", "i accept"], 0],

  // Aliases widen what is recognised, never what is guessed: nothing
  // here means this thing, so it stays blank.
  [["Carrier pigeon", "Smoke signal"],
   "Job board", ["job board", "job portal", "indeed"], -1]
];

var failures = 0;

OPTION_CASES.forEach(function (entry) {
  var got = aceChooseOption(entry[0], entry[1]);

  if (got !== entry[2]) {
    failures += 1;
    console.log(
      "FAIL  answer " + JSON.stringify(entry[1]) +
      "\n      got index " + got + ", want " + entry[2] +
      "\n      options " + JSON.stringify(entry[0])
    );
  }
});

ALIAS_CASES.forEach(function (entry) {
  var got = aceChooseOption(entry[0], entry[1], entry[2]);

  if (got !== entry[3]) {
    failures += 1;
    console.log(
      "FAIL  answer " + JSON.stringify(entry[1]) + " with aliases" +
      "\n      got index " + got + ", want " + entry[3] +
      "\n      options " + JSON.stringify(entry[0])
    );
  }
});

DELL_CASES.forEach(function (entry) {
  var got = aceAnswerNameFor(aceNormalise(entry[0]), entry[1]);

  if (got !== entry[2]) {
    failures += 1;
    console.log(
      "FAIL  [" + entry[1] + "] " + JSON.stringify(entry[0].slice(0, 60)) +
      "\n      got " + JSON.stringify(got) +
      ", want " + JSON.stringify(entry[2])
    );
  }
});

CASES.forEach(function (pair) {
  // Through aceNormalise, matching how this is actually called: the
  // pinned wording is written as a person reads it on the page, not
  // pre-cleaned by hand, so a fixture with real punctuation is what
  // it looks like in production.
  var got = aceAnswerNameFor(aceNormalise(pair[0]));

  if (got !== pair[1]) {
    failures += 1;
    console.log(
      "FAIL  " + JSON.stringify(pair[0]) +
      "\n      got " + JSON.stringify(got) +
      ", want " + JSON.stringify(pair[1])
    );
  }
});

var total = CASES.length + OPTION_CASES.length + DELL_CASES.length +
  ALIAS_CASES.length;

console.log(
  failures
    ? failures + " of " + total + " failed"
    : "all " + total + " cases pass"
);

process.exit(failures ? 1 : 0);
