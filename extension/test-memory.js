const assert = require("node:assert/strict");
const memory = require("./memory.js");

const first = "Explain a distributed systems design tradeoff you faced";
const equivalent = "Describe a difficult distributed architecture tradeoff you handled";
const saved = [{ concept: memory.concept(first), question: first, answer: "Synthetic approved answer", answer_type: "text", reuse_policy: "reusable" }];

assert.equal(memory.concept(first), memory.concept(equivalent));
assert.equal(memory.resolve(equivalent, "text", saved)?.answer, "Synthetic approved answer");
assert.equal(memory.resolve(equivalent, "choice", saved), null);
assert.equal(memory.policy("Do you have authorization to work in the US?"), "sensitive");
assert.equal(memory.policy("Will you require sponsorship in the future?"), "sensitive");
assert.equal(memory.policy("Have you ever worked at Cedarcloud?"), "company");
assert.equal(memory.policy("Why do you want to join Cedarcloud?"), "employer_motivation");
assert.equal(memory.policy("Have you applied to Cedarcloud before?"), "company");
assert.equal(memory.policy("Do you have relatives employed at Cedarcloud?"), "company");
assert.equal(memory.policy("Please acknowledge this by entering today's date."), "sensitive");
assert.equal(memory.resolve("Why do you want to join Northstar Labs?", "text", saved), null);
assert.equal(memory.resolve("Do you have authorization to work in the US?", "text", saved), null);
assert.equal(memory.equivalent("Did you work in Python?", "Did you not work in Python?", "text", "text"), false);
assert.equal(memory.resolve(equivalent, "text", saved.concat(saved))?.answer, saved[0].answer);
assert.equal(memory.resolve(equivalent, "text", saved.concat({ ...saved[0], answer: "Conflicting fictional answer" })), null);
const testing = "Describe your experience writing integration tests";
const testingSaved = [{ concept: memory.concept(testing), question: testing, answer: "Fictional approved testing answer", answer_type: "text", reuse_policy: "reusable" }];
assert.equal(memory.resolve("Please tell us about your experience writing integration tests.", "text", testingSaved)?.answer, testingSaved[0].answer);
assert.equal(memory.resolve("Could you describe your experience writing integration tests?", "text", testingSaved)?.answer, testingSaved[0].answer);
assert.equal(memory.resolve("Describe your experience writing unit tests", "text", testingSaved), null);
assert.equal(memory.resolve("Describe your experience writing integration tests without external services", "text", testingSaved), null);
assert.equal(memory.resolve("Describe your experience writing integration tests in the last 3 years", "text", testingSaved), null);
assert.equal(memory.resolve("Describe your experience writing integration tests", "choice", testingSaved), null);
assert.equal(memory.equivalent("Describe your experience building Python APIs", "How many years of experience do you have building Python APIs?", "text", "text"), false);
assert.equal(memory.equivalent("Describe your experience building Python 2 APIs", "Describe your experience building Python 3 APIs", "text", "text"), false);
assert.notEqual(memory.concept("How many years have you worked building Python APIs?"), memory.concept("How many projects have you built using Python APIs?"));
for (const question of [
  "Why this company?",
  "Why do you want to work at Cobalt Systems?",
  "What interests you about joining us?",
  "What excites you about working at Northstar Labs?",
  "Please describe your motivation for applying here",
]) {
  assert.equal(memory.isEmployerMotivation(question), true, question);
  assert.equal(memory.resolve(question, "text", [{ ...saved[0], question }]), null);
}
for (const question of [
  "Why did you choose Terraform instead of Pulumi?",
  "Why was eventual consistency appropriate?",
  "Explain a technical design tradeoff you faced",
]) assert.equal(memory.isEmployerMotivation(question), false, question);
assert.equal(memory.equivalent("Describe your current Python API experience", "Describe your previous Python API experience", "text", "text"), false);
console.log("memory safety cases pass");

