"""Tokenization and syntax trees for the supported voltage/event language.

Consume every token and retain source locations; instance binding and lowering
belong to frontend.py.
"""

from dataclasses import dataclass
import math
import re


class CompileError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    text: str
    kind: str
    line: int
    column: int


_TOKEN = re.compile(
    r"(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)"
    r'|(?P<include>`include[ \t]+"(?:constants|disciplines)\.vams")'
    r"|(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[TGMkKmunpfa]?)"
    r"|(?P<name>[A-Za-z_][A-Za-z_0-9]*)|(?P<symbol><\+|<=|>=|[<>()+*/;,=@\-])"
)
_SUFFIX = dict(T=1e12, G=1e9, M=1e6, k=1e3, K=1e3, m=1e-3,
               u=1e-6, n=1e-9, p=1e-12, f=1e-15, a=1e-18)
_RESERVED = {"module", "endmodule", "input", "output", "inout", "electrical",
             "parameter", "real", "analog", "begin", "end", "V", "pow", "integer", "initial_step", "if", "else", "or", "timer", "cross", "transition", "absdelay", "slew", "idt"}


def _tokens(source: str, name: str) -> list[Token]:
    result = []
    offset, line, column = 0, 1, 1
    while offset < len(source):
        match = _TOKEN.match(source, offset)
        if not match:
            raise CompileError(f"{name}:{line}:{column}: unsupported or invalid token {source[offset:offset+20]!r}")
        text, kind = match.group(), match.lastgroup
        if kind not in ("space", "comment"):
            result.append(Token(text, kind, line, column))
        if "\n" in text:
            line += text.count("\n")
            column = len(text.rsplit("\n", 1)[1]) + 1
        else:
            column += len(text)
        offset = match.end()
    result.append(Token("<eof>", "eof", line, column))
    return result


@dataclass(frozen=True)
class Expr:
    op: str
    value: str | float | None
    args: tuple["Expr", ...]
    token: Token


@dataclass(frozen=True)
class Assignment:
    name: str
    rhs: Expr
    token: Token


@dataclass(frozen=True)
class Conditional:
    relation: str
    left: Expr
    right: Expr
    then_body: tuple["Assignment | Conditional", ...]
    else_body: tuple["Assignment | Conditional", ...]
    token: Token


@dataclass(frozen=True)
class Trigger:
    kind: str
    arguments: tuple[Expr | None, ...]
    token: Token


@dataclass(frozen=True)
class Event:
    triggers: tuple[Trigger, ...]
    body: tuple[Assignment | Conditional, ...]
    token: Token


@dataclass
class Model:
    name: str
    source: str
    ports: tuple[str, ...]
    nodes: set[str]
    parameters: dict[str, Expr]
    contributions: list[tuple[Expr, Expr]]
    variables: dict[str, str]
    initial: list[Assignment]
    events: list[Event]


