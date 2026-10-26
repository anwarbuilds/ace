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
assert.equal(memory.resolve(equivalent, "text", saved.concat(saved)), null);
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
