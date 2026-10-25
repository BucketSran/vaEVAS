"""Read-only calibration using actual references and altered metadata copies."""

import argparse, json, shutil, tempfile
from pathlib import Path
from cases import CASES, PROFILES, decks
from native_reference import load_reference
from validate import SOURCE

p = argparse.ArgumentParser()
p.add_argument("--reference", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
name = "timer_after-tight"
native = a.reference / "spectre" / name
_, deck = decks(CASES["timer_after"], PROFILES["tight"], Path("unused"))
positive = load_reference(native, SOURCE.read_bytes(), deck)
controls = {}
with tempfile.TemporaryDirectory() as t:
    root = Path(t)
    d = root / "spectre" / name
    d.mkdir(parents=True)
    for f in ("sample_hold.va", "tb.scs", "result.json", "spectre.log", "STARTED.json"):
        shutil.copy2(native / f, d / f)
    shutil.copy2(a.reference / "TOOL_IDENTITY.json", root / "TOOL_IDENTITY.json")
    (d / "psf").mkdir()
    (d / "psf/tran.tran.tran").symlink_to((native / "psf/tran.tran.tran").resolve())
    good = json.loads((d / "result.json").read_text())
    for label, bad in [
        ("failed", dict(good, exit_code=1)),
        ("timed_out", dict(good, timed_out=True)),
    ]:
        (d / "result.json").write_text(json.dumps(bad))
        try:
            load_reference(d, SOURCE.read_bytes(), deck)
            controls[label] = False
        except ValueError:
            controls[label] = True
    (d / "result.json").write_text(json.dumps(good))
    (d / "spectre.log").write_text("unqualified output")
    try:
        load_reference(d, SOURCE.read_bytes(), deck)
        controls["missing_native_completion"] = False
    except ValueError:
        controls["missing_native_completion"] = True
result = {
    "passed": all(controls.values()),
    "actual_reference": positive,
    "rejected_controls": controls,
}
a.output.write_text(json.dumps(result, indent=2) + "\n")
print("reference admission", result["passed"])
raise SystemExit(0 if result["passed"] else 1)
