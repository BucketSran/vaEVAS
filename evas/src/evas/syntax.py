"""Tokenization and syntax trees for the supported voltage/event language.

Consume every token and retain source locations; instance binding and lowering
belong to frontend.py.
"""

from dataclasses import dataclass, field, replace
import math
import re
from typing import Literal


from .errors import CompileError
from .limits import MAX_SOURCE_NESTING, check_expression


@dataclass(frozen=True)
class Token:
    text: str
    kind: str
    line: int
    column: int
    source: str = ''
    expansion: tuple[tuple[str, int], ...] = ()


_TOKEN = re.compile(
    r"(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)"
    r'|(?P<include>`include[ \t]+"[^"\n]+")'
    r"|(?P<macro>`M_PI\b)"
    r'|(?P<directive>`[A-Za-z_][A-Za-z_0-9]*)|(?P<string>"[^"\n]*")'
    r"|(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[TGMkKmunpfa]?)"
    r"|(?P<name>[A-Za-z_][A-Za-z_0-9]*)|(?P<symbol><\+|<=|>=|'\{|[\[\]:<>(){}+*/;,=@#.\-])"
)
_SUFFIX = dict(T=1e12, G=1e9, M=1e6, k=1e3, K=1e3, m=1e-3,
               u=1e-6, n=1e-9, p=1e-12, f=1e-15, a=1e-18)
OPERATOR_ARITIES = {"transition": (4,), "absdelay": (2,), "slew": (3,),
                    "idt": (2, 3), "laplace_nd": (3,), "idtmod": (4,), "ddt": (1,)}
OPERATOR_NAMES = frozenset(OPERATOR_ARITIES) | {"sin"}
_KEYWORDS = {"module", "endmodule", "input", "output", "inout", "electrical",
             "parameter", "real", "analog", "begin", "end", "integer", "initial_step", "if", "else", "or",
             "function", "endfunction", "for", "genvar"}
_BUILTINS = OPERATOR_NAMES | {"V", "pow", "timer", "cross"}
_RESERVED = _KEYWORDS | _BUILTINS


def _tokens(source: str, name: str, *, tolerant=False) -> list[Token]:
    result = []
    offset, line, column = 0, 1, 1
    while offset < len(source):
        match = _TOKEN.match(source, offset)
        if not match:
            if not tolerant:
                raise CompileError(f"{name}:{line}:{column}: unsupported or invalid token {source[offset:offset+20]!r}")
            result.append(Token(source[offset], 'unsupported', line, column, name))
            if len(result) > 100_000:
                raise CompileError(f'{name}:{line}:{column}: source token budget exceeded')
            offset += 1
            column += 1
            continue
        text, kind = match.group(), match.lastgroup
        if kind not in ("space", "comment"):
            result.append(Token(text, kind, line, column, name))
            if len(result) > 100_000:
                raise CompileError(f'{name}:{line}:{column}: source token budget exceeded')
        if "\n" in text:
            line += text.count("\n")
            column = len(text.rsplit("\n", 1)[1]) + 1
        else:
            column += len(text)
        offset = match.end()
    result.append(Token("<eof>", "eof", line, column, name))
    return result


@dataclass(frozen=True)
class Expr:
    op: Literal["number", "parameter", "node", "voltage", "array", "unary+", "unary-",
                "+", "-", "*", "/", "power", "sin", "transition", "absdelay", "slew",
                "idt", "laplace_nd", "idtmod", "ddt", "call", "index"]
    value: str | float | None
    args: tuple["Expr", ...]
    token: Token
    expansion: tuple[tuple[str, int], ...] = ()


def contains_operator(expr: Expr) -> bool:
    pending = [expr]
    while pending:
        current = pending.pop()
        if current.op in OPERATOR_NAMES:
            return True
        pending.extend(current.args)
    return False


@dataclass(frozen=True)
class Assignment:
    name: str
    rhs: Expr
    token: Token
    index: Expr | None = None


@dataclass(frozen=True)
class Conditional:
    relation: str
    left: Expr
    right: Expr
    then_body: tuple["Assignment | Conditional", ...]
    else_body: tuple["Assignment | Conditional", ...]
    token: Token