class Parser:
    def __init__(self, source: str, name: str):
        self.source = name
        self.tokens = _tokens(source, name)
        self.index = 0

    @property
    def token(self) -> Token:
        return self.tokens[self.index]

    def fail(self, message: str, token: Token | None = None):
        token = token or self.token
        raise CompileError(f"{self.source}:{token.line}:{token.column}: {message}")

    def take(self, text: str | None = None) -> Token:
        token = self.token
        if text is not None and token.text != text:
            self.fail(f"expected {text!r}, got {token.text!r}; outside affine-voltage syntax")
        self.index += 1
        return token

    def name(self) -> str:
        if self.token.kind != "name" or self.token.text in _RESERVED:
            self.fail("expected a non-reserved identifier")
        return self.take().text

    def names(self) -> list[str]:
        names = [self.name()]
        while self.token.text == ",":
            self.take(",")
            names.append(self.name())
        if len(names) != len(set(names)):
            self.fail("duplicate identifier in declaration")
        return names

    def expression(self, minimum: int = 0) -> Expr:
        token = self.take()
        if token.text in ("+", "-"):
            left = Expr("unary" + token.text, None, (self.expression(30),), token)
        elif token.text == "(":
            left = self.expression()
            self.take(")")
        elif token.kind == "number":
            text = token.text
            factor = _SUFFIX.get(text[-1], 1.0)
            value = float(text[:-1] if text[-1] in _SUFFIX else text) * factor
            if not math.isfinite(value):
                self.fail("nonfinite numeric literal", token)
            left = Expr("number", value, (), token)
        elif token.text == "V":
            self.take("(")
            p = self.name()
            n = "0"
            if self.token.text == ",":
                self.take(",")
                n = self.take().text if self.token.text == "0" else self.name()
            self.take(")")
            left = Expr("voltage", None, (Expr("node", p, (), token), Expr("node", n, (), token)), token)
        elif token.text in ("transition", "absdelay", "slew", "idt"):
            self.take("(")
            arguments = [self.expression()]
            while self.token.text == ",":
                self.take(",")
                arguments.append(self.expression())
            self.take(")")
            required = {"transition": 4, "absdelay": 2, "slew": 3, "idt": 2}[token.text]
            if len(arguments) != required:
                self.fail(f"{token.text} requires {required} explicit arguments", token)
            left = Expr(token.text, None, tuple(arguments), token)
        elif token.text == "pow":
            self.take("(")
            base = self.expression()
            self.take(",")
            exponent = self.expression()
            self.take(")")
            left = Expr("power", None, (base, exponent), token)
        elif token.kind == "name" and token.text not in _RESERVED:
            if self.token.text == "(":
                self.fail(f"call {token.text!r} is not supported in this slice", token)
            left = Expr("parameter", token.text, (), token)
        else:
            self.fail(f"unsupported expression {token.text!r}", token)
        while self.token.text in ("+", "-", "*", "/"):
            op = self.token
            precedence = 10 if op.text in ("+", "-") else 20
            if precedence < minimum:
                break
            self.take()
            left = Expr(op.text, None, (left, self.expression(precedence + 1)), op)
        return left

    def statements(self, conditional=False) -> tuple[Assignment | Conditional, ...]:
        token = self.token
        if token.text == ";":
            self.take(";")
            return ()
        if token.text == "begin":
            self.take("begin")
            result = []
            while self.token.text != "end":
                result.extend(self.statements(conditional))
            self.take("end")
            return tuple(result)
        if token.text == "if" and conditional:
            self.take("if")
            self.take("(")
            left = self.expression()
            relation = self.take()
            if relation.text not in ("<", "<=", ">", ">="):
                self.fail("event condition requires <, <=, > or >=", relation)
            right = self.expression()
            self.take(")")
            then_body = self.statements(True)
            else_body = ()
            if self.token.text == "else":
                self.take("else")
                else_body = self.statements(True)
            return (Conditional(relation.text, left, right, then_body, else_body, token),)
        name = self.name()
        self.take("=")
        rhs = self.expression()
        self.take(";")
        return (Assignment(name, rhs, token),)

    def parse(self) -> Model:
        while self.token.kind == "include":
            self.take()
        self.take("module")
        name = self.name()
        self.take("(")
        ports = self.names()
        self.take(")")
        self.take(";")
        directions, nodes, parameters, variables = {}, set(), {}, {}
        while self.token.text in ("input", "output", "inout", "electrical", "parameter", "integer", "real"):
            kind = self.take().text
            if kind == "parameter":
                self.take("real")
                param = self.name()
                if param in parameters or param in ports or param in nodes or param in variables:
                    self.fail(f"duplicate parameter/node name {param!r}")
                self.take("=")
                parameters[param] = self.expression()
            else:
                names = self.names()
                if kind in ("integer", "real"):
                    if (set(names) & (nodes | set(ports) | parameters.keys() | variables.keys())):
                        self.fail("duplicate variable/node/parameter name")
                    variables.update(dict.fromkeys(names, kind))
                elif kind == "electrical":
                    if nodes.intersection(names) or (parameters.keys() | variables.keys()) & set(names):
                        self.fail("duplicate electrical/parameter name")
                    nodes.update(names)
                else:
                    if directions.keys() & set(names) or not set(names) <= set(ports):
                        self.fail("duplicate direction or direction on a non-port")
                    directions.update(dict.fromkeys(names, kind))
            self.take(";")
        if set(directions) != set(ports) or not set(ports) <= nodes:
            self.fail("every port must have a direction and an electrical declaration")
        self.take("analog")
        self.take("begin")
        contributions, initial, events = [], [], []
        while self.token.text != "end":
            if self.token.text == "@":
                token = self.take("@")
                self.take("(")
                if self.token.text == "initial_step":
                    self.take("initial_step")
                    self.take(")")
                    initial.extend(self.statements())
                else:
                    triggers = []
                    while True:
                        leaf = self.take()
                        kind = leaf.text
                        if kind not in ("cross", "timer"):
                            self.fail("only cross and timer events are supported", leaf)
                        self.take("(")
                        arguments = [self.expression()]
                        while self.token.text == ",":
                            self.take(",")
                            if kind == "timer" and len(arguments) == 1 and self.token.text == ",":
                                arguments.append(None)  # LRM optional period argument
                            else:
                                arguments.append(self.expression())
                        self.take(")")
                        if len(arguments) > 4:
                            self.fail(f"{kind} accepts at most four supported arguments", leaf)
                        if kind == "timer" and len(arguments) < 3:
                            self.fail("timer requires explicit positive time_tol; use timer(start,0,tol) for one shot", leaf)
                        triggers.append(Trigger(kind, tuple(arguments), leaf))
                        if self.token.text != "or":
                            break
                        self.take("or")
                    self.take(")")
                    if len(triggers) > 1 and any(t.kind != "cross" for t in triggers):
                        self.fail("event OR supports only cross leaves", token)
                    events.append(Event(tuple(triggers), self.statements(True), token))
                continue
            if self.token.text != "V":
                self.fail("only voltage contributions, initial_step, cross and timer assignments are supported")
            branch = self.expression()
            if branch.op != "voltage":
                self.fail("contribution target must be V(p) or V(p,n)", branch.token)
            self.take("<+")
            rhs = self.expression()
            self.take(";")
            contributions.append((branch, rhs))
        self.take("end")
        self.take("endmodule")
        self.take("<eof>")
        if not contributions:
            self.fail("model must contain at least one voltage contribution", self.tokens[0])
        return Model(name, self.source, tuple(ports), nodes, parameters, contributions, variables, initial, events)
