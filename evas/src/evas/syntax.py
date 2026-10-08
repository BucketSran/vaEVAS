"""Tokenization and syntax trees for the supported voltage/event language.

Consume every token and retain source locations; instance binding and lowering
belong to frontend.py.
"""

from dataclasses import dataclass, field, replace
import math
import re
from typing import Literal


from .errors import CompileError
from .limits import MAX_SOURCE_NESTING, check_expression, check_ir


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
    r"|(?P<name>[A-Za-z_][A-Za-z_0-9]*)|(?P<symbol><\+|<=|>=|&&|\|\||'\{|[\[\]:<>(){}+*/;,=@#.?!\-])"
)
_SUFFIX = dict(T=1e12, G=1e9, M=1e6, k=1e3, K=1e3, m=1e-3,
               u=1e-6, n=1e-9, p=1e-12, f=1e-15, a=1e-18)
OPERATOR_ARITIES = {"transition": (3, 4), "absdelay": (2,), "slew": (3,),
                    "idt": (2, 3), "laplace_nd": (3,), "laplace_np": (3, 4), "idtmod": (4,), "ddt": (1,)}
OPERATOR_NAMES = frozenset(OPERATOR_ARITIES) | {"sin"}
DECISION_NAMES = frozenset(("<", "<=", ">", ">=", "&&", "||", "unary!", "ternary"))
_KEYWORDS = {"module", "endmodule", "input", "output", "inout", "electrical",
             "parameter", "real", "analog", "begin", "end", "integer", "initial_step", "if", "else", "or",
             "function", "endfunction", "for", "genvar", "from", "exclude", "inf",
             "case", "endcase", "default", "casex", "casez"}
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
                raise CompileError(f'{name}:{line}:{column}: source token budget exceeded',
                                   code='resource_budget', token=result[-1])
            offset += 1
            column += 1
            continue
        text, kind = match.group(), match.lastgroup
        if kind not in ("space", "comment"):
            result.append(Token(text, kind, line, column, name))
            if len(result) > 100_000:
                raise CompileError(f'{name}:{line}:{column}: source token budget exceeded',
                                   code='resource_budget', token=result[-1])
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
                "idt", "laplace_nd", "laplace_np", "idtmod", "ddt", "call", "index",
                "<", "<=", ">", ">=", "&&", "||", "unary!", "ternary", "checked"]
    value: str | float | None
    args: tuple["Expr", ...]
    token: Token
    expansion: tuple[tuple[str, int], ...] = ()


def contains_operator(expr: Expr) -> bool:
    pending, seen = [expr], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if current.op in OPERATOR_NAMES:
            return True
        pending.extend(current.args)
    return False


def contains_decision(expr: Expr) -> bool:
    pending, seen = [expr], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if current.op in DECISION_NAMES:
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
    then_body: tuple["Assignment | Conditional | ContributionStatement | Loop | Event", ...]
    else_body: tuple["Assignment | Conditional | ContributionStatement | Loop | Event", ...]
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
    body: tuple["Assignment | Conditional | ContributionStatement | Loop | Event", ...]
    token: Token


@dataclass(frozen=True)
class Trigger:
    kind: str
    arguments: tuple[Expr | None, ...]
    token: Token


@dataclass(frozen=True)
class Event:
    triggers: tuple[Trigger, ...]
    body: tuple[Assignment | Conditional | Loop, ...]
    token: Token


@dataclass(frozen=True)
class Function:
    name: str
    inputs: tuple[str, ...]
    variables: frozenset[str]
    body: tuple[Assignment | Conditional | Loop, ...]
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
    analog: list[Assignment | Conditional | ContributionStatement | Loop | Event]
    variables: dict[str, str]
    initial: list[Assignment]
    events: list[Event]
    functions: dict[str, Function] = field(default_factory=dict)
    genvars: frozenset[str] = frozenset()
    arrays: dict[str, tuple[Expr, Expr]] = field(default_factory=dict)
    children: tuple[ChildInstance, ...] = ()
    parameter_types: dict[str, str] = field(default_factory=dict)
    parameter_ranges: dict[str, tuple["ParameterRange", ...]] = field(default_factory=dict)
    node_ranges: dict[str, tuple[Expr, Expr] | None] = field(default_factory=dict)
    port_ranges: dict[str, tuple[Expr, Expr] | None] = field(default_factory=dict)
    declaration_token: Token | None = None