@dataclass(frozen=True)
class ContributionStatement:
    branch: Expr
    rhs: Expr
    token: Token


@dataclass(frozen=True)
class Loop:
    name: str
    start: Expr
    relation: str
    limit: Expr
    update: Expr
    body: tuple["Assignment | Conditional | ContributionStatement | Loop", ...]
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


@dataclass(frozen=True)
class Function:
    name: str
    inputs: tuple[str, ...]
    variables: frozenset[str]
    body: tuple[Assignment, ...]
    token: Token


@dataclass(frozen=True)
class ChildInstance:
    module: str
    name: str
    connections: tuple[str, ...] | dict[str, str]
    parameters: dict[str, Expr] | tuple[Expr, ...]
    token: Token


@dataclass
class Model:
    name: str
    source: str
    ports: tuple[str, ...]
    directions: dict[str, str]
    nodes: set[str]
    parameters: dict[str, Expr]
    analog: list[Assignment | Conditional | ContributionStatement | Loop]
    variables: dict[str, str]
    initial: list[Assignment]
    events: list[Event]
    functions: dict[str, Function] = field(default_factory=dict)
    genvars: frozenset[str] = frozenset()
    arrays: dict[str, tuple[Expr, Expr]] = field(default_factory=dict)
    children: tuple[ChildInstance, ...] = ()


