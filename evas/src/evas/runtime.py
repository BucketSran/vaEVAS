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
from .limits import MAX_PROOF_WORK_LIMIT
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
              analytic_sources: dict[str, dict] | None = None,
              source_errors: dict[str, float] | None = None,
              source_shapes: dict[str, list[dict]] | None = None,
              strobetimes=None, strobeperiod=None, strobedelay=0.0, skipstart=0.0, skipstop=None,
              kernel: str | Path | None = None, vabstol: float | None = None, reltol: float | None = None,
              absolute: float | None = None, relative: float | None = None,
              proof_work_limit: int | None = None,
              timeout: float | None = DEFAULT_TIMEOUT) -> dict:
    """Advance typed physical inputs in Rust; observations are post-event values.

    ``proof_work_limit`` raises or lowers the kernel's source-transition proof work
    limit for this request (an integer in 1..MAX_PROOF_WORK_LIMIT). Unset keeps the
    default and the request unchanged; the response echoes the limit in force.
    """
    _proof_work_limit(proof_work_limit)
    request = dict(program=program.to_dict(), driven=list(sources), samples=[],
                   transient=dict(pwl=list(sources.values()), output_times=output_times,
                                  stop=stop, max_step=max_step),
                   tolerances=_tolerances(vabstol, reltol, absolute, relative))
    if proof_work_limit is not None:
        request['transient']['proof_work_limit'] = proof_work_limit
    if analytic_sources is not None:
        if not isinstance(analytic_sources,dict) or set(analytic_sources)-set(sources):
            raise ValueError('analytic_sources must map driven names to typed descriptors')
        request['transient']['analytic_sources']=[analytic_sources.get(n) for n in sources]
    if source_errors is not None or source_shapes is not None:
        source_errors = {} if source_errors is None else source_errors
        source_shapes = {} if source_shapes is None else source_shapes
        if not isinstance(source_errors,dict) or set(source_errors)-set(sources):
            raise ValueError('source_errors must map driven source names to nonnegative finite voltage bounds')
        if not isinstance(source_shapes,dict) or set(source_shapes)-set(sources):
            raise ValueError('source_shapes must map driven source names to exact PWL knots')
        errors=[]
        for name in sources:
            error=source_errors.get(name,0.)
            try:
                valid=not isinstance(error,bool) and isinstance(error,(int,float)) and math.isfinite(error) and error>=0
            except OverflowError:
                valid=False
            if not valid:
                raise ValueError('source_errors must contain nonnegative finite voltage bounds')
            if name in source_shapes:
                if not isinstance(source_shapes[name],list):
                    raise ValueError('source_shapes must contain lists of exact PWL knots')
                errors.append(dict(voltage_error_bound_V=float(error),exact_knots=source_shapes[name]))
            else:
                errors.append(float(error))
        request['transient']['pwl_errors_V']=errors
    points = (expand(stop, strobetimes=strobetimes, strobeperiod=strobeperiod,
                     strobedelay=strobedelay, skipstart=skipstart, skipstop=skipstop)
              if strobetimes is not None or strobeperiod is not None or strobedelay != 0 or skipstart != 0 or skipstop is not None else [])
    if points:
        request["transient"]["strobetimes"] = points
    response = _invoke(request, kernel, timeout)
    return validate_response(response, program, len(output_times), output_times, strobetimes=points,
                             proof_work_limit=proof_work_limit)


def _proof_work_limit(value):
    """Only an exact integer in range is sent; anything else never reaches the kernel."""
    if value is not None and (type(value) is not int or not 1 <= value <= MAX_PROOF_WORK_LIMIT):
        raise ValueError(f'proof_work_limit must be an integer between 1 and {MAX_PROOF_WORK_LIMIT}')


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
