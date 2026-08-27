import { ASTNode, evaluateCondition, parseCondition } from './conditionParser';

export interface RuleOutput {
  domain: string;
  text: string;
}

export interface RuleDefinition {
  id: string;
  condition: string;
  /** Optional key into meta.weightings (e.g. 'main_lines', 'hand_shape', 'mounts'). Defaults to weight 1.0. */
  category?: string;
  output: RuleOutput;
}

export interface MatchedRule {
  id: string;
  domain: string;
  text: string;
  weight: number;
}

interface CompiledRule extends RuleDefinition {
  ast: ASTNode;
}

export class RuleEngine {
  private readonly compiled: CompiledRule[];
  private readonly weightings: Record<string, number>;

  constructor(rules: RuleDefinition[], weightings: Record<string, number> = {}) {
    this.weightings = weightings;
    this.compiled = rules.map((rule) => {
      try {
        return { ...rule, ast: parseCondition(rule.condition) };
      } catch (err) {
        throw new Error(`Failed to parse condition for rule '${rule.id}': ${(err as Error).message}`);
      }
    });
  }

  /** Returns all rules whose condition matches, sorted by weight (descending). */
  evaluate(features: Record<string, unknown>): MatchedRule[] {
    const matches: MatchedRule[] = [];
    for (const rule of this.compiled) {
      if (evaluateCondition(rule.ast, features)) {
        const weight = rule.category ? this.weightings[rule.category] ?? 1.0 : 1.0;
        matches.push({ id: rule.id, domain: rule.output.domain, text: rule.output.text, weight });
      }
    }
    return matches.sort((a, b) => b.weight - a.weight);
  }

  /** Same as evaluate(), but grouped by output domain (e.g. 'career', 'relationships'). */
  evaluateByDomain(features: Record<string, unknown>): Record<string, MatchedRule[]> {
    const grouped: Record<string, MatchedRule[]> = {};
    for (const match of this.evaluate(features)) {
      (grouped[match.domain] ??= []).push(match);
    }
    return grouped;
  }
}
