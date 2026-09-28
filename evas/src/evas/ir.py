"""Version 2: affine voltage contributions with structured local branch identity.

There is no node-write operation. Contributions in one instance on the same
unoriented branch are summed by the kernel. Different instances remain separate
voltage constraints, including when connected to the same external nodes.
"""

from dataclasses import asdict, dataclass
from typing import Literal


SCHEMA_VERSION = 2


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
    rhs: Affine
    origin: Origin


@dataclass(frozen=True)
class Program:
    nodes: tuple[str, ...]
    contributions: tuple[Contribution, ...]
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)
