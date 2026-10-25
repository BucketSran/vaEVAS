"""Compatibility access to the versioned historical comparison import.

Current normative and qualification records live in data/ and registry.py.
Historical scores retain their original scope and are never current qualification.
"""
import json
from pathlib import Path

_DATA = json.loads((Path(__file__).resolve().parent / "data" /
                         "historical-comparison.json").read_text())
CHAPTERS = tuple(_DATA["chapters"])
BACKENDS = tuple(_DATA["backends"])
CAMPAIGNS = _DATA["campaigns"]
NODES = _DATA["nodes"]
