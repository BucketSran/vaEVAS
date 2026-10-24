"""Load checkout-owned paper inputs without importing backend execution tools."""
import importlib.util
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    'paper_case_inputs', Path(__file__).resolve().parents[1] / 'validation/paper/case_inputs.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
load_core = _module.load_core
case_source = _module.case_source
binding = _module.binding
stimulus = _module.stimulus
