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
assert.equal(memory.policy("Why do you want to join Cedarcloud?"), "company");
assert.equal(memory.policy("Have you applied to Cedarcloud before?"), "company");
assert.equal(memory.policy("Do you have relatives employed at Cedarcloud?"), "company");
assert.equal(memory.policy("Please acknowledge this by entering today's date."), "sensitive");
assert.equal(memory.resolve("Why do you want to join Northstar Labs?", "text", saved), null);
assert.equal(memory.resolve("Do you have authorization to work in the US?", "text", saved), null);
assert.equal(memory.equivalent("Did you work in Python?", "Did you not work in Python?", "text", "text"), false);
assert.equal(memory.resolve(equivalent, "text", saved.concat(saved)), null);
console.log("all 14 memory safety cases pass");
