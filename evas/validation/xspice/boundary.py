"""Near-zero rising cross and unsupported UIC, through the public CLI.

The near-zero DC guard is -VTOL/2; VTOL is localization tolerance, not a
hysteresis threshold. Native Spectre input is prepared for an explicit run.
"""

import argparse, json, shutil, sys
from pathlib import Path
from cases import CASES, PROFILES, decks
from check import read_ng, read_spectre, grade, compare
from reference import expected
from validate import ROOT, SOURCE, run, sha
from native_reference import load_reference

CFG = dict(
    CASES["clock_feedback"],
    clock_feedback=False,
    threshold=0.0,
    clock_low=-0.0005,
    clock_high=0.5,
)
PROFILE = dict(PROFILES["refined"], maxstep="10p")


def boundary_decks(lib=Path("unused")):
    ng, sp = decks(CFG, PROFILE, lib)
    ng = (
        ng.replace("pulse(0 1.8", "pulse(-0.0005 0.5")
        .replace(" evas_inject=", " threshold=0 vtol=0.001 evas_inject=")
        .replace(' evas_trace="trace.csv"', "")
        .replace("8.4u", "1.6u")
    )
    sp = (
        sp.replace("val0=0 val1=1.8", "val0=-0.0005 val1=0.5")
        .replace(
            "sample_hold timer_start=",
            "sample_hold threshold=0 vtol=0.001 timer_start=",
        )
        .replace("8.4u", "1.6u")
    )
    return ng, sp


def prepare(output, sdk, python):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    artifact = output / "generated"
    cmd = [
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
        "threshold=0",
        "--parameter",
        "vtol=0.001",
    ]
    r = run(cmd, ROOT, output / "compile.log", 20)
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
    ng, sp = boundary_decks(lib)
    d = output / "ngspice/near_zero-refined"
    d.mkdir(parents=True)
    (d / "model.cm").symlink_to(lib)
    (d / ".spiceinit").write_text("codemodel model.cm\n")
    (d / "tb.cir").write_text(ng)
    r = run([receipt["ngspice"], "-b", "tb.cir"], d, d / "stdout.log", 30)
    (d / "result.json").write_text(
        json.dumps(
            {**r, "library_sha256": sha(lib), "deck_sha256": sha(d / "tb.cir")},
            indent=2,
        )
        + "\n"
    )
    assert r["exit_code"] == 0, r
    answer = expected(CFG, stop=1.6e-6)
    g = grade(read_ng(d / "wave.raw"), answer, CFG)
    spec = output / "spectre/near_zero-refined"
    spec.mkdir(parents=True)
    (spec / "sample_hold.va").write_bytes(SOURCE.read_bytes())
    (spec / "tb.scs").write_text(sp)
    manifest = {str(p.relative_to(output)): sha(p) for p in spec.iterdir()}
    (output / "input-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "expected.json").write_text(json.dumps(answer, indent=2) + "\n")
    (output / "analysis.json").write_text(
        json.dumps({"ngspice": g, "source_sha256": sha(SOURCE)}, indent=2) + "\n"
    )
    return g


def analyze(output):
    output = Path(output)
    a = json.loads((output / "expected.json").read_text())
    d = output / "spectre/near_zero-refined"
    native_identity = load_reference(d, SOURCE.read_bytes(), boundary_decks()[1])
    n = read_ng(output / "ngspice/near_zero-refined/wave.raw")
    s = read_spectre(d / "psf/tran.tran.tran")
    g = grade(s, a, CFG)
    pair = compare(n, s)
    result = {"ngspice": grade(n, a, CFG), "spectre": g, "pair": pair}
    result["passed"] = all(x["passed"] for x in result.values())
    result["native_identity"] = native_identity
    (output / "paired-analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--sdk")
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--analyze", action="store_true")
    a = p.parse_args()
    r = analyze(a.output) if a.analyze else prepare(a.output, a.sdk, a.python)
    print(json.dumps(r, indent=2))
