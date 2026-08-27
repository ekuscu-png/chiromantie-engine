import * as assert from 'assert';
import { evaluateCondition, parseCondition } from './conditionParser';
import { RuleDefinition, RuleEngine } from './ruleEngine';

// --- conditionParser ---

assert.strictEqual(
  evaluateCondition(parseCondition("hand_shape == 'earth'"), { hand_shape: 'earth' }),
  true,
  'simple equality should match',
);

assert.strictEqual(
  evaluateCondition(parseCondition("hand_shape == 'earth'"), { hand_shape: 'air' }),
  false,
  'simple equality should not match on mismatch',
);

assert.strictEqual(
  evaluateCondition(parseCondition("hand_shape != 'earth'"), { hand_shape: 'air' }),
  true,
  'not-equal should match on mismatch',
);

assert.strictEqual(
  evaluateCondition(
    parseCondition("mounts.jupiter.developed == 'strong' AND fate_line.end == 'to_jupiter'"),
    { mounts: { jupiter: { developed: 'strong' } }, fate_line: { end: 'to_jupiter' } },
  ),
  true,
  'AND with nested paths should match when both sides true',
);

assert.strictEqual(
  evaluateCondition(
    parseCondition("mounts.jupiter.developed == 'strong' AND fate_line.end == 'to_jupiter'"),
    { mounts: { jupiter: { developed: 'weak' } }, fate_line: { end: 'to_jupiter' } },
  ),
  false,
  'AND should fail when one side is false',
);

assert.strictEqual(
  evaluateCondition(parseCondition("life_line.marks contains 'square'"), {
    life_line: { marks: ['square', 'island'] },
  }),
  true,
  "'contains' should match array membership",
);

assert.strictEqual(
  evaluateCondition(parseCondition("life_line.marks contains 'square'"), {
    life_line: { marks: ['island'] },
  }),
  false,
  "'contains' should not match when absent",
);

assert.strictEqual(
  evaluateCondition(parseCondition('life_line.has_break == true'), { life_line: { has_break: true } }),
  true,
  'boolean literal comparison should work',
);

assert.strictEqual(
  evaluateCondition(parseCondition("a == 'x' OR b == 'y'"), { a: 'nope', b: 'y' }),
  true,
  'OR should match when second side true',
);

assert.strictEqual(
  evaluateCondition(parseCondition("(a == 'x' OR b == 'y') AND c != 'z'"), { a: 'x', b: 'nope', c: 'ok' }),
  true,
  'parenthesized OR combined with AND should work',
);

assert.strictEqual(
  evaluateCondition(parseCondition("missing.deeply.nested == 'x'"), {}),
  false,
  'missing nested path should resolve to undefined, not throw',
);

assert.throws(() => parseCondition(''), /Empty condition/, 'empty condition should throw');
assert.throws(() => parseCondition("hand_shape =="), /Expected value/, 'incomplete condition should throw');

// --- RuleEngine ---

const rules: RuleDefinition[] = [
  { id: 'r1', condition: "hand_shape == 'earth'", category: 'hand_shape', output: { domain: 'personality', text: 'Erdhand-Text' } },
  { id: 'r2', condition: "hand_shape == 'air'", category: 'hand_shape', output: { domain: 'personality', text: 'Lufthand-Text' } },
  { id: 'r3', condition: "life_line.marks contains 'square'", category: 'main_lines', output: { domain: 'protection', text: 'Schutz-Text' } },
];
const weightings = { hand_shape: 2.5, main_lines: 3.0 };

const engine = new RuleEngine(rules, weightings);
const matches = engine.evaluate({ hand_shape: 'earth', life_line: { marks: ['square'] } });

assert.strictEqual(matches.length, 2, 'engine should return only matching rules');
assert.strictEqual(matches[0].id, 'r3', 'higher-weighted rule (main_lines: 3.0) should sort first');
assert.strictEqual(matches[1].id, 'r1', 'lower-weighted rule (hand_shape: 2.5) should sort second');

const grouped = engine.evaluateByDomain({ hand_shape: 'earth', life_line: { marks: ['square'] } });
assert.strictEqual(grouped.personality.length, 1);
assert.strictEqual(grouped.protection.length, 1);

console.log('Alle Tests bestanden.');
