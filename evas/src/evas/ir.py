"""Version 16: combined voltage/event IR with selects, reset histories and operators.

There is no node-write operation. Contributions in one instance on the same
unoriented branch are summed by the kernel. Different instances remain separate
voltage constraints, including when connected to the same external nodes.
"""

from dataclasses import asdict, dataclass, field
from typing import Literal


SCHEMA_VERSION = 16


@dataclass(frozen=True)
class Origin:
    source: str
    line: int
    column: int
    instance: str


@dataclass(frozen=True)
class Term:
    node: int
    coefficient: float


@dataclass(frozen=True)
class Affine:
    constant: float
    terms: tuple[Term, ...]
    op: str = field(default="affine", init=False)


@dataclass(frozen=True)
class Binary:
    op: Literal["add", "multiply"]
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Power:
    base: "Expression"
    exponent: int
    op: str = field(default="power", init=False)


@dataclass(frozen=True)
class Select:
    relation: Literal["lt", "le", "gt", "ge"]
    left: "Expression"
    right: "Expression"
    then_value: "Expression"
    else_value: "Expression"
    origin: Origin
    op: str = field(default="select", init=False)


@dataclass(frozen=True)
class StateRef:
    state: int
    op: str = field(default="state", init=False)


@dataclass(frozen=True)
class OperatorRef:
    operator: int
    op: str = field(default="operator", init=False)


Expression = Affine | Binary | Power | Select | StateRef | OperatorRef


@dataclass(frozen=True)
class Transition:
    input: Expression
    delay: float
    rise: float
    fall: float
    origin: Origin
    kind: str = field(default="transition", init=False)


@dataclass(frozen=True)
class Slew:
    input: Expression
    rise: float
    fall: float
    origin: Origin
    kind: str = field(default="slew", init=False)


@dataclass(frozen=True)
class AbsDelay:
    input: Expression
    delay: float
    origin: Origin
    kind: str = field(default="abs_delay", init=False)


@dataclass(frozen=True)
class Idt:
    input: Expression
    ic: float
    origin: Origin
    reset: Expression | None = None
    kind: str = field(default="idt", init=False)


@dataclass(frozen=True)
class Ddt:
    input: Expression
    origin: Origin
    kind: str = field(default="ddt", init=False)


@dataclass(frozen=True)
class LaplaceNd:
    input: Expression
    numerator: tuple[float, ...]
    denominator: tuple[float, ...]
    origin: Origin
    kind: str = field(default="laplace_nd", init=False)


@dataclass(frozen=True)
class IdtMod:
    input: Expression
    ic: float
    modulus: float
    offset: float
    origin: Origin
    kind: str = field(default="idt_mod", init=False)


@dataclass(frozen=True)
class Sin:
    input: Expression
    origin: Origin
    kind: str = field(default="sin", init=False)


@dataclass(frozen=True)
class State:
    instance: str
    name: str
    kind: Literal["real", "integer"]
    initial: float


@dataclass(frozen=True)
class Assignment:
    state: int
    rhs: Expression
    kind: str = field(default="assign", init=False)


@dataclass(frozen=True)
class Conditional:
    relation: Literal["lt", "le", "gt", "ge"]
    left: Expression
    right: Expression
    then_body: tuple["Assignment | Conditional", ...]
    else_body: tuple["Assignment | Conditional", ...]
    origin: Origin
    kind: str = field(default="if", init=False)


@dataclass(frozen=True)
class CrossTrigger:
    guard: Expression
    direction: int
    time_tolerance: float
    expression_tolerance: float
    kind: str = field(default="cross", init=False)


@dataclass(frozen=True)
class TimerTrigger:
    start: float
    period: float
    time_tolerance: float
    enabled: bool
    kind: str = field(default="timer", init=False)


@dataclass(frozen=True)
class OrTrigger:
    triggers: tuple[CrossTrigger, ...]
    kind: str = field(default="or", init=False)


@dataclass(frozen=True)
class Event:
    trigger: CrossTrigger | TimerTrigger | OrTrigger
    body: tuple[Assignment | Conditional, ...]
    origin: Origin


@dataclass(frozen=True)
class BranchIdentity:
    """Canonical local endpoints, independent of global net binding and origin."""
    instance: str
    local_positive: str
    local_negative: str
    kind: Literal["voltage"] = "voltage"


@dataclass(frozen=True)
class Contribution:
    branch: BranchIdentity
    positive: int
    negative: int
    rhs: Expression
    origin: Origin


@dataclass(frozen=True)
class Program:
    nodes: tuple[str, ...]
    contributions: tuple[Contribution, ...]
    states: tuple[State, ...] = ()
    events: tuple[Event, ...] = ()
    operators: tuple[Transition | AbsDelay | Slew | Idt | LaplaceNd | IdtMod | Sin | Ddt, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)
