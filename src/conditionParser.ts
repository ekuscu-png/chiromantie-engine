/**
 * Parses and evaluates the small condition DSL used in knowledge_base.json's
 * `example_rules[].condition`, e.g.:
 *   hand_shape == 'earth'
 *   mounts.jupiter.developed == 'strong' AND fate_line.end == 'to_jupiter'
 *   life_line.marks contains 'square'
 *   (a == 'x' OR b == 'y') AND c != 'z'
 */

type TokenType = 'STRING' | 'NUMBER' | 'BOOLEAN' | 'PATH' | 'OP' | 'AND' | 'OR' | 'CONTAINS' | 'LPAREN' | 'RPAREN';

interface Token {
  type: TokenType;
  value: string;
}

const TOKEN_RE = /'([^']*)'|(\()|(\))|(==|!=)|(\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_.]*)/g;

function tokenize(input: string): Token[] {
  const tokens: Token[] = [];
  let match: RegExpExecArray | null;
  TOKEN_RE.lastIndex = 0;
  while ((match = TOKEN_RE.exec(input)) !== null) {
    const [, str, lparen, rparen, op, num, word] = match;
    if (str !== undefined) {
      tokens.push({ type: 'STRING', value: str });
    } else if (lparen) {
      tokens.push({ type: 'LPAREN', value: '(' });
    } else if (rparen) {
      tokens.push({ type: 'RPAREN', value: ')' });
    } else if (op) {
      tokens.push({ type: 'OP', value: op });
    } else if (num) {
      tokens.push({ type: 'NUMBER', value: num });
    } else if (word) {
      const upper = word.toUpperCase();
      if (upper === 'AND') tokens.push({ type: 'AND', value: word });
      else if (upper === 'OR') tokens.push({ type: 'OR', value: word });
      else if (upper === 'CONTAINS') tokens.push({ type: 'CONTAINS', value: word });
      else if (word === 'true' || word === 'false') tokens.push({ type: 'BOOLEAN', value: word });
      else tokens.push({ type: 'PATH', value: word });
    }
  }
  return tokens;
}

export type ASTNode =
  | { type: 'AND'; left: ASTNode; right: ASTNode }
  | { type: 'OR'; left: ASTNode; right: ASTNode }
  | { type: 'COMPARISON'; path: string; op: '==' | '!=' | 'contains'; value: string | number | boolean };

class Parser {
  private pos = 0;

  constructor(private readonly tokens: Token[]) {}

  parse(): ASTNode {
    const node = this.parseOr();
    if (this.pos < this.tokens.length) {
      throw new Error(`Unexpected token at position ${this.pos}: '${this.tokens[this.pos].value}'`);
    }
    return node;
  }

  private parseOr(): ASTNode {
    let node = this.parseAnd();
    while (this.peek()?.type === 'OR') {
      this.pos++;
      node = { type: 'OR', left: node, right: this.parseAnd() };
    }
    return node;
  }

  private parseAnd(): ASTNode {
    let node = this.parseTerm();
    while (this.peek()?.type === 'AND') {
      this.pos++;
      node = { type: 'AND', left: node, right: this.parseTerm() };
    }
    return node;
  }

  private parseTerm(): ASTNode {
    if (this.peek()?.type === 'LPAREN') {
      this.pos++;
      const node = this.parseOr();
      this.expect('RPAREN');
      return node;
    }
    return this.parseComparison();
  }

  private parseComparison(): ASTNode {
    const pathTok = this.expect('PATH');
    const opTok = this.peek();
    if (!opTok) throw new Error(`Expected operator after path '${pathTok.value}'`);

    let op: '==' | '!=' | 'contains';
    if (opTok.type === 'OP') {
      op = opTok.value as '==' | '!=';
      this.pos++;
    } else if (opTok.type === 'CONTAINS') {
      op = 'contains';
      this.pos++;
    } else {
      throw new Error(`Expected '==', '!=' or 'contains' after path '${pathTok.value}', got ${opTok.type}`);
    }

    const valTok = this.peek();
    if (!valTok) throw new Error(`Expected value after operator for path '${pathTok.value}'`);
    this.pos++;

    let value: string | number | boolean;
    if (valTok.type === 'STRING') value = valTok.value;
    else if (valTok.type === 'NUMBER') value = parseFloat(valTok.value);
    else if (valTok.type === 'BOOLEAN') value = valTok.value === 'true';
    else throw new Error(`Invalid value token for path '${pathTok.value}': '${valTok.value}'`);

    return { type: 'COMPARISON', path: pathTok.value, op, value };
  }

  private peek(): Token | undefined {
    return this.tokens[this.pos];
  }

  private expect(type: TokenType): Token {
    const tok = this.tokens[this.pos];
    if (!tok || tok.type !== type) {
      throw new Error(`Expected ${type} at position ${this.pos}, got ${tok ? tok.type : 'EOF'}`);
    }
    this.pos++;
    return tok;
  }
}

function getPath(obj: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (acc == null || typeof acc !== 'object') return undefined;
    return (acc as Record<string, unknown>)[key];
  }, obj);
}

export function parseCondition(input: string): ASTNode {
  const tokens = tokenize(input);
  if (tokens.length === 0) throw new Error('Empty condition string');
  return new Parser(tokens).parse();
}

export function evaluateCondition(ast: ASTNode, features: Record<string, unknown>): boolean {
  switch (ast.type) {
    case 'AND':
      return evaluateCondition(ast.left, features) && evaluateCondition(ast.right, features);
    case 'OR':
      return evaluateCondition(ast.left, features) || evaluateCondition(ast.right, features);
    case 'COMPARISON': {
      const actual = getPath(features, ast.path);
      if (ast.op === 'contains') {
        if (Array.isArray(actual)) return actual.includes(ast.value);
        if (typeof actual === 'string') return actual.includes(String(ast.value));
        return false;
      }
      const isEqual = actual === ast.value;
      return ast.op === '==' ? isEqual : !isEqual;
    }
  }
}
