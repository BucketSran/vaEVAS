"""Process adapter: one batch crosses to Rust; no Python evaluation callbacks."""

import json
import math
import os
from pathlib import Path
import subprocess

from .ir import Program
from .errors import KernelError
from .manifest import finite_float, reject_constant, unique_object
from .protocol import validate_response
from .kernel import select_kernel
from .strobe import expand

DEFAULT_TIMEOUT = 300.0


def solve(program: Program, driven: list[str], samples: list[list[float]], *,
          kernel: str | Path | None = None, vabstol: float | None = None, reltol: float | None = None,
          absolute: float | None = None, relative: float | None = None,
          timeout: float | None = DEFAULT_TIMEOUT) -> dict:
    """Solve with voltage tolerances; absolute/relative are legacy aliases."""
    request = dict(program=program.to_dict(), driven=driven, samples=samples,
                   tolerances=_tolerances(vabstol, reltol, absolute, relative))
    response = _invoke(request, kernel, timeout)
    return validate_response(response, program, len(samples))


def transient(program: Program, sources: dict[str, list[list[float]]],
              output_times: list[float], *, stop: float, max_step: float,
              strobetimes=None, strobeperiod=None, strobedelay=0.0, skipstart=0.0, skipstop=None,
              kernel: str | Path | None = None, vabstol: float | None = None, reltol: float | None = None,
              absolute: float | None = None, relative: float | None = None,
              timeout: float | None = DEFAULT_TIMEOUT) -> dict:
    """Advance PWL physical inputs in Rust; observations are post-event values."""
    request = dict(program=program.to_dict(), driven=list(sources), samples=[],
                   transient=dict(pwl=list(sources.values()), output_times=output_times,
                                  stop=stop, max_step=max_step),
                   tolerances=_tolerances(vabstol, reltol, absolute, relative))
    points = (expand(stop, strobetimes=strobetimes, strobeperiod=strobeperiod,
                     strobedelay=strobedelay, skipstart=skipstart, skipstop=skipstop)
              if strobetimes is not None or strobeperiod is not None or strobedelay != 0 or skipstart != 0 or skipstop is not None else [])
    if points:
        request["transient"]["strobetimes"] = points
    response = _invoke(request, kernel, timeout)
    return validate_response(response, program, len(output_times), output_times, strobetimes=points)


def _tolerances(vabstol, reltol, absolute, relative):
    if vabstol is not None and absolute is not None:
        raise ValueError("cannot specify both vabstol and absolute")
    if reltol is not None and relative is not None:
        raise ValueError("cannot specify both reltol and relative")
    absolute = vabstol if vabstol is not None else absolute
    relative = reltol if reltol is not None else relative
    return dict(absolute=1e-12 if absolute is None else absolute,
                relative=1e-10 if relative is None else relative)


def _invoke(request, kernel, timeout=DEFAULT_TIMEOUT, *, diagnostics_path=None):
    if timeout is not None:
        try:
            valid = not isinstance(timeout, bool) and isinstance(timeout, (int, float)) and math.isfinite(timeout) and timeout > 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("timeout must be a positive finite number of seconds or None")
    kernel = select_kernel() if kernel is None else kernel
    try:
        # subprocess.run kills and waits for its child before TimeoutExpired
        # escapes. No abandoned kernel can keep writing after this diagnostic.
        options = {}
        if diagnostics_path is not None:
            options["env"] = dict(os.environ, EVAS_DIAGNOSTICS_PATH=str(diagnostics_path))
        result = subprocess.run([str(kernel)], input=json.dumps(request, allow_nan=False),
                                text=True, capture_output=True, check=False, timeout=timeout, **options)
    except subprocess.TimeoutExpired as exc:
        raise KernelError(dict(kind="kernel_timeout", message=f"kernel exceeded execution timeout ({timeout} s)", timeout_seconds=timeout)) from exc
    except (OSError, UnicodeError) as exc:
        raise KernelError(dict(kind="kernel_process", message=f"cannot execute selected kernel {kernel}: {exc}; install the matching platform wheel or rebuild and pass --kernel PATH")) from exc
    if result.returncode:
        try:
            detail = json.loads(result.stderr, object_pairs_hook=unique_object,
                                parse_constant=reject_constant, parse_float=finite_float)
            if (not isinstance(detail, dict) or not isinstance(detail.get("kind"), str)
                    or not isinstance(detail.get("message"), str)
                    or "sample" in detail and (type(detail["sample"]) is not int or detail["sample"] < 0)):
                raise ValueError("invalid kernel diagnostic")
        except (ValueError, RecursionError):
            detail = dict(kind="kernel_process", message=result.stderr or f"exit {result.returncode}")
        raise KernelError(detail)
    try:
        return json.loads(result.stdout, object_pairs_hook=unique_object,
                          parse_constant=reject_constant, parse_float=finite_float)
    except (ValueError, RecursionError) as exc:
        raise KernelError(dict(kind="invalid_response", message=f"invalid kernel JSON: {exc}")) from exc
