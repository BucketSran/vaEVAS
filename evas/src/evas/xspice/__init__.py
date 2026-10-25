"""Compile the documented voltage-event subset into ngspice XSPICE models.

This backend uses ngspice's circuit solver, not the EVAS Rust execution path.
"""

from .compiler import compile_model
from .build import build_model

__all__ = ["compile_model", "build_model"]
