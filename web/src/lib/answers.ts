import type { Answer } from "./types";

// Sections are cosmetic and live here rather than in the database, so an
// answer the user adds themselves still appears, under Other.
export const ANSWER_SECTIONS: [string, string[]][] = [
  ["You", ["First name", "Last name", "Full name", "Email", "Phone", "Phone type", "Pronouns"]],
  ["Address", ["Location", "Address", "Address line 2", "City", "State", "Postcode", "Country"]],
  ["Links", ["LinkedIn", "GitHub", "Portfolio"]],
  [
    "Work authorisation",
    [
      "Work authorisation",
      "Need sponsorship now",
      "Need sponsorship in future",
      "Work authorization through spouse visa",
      "Eligible for bilateral visa classification",
      "Currently on F-1 student visa",
      "Maximum OPT or CPT authorization end date",
      "On a temporary work visa",
      "Visa type",
      "US citizen or permanent resident",
      "Citizen of an embargoed country",
      "Citizen or permanent resident of restricted regions",
      "Security clearance",
    ],
  ],
  [
    "Background",
    [
      "Employed by the federal government",
      "Employed by state or local government",
      "Federal government employment in last 5 years",
      "Federal government conflict with employer",
      "Government employment in last 5 years",
      "Immediate family government employment in last 5 years",
      "Government contract suspension or debarment",
      "Involuntarily discharged from a job",
      "Criminal conviction",
      "Bound by a non-compete",
      "Previously employed by this company",
      "Previously employed by ServiceNow",
      "Previously employed by PwC",
      "Big Four employment in prior 18 months",
      "Related to an employee here",
      "Employer relationship with this company",
      "Relative owns a competing business",
      "Government official",
      "Related to a government official",
      "Referred by an employee",
      "Referred by a merchant or third party",
    ],
  ],
  ["Consent", ["Consent to keep my application on file", "Agree to the terms shown", "Consent to AI in hiring"]],
  [
    "Education",
    [
      "University",
      "Degree",
      "Field of study",
      "GPA",
      "Graduation date",
      "Years of experience",
      "Recent graduate",
      "ServiceNow RiseUp graduate",
      "Language",
      "Language fluency",
      "Fluent in this language",
      "Experience with this tech stack",
      "Enterprise software experience",
    ],
  ],
  [
    "Logistics",
    [
      "Earliest start date",
      "How did you hear about us",
      "Preferred contact method",
      "At least 18 years old",
      "Role is located in the US",
      "Willing to relocate",
      "Willing to work onsite",
      "Willing to travel",
      "Driving licence",
      "Needs an accommodation",
    ],
  ],
  [
    "Voluntary disclosures",
    ["Gender", "Race or ethnicity", "Hispanic or Latino", "Veteran status", "Disability status", "Transgender", "Sexual orientation"],
  ],
  ["Written answers", ["Salary expectation", "Why this company"]],
];

export function answerSections<T extends Pick<Answer, "label">>(answers: T[]): [string, T[]][] {
  const seen = new Set<T>();
  const out: [string, T[]][] = [];
  for (const [title, labels] of ANSWER_SECTIONS) {
    const rows: T[] = [];
    for (const label of labels)
      for (const a of answers)
        if (a.label === label && !seen.has(a)) {
          seen.add(a);
          rows.push(a);
        }
    if (title === "Background")
      for (const a of answers)
        if (a.label.startsWith("Previously employed by ") && !seen.has(a)) {
          seen.add(a);
          rows.push(a);
        }
    if (rows.length) out.push([title, rows]);
  }
  const other = answers.filter((a) => !seen.has(a));
  if (other.length) out.push(["Other", other]);
  return out;
}
