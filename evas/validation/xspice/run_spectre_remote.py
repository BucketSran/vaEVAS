"""Run frozen multi-source references on an existing licensed Linux host."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import signal
import subprocess
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, cases, profile_path, lock_path, timeout):
    root = Path(root).resolve()
    lock = Path(lock_path).open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    profile = json.loads(Path(profile_path).read_text())
    binary = Path(profile["spectre"])
    cpu = min(os.sched_getaffinity(0))
    identity = {"spectre": str(binary), "spectre_sha256": sha(binary),
                "setup_sha256": {p: sha(Path(p)) for p in profile["setup_scripts"]},
                "runner_sha256": sha(Path(__file__)), "host": os.uname().nodename,
                "cpu": cpu, "omp_num_threads": 1}
    tool = root / "TOOL_IDENTITY.json"
    if tool.exists():
        if json.loads(tool.read_text()) != identity:
            raise ValueError("tool identity changed between batch invocations")
    else:
        tool.write_text(json.dumps(identity, indent=2) + "\n")
    manifest = json.loads((root / "input-manifest.json").read_text())
    for case in cases:
        if not case.isalnum():
            raise ValueError("invalid case name")
        d = root / "spectre" / case
        sources = sorted(d.glob("*.va"))
        if not sources or (d / "STARTED.json").exists():
            raise ValueError("missing sources or execution already started: " + case)
        inputs = {p.name: sha(p) for p in [d / "tb.scs", *sources]}
        if any(manifest[str((d / name).relative_to(root))] != value for name, value in inputs.items()):
            raise ValueError("input identity mismatch: " + case)
        (d / "STARTED.json").write_text(json.dumps({
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": inputs, "netlist_sha256": inputs["tb.scs"],
            "va_sha256": {p.name: inputs[p.name] for p in sources}}, indent=2) + "\n")
        setup = "".join("source " + shlex.quote(p) + "\n" for p in profile["setup_scripts"])
        command = [str(binary), "-64", "tb.scs", "+log", "spectre.log", "-format", "psfascii",
                   "-raw", "psf", "+lqtimeout", "20", "+mt=1"]
        (d / "run.csh").write_text(setup + shlex.join(command) + "\nexit $status\n")
        wrapper = ["taskset", "-c", str(cpu), "/bin/csh", "-f", "run.csh"]
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        timed_out = False
        with (d / "stdout.log").open("x") as stream:
            process = subprocess.Popen(wrapper, cwd=d, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True, env=dict(os.environ, OMP_NUM_THREADS="1"))
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    code = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        result = {"exit_code": code, "timed_out": timed_out, "wall_s": time.monotonic() - start,
                  "user_s": after.ru_utime - before.ru_utime, "system_s": after.ru_stime - before.ru_stime,
                  "timeout_s": timeout, "command": wrapper, "spectre_command": command}
        (d / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(case, json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("cases", nargs="+")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--lock", required=True)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    run(args.root, args.cases, args.profile, args.lock, args.timeout)
