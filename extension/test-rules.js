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

var failures = 0;

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

console.log(
  failures
    ? failures + " of " + CASES.length + " failed"
    : "all " + CASES.length + " cases pass"
);

process.exit(failures ? 1 : 0);
