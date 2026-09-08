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

  // Must stay empty.
  ["do you identify as transgender?", null],
  ["would you like to receive communications via sms and email", null],
  ["have you worked at doordash?*", null],
  ["applicant privacy acknowledgement *", null],
  ["what is your age range?", null],
  ["current company", null],
  ["video link url", null],
  ["we work from our offices on mondays, tuesdays, and thursdays", null]
];

/* Choosing between the options a form offers. The stored answers are
   short and real options are sentences, so every one of these was a
   miss or a misfire before the matcher scored intent and overlap. */
var OPTION_CASES = [
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

CASES.forEach(function (pair) {
  var got = aceAnswerNameFor(pair[0]);

  if (got !== pair[1]) {
    failures += 1;
    console.log(
      "FAIL  " + JSON.stringify(pair[0]) +
      "\n      got " + JSON.stringify(got) +
      ", want " + JSON.stringify(pair[1])
    );
  }
});

var total = CASES.length + OPTION_CASES.length;

console.log(
  failures
    ? failures + " of " + total + " failed"
    : "all " + total + " cases pass"
);

process.exit(failures ? 1 : 0);
