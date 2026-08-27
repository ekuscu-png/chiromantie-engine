import * as fs from 'fs';
import * as path from 'path';
import { RuleDefinition, RuleEngine } from './ruleEngine';

const kbPath = path.join(__dirname, '..', 'data', 'knowledge_base.json');
const kb = JSON.parse(fs.readFileSync(kbPath, 'utf-8'));

const rules: RuleDefinition[] = kb.example_rules;
const weightings: Record<string, number> = kb.meta.weightings;

const engine = new RuleEngine(rules, weightings);

// Beispiel-Features, wie sie aus der Bildanalyse (Schritt 3 in app_workflow) kommen könnten.
// Achtung: example_rules referenziert sowohl `mounts.jupiter.developed` als auch das
// eigenständige Feld `venus_mount.developed` (statt `mounts.venus.developed`) - diese
// Inkonsistenz stammt aus der Quelldatei und wird hier bewusst so gespiegelt.
const sampleFeatures = {
  hand_shape: 'earth',
  finger_tip: 'conical',
  mounts: {
    jupiter: { developed: 'strong' },
  },
  venus_mount: { developed: 'strong' },
  fate_line: { end: 'to_jupiter' },
  heart_line: { end: 'under_jupiter' },
  sun_line: { exists: true },
  life_line: { has_break: true, marks: ['square'] },
};

const matches = engine.evaluate(sampleFeatures);

console.log(`${matches.length} Regel(n) getroffen:\n`);
for (const m of matches) {
  console.log(`[${m.domain}] (weight ${m.weight}) ${m.id}`);
  console.log(`  -> ${m.text}\n`);
}
