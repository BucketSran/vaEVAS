"""Version 3: polynomial voltage contributions with structured local branch identity.

There is no node-write operation. Contributions in one instance on the same
unoriented branch are summed by the kernel. Different instances remain separate
voltage constraints, including when connected to the same external nodes.
"""

from dataclasses import asdict, dataclass, field
from typing import Literal


SCHEMA_VERSION = 3


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


Expression = Affine | Binary | Power


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
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)
