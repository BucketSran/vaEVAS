"""Frozen ordinary-condition diagnostics with exact rational answers at t=1 s.

These six development probes are separate from the original 31-condition matrix.
Spectre tolerances are convergence controls, not an asserted forward-error bound.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILES = {
    "base": dict(vabstol=1e-9, reltol=1e-10, iabstol=1e-12, maxstep=.25),
    "fine": dict(vabstol=1e-12, reltol=1e-12, iabstol=1e-13, maxstep=.03125),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def manifest(root):
    return {str(p.relative_to(root)): dict(sha256=sha(p), bytes=p.stat().st_size)
            for p in sorted(root.rglob("*")) if p.is_file()}


def verify(root, filename):
    for rel, identity in json.loads((root/filename).read_text()).items():
        p = root/rel
        if not p.resolve().is_relative_to(root.resolve()) or sha(p) != identity["sha256"] or p.stat().st_size != identity["bytes"]:
            raise ValueError("artifact drift: " + rel)


def cases():
    threshold = float("0.3333333333333333")
    high = math.nextafter(1., math.inf)
    gain_answer = Q(10**16) * (Q(high)-1) / 3
    assert gain_answer == Q(152587890625, 206158430208)
    assert Q(1, 3) > Q(threshold)
    probes = [
        ("knot-equality", [[0., 0.], [1., threshold], [3., 1.]],
         "tmp=0; if(V(u,r)>0.3333333333333333) tmp=tmp+1; "
         "if(V(u,r)<0.3333333333333333) tmp=tmp+2; "
         "if(V(u,r)>=0.3333333333333333) tmp=tmp+4; "
         "if(V(u,r)<=0.3333333333333333) tmp=tmp+8; V(y,r)<+tmp;", Q(12)),
        ("large-cancellation", [[0., 1.], [3., 1.]],
         "if(V(u,r)+1e16>1e16) tmp=1; else tmp=0; V(y,r)<+tmp;", Q(1)),
        ("pwl-threshold", [[0., 0.], [3., 1.]],
         "if(V(u,r)>0.3333333333333333) tmp=1; else tmp=0; V(y,r)<+tmp;", Q(1)),
    ]
    expression = "1e16*(V(u,r)-1)"
    for name, extra in [
        ("gain-plain", ""),
        ("gain-empty-if", "if(V(u,r)>0) begin end "),
        ("gain-unused-if", "unused=0; if(V(u,r)>0) unused=1; "),
    ]:
        probes.append((name, [[0., 1.], [3., high]],
                       "tmp="+expression+"; "+extra+"V(y,r)<+tmp;", gain_answer))
    return [dict(id=name, inputs=dict(u=points), output_times=[1.], stop=3.,
                 body=body, expected=dict(numerator=answer.numerator, denominator=answer.denominator))
            for name, points, body, answer in probes]


def build(root):
    root.mkdir(parents=True, exist_ok=False)
    specs = []
    for case in cases():
        for profile, controls in PROFILES.items():
            c = dict(case, profile=profile, controls=controls)
            specs.append(c)
            work = root/"runs"/c["id"]/profile
            work.mkdir(parents=True)
            save(work/"condition.json", c)
            (work/"dut.va").write_text(
                '`include "disciplines.vams"\n'
                "module m(u,y,r); input u; output y; inout r; electrical u,y,r; "
                "real tmp,unused; analog begin "+c["body"]+" end endmodule\n")
            wave = " ".join(f"{t:.17g} {v:.17g}" for t, v in c["inputs"]["u"])
            (work/"tb.scs").write_text(
                'simulator lang=spectre\nahdl_include "dut.va"\n'
                f"Vu (u 0) vsource type=pwl wave=[{wave}]\ndut (u y 0) m\n"
                f"options options reltol={controls['reltol']:.17g} vabstol={controls['vabstol']:.17g} iabstol={controls['iabstol']:.17g}\n"
                f"tran tran stop=3 step={controls['maxstep']:.17g} maxstep={controls['maxstep']:.17g} method=traponly strobeperiod=1 strobeoutput=all\n"
                "save u y\n")
    save(root/"conditions.json", specs)
    shutil.copyfile(Path(__file__), root/"analog_boundaries.py")
    shutil.copyfile(ROOT/"experiments/dvs2-spectre-validation/remote.py", root/"remote.py")
    save(root/"INPUT_MANIFEST.json", manifest(root))
    print("Frozen", len(specs), "configurations; rational answers fixed before execution")


def evas(root, kernel):
    sys.path.insert(0, str(ROOT/"evas/src"))
    from evas import Instance, KernelError, compile_sources, transient
    verify(root, "INPUT_MANIFEST.json")
    save(root/"EVAS_STARTED.json", dict(kernel_sha256=sha(kernel), python=sys.version,
         input_manifest_sha256=sha(root/"INPUT_MANIFEST.json"),
         source_sha256={str(p.relative_to(ROOT)): sha(p) for pattern in
                       ["evas/src/**/*.py", "evas/rust_core/src/**/*.rs"] for p in ROOT.glob(pattern)}))
    for c in json.loads((root/"conditions.json").read_text()):
        work = root/"runs"/c["id"]/c["profile"]
        program = compile_sources({"dut.va": (work/"dut.va").read_text()},
                                  [Instance("dut", "m", dict(u="u", y="y", r="0"), {})])
        save(work/"program.json", program.to_dict())
        try:
            result = transient(program, c["inputs"], c["output_times"], stop=c["stop"],
                               max_step=c["controls"]["maxstep"], kernel=kernel,
                               vabstol=c["controls"]["vabstol"], reltol=c["controls"]["reltol"])
            save(work/"evas.json", result)
            print(c["id"], c["profile"], "accepted", flush=True)
        except KernelError as error:
            save(work/"evas-failure.json", error.detail)
            print(c["id"], c["profile"], error.detail["kind"], flush=True)


def spectre(root, profile):
    # The frozen copy is self-contained on the remote host.
    sys.path.insert(0, str(Path(__file__).parent))
    from remote import execute
    verify(root, "INPUT_MANIFEST.json")
    os.umask(0o077)
    config = json.loads(profile.read_text())
    binary, scripts = config["spectre"], config["setup_scripts"]
    if any(not re.fullmatch(r"/[A-Za-z0-9_./-]+", p) for p in [binary, *scripts]):
        raise ValueError("unsupported tool path")
    setup = "\n".join("source "+p for p in scripts)+"\n"
    cpu = min(os.sched_getaffinity(0))
    save(root/"SPECTRE_STARTED.json", dict(max_attempts=12, timeout_s=90, license_timeout_s=30,
         cpu=cpu, input_manifest_sha256=sha(root/"INPUT_MANIFEST.json"), binary_sha256=sha(Path(binary)),
         setup_sha256=[sha(Path(p)) for p in scripts]))
    (root/"version.csh").write_text(setup+binary+" -W\nexit $status\n")
    version = execute(["/bin/csh", "-f", "version.csh"], root, "version.log", 30)
    save(root/"version.json", version)
    if version["returncode"] or version["timeout"]:
        raise RuntimeError("version preflight failed")
    specs = json.loads((root/"conditions.json").read_text())
    assert len(specs) == 12
    for c in specs:
        work = root/"runs"/c["id"]/c["profile"]
        (work/"run.csh").write_text(setup+binary+" -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n")
        result = execute(["taskset", "-c", str(cpu), "/bin/csh", "-f", "run.csh"], work, "stdout.log", 90)
        save(work/"spectre-execution.json", result)
        print(c["id"], c["profile"], result["returncode"], flush=True)
    save(root/"FILE_MANIFEST.json", manifest(root))


def inspect(value, expected, controls):
    if not math.isfinite(value):
        return dict(status="observation_invalid", reason="nonfinite voltage")
    error = abs(Q(value)-expected)
    budget = Q(controls["vabstol"]) + Q(controls["reltol"]) * abs(expected)
    return dict(status="within_rational_target" if error <= budget else "outside_rational_target",
                value_v=value, exact_reference_v=float(expected), error_v=float(error), budget_v=float(budget))


def analyze(root, remote, output):
    sys.path.insert(0, str(ROOT/"experiments/dvs2-spectre-validation"))
    from report import settings
    from check_results import read_waveform
    verify(root, "INPUT_MANIFEST.json")
    verify(remote, "INPUT_MANIFEST.json")
    verify(remote, "FILE_MANIFEST.json")
    if sha(root/"INPUT_MANIFEST.json") != sha(remote/"INPUT_MANIFEST.json"):
        raise ValueError("remote input drift")
    records = []
    for c in json.loads((root/"conditions.json").read_text()):
        expected = Q(c["expected"]["numerator"], c["expected"]["denominator"])
        for backend, base in [("evas", root), ("spectre", remote)]:
            work = base/"runs"/c["id"]/c["profile"]
            row = dict(case=c["id"], profile=c["profile"], backend=backend,
                       input_sha256={n: sha(work/n) for n in ["dut.va", "condition.json", "tb.scs"]})
            if backend == "evas" and (work/"evas-failure.json").exists():
                row.update(status="kernel_rejected", detail=json.loads((work/"evas-failure.json").read_text()))
            elif backend == "evas":
                result = json.loads((work/"evas.json").read_text())
                row.update(inspect(result["solutions"][0]["voltages"][result["nodes"].index("y")], expected, c["controls"]),
                           waveform_sha256=sha(work/"evas.json"))
            else:
                execution = json.loads((work/"spectre-execution.json").read_text())
                row["execution"] = execution
                if execution["returncode"] or execution["timeout"]:
                    row.update(status="execution_failure")
                else:
                    waveform = work/"psf/tran.tran.tran"
                    rows = read_waveform(waveform, "spectre")
                    # No interpolation or nearest-point replacement of the rational target.
                    target = [r for r in rows if r["time"] == 1.]
                    if len(target) != 1:
                        row.update(status="observation_invalid", reason="missing or duplicate exact t=1 export")
                    else:
                        row.update(inspect(target[0]["y"], expected, c["controls"]), input_v=target[0]["u"])
                    log = (work/"spectre.log").read_text()
                    actual = settings(log)
                    if not all(math.isclose(actual[k], v, rel_tol=1e-12, abs_tol=0) for k, v in c["controls"].items()):
                        raise ValueError("effective setting mismatch")
                    row.update(effective=actual, waveform_sha256=sha(waveform),
                               strobeperiod_log=re.findall(r"^\s*strobeperiod = ([^\n]+)$", log, re.M),
                               strobe_audit="requested in frozen netlist; not printed in tool log; exact t=1 export checked directly",
                               warning_codes=dict(Counter(re.findall(r"WARNING \(([^)]+)\)", log))))
            records.append(row)
    save(output, dict(records=records, cases=6, configurations_per_backend=12,
         oracle="Exact real arithmetic over submitted binary64 constants and PWL knots at t=1 s",
         formal_dvs_qualification="I", continuous_time_qualified=False,
         input_manifest_sha256=sha(root/"INPUT_MANIFEST.json"),
         spectre_file_manifest_sha256=sha(remote/"FILE_MANIFEST.json"),
         analyzer_sha256=sha(Path(__file__)),
         summary={b: dict(Counter(r["status"] for r in records if r["backend"] == b)) for b in ["evas", "spectre"]}))
    for r in records:
        print(r["case"], r["profile"], r["backend"], r["status"], r.get("error_v"))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["build", "evas", "spectre", "check"])
    p.add_argument("root", type=Path)
    p.add_argument("--kernel", type=Path)
    p.add_argument("--spectre-profile", type=Path)
    p.add_argument("--remote", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    if a.action == "build": build(a.root)
    elif a.action == "evas": evas(a.root, a.kernel)
    elif a.action == "spectre": spectre(a.root, a.spectre_profile)
    else: analyze(a.root, a.remote, a.output)
