"""Check packaged audit evidence, without importing or running either EVAS."""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent


def read_json(name):
    return json.loads((ROOT / "evidence" / name).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = read_json("artifact-manifest.json")
    for name, expected in manifest.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        require(actual == expected, f"asset hash mismatch: {name}")

    primary = read_json("python-probes.json")["records"]
    frontend = read_json("frontend-waveform-probes.json")
    kernels = [json.loads(line) for line in (ROOT / "evidence/rust-probes.jsonl").read_text().splitlines()]
    rows = primary + frontend + kernels
    require((len(primary), len(frontend), len(kernels)) == (35, 8, 4), "probe group count changed")
    require(len({row["id"] for row in rows}) == 47, "duplicate or missing probe ID")
    by_id = {row["id"]: row for row in primary}
    production_prefixes = {
        "D07", "D08", "D09", "D10", "D11", "D12",
        "L01", "L02", "L03", "L04", "L08", "L09",
        "C01", "C02", "C03", "H02",
    }
    production = [row for row in primary if row["id"].split("_")[0] in production_prefixes]
    require(len(production) == 16, "full-model request count changed")
    require(sum(row["probe_status"] == "completed" for row in production) == 12, "completion count changed")
    rejected = {row["id"].split("_")[0] for row in production if row["probe_status"] == "exception"}
    require(rejected == {"D12", "L03", "L09", "H02"}, "rejection identities changed")

    oracles = {
        "D07_idt_constant": lambda t: .25 + t,
        "D08_idt_ramp": lambda t: .25 + t * t / 2,
        "D09_idtmod_wrap": lambda t: (.125 + 1.5 * t) % 1,
        "D10_idtmod_omitted_modulus": lambda t: 1.5 * t,
        "D11_two_calls_same_target": lambda t: 2 * t,
        "L01_single_nd_ramp_h4": lambda t: t - 1 + math.exp(-t),
        "L02_single_nd_ramp_h8": lambda t: t - 1 + math.exp(-t),
        "L04_differential_assignment": lambda t: t - 1 + math.exp(-t),
        "C01_contribution_order_ab": lambda t: 3.,
        "C02_contribution_order_ba": lambda t: 3.,
        "C03_implicit": lambda t: 2.,
    }
    summary = read_json("summary.json")
    require(set(summary["metrics"]) == set(oracles), "metric identities changed")
    for name, oracle in oracles.items():
        observation = by_id[name]["observation"]
        times, values = observation["time"], observation["y"]
        require(len(times) == len(values) > 0, f"invalid observations: {name}")
        metrics = {
            "samples": len(times),
            "max_abs_error": max(abs(y - oracle(t)) for t, y in zip(times, values)),
            "final_actual": values[-1],
            "final_expected": oracle(times[-1]),
        }
        for key, value in metrics.items():
            # Comparison tolerance is for re-evaluating the published scalar
            # metrics across libm versions, not a DUT acceptance threshold.
            require(math.isclose(value, summary["metrics"][name][key], rel_tol=1e-14, abs_tol=1e-15), f"metric mismatch: {name}/{key}")

    provenance = read_json("provenance.json")
    for name in ("probe_legacy.py", "probe_frontend_waveforms.py", "probe_kernels.rs"):
        require(manifest[f"probes/{name}"] == provenance["original_artifact_sha256"][name], f"runner changed: {name}")
    print(f"Verified {len(manifest)} asset hashes, 47 unique observations, 16 full-model requests (12 returned / 4 rejected), and 11 analytic summaries. Not a simulator pass count.")


if __name__ == "__main__":
    main()
