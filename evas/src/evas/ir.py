"""Version 1: affine voltage contributions, before branch assembly.

There is no node-write operation. Contributions in one instance on the same
unoriented branch are summed by the kernel. Different instances remain separate
voltage constraints, including when connected to the same external nodes.
"""

from dataclasses import asdict, dataclass


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
class Contribution:
    # Canonical local node pair, before port binding. External net aliases must
    # never accidentally merge two distinct model branches.
    branch: str
    positive: int
    negative: int
    rhs: Affine
    origin: Origin


@dataclass(frozen=True)
class Program:
    nodes: tuple[str, ...]
    contributions: tuple[Contribution, ...]
    schema_version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)
