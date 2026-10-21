"""Version 30: voltage/event IR with typed integers and forcing markers.

There is no node-write operation. Contributions in one instance on the same
unoriented branch are summed by the kernel. Different instances remain separate
voltage constraints, including when connected to the same external nodes.
"""

from dataclasses import asdict, dataclass, field
from typing import Literal

from .limits import check_ir


SCHEMA_VERSION = 32


@dataclass(frozen=True)
class Origin:
    source: str
    line: int
    column: int
    instance: str
    expansion: tuple[tuple[str, int], ...] = ()


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
    op: Literal["add", "multiply", "divide"]
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
class Forcing:
    value: "Expression"
    origin: Origin
    checked: tuple["Expression", ...] = ()
    op: str = field(default="forcing", init=False)


@dataclass(frozen=True)
class StateRef:
    state: int
    op: str = field(default="state", init=False)


@dataclass(frozen=True)
class OperatorRef:
    operator: int
    op: str = field(default="operator", init=False)


@dataclass(frozen=True)
class EventMath:
    function: Literal["sqrt", "abs", "min", "max", "floor", "ln"]
    args: tuple["Expression", ...]
    origin: Origin
    op: str = field(default="event_math", init=False)


@dataclass(frozen=True)
class CheckedIndex:
    index: "Expression"
    first: int
    last: int
    origin: Origin
    op: str = field(default="checked_index", init=False)


@dataclass(frozen=True)
class IntegerRound:
    value: "Expression"
    origin: Origin
    op: str = field(default="integer_round", init=False)


@dataclass(frozen=True)
class CheckedInteger:
    value: "Expression"
    origin: Origin
    op: str = field(default="checked_integer", init=False)


@dataclass(frozen=True)
class ArrayRead:
    states: tuple[int, ...]
    index: "Expression"
    first: int
    last: int
    origin: Origin
    op: str = field(default="array_read", init=False)


@dataclass(frozen=True)
class IntegerLiteral:
    value: int
    op: str = field(default="integer_literal", init=False)


@dataclass(frozen=True)
class IntegerState:
    state: int
    op: str = field(default="integer_state", init=False)


@dataclass(frozen=True)
class IntegerPrimitive:
    function: Literal["add", "subtract", "remainder", "shift_right", "bit_and"]
    args: tuple["IntegerLiteral | IntegerState | IntegerPrimitive", ...]
    origin: Origin
    op: str = field(default="integer_primitive", init=False)


Expression = IntegerRound | Forcing | IntegerPrimitive | ArrayRead | CheckedInteger | CheckedIndex | Affine | Binary | Power | Select | StateRef | OperatorRef | EventMath


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
class MathFunction:
    function: Literal["cos", "exp", "ln", "sqrt", "tanh"]
    input: Expression
    origin: Origin
    kind: str = field(default="math", init=False)


@dataclass(frozen=True)
class State:
    instance: str
    name: str
    kind: Literal["real", "integer"]
    initial: float | Expression


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
class ArrayWrite:
    states: tuple[int, ...]
    index: Expression
    rhs: Expression
    first: int
    last: int
    origin: Origin
    kind: str = field(default="array_write", init=False)


@dataclass(frozen=True)
class Loop:
    initialize: tuple["Assignment | Conditional | Display | Loop | ArrayWrite", ...]
    relation: Literal["lt", "le", "gt", "ge"]
    left: Expression
    right: Expression
    body: tuple["Assignment | Conditional | Display | Loop | ArrayWrite", ...]
    update: tuple["Assignment | Conditional | Display | Loop | ArrayWrite", ...]
    origin: Origin
    kind: str = field(default="loop", init=False)


@dataclass(frozen=True)
class Display:
    format: str
    args: tuple[Expression, ...]
    origin: Origin
    kind: str = field(default="display", init=False)


@dataclass(frozen=True)
class InitialStepTrigger:
    kind: str = field(default="initial_step", init=False)


@dataclass(frozen=True)
class FinalStepTrigger:
    kind: str = field(default="final_step", init=False)


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
class HeldTimerTrigger:
    start: Expression
    period: Expression
    time_tolerance: float
    enabled: Expression
    kind: str = field(default="held_timer", init=False)


@dataclass(frozen=True)
class OrTrigger:
    triggers: tuple[CrossTrigger | TimerTrigger | HeldTimerTrigger, ...]
    kind: str = field(default="or", init=False)


@dataclass(frozen=True)
class Event:
    trigger: CrossTrigger | TimerTrigger | HeldTimerTrigger | OrTrigger | FinalStepTrigger | InitialStepTrigger
    body: tuple[Assignment | Conditional | Display | Loop | ArrayWrite, ...]
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
class StepBound:
    value: Expression
    active: Expression
    origin: Origin


@dataclass(frozen=True)
class Program:
    nodes: tuple[str, ...]
    contributions: tuple[Contribution, ...]
    states: tuple[State, ...] = ()
    events: tuple[Event, ...] = ()
    operators: tuple[Transition | AbsDelay | Slew | Idt | LaplaceNd | IdtMod | Sin | MathFunction | Ddt, ...] = ()
    schema_version: int = SCHEMA_VERSION
    step_bounds: tuple[StepBound, ...] = ()

    def to_dict(self) -> dict:
        audit = getattr(self, "_native_audit", None)
        check_ir(self, work=audit.ir_work if audit is not None else None,
                 cache=audit.ir_cache if audit is not None else None)
        return audit.materialize(self) if audit is not None and audit.active else asdict(self)
