"""Run existing event tests through two kernels and compare response text exactly.

Use binaries built from the baseline and candidate on the same host/toolchain.
The tests keep their existing assertions; they receive the candidate response.
Raw requests and both responses go to a new, local-only output directory.
Coverage is the captured fixed-debug-kernel subprocess.run requests, not all
possible subprocess entry points. Diagnostic timings are not compared.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


MODULES = """
test_events test_timer test_dynamic_timer test_dynamic_cross
test_event_horizons test_event_window_sampling test_lifecycle_closure
test_semantic_invariants test_event_history_continuation
test_bounded_event_closure test_al4_lifecycle
test_initialized_event_composition test_event_relocalization
test_history_relocalization test_event_or test_event_conditions
test_event_writers test_timed_composition test_sample_state_precision
test_timer_history_order test_strobe test_boundary_portability
test_input_clamp test_timer_ordering
""".split()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def equal(a, b):
    return (a.returncode, a.stdout, a.stderr) == (b.returncode, b.stdout, b.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-requests", type=int)
    args = parser.parse_args()
    baseline, candidate, output = (p.resolve() for p in
                                   (args.baseline, args.candidate, args.output))
    root = Path(__file__).resolve().parents[3]
    kernel = root / "evas/rust_core/target/debug/evas-kernel"
    sys.path[:0] = [str(root / "evas/src"), str(root / "evas/tests")]
    identities = {name: {"path": str(p), "sha256": sha(p.read_bytes())}
                  for name, p in (("baseline", baseline), ("candidate", candidate))}
    output.mkdir(parents=True, exist_ok=False)
    original = subprocess.run
    records = []
    timeouts = []
    current_test = "module-load"

    def capture(command, *positional, **kwargs):
        if not (isinstance(command, (tuple, list)) and command
                and Path(command[0]).resolve() == kernel.resolve()):
            return original(command, *positional, **kwargs)
        if list(command[1:]) == ["--version", "--json"]:
            return original(command, *positional, **kwargs)
        request = kwargs.get("input")
        if not isinstance(request, str):
            raise TypeError("Selected kernel tests must send a text request")
        prefix = f"{len(records):04d}"
        (output / f"{prefix}.request.json").write_text(request)
        results = []
        for name, binary in (("baseline", baseline), ("candidate", candidate)):
            options = dict(kwargs)
            options.setdefault("timeout", 90)
            environment = options.get("env", os.environ)
            sidecar = environment.get("EVAS_DIAGNOSTICS_PATH")
            if sidecar and name == "baseline":
                # Diagnostic output uses create-new semantics. The two runs
                # must not share that file; the caller reads the candidate's.
                options["env"] = dict(environment, EVAS_DIAGNOSTICS_PATH=str(
                    output / f"{prefix}.baseline.diagnostics.json"))
            try:
                result = original([str(binary), *command[1:]], *positional, **options)
            except subprocess.TimeoutExpired as error:
                timeouts.append(dict(id=prefix, test=current_test, kernel=name,
                                     timeout_seconds=error.timeout))
                # Preserve partial bytes as evidence; do not fabricate a kernel
                # response or turn matching timeouts into successful comparison.
                for stream in ("stdout", "stderr"):
                    data = getattr(error, stream) or b""
                    if isinstance(data, str):
                        data = data.encode()
                    (output / f"{prefix}.{name}.timeout.{stream}").write_bytes(data)
                raise
            if sidecar and name == "candidate" and Path(sidecar).is_file():
                (output / f"{prefix}.candidate.diagnostics.json").write_bytes(
                    Path(sidecar).read_bytes())
            for stream in ("stdout", "stderr"):
                (output / f"{prefix}.{name}.{stream}").write_text(getattr(result, stream))
            results.append(result)
        a, b = results
        records.append(dict(id=prefix, test=current_test, request_sha256=sha(request.encode()),
                            baseline_returncode=a.returncode, candidate_returncode=b.returncode,
                            equal=equal(a, b), stdout_sha256=sha(b.stdout.encode()),
                            stderr_sha256=sha(b.stderr.encode())))
        return b

    class Result(unittest.TextTestResult):
        def startTest(self, test):
            nonlocal current_test
            current_test = test.id()
            super().startTest(test)

    # Calibrate exact comparison, including a binary64 least-significant-bit
    # change, signed zero, event ordering, diagnostics and process failure.
    def response(out="1.0", err="", code=0):
        return subprocess.CompletedProcess([], code, out, err)

    controls = [
        not equal(response(), response("1.0000000000000002")),
        not equal(response("0.0"), response("-0.0")),
        not equal(response("[1,2]"), response("[2,1]")),
        not equal(response(), response(err="event_resolution")),
        not equal(response(), response(code=1)),
        equal(response(), response()),
    ]
    subprocess.run = capture
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
        result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    finally:
        subprocess.run = original
    summary = dict(identities=identities, modules=MODULES, tests=result.testsRun,
                   failures=len(result.failures), errors=len(result.errors),
                   skipped=len(result.skipped), requests=len(records),
                   different=sum(not r["equal"] for r in records),
                   baseline_rejections=sum(r["baseline_returncode"] != 0 for r in records),
                   expected_requests=args.expected_requests, timeouts=timeouts,
                   comparator_controls=controls, records=records)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    count_matches = args.expected_requests is None or len(records) == args.expected_requests
    return 0 if (result.wasSuccessful() and records and not summary["different"]
                 and count_matches and not timeouts
                 and all(controls)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