const fs = require('node:fs');
const path = require('node:path');
const screening = JSON.parse(fs.readFileSync(path.join(__dirname, '../backend/tests/fixtures/screening_memory.json'), 'utf8'));
for (const row of screening) {
  assert.equal(memory.screeningConcept(row.question, 'https://fixture.example/apply'), row.key, row.question);
  if (!row.key) continue;
  const record = { concept: row.key, question: row.question, answer: 'No', answer_type: 'yesno', reuse_policy: 'scoped' };
  assert.equal(memory.resolve(row.question, 'choice', [record], 'https://fixture.example/apply')?.answer, 'No');
  assert.equal(memory.resolve(row.question, 'text', [record], 'https://fixture.example/apply'), null);
  assert.equal(memory.resolve(row.question, 'choice', [{ ...record, reuse_policy: 'reusable' }], 'https://fixture.example/apply'), null);
}
const tenantQuestion = screening[7].question;
const tenantKey = memory.screeningConcept(tenantQuestion, 'https://job-boards.greenhouse.io/silverpine/jobs/1');
const tenantRecord = { concept: tenantKey, question: tenantQuestion, answer: 'No', answer_type: 'yesno', reuse_policy: 'scoped' };
assert.equal(memory.resolve(tenantQuestion, 'yesno', [tenantRecord], 'https://job-boards.greenhouse.io/another-lab/jobs/2'), null);
assert.equal(memory.resolve(tenantQuestion, 'yesno', [tenantRecord], 'https://job-boards.greenhouse.io/silverpine/jobs/3')?.answer, 'No');
assert.notEqual(memory.screeningConcept(screening[0].question), memory.screeningConcept(screening[1].question));
assert.notEqual(memory.screeningConcept(screening[5].question), memory.screeningConcept(screening[5].question.replace('Silverpine Labs', 'Another Fictional Lab')));
assert.notEqual(memory.screeningConcept(screening[5].question), memory.screeningConcept(screening[5].question.replace(' or any of its subsidiaries', '')));
assert.notEqual(memory.screeningConcept('Have you ever worked for Silverpine Labs?'), memory.screeningConcept('Have you previously worked for Silverpine Labs?'));
for (const [a, b] of [
  ['https://jobs.eu.lever.co/silverpine/one', 'https://jobs.eu.lever.co/another/two'],
  ['https://silverpine.wd5.myworkdayjobs.com/en-US/Parent/job/one', 'https://silverpine.wd5.myworkdayjobs.com/en-US/Subsidiary/job/two'],
  ['https://wd5.myworkdaysite.com/recruiting/silverpine/Main/job/one', 'https://wd5.myworkdaysite.com/recruiting/another/Main/job/two'],
]) assert.notEqual(memory.screeningConcept(tenantQuestion, a), memory.screeningConcept(tenantQuestion, b));
assert.equal(memory.storagePolicy(tenantQuestion, 'yesno', 'https://unknown.greenhouse.io/apply'), null);
assert.equal(memory.equivalent('Describe your experience building integration tests', 'Tell us about your experience writing integration tests', 'text', 'text'), true);
console.log('scoped screening and paraphrase cases pass');

// Owner decision 2026-10-28: every owner answer is learned and reused for
// questions with the same meaning. Fictional employers only.
const ctx = 'https://silverpine.wd5.myworkdayjobs.com/en-US/Careers/job/Engineer_R1/apply/applyManually';
assert.equal(memory.learnable('Do you require any type of sponsorship now or in the future?'), true);
assert.equal(memory.learnable('Please select your gender.'), true);
assert.equal(memory.learnable('Why do you want to join Silverpine?'), false);
assert.equal(memory.learnable('Electronic signature: type your full name'), false);
const sim = (a, b) => memory.similarity(memory.topic(a), memory.topic(b));
assert.ok(sim('Describe your experience writing integration tests', 'Please tell us about your experience writing integration tests.') >= 0.72);
assert.ok(sim('Describe your experience writing integration tests', 'Describe your experience writing unit tests') < 0.72);
assert.ok(sim('Do you require sponsorship now?', 'Do you require sponsorship in the future?') < 0.72, 'timeframe');
assert.ok(sim('Are you comfortable working in an office five days a week?', 'Are you comfortable working in an office three days a week?') < 0.72, 'number words');
assert.ok(sim('Are you authorized to work in the U.S.?', 'Are you legally authorized to work in Canada?') < 0.72, 'country');
assert.ok(sim('Are you willing to relocate?', 'Are you willing to travel?') < 0.72);
assert.equal(memory.employerScoped('Have you ever worked for Silverpine Labs?'), true);
assert.equal(memory.employerScoped('Were you referred by an employee?'), true);
assert.equal(memory.employerScoped('Do you have relatives working at Silverpine?'), false);
assert.equal(memory.employerScoped('Have you worked with React?'), false);
const bankKey = memory.learnedConcept('Please select your gender.', 'choice', ctx, 'Gender', ['silverpine']);
assert.equal(bankKey, 'learn:bank:choice:gender');
const genderRecord = { concept: bankKey, question: 'Please select your gender.', answer: 'Male', answer_type: 'choice', reuse_policy: 'learned' };
assert.equal(memory.learnedMatch('What is your gender?', 'yesno', [genderRecord], 'https://boards.greenhouse.io/cobalt/jobs/1', 'Gender', ['cobalt'])?.answer, 'Male');
assert.equal(memory.learnedMatch('What is your gender?', 'text', [genderRecord], 'https://boards.greenhouse.io/cobalt/jobs/1', 'Gender', ['cobalt']), null, 'text never takes a choice answer');
const workedKey = memory.learnedConcept('Have you previously worked for Silverpine?', 'text', ctx, null, ['silverpine']);
assert.match(workedKey, /@silverpine\.wd5\.myworkdayjobs\.com\/careers$/);
const workedRecord = { concept: workedKey, question: 'Have you previously worked for Silverpine?', answer: 'No', answer_type: 'text', reuse_policy: 'learned' };
assert.equal(memory.learnedMatch('Have you previously worked for Cobalt?', 'text', [workedRecord], 'https://cobalt.wd1.myworkdayjobs.com/en-US/Jobs/job/X/apply', null, ['cobalt']), null, 'another employer never reuses it');
assert.equal(memory.learnedConcept('Are you a U.S. citizen or permanent resident?', 'choice', ctx, 'US citizen or permanent resident'), 'learn:fact:choice:us-status:citizen,resident');
const older = { ...genderRecord, concept: 'q:please select your gender', reuse_policy: 'reusable', answer: 'Female', approved_at: '2026-10-01T00:00:00Z' };
assert.equal(memory.learnedMatch('Please select your gender.', 'choice', [older, genderRecord], ctx, 'Gender')?.answer, 'Male', 'learned answers win over older records');
console.log('learned answer cases pass');
