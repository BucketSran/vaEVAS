"""Actual public default artifact: two instances, paths with spaces and no trace.

Expected independent RC answers use the retained analytic contract; no DUT
history function is used by the oracle.
"""

import argparse, json, sys, shutil
from pathlib import Path
from validate import run, ROOT, SOURCE, sha
from cases import CASES
from reference import expected
from check import read_ng, grade


def validate(output, sdk, python):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    artifact = output / "artifact with spaces"
    command = [
        python,
        "-B",
        "-m",
        "evas",
        "xspice",
        "compile",
        SOURCE,
        "-o",
        artifact,
        "--model-name",
        "sample_hold_cm",
        "--parameter",
        "timer_start=1.08e-6",
    ]
    r = run(command, ROOT, output / "compile.log", 20)
    assert r["exit_code"] == 0, r
    r = run(
        [
            python,
            "-B",
            "-m",
            "evas",
            "xspice",
            "build",
            artifact,
            "--sdk",
            str(Path(sdk).resolve()),
        ],
        ROOT,
        output / "build.log",
        120,
    )
    assert r["exit_code"] == 0, r
    receipt = json.loads((artifact / "native/build.json").read_text())
    lib = Path(receipt["library"])
    d = output / "two-instances"
    d.mkdir()
    (d / "model.cm").symlink_to(lib)
    (d / ".spiceinit").write_text("codemodel model.cm\n")
    shutil.copy2(artifact / "model.inc", d / "model.inc")
    text = "EVAS two independent model instances\n.include model.inc\nvclock clk 0 pulse(0 1.8 1u 10n 10n 1u 3u)\nvdin dina 0 pwl(0 .1 9u 1.0)\nvbias bias outb .2\nrfb bias dinb 1k\ncfb dinb 0 1n\n"
    for suffix in ("a", "b"):
        text += (
            "a"
            + suffix
            + " din"
            + suffix
            + " clk "
            + " ".join(
                n + suffix for n in ("out", "held", "count", "ticks", "order", "stamp")
            )
            + " sample_hold_cm\n"
        )
    text += (
        ".options method=gear maxord=2 reltol=1e-10 vntol=1e-13 abstol=1e-16\n.save v(clk) "
        + " ".join(
            "v(" + n + s + ")"
            for s in ("a", "b")
            for n in ("din", "out", "held", "count", "ticks", "order", "stamp")
        )
        + "\n.tran 1n 8.4u 0 .25n\n.control\nset filetype=ascii\nset numdgt=17\nrun\nwrite wave.raw all\nquit\n.endc\n.end\n"
    )
    (d / "tb.cir").write_text(text)
    r = run([receipt["ngspice"], "-b", "tb.cir"], d, d / "stdout.log", 30)
    (d / "result.json").write_text(
        json.dumps(
            {**r, "library_sha256": sha(lib), "deck_sha256": sha(d / "tb.cir")},
            indent=2,
        )
        + "\n"
    )
    assert r["exit_code"] == 0, r
    v = read_ng(d / "wave.raw")
    grades = {}
    for suffix in ("a", "b"):
        cfg = dict(CASES["timer_after"], feedback=suffix == "b")
        waveform = {
            "time": v["time"],
            "clk": v["clk"],
            **{
                n: v[n + suffix]
                for n in ("din", "out", "held", "count", "ticks", "order", "stamp")
            },
        }
        grades[suffix] = grade(waveform, expected(cfg), cfg)
    # The native output folder itself has a generated relative startup file.
    # A forbidden fault request must fail even though its parameter is visible.
    reject = output / "disabled-hooks"
    reject.mkdir()
    (reject / "model.cm").symlink_to(lib)
    (reject / ".spiceinit").write_text("codemodel model.cm\n")
    bad = text.replace(
        ".include model.inc",
        '.model sample_hold_cm sample_hold_cm(evas_inject=true evas_trace="trace.csv")',
    )
    (reject / "tb.cir").write_text(bad)
    rr = run([receipt["ngspice"], "-b", "tb.cir"], reject, reject / "stdout.log", 30)
    (reject / "result.json").write_text(json.dumps(rr, indent=2) + "\n")
    hooks_rejected = (
        rr["exit_code"] != 0
        and "test hooks were not enabled at compilation"
        in (reject / "stdout.log").read_text()
    )
    result = {
        "passed": all(g["passed"] for g in grades.values())
        and not list(d.glob("trace*"))
        and hooks_rejected,
        "instances": grades,
        "default_creates_no_trace": not list(d.glob("trace*")),
        "disabled_hooks_rejected": hooks_rejected,
        "artifact_test_hooks": json.loads((artifact / "metadata.json").read_text())[
            "test_hooks"
        ],
        "library_sha256": sha(lib),
        "new_ng_circuit_runs": 2,
        "new_ng_build_probes": 1,
    }
    (output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--sdk", required=True)
    p.add_argument("--python", default=sys.executable)
    a = p.parse_args()
    v = validate(a.output, a.sdk, a.python)
    print("multi-instance/default-mode", v["passed"])
    sys.exit(0 if v["passed"] else 1)