class Parser:
    def __init__(self, source: str, name: str, *, tokens=None):
        self.source = name
        self.tokens = _tokens(source, name) if tokens is None else tokens
        self.index = 0
        self.nesting = 0

    @property
    def token(self) -> Token:
        return self.tokens[self.index]

    def fail(self, message: str, token: Token | None = None):
        token = token or self.token
        raise CompileError(f"{token.source or self.source}:{token.line}:{token.column}: {message}")

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
        if self.nesting >= MAX_SOURCE_NESTING:
            self.fail(f"syntax nesting limit ({MAX_SOURCE_NESTING}) exceeded")
        self.nesting += 1
        try:
            result = self._expression(minimum)
            check_expression(result, self.source)
            return result
        finally:
            self.nesting -= 1

    def _expression(self, minimum: int = 0) -> Expr:
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
        elif token.kind == "macro":
            left = Expr("number", math.pi, (), token)
        elif token.text == "V":
            self.take("(")
            p = self.name()
            n = "0"
            if self.token.text == ",":
                self.take(",")
                n = self.take().text if self.token.text == "0" else self.name()
            self.take(")")
            left = Expr("voltage", None, (Expr("node", p, (), token), Expr("node", n, (), token)), token)
        elif token.text == "'{":
            arguments = [self.expression()]
            while self.token.text == ",":
                self.take(",")
                arguments.append(self.expression())
            self.take("}")
            left = Expr("array", None, tuple(arguments), token)
        elif token.text in OPERATOR_ARITIES:
            self.take("(")
            arguments = [self.expression()]
            while self.token.text == ",":
                self.take(",")
                arguments.append(self.expression())
            self.take(")")
            allowed = OPERATOR_ARITIES[token.text]
            if len(arguments) not in allowed:
                label = " or ".join(str(count) for count in allowed)
                self.fail(f"{token.text} requires {label} explicit arguments", token)
            left = Expr(token.text, None, tuple(arguments), token)
        elif token.text == "sin":
            self.take("(")
            argument = self.expression()
            self.take(")")
            left = Expr("sin", None, (argument,), token)
        elif token.text == "pow":
            self.take("(")
            base = self.expression()
            self.take(",")
            exponent = self.expression()
            self.take(")")
            left = Expr("power", None, (base, exponent), token)
        elif token.kind == "name" and token.text not in _RESERVED:
            if self.token.text == "(":
                self.take("(")
                arguments = []
                if self.token.text != ")":
                    arguments.append(self.expression())
                    while self.token.text == ",":
                        self.take(",")
                        arguments.append(self.expression())
                self.take(")")
                left = Expr("call", token.text, tuple(arguments), token)
            elif self.token.text == "[":
                self.take("[")
                index = self.expression()
                self.take("]")
                left = Expr("index", token.text, (index,), token)
            else:
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
        return replace(left, expansion=left.token.expansion)

    def statements(self, conditional=False, analog=False):
        if self.nesting >= MAX_SOURCE_NESTING:
            self.fail(f"syntax nesting limit ({MAX_SOURCE_NESTING}) exceeded")
        self.nesting += 1
        try:
            return self._statements(conditional, analog)
        finally:
            self.nesting -= 1

    def _statements(self, conditional=False, analog=False):
        token = self.token
        if token.text == ";":
            self.take(";")
            return ()
        if token.text == "begin":
            self.take("begin")
            result = []
            while self.token.text != "end":
                result.extend(self.statements(conditional, analog))
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
            then_body = self.statements(True, analog)
            else_body = ()
            if self.token.text == "else":
                self.take("else")
                else_body = self.statements(True, analog)
            return (Conditional(relation.text, left, right, then_body, else_body, token),)
        if analog and token.text == "for":
            self.take("for")
            self.take("(")
            name = self.name()
            self.take("=")
            start = self.expression()
            self.take(";")
            left = self.expression()
            relation = self.take()
            if left.op != "parameter" or left.value != name or relation.text not in ("<", "<=", ">", ">="):
                self.fail("static for condition requires its genvar and <, <=, > or >=", relation)
            limit = self.expression()
            self.take(";")
            if self.name() != name:
                self.fail("for initialization and update must write the same genvar", token)
            self.take("=")
            update = self.expression()
            self.take(")")
            return (Loop(name, start, relation.text, limit, update, self.statements(True, True), token),)
        if analog and token.text == "V":
            branch = self.expression()
            if branch.op != "voltage":
                self.fail("contribution target must be V(p) or V(p,n)", branch.token)
            self.take("<+")
            rhs = self.expression()
            self.take(";")
            return (ContributionStatement(branch, rhs, token),)
        name = self.name()
        index = None
        if self.token.text == "[":
            self.take("[")
            index = self.expression()
            self.take("]")
        self.take("=")
        rhs = self.expression()
        self.take(";")
        return (Assignment(name, rhs, token, index),)

    def function(self) -> Function:
        token = self.take("analog")
        self.take("function")
        if self.token.text == "integer":
            self.fail("analog function return type currently requires real")
        if self.token.text == "real":
            self.take("real")
        name = self.name()
        self.take(";")
        inputs, variables = [], set()
        while self.token.text in ("input", "real"):
            kind = self.take().text
            names = self.names()
            target = inputs if kind == "input" else variables
            if set(names) & set(target) or name in names:
                self.fail("duplicate function input/local name")
            if kind == "input":
                inputs.extend(names)
            else:
                variables.update(names)
            self.take(";")
        if not inputs or not set(inputs) <= variables:
            self.fail("function requires typed real input arguments", token)
        body = self.statements()
        self.take("endfunction")
        return Function(name, tuple(inputs), frozenset(variables), body, token)

    def analog_block(self):
        self.take("analog")
        self.take("begin")
        analog, initial, events = [], [], []
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
                    events.append(Event(tuple(triggers), self.statements(True), token))
                continue
            analog.extend(self.statements(True, True))
        self.take("end")
        return analog, initial, events

    def child_instances(self):
        token = self.token
        module = self.name()
        parameters = {}
        if self.token.text == '#':
            self.take('#')
            self.take('(')
            named = self.token.text == '.'
            parameters = {} if named else []
            while self.token.text != ')':
                if named:
                    self.take('.')
                    parameter = self.name()
                    if parameter in parameters:
                        self.fail('duplicate child parameter override', token)
                    self.take('(')
                    parameters[parameter] = self.expression()
                    self.take(')')
                else:
                    parameters.append(self.expression())
                if self.token.text != ',':
                    break
                self.take(',')
                if self.token.text == ')':
                    self.fail('empty child parameter override is unsupported')
            self.take(')')
            if not named:
                parameters = tuple(parameters)
        result = []
        while True:
            name = self.name()
            self.take('(')
            named = self.token.text == '.'
            connections = {} if named else []
            while self.token.text != ')':
                if named:
                    self.take('.')
                    port = self.name()
                    if port in connections:
                        self.fail('duplicate child port connection', token)
                    self.take('(')
                net = self.take().text if self.token.text == '0' else self.name()
                if named:
                    self.take(')')
                    connections[port] = net
                else:
                    connections.append(net)
                if self.token.text != ',':
                    break
                self.take(',')
                if self.token.text == ')':
                    self.fail('empty child port connection is unsupported')
            self.take(')')
            result.append(ChildInstance(module, name, connections if named else tuple(connections), parameters, token))
            if self.token.text != ',':
                break
            self.take(',')
        self.take(';')
        return tuple(result)

    def parse_all(self):
        result = []
        while self.token.kind != 'eof':
            result.append(self.parse(eof=False))
        self.take('<eof>')
        return tuple(result)

    def parse(self, *, eof=True) -> Model:
        while self.token.kind == "include":
            self.take()
        module_token = self.take("module")
        name = self.name()
        self.take("(")
        ports = self.names()
        self.take(")")
        self.take(";")
        directions, nodes, parameters, variables, functions, genvars, arrays = {}, set(), {}, {}, {}, set(), {}
        while (self.token.text in ("input", "output", "inout", "electrical", "parameter", "integer", "real", "genvar")
               or self.token.text == "analog" and self.tokens[self.index+1].text == "function"):
            if self.token.text == "analog":
                function = self.function()
                if function.name in functions:
                    self.fail("duplicate analog function name", function.token)
                functions[function.name] = function
                continue
            kind = self.take().text
            if kind == "parameter":
                self.take("real")
                param = self.name()
                if param in parameters or param in ports or param in nodes or param in variables or param in genvars:
                    self.fail(f"duplicate parameter/node name {param!r}")
                self.take("=")
                parameters[param] = self.expression()
            else:
                if kind in ("integer", "real"):
                    names = []
                    while True:
                        variable = self.name()
                        if variable in names:
                            self.fail("duplicate variable in declaration")
                        names.append(variable)
                        if self.token.text == "[":
                            self.take("[")
                            left = self.expression()
                            self.take(":")
                            right = self.expression()
                            self.take("]")
                            if self.token.text == "[":
                                self.fail("multidimensional variable arrays are not yet supported")
                            arrays[variable] = (left, right)
                        if self.token.text != ",":
                            break
                        self.take(",")
                else:
                    names = self.names()
                if set(names) & genvars:
                    self.fail("duplicate genvar name")
                if kind in ("integer", "real"):
                    if (set(names) & (nodes | set(ports) | parameters.keys() | variables.keys())):
                        self.fail("duplicate variable/node/parameter name")
                    variables.update(dict.fromkeys(names, kind))
                elif kind == "genvar":
                    if set(names) & (nodes | set(ports) | parameters.keys() | variables.keys()):
                        self.fail("genvar name conflicts with a module declaration")
                    genvars.update(names)
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
        children = []
        while self.token.kind == 'name' and self.token.text not in _RESERVED:
            for child in self.child_instances():
                if child.name in {c.name for c in children} or child.name in (nodes | parameters.keys() | variables.keys() | functions.keys() | genvars):
                    self.fail('duplicate child instance/module identifier', child.token)
                children.append(child)
        if self.token.text != 'analog' and not children:
            self.fail('module requires an analog block or child instances')
        analog, initial, events = self.analog_block() if self.token.text == 'analog' else ([], [], [])
        self.take("endmodule")
        if eof:
            self.take("<eof>")
        pending = list(analog)
        contributed = False
        while pending:
            statement = pending.pop()
            contributed |= isinstance(statement, ContributionStatement)
            if isinstance(statement, Loop):
                pending.extend(statement.body)
            elif isinstance(statement, Conditional):
                pending.extend((*statement.then_body, *statement.else_body))
        if not contributed and (not children or initial or events):
            self.fail("model must contain at least one voltage contribution", self.tokens[0])
        if set(functions) & (nodes | set(ports) | parameters.keys() | variables.keys() | genvars):
            self.fail("function name conflicts with a module declaration")
        return Model(name, module_token.source or self.source, tuple(ports), directions, nodes, parameters, analog, variables, initial, events, functions, frozenset(genvars), arrays, tuple(children))
