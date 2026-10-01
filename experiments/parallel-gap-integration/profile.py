"""Alternate two archived release test binaries on the same frozen requests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def profile(baseline, candidate, inputs, root, rounds):
    if rounds < 2:
        raise ValueError("use at least two alternating rounds")
    root.mkdir(parents=True, exist_ok=False)
    binaries = dict(baseline=baseline.resolve(), candidate=candidate.resolve())
    cases = json.loads(inputs.read_text())
    identity = dict(
        binary_sha256={k: sha(v) for k, v in binaries.items()},
        input_manifest_sha256=sha(inputs),
        input_sha256={c["name"]: sha(Path(c["path"])) for c in cases},
        rounds=rounds, repeats_per_process=5,
        command=["BINARY", "profile_accuracy_components", "--ignored", "--nocapture",
                 "--test-threads=1"],
        timing_scope="in-process kernel; excludes parsing, request cloning, serialization and process launch",
        availability="raw logs and binaries local-only",
    )
    save(root / "IDENTITY.json", identity)
    records, responses = [], {}
    env = dict(os.environ, EVAS_PROFILE_INPUTS=str(inputs.resolve()))
    for round_index in range(rounds):
        order = ["baseline", "candidate"] if round_index % 2 == 0 else ["candidate", "baseline"]
        for version in order:
            log = root / f"round-{round_index}-{version}.log"
            with log.open("x") as handle:
                subprocess.run([str(binaries[version]), *identity["command"][1:]],
                               env=env, stdout=handle, stderr=subprocess.STDOUT, check=True)
            parsed = [json.loads(line.split("EVAS_PROFILE ", 1)[1])
                      for line in log.read_text().splitlines() if "EVAS_PROFILE " in line]
            expected = {(c["name"], repeat) for c in cases for repeat in range(5)}
            if len(parsed) != len(expected) or {(r["case"], r["repeat"]) for r in parsed} != expected:
                raise ValueError("profile records missing or duplicated")
            for record in parsed:
                response = record.pop("response")
                digest = hashlib.sha256(json.dumps(response, sort_keys=True).encode()).hexdigest()
                case = record["case"]
                if case in responses and digest != responses[case]:
                    raise ValueError("full response changed: " + case)
                responses[case] = digest
                records.append(dict(version=version, round=round_index,
                                    response_sha256=digest, **record))
            print(round_index, version, "complete; responses identical", flush=True)
    if sha(inputs) != identity["input_manifest_sha256"] or any(
        sha(v) != identity["binary_sha256"][k] for k, v in binaries.items()
    ) or any(sha(Path(c["path"])) != identity["input_sha256"][c["name"]] for c in cases):
        raise ValueError("profile inputs or binaries changed during measurement")
    summaries = {}
    for case in responses:
        stages = {}
        for stage in next(r["stages_s"] for r in records if r["case"] == case):
            samples = {v: [r["stages_s"][stage] for r in records
                           if r["case"] == case and r["version"] == v] for v in binaries}
            medians = {v: statistics.median(values) for v, values in samples.items()}
            stages[stage] = dict(median_s=medians,
                                 range_s={v: [min(a), max(a)] for v, a in samples.items()},
                                 candidate_speedup=medians["baseline"] / medians["candidate"])
        summaries[case] = dict(samples_per_version=rounds * 5, stages=stages,
                               response_sha256=responses[case])
    save(root / "SUMMARY.json", dict(identity=identity, cases=summaries, records=records,
                                     full_responses_identical=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "inputs", "root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=4)
    args = parser.parse_args()
    profile(args.baseline, args.candidate, args.inputs, args.root, args.rounds)
