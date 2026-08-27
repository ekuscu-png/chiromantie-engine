"""
Parst und wertet die kleine Condition-DSL aus knowledge_base.json's
`example_rules[].condition` aus, z.B.:

    hand_shape == 'earth'
    mounts.jupiter.developed == 'strong' AND fate_line.end == 'to_jupiter'
    life_line.marks contains 'square'
    (a == 'x' OR b == 'y') AND c != 'z'
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Union

_TOKEN_RE = re.compile(
    r"'([^']*)'"          # 1: quoted string
    r"|(\()"              # 2: lparen
    r"|(\))"              # 3: rparen
    r"|(==|!=)"           # 4: operator
    r"|(\d+(?:\.\d+)?)"   # 5: number
    r"|([A-Za-z_][A-Za-z0-9_.]*)"  # 6: word (path / keyword / boolean)
)


@dataclass(frozen=True)
class Token:
    type: str
    value: str


def _tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    for m in _TOKEN_RE.finditer(text):
        string, lparen, rparen, op, num, word = m.groups()
        if string is not None:
            tokens.append(Token("STRING", string))
        elif lparen:
            tokens.append(Token("LPAREN", "("))
        elif rparen:
            tokens.append(Token("RPAREN", ")"))
        elif op:
            tokens.append(Token("OP", op))
        elif num:
            tokens.append(Token("NUMBER", num))
        elif word:
            upper = word.upper()
            if upper == "AND":
                tokens.append(Token("AND", word))
            elif upper == "OR":
                tokens.append(Token("OR", word))
            elif upper == "CONTAINS":
                tokens.append(Token("CONTAINS", word))
            elif word in ("true", "false"):
                tokens.append(Token("BOOLEAN", word))
            else:
                tokens.append(Token("PATH", word))
    return tokens


@dataclass(frozen=True)
class Comparison:
    path: str
    op: str  # '==' | '!=' | 'contains'
    value: Union[str, float, bool]


@dataclass(frozen=True)
class BinaryOp:
    kind: str  # 'AND' | 'OR'
    left: "ASTNode"
    right: "ASTNode"


ASTNode = Union[Comparison, BinaryOp]


class _Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> ASTNode:
        node = self._parse_or()
        if self._pos < len(self._tokens):
            tok = self._tokens[self._pos]
            raise ValueError(f"Unexpected token at position {self._pos}: '{tok.value}'")
        return node

    def _parse_or(self) -> ASTNode:
        node = self._parse_and()
        while self._peek() is not None and self._peek().type == "OR":
            self._pos += 1
            node = BinaryOp("OR", node, self._parse_and())
        return node

    def _parse_and(self) -> ASTNode:
        node = self._parse_term()
        while self._peek() is not None and self._peek().type == "AND":
            self._pos += 1
            node = BinaryOp("AND", node, self._parse_term())
        return node

    def _parse_term(self) -> ASTNode:
        tok = self._peek()
        if tok is not None and tok.type == "LPAREN":
            self._pos += 1
            node = self._parse_or()
            self._expect("RPAREN")
            return node
        return self._parse_comparison()

    def _parse_comparison(self) -> ASTNode:
        path_tok = self._expect("PATH")
        op_tok = self._peek()
        if op_tok is None:
            raise ValueError(f"Expected operator after path '{path_tok.value}'")

        if op_tok.type == "OP":
            op = op_tok.value
            self._pos += 1
        elif op_tok.type == "CONTAINS":
            op = "contains"
            self._pos += 1
        else:
            raise ValueError(
                f"Expected '==', '!=' or 'contains' after path '{path_tok.value}', got {op_tok.type}"
            )

        val_tok = self._peek()
        if val_tok is None:
            raise ValueError(f"Expected value after operator for path '{path_tok.value}'")
        self._pos += 1

        value: Union[str, float, bool]
        if val_tok.type == "STRING":
            value = val_tok.value
        elif val_tok.type == "NUMBER":
            value = float(val_tok.value)
        elif val_tok.type == "BOOLEAN":
            value = val_tok.value == "true"
        else:
            raise ValueError(f"Invalid value token for path '{path_tok.value}': '{val_tok.value}'")

        return Comparison(path_tok.value, op, value)

    def _peek(self) -> Token | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _expect(self, type_: str) -> Token:
        tok = self._peek()
        if tok is None or tok.type != type_:
            got = tok.type if tok else "EOF"
            raise ValueError(f"Expected {type_} at position {self._pos}, got {got}")
        self._pos += 1
        return tok


def _get_path(obj: Any, path: str) -> Any:
    current = obj
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def parse_condition(text: str) -> ASTNode:
    tokens = _tokenize(text)
    if not tokens:
        raise ValueError("Empty condition string")
    return _Parser(tokens).parse()


def evaluate_condition(ast: ASTNode, features: dict) -> bool:
    if isinstance(ast, BinaryOp):
        if ast.kind == "AND":
            return evaluate_condition(ast.left, features) and evaluate_condition(ast.right, features)
        return evaluate_condition(ast.left, features) or evaluate_condition(ast.right, features)

    actual = _get_path(features, ast.path)
    if ast.op == "contains":
        if isinstance(actual, (list, tuple, set)):
            return ast.value in actual
        if isinstance(actual, str):
            return str(ast.value) in actual
        return False

    is_equal = actual == ast.value
    return is_equal if ast.op == "==" else not is_equal
