"""Version 10: voltage/event IR with ordered event bodies and analog select.

There is no node-write operation. Contributions in one instance on the same
unoriented branch are summed by the kernel. Different instances remain separate
voltage constraints, including when connected to the same external nodes.
"""

from dataclasses import asdict, dataclass, field
from typing import Literal


SCHEMA_VERSION = 14