@dataclass(frozen=True)
class ParameterRange:
    kind: str
    lower: Expr | float
    upper: Expr | float | None
    closed_left: bool
    closed_right: bool
    token: Token


class Parser:
    def __init__(self, source: str, name: str, *, tokens=None):
        self.source = name
        self.tokens = _tokens(source, name) if tokens is None else tokens
        self.index = 0
        self.nesting = 0
        self.mixed_initial_body = False

    @property
    def token(self) -> Token:
        return self.tokens[self.index]

    def fail(self, message: str, token: Token | None = None, *, code='syntax_error'):
        token = token or self.token
        raise CompileError(f"{token.source or self.source}:{token.line}:{token.column}: {message}", code=code, token=token)

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

    def parameter_ranges(self):
        def bound():
            if self.token.text == 'inf':
                self.take()
                return math.inf
            if self.token.text in ('+', '-') and self.tokens[self.index+1].text == 'inf':
                sign = self.take().text
                self.take('inf')
                return -math.inf if sign == '-' else math.inf
            return self.expression()

        ranges = []
        while self.token.text in ('from', 'exclude'):
            token = self.take()
            if self.token.text in ('[', '('):
                left = self.take().text == '['
                lower = bound()
                self.take(':')
                upper = bound()
                if self.token.text not in (']', ')'):
                    self.fail('range requires a closing bracket or parenthesis')
                right = self.take().text == ']'
            elif token.text == 'exclude':
                lower, upper, left, right = self.expression(), None, True, True
            else:
                self.fail('from requires an interval', token)
            ranges.append(ParameterRange(token.text, lower, upper, left, right, token))
        return tuple(ranges)

    def node(self):
        token = self.token
        name = self.take().text if self.token.text == '0' else self.name()
        args = ()
        if self.token.text == '[':
            self.take('[')
            args = (self.expression(),)
            self.take(']')
        return Expr('node', name, args, token)

    def declared_range(self):
        if self.token.text != '[':
            return None
        self.take('[')
        left = self.expression()
        self.take(':')
        right = self.expression()
        self.take(']')
        if self.token.text == '[':
            self.fail('only one-dimensional electrical vectors are supported', code='unsupported_vector')
        return (left, right)

    def expression(self, minimum: int = 0) -> Expr:
        if self.nesting >= MAX_SOURCE_NESTING:
            self.fail(f"syntax nesting limit ({MAX_SOURCE_NESTING}) exceeded", code="resource_budget")
        self.nesting += 1
        try:
            result = self._expression(minimum)
            check_expression(result, self.source)
            return result
        finally:
            self.nesting -= 1

    def _expression(self, minimum: int = 0) -> Expr:
        token = self.take()
        if token.text in ("+", "-", "!"):
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
            p = self.node()
            n = Expr('node', '0', (), token)
            if self.token.text == ",":
                self.take(",")
                n = self.node()
            self.take(")")
            left = Expr("voltage", None, (p, n), token)
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
        precedence_table = {"||": 1, "&&": 2, "<": 3, "<=": 3, ">": 3, ">=": 3,
                            "+": 10, "-": 10, "*": 20, "/": 20}
        while self.token.text in precedence_table or self.token.text == "?":
            op = self.token
            if op.text == "?":
                if minimum > 0:
                    break
                self.take()
                then_value = self.expression()
                self.take(":")
                left = Expr("ternary", None, (left, then_value, self.expression()), op)
            else:
                precedence = precedence_table[op.text]
                if precedence < minimum:
                    break
                self.take()
                left = Expr(op.text, None, (left, self.expression(precedence + 1)), op)
        return replace(left, expansion=left.token.expansion)

    def statements(self, conditional=False, analog=False):
        if self.nesting >= MAX_SOURCE_NESTING:
            self.fail(f"syntax nesting limit ({MAX_SOURCE_NESTING}) exceeded", code="resource_budget")
        self.nesting += 1
        try:
            return self._statements(conditional, analog)
        finally:
            self.nesting -= 1

    def _statements(self, conditional=False, analog=False):
        token = self.token
        if token.text == '@' and self.mixed_initial_body:
            self.fail('nested events are not supported in a mixed initial_step body',
                      token, code='unsupported_initial_event')
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
            left = self.expression(4)
            relation = self.take()
            if relation.text not in ("<", "<=", ">", ">="):
                self.fail("event condition requires <, <=, > or >=", relation)
            right = self.expression(4)
            self.take(")")
            then_body = self.statements(True, analog)
            else_body = ()
            if self.token.text == "else":
                self.take("else")
                else_body = self.statements(True, analog)
            return (Conditional(relation.text, left, right, then_body, else_body, token),)
        if (analog or conditional) and token.text == "case":
            self.take("case")
            self.take("(")
            selector = self.expression()
            self.take(")")
            if contains_operator(selector):
                self.fail("case selectors cannot contain waveform operators", token)
            items, default = [], None
            while self.token.text != "endcase":
                if self.token.text == "default":
                    default_token = self.take("default")
                    if default is not None:
                        self.fail("case permits at most one default item", default_token)
                    if self.token.text == ":":
                        self.take(":")
                    default = self.statements(True, analog)
                    continue
                labels = [self.expression()]
                while self.token.text == ",":
                    self.take(",")
                    labels.append(self.expression())
                self.take(":")
                if any(contains_operator(label) for label in labels):
                    self.fail("case labels cannot contain waveform operators", token)
                if len(items) + len(labels) > 16:
                    self.fail("case label budget (16) exceeded", token, code="resource_budget")
                body = self.statements(True, analog)
                items.extend((label, body) for label in labels)
            self.take("endcase")
            if not items:
                self.fail("case requires at least one non-default label in this slice", token)
            # Scalar finite values match exactly when both ordered comparisons
            # hold. No body executes between these comparisons, so its writes
            # cannot change the captured selection. Else links preserve the
            # first matching label, including overlapping labels/items.
            result = default or ()
            for label, body in reversed(items):
                equal = Conditional(">=", selector, label, body, result, token)
                result = (Conditional("<=", selector, label, (equal,), result, token),)
            # Generated comparison trees duplicate fallbacks on the wire.
            # Check their expanded size before later recursive compiler passes.
            check_ir(result, token)
            return result
        if (analog or conditional) and token.text == "for":
            self.take("for")
            self.take("(")
            name = self.name()
            self.take("=")
            start = self.expression()
            self.take(";")
            left = self.expression(4)
            relation = self.take()
            if left.op != "parameter" or left.value != name or relation.text not in ("<", "<=", ">", ">="):
                self.fail("static for condition requires its genvar and <, <=, > or >=", relation)
            limit = self.expression(4)
            self.take(";")
            if self.name() != name:
                self.fail("for initialization and update must write the same genvar", token)
            self.take("=")
            update = self.expression()
            self.take(")")
            return (Loop(name, start, relation.text, limit, update, self.statements(True, analog), token),)
        if analog and token.text == "@":
            self.take("@")
            self.take("(")
            return (self.monitored_event(token),)
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
        body = self.statements(conditional=True)
        self.take("endfunction")
        return Function(name, tuple(inputs), frozenset(variables), body, token)

    def monitored_event(self, token, initial=None):
        """Parse after @(; only top-level callers can split initialization."""
        triggers, initial_count, unqualified, qualified = [], 0, False, False
        while True:
            leaf = self.take()
            kind = leaf.text
            if kind == 'initial_step' and initial is not None:
                initial_count += 1
                if self.token.text == '(':
                    qualified = True
                    self.take('(')
                    while True:
                        if self.token.text not in ('"dc"', '"tran"'):
                            self.fail('only dc/tran analysis labels in a redundant initialization OR are supported', code='unsupported_initial_event')
                        self.take()
                        if self.token.text != ',':
                            break
                        self.take(',')
                    self.take(')')
                else:
                    unqualified = True
                if self.token.text != 'or':
                    break
                self.take('or')
                continue
            if kind not in ("cross", "timer"):
                self.fail("only cross and timer events are supported here; initial_step must be top-level", leaf,
                          code='unsupported_initial_event' if kind == 'initial_step' else 'syntax_error')
            self.take("(")
            arguments = [self.expression()]
            while self.token.text == ",":
                self.take(",")
                if kind == "timer" and len(arguments) in (1, 2) and self.token.text in (",", ")"):
                    arguments.append(None)  # LRM optional period/time_tol
                else:
                    arguments.append(self.expression())
            self.take(")")
            if len(arguments) > 4:
                self.fail(f"{kind} accepts at most four supported arguments", leaf)
            triggers.append(Trigger(kind, tuple(arguments), leaf))
            if self.token.text != "or":
                break
            self.take("or")
        self.take(")")
        if initial_count:
            if not unqualified:
                self.fail('analysis-specific initialization requires an analysis lifecycle; include an unqualified initial_step leaf', token, code='unsupported_initial_event')
            if triggers and (qualified or initial_count != 1 or any(leaf.kind != 'cross' for leaf in triggers)):
                self.fail('mixed initialization requires one unqualified initial_step and only cross leaves', token, code='unsupported_initial_event')
            previous_context = self.mixed_initial_body
            self.mixed_initial_body = bool(triggers)
            try:
                body = self.statements(bool(triggers))
            finally:
                self.mixed_initial_body = previous_context
            if any(not isinstance(statement, Assignment) for statement in body):
                self.fail('mixed initial_step body requires unconditional instance-constant assignments', token, code='unsupported_initial_event')
            initial.extend(body)
            return Event(tuple(triggers), body, token) if triggers else None
        return Event(tuple(triggers), self.statements(True), token)

    def analog_block(self):
        self.take("analog")
        self.take("begin")
        analog, initial, events = [], [], []
        while self.token.text != "end":
            if self.token.text == "@":
                token = self.take("@")
                self.take("(")
                # Initialization is installed once by the existing state path;
                # only monitored leaves become runtime events.
                event = self.monitored_event(token, initial)
                if event is not None:
                    analog.append(event)
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
        parameter_types, parameter_ranges = {}, {}
        node_ranges, port_ranges = {}, {}
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
                if self.token.text not in ('real', 'integer'):
                    self.fail('parameter requires an explicit real or integer type')
                parameter_type = self.take().text
                while True:
                    param = self.name()
                    if param in parameters or param in ports or param in nodes or param in variables or param in genvars:
                        self.fail(f"duplicate parameter/node name {param!r}")
                    self.take("=")
                    parameters[param] = self.expression()
                    parameter_types[param] = parameter_type
                    parameter_ranges[param] = self.parameter_ranges()
                    if self.token.text != ',':
                        break
                    self.take(',')
            else:
                declared_range = self.declared_range() if kind in ('input', 'output', 'inout', 'electrical') else None
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
                    node_ranges.update(dict.fromkeys(names, declared_range))
                else:
                    if directions.keys() & set(names) or not set(names) <= set(ports):
                        self.fail("duplicate direction or direction on a non-port")
                    directions.update(dict.fromkeys(names, kind))
                    port_ranges.update(dict.fromkeys(names, declared_range))
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
        contributed = monitored = False
        while pending:
            statement = pending.pop()
            contributed |= isinstance(statement, ContributionStatement)
            monitored |= isinstance(statement, Event)
            if isinstance(statement, Loop):
                pending.extend(statement.body)
            elif isinstance(statement, Conditional):
                pending.extend((*statement.then_body, *statement.else_body))
        if not contributed and (not children or initial or events or monitored):
            self.fail("model must contain at least one voltage contribution", self.tokens[0])
        if set(functions) & (nodes | set(ports) | parameters.keys() | variables.keys() | genvars):
            self.fail("function name conflicts with a module declaration")
        return Model(name, module_token.source or self.source, tuple(ports), directions, nodes, parameters, analog, variables, initial, events, functions, frozenset(genvars), arrays, tuple(children), parameter_types, parameter_ranges, node_ranges, port_ranges, module_token)
