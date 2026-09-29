"""Process adapter: one batch crosses to Rust; no Python evaluation callbacks."""

import json
from pathlib import Path
import subprocess

from .ir import Program, SCHEMA_VERSION


class KernelError(RuntimeError):
    def __init__(self, detail: dict):
        self.detail = detail
        super().__init__(f"{detail['kind']}: {detail['message']}")


def solve(program: Program, driven: list[str], samples: list[list[float]], *,
          kernel: str | Path, vabstol: float | None = None, reltol: float | None = None,
          absolute: float | None = None, relative: float | None = None) -> dict:
    """Solve with voltage tolerances; absolute/relative are legacy aliases."""
    request = dict(program=program.to_dict(), driven=driven, samples=samples,
                   tolerances=_tolerances(vabstol, reltol, absolute, relative))
    response = _invoke(request, kernel)
    if (response.get("schema_version") != SCHEMA_VERSION or response.get("nodes") != list(program.nodes)
            or len(response.get("solutions", [])) != len(samples)):
        raise KernelError(dict(kind="invalid_response", message="kernel response identity or shape mismatch"))
    return response


def transient(program: Program, sources: dict[str, list[list[float]]],
              output_times: list[float], *, stop: float, max_step: float,
              kernel: str | Path, vabstol: float | None = None, reltol: float | None = None,
              absolute: float | None = None, relative: float | None = None) -> dict:
    """Advance PWL physical inputs in Rust; observations are post-event values."""
    request = dict(program=program.to_dict(), driven=list(sources), samples=[],
                   transient=dict(pwl=list(sources.values()), output_times=output_times,
                                  stop=stop, max_step=max_step),
                   tolerances=_tolerances(vabstol, reltol, absolute, relative))
    response = _invoke(request, kernel)
    if (response.get("schema_version") != SCHEMA_VERSION
            or response.get("nodes") != list(program.nodes)
            or len(response.get("solutions", [])) != len(output_times)
            or response.get("transient", {}).get("times") != output_times
            or response["transient"].get("state_names") != [f"{s.instance}:{s.name}" for s in program.states]
            or len(response["transient"].get("states", [])) != len(output_times)):
        raise KernelError(dict(kind="invalid_response", message="transient response identity or shape mismatch"))
    return response


def _tolerances(vabstol, reltol, absolute, relative):
    if vabstol is not None and absolute is not None:
        raise ValueError("cannot specify both vabstol and absolute")
    if reltol is not None and relative is not None:
        raise ValueError("cannot specify both reltol and relative")
    absolute = vabstol if vabstol is not None else absolute
    relative = reltol if reltol is not None else relative
    return dict(absolute=1e-12 if absolute is None else absolute,
                relative=1e-10 if relative is None else relative)


def _invoke(request, kernel):
    result = subprocess.run([str(kernel)], input=json.dumps(request, allow_nan=False),
                            text=True, capture_output=True, check=False)
    if result.returncode:
        try:
            detail = json.loads(result.stderr)
        except json.JSONDecodeError:
            detail = dict(kind="kernel_process", message=result.stderr or f"exit {result.returncode}")
        raise KernelError(detail)
    response = json.loads(result.stdout)
    return response
