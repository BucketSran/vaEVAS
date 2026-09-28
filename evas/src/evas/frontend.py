"""Strict frontend for the first, stateless affine-voltage migration slice.

All tokens are consumed. Unsupported syntax is rejected, never skipped or sent
to the old runtime. Expressions are parsed before instance parameter binding.
"""

from dataclasses import dataclass, field
import math
import re
from typing import Mapping

from .ir import Affine, Contribution, Origin, Program, Term


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
    r"|(?P<name>[A-Za-z_][A-Za-z_0-9]*)|(?P<symbol><\+|[()+*/;,=\-])"
)
_SUFFIX = dict(T=1e12, G=1e9, M=1e6, k=1e3, K=1e3, m=1e-3,
               u=1e-6, n=1e-9, p=1e-12, f=1e-15, a=1e-18)
_RESERVED = {"module", "endmodule", "input", "output", "inout", "electrical",
             "parameter", "real", "analog", "begin", "end", "V"}


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


@dataclass
class Model:
    name: str
    source: str
    ports: tuple[str, ...]
    nodes: set[str]
    parameters: dict[str, Expr]
    contributions: list[tuple[Expr, Expr]]


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

    def parse(self) -> Model:
        while self.token.kind == "include":
            self.take()
        self.take("module")
        name = self.name()
        self.take("(")
        ports = self.names()
        self.take(")")
        self.take(";")
        directions, nodes, parameters = {}, set(), {}
        while self.token.text in ("input", "output", "inout", "electrical", "parameter"):
            kind = self.take().text
            if kind == "parameter":
                self.take("real")
                param = self.name()
                if param in parameters or param in ports or param in nodes:
                    self.fail(f"duplicate parameter/node name {param!r}")
                self.take("=")
                parameters[param] = self.expression()
            else:
                names = self.names()
                if kind == "electrical":
                    if nodes.intersection(names) or parameters.keys() & set(names):
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
        contributions = []
        while self.token.text != "end":
            if self.token.text != "V":
                self.fail("only unconditional voltage contributions are supported in this slice")
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
        return Model(name, self.source, tuple(ports), nodes, parameters, contributions)


@dataclass(frozen=True)
class Instance:
    name: str
    module: str
    connections: Mapping[str, str]
    parameters: Mapping[str, float] = field(default_factory=dict)


def _affine(expr: Expr, parameters, nodes: Mapping[str, int], source: str) -> tuple[float, dict[int, float]]:
    def fail(message):
        raise CompileError(f"{source}:{expr.token.line}:{expr.token.column}: {message}")

    if expr.op == "number":
        return float(expr.value), {}
    if expr.op == "parameter":
        return parameters(str(expr.value)), {}
    if expr.op == "voltage":
        p, n = (str(arg.value) for arg in expr.args)
        if p not in nodes or n not in nodes:
            fail(f"undeclared electrical node in V({p},{n})")
        if nodes[p] == nodes[n]:
            return 0.0, {}
        return 0.0, {nodes[p]: 1.0, nodes[n]: -1.0}
    values = [_affine(arg, parameters, nodes, source) for arg in expr.args]
    a, terms = values[0]
    if expr.op.startswith("unary"):
        scale = -1.0 if expr.op == "unary-" else 1.0
        result = a * scale, {n: c * scale for n, c in terms.items()}
    else:
        b, other = values[1]
        if expr.op in ("+", "-"):
            scale = 1.0 if expr.op == "+" else -1.0
            merged = dict(terms)
            for n, c in other.items():
                merged[n] = merged.get(n, 0.0) + scale * c
            result = a + scale * b, merged
        elif expr.op == "*":
            if terms and other:
                fail("nonlinear product; affine-voltage slice cannot lower this expression")
            result = a * b, {n: c * (b if terms else a) for n, c in (terms or other).items()}
        else:
            if other or b == 0:
                fail("division requires a nonzero constant denominator")
            result = a / b, {n: c / b for n, c in terms.items()}
    constant, terms = result
    if not all(math.isfinite(x) for x in (constant, *terms.values())):
        fail("nonfinite coefficient during constant folding")
    return constant, {n: c for n, c in terms.items() if c != 0.0}


