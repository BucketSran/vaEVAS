"""Freeze/admit P0 same-source references; local analysis starts no remote job."""

import argparse
import json
from pathlib import Path
import shutil

from alias_cases import CASES, BUDGETS
from alias_reference import score_wave, native_state, pair
from boundary import CFG, PROFILE, boundary_decks
from cases import TOL
from check import read_ng, read_spectre, grade, compare
from validate import ROOT, SOURCE, sha
from validate_spectre_r53 import admit, selection_verdict

CHECKERS = ("alias_cases.py", "alias_reference.py", "validate_aliases.py", "calibrate_aliases.py",
            "validate_spectre_aliases.py", "check.py", "r53_reference.py", "rollback.py",
            "boundary.py", "cases.py", "reference.py", "validate_spectre_r53.py")


def prepare(phase, local, nearzero):
    phase, local, nearzero = map(lambda p: Path(p).resolve(), (phase, local, nearzero))
    batch = phase / "batch01"
    batch.mkdir(exist_ok=False)
    protocol = {"fixed_denominator": 6, "cases": {}, "micro_budgets": BUDGETS,
                "nearzero_budgets": TOL, "availability": "local-only",
                "source_policy": "Unchanged prior alias sources and original nearzero fixture; direct expression is a labelled control, never a substitute for an alias failure.",
                "checker_sha256": {n: sha(Path(__file__).parent / n) for n in CHECKERS}}
    for case in (*CASES, "nearzero"):
        d = batch / "spectre" / case
        src = local / "spectre" / case if case != "nearzero" else nearzero / "spectre/near_zero-refined"
        shutil.copytree(src, d)
        if case == "nearzero":
            if (d / "tb.scs").read_text() != boundary_decks()[1] or (d / "sample_hold.va").read_bytes() != SOURCE.read_bytes():
                raise ValueError("original nearzero input differs")
            cfg = {"case": case, "cfg": CFG, "profile": PROFILE, "stop": 1.6e-6}
            (d / "contract.json").write_text(json.dumps(cfg, indent=2) + "\n")
        files = {f.name: sha(f) for f in d.iterdir() if f.is_file() and f.name != "preparation.json"}
        protocol["cases"][case] = {"sources": sorted(f.name for f in d.glob("*.va")), "files": files,
            "ng_directory": str(nearzero / "ngspice/near_zero-refined" if case == "nearzero" else local / (case + "-normal")),
            "expected_json": str(nearzero / "expected.json") if case == "nearzero" else None}
    shutil.copy2(Path(__file__).parent / "run_spectre_remote.py", batch / "runner.py")
    manifest = {str(f.relative_to(batch)): sha(f) for f in (batch / "spectre").rglob("*") if f.is_file()}
    (batch / "input-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    freeze_local_evidence(protocol)
    (phase / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    return protocol


def freeze_local_evidence(protocol):
    for spec in protocol["cases"].values():
        d = Path(spec["ng_directory"])
        names = ("wave.raw", "result.json") if spec["expected_json"] else ("wave.raw", "analysis.json", "execution.json")
        spec["ng_files"] = {n: sha(d / n) for n in names}
        if spec["expected_json"]:
            spec["expected_sha256"] = sha(Path(spec["expected_json"]))


def analyze(phase, output, cases, protocol_path=None):
    phase, output = map(lambda p: Path(p).resolve(), (phase, output))
    output.mkdir(exist_ok=False)
    protocol_path = Path(protocol_path).resolve() if protocol_path else phase / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, identity in protocol["checker_sha256"].items():
        if sha(Path(__file__).parent / name) != identity:
            raise ValueError("frozen P0 checker differs: " + name)
    results = {}
    for case in cases:
        spec = protocol["cases"][case]
        d = phase / "batch01/spectre" / case
        try:
            identity = admit(d, spec)
            if sha(d / "contract.json") != spec["files"]["contract.json"]:
                raise ValueError("contract differs")
            native = read_spectre(d / "psf/tran.tran.tran")
            ngdir = Path(spec["ng_directory"])
            for name, identity_hash in spec.get("ng_files", {}).items():
                if sha(ngdir / name) != identity_hash:
                    raise ValueError("frozen ng evidence differs: " + name)
            ng = read_ng(ngdir / "wave.raw")
            if case == "nearzero":
                if spec.get("expected_sha256") != sha(Path(spec["expected_json"])):
                    raise ValueError("frozen nearzero expected answer differs or is not identified")
                answer = json.loads(Path(spec["expected_json"]).read_text())
                physical = grade(native, answer, CFG)
                local = grade(ng, answer, CFG)
                paired = compare(ng, native)
                result = {"passed": physical["passed"] and local["passed"] and paired["passed"],
                          "physical": physical, "ng_physical": local, "continuous_pair": paired,
                          "contract": "original nearzero50ps/20uV, unchanged source/deck/checker"}
            else:
                cfg = json.loads((d / "contract.json").read_text())
                if (ngdir / "contract.json").read_bytes() != (d / "contract.json").read_bytes():
                    raise ValueError("native and ng independent contract differs")
                local = json.loads((ngdir / "analysis.json").read_text())
                if local["passed"] is not True:
                    raise ValueError("selected ng run did not pass")
                local_physical = score_wave(ng, cfg)
                physical = score_wave(native, cfg)
                states = {i: native_state(native, i, s, cfg["budgets"]) for i, s in cfg["instances"].items()}
                state_pairs = {}
                for inst, state in states.items():
                    a, b = state.get("observed", []), local["states"][inst].get("observed", [])
                    same = len(a) == len(b) == 1
                    dt = abs(a[0][0] - b[0][0]) if same else None
                    dq = abs(a[0][1] - b[0][1]) if same else None
                    state_pairs[inst] = {"passed": same and dt <= BUDGETS["pair_event_s"] and dq <= BUDGETS["pair_platform_V"],
                                         "max_time_s": dt, "max_state_V": dq}
                paired = pair(ng, native, cfg)
                result = {"passed": local_physical["passed"] and physical["passed"] and all(s["passed"] for s in states.values()) and all(s["passed"] for s in state_pairs.values()) and paired["passed"],
                          "physical": physical, "ng_physical": local_physical, "states": states, "state_pairs": state_pairs, "continuous_pair": paired}
            results[case] = {**result, "identity": identity, "ng_wave_sha256": sha(ngdir / "wave.raw")}
        except (OSError, ValueError, KeyError, StopIteration) as exc:
            results[case] = {"passed": False, "admission_or_analysis_error": str(exc)}
        (output / (case + ".json")).write_text(json.dumps(results[case], indent=2, allow_nan=False) + "\n")
        print(case, results[case]["passed"], flush=True)
    equivalence = None
    if "ramp" in results and "direct" in results and all(results[c]["passed"] for c in ("ramp", "direct")):
        cfg = json.loads((phase / "batch01/spectre/ramp/contract.json").read_text())
        equivalence = {}
        for engine in ("ngspice", "spectre"):
            waves = []
            for case in ("ramp", "direct"):
                spec = protocol["cases"][case]
                waves.append(read_ng(Path(spec["ng_directory"]) / "wave.raw") if engine == "ngspice" else read_spectre(phase / "batch01/spectre" / case / "psf/tran.tran.tran"))
            equivalence[engine] = pair(*waves, cfg)
    verdict = selection_verdict(results, cases, protocol)
    if verdict["complete_selection"]:
        verdict["passed"] = verdict["passed"] and equivalence is not None and all(r["passed"] for r in equivalence.values())
    final = {**verdict, "cases": results, "alias_direct_equivalence": equivalence,
             "fixed_denominator": protocol["fixed_denominator"], "analyzed": len(results),
             "protocol_sha256": sha(protocol_path), "new_simulator_runs_in_analysis": 0}
    (output / "analysis.json").write_text(json.dumps(final, indent=2, allow_nan=False) + "\n")
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--local")
    parser.add_argument("--nearzero")
    parser.add_argument("--output")
    parser.add_argument("--protocol", help="Versioned protocol for reanalysis; execution inputs remain frozen")
    parser.add_argument("--cases", default=",".join((*CASES, "nearzero")))
    args = parser.parse_args()
    if args.prepare:
        prepare(args.phase, args.local, args.nearzero)
    else:
        result = analyze(args.phase, args.output, args.cases.split(","), args.protocol)
        raise SystemExit(0 if result["passed"] else 1)