def compile_sources(sources: Mapping[str, str], instances: list[Instance]) -> Program:
    """Compile source text and explicit flat instances; never import validation data."""
    models = {}
    for path, text in sources.items():
        model = Parser(text, path).parse()
        if model.name in models:
            raise CompileError(f"duplicate module {model.name!r}")
        models[model.name] = model
    if not instances or len({i.name for i in instances}) != len(instances):
        raise CompileError("instances must be nonempty and have unique names")
    bindings = []
    for instance in instances:
        if not instance.name or not instance.module or instance.module not in models:
            raise CompileError(f"unknown module or empty instance identity: {instance}")
        model = models[instance.module]
        if set(instance.connections) != set(model.ports):
            raise CompileError(f"{instance.name}: connections must exactly match {model.ports}")
        if any(not isinstance(n, str) or not n or ":" in n for n in instance.connections.values()):
            raise CompileError("net names must be nonempty strings without ':' (reserved for internal nodes)")
        if ":" in instance.name:
            raise CompileError("instance names cannot contain ':'")
        if not set(instance.parameters) <= model.parameters.keys():
            raise CompileError(f"{instance.name}: unknown parameter override")
        nets = {n: instance.connections.get(n, f"{instance.name}:{n}") for n in model.nodes}
        nets["0"] = "0"
        bindings.append((instance, model, nets))
    names = ("0", *sorted({n for _, _, nets in bindings for n in nets.values()} - {"0"}))
    indices = {n: i for i, n in enumerate(names)}
    contributions = []
    for instance, model, nets in bindings:
        cache, active = {}, set()

        def parameter(name):
            if name not in model.parameters:
                raise CompileError(f"{model.source}: unknown parameter {name!r}")
            if name in active:
                raise CompileError(f"{model.source}: cyclic parameter defaults involving {name!r}")
            if name not in cache:
                active.add(name)
                if name in instance.parameters:
                    value = instance.parameters[name]
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise CompileError(f"{instance.name}: parameter {name!r} must be numeric")
                    value = float(value)
                else:
                    value, _ = _affine(model.parameters[name], parameter, {}, model.source)
                if not math.isfinite(value):
                    raise CompileError(f"{instance.name}: nonfinite parameter {name!r}")
                cache[name] = value
                active.remove(name)
            return cache[name]

        # Validate defaults even if an override would otherwise hide an invalid expression.
        def validate_default(expr):
            if expr.op == "voltage" or (expr.op == "parameter" and expr.value not in model.parameters):
                raise CompileError(f"{model.source}:{expr.token.line}: invalid parameter default")
            for arg in expr.args:
                validate_default(arg)

        for expr in model.parameters.values():
            validate_default(expr)
        for name in model.parameters:
            parameter(name)
        node_ids = {n: indices[net] for n, net in nets.items()}
        bound_branches = {}
        for branch, rhs in model.contributions:
            _affine(branch, parameter, node_ids, model.source)  # validates both target nodes
            local_p, local_n = (str(arg.value) for arg in branch.args)
            pair = tuple(sorted((local_p, local_n)))
            p, n = (node_ids[name] for name in pair)
            bound_pair = tuple(sorted((p, n)))
            if bound_pair in bound_branches and bound_branches[bound_pair] != pair:
                raise CompileError(f"{model.source}:{branch.token.line}: distinct local contribution branches alias after connection; not supported in this slice")
            bound_branches[bound_pair] = pair
            constant, terms = _affine(rhs, parameter, node_ids, model.source)
            sign = 1.0 if (local_p, local_n) == pair else -1.0
            origin = Origin(model.source, branch.token.line, branch.token.column, instance.name)
            contributions.append(Contribution(",".join(pair), p, n, Affine(sign * constant, tuple(
                Term(node, sign * coefficient) for node, coefficient in sorted(terms.items()))), origin))
    return Program(names, tuple(contributions))
