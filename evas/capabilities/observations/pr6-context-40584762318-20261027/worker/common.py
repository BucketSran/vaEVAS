"""Shared helpers for the PR6 E1 raw intake and bundle scripts (read-only, no scientific execution)."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

D = Path(__file__).resolve().parent
B = D.parents[1]
W = Path("/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night")
GD = Path("/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night")
GIT = "/usr/bin/git"
REAL_HEAD = "168a9d7a4305e7ce21d1577b4ca1dda65beae4ce"
CONFIG_ACCEPTED_BASELINE = "de2b08ef3ba66e96be8b70c87346ff4a96f905e1272934ddd86c218dba501ea8"

HEAD = "fa5556de20de4fecbf9db4e3630cd5d6754b07c2"
TREE = "470ad588ddeb848b7c05d3f23656a96f085f8bfd"
TRUSTED = "4d6ebc71efea35822a28f2861f2b0a2a6db17e59"
TRUSTED_TREE = "33a1a097624a24d46dda3ec289b1d899280d7e18"
MERGE_OBJECT = "253082c49e6b37155becf8ed2e40a899bf99c130"
RUN = 40584762318
OLD_RUN = 40569530278
OLD_HEAD = "5fe590c0c573c7296b30f38245f769ff2f71ab8a"
REPO = "BucketSran/vaEVAS"
REPO_URL = "https://github.com/" + REPO
RUN_URL = REPO_URL + "/actions/runs/" + str(RUN)
OLD_RUN_URL = REPO_URL + "/actions/runs/" + str(OLD_RUN)
R7 = B / "pr6/rebind-r7-20261027"
C = R7 / "ci-40584762318"
S = R7 / "source"
PRE = B / "pr6/e1-precheck-20261027"
CROSS_REPORT = B / ("pr6/runner-image-tolerance-20261027/r2/ci-40507402194/attempt-1/artifacts/"
                    "python-regression-timings/python-regression.json")
BASELINE_PATH = "evas/validation/baselines/regression-v1.json"
PROXY = "http://127.0.0.1:12639"


def env():
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k not in ("ALL_PROXY", "all_proxy")}
    e["HTTPS_PROXY"] = e["https_proxy"] = e["HTTP_PROXY"] = e["http_proxy"] = PROXY
    e["GIT_OPTIONAL_LOCKS"] = "0"
    e["GIT_TERMINAL_PROMPT"] = "0"
    return e


ENV = env()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h, n = hashlib.sha256(), 0
    with open(path, "rb") as s:
        for block in iter(lambda: s.read(1 << 20), b""):
            h.update(block)
            n += len(block)
    return h.hexdigest(), n


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def git(*argv, text=False, check=True):
    r = subprocess.run([GIT, "--no-lazy-fetch", "--git-dir=" + str(GD), "--work-tree=" + str(W), *argv],
                       env=ENV, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if not check:
        return r
    return r.stdout.decode() if text else r.stdout


def object_type(rev):
    r = git("cat-file", "-t", rev, check=False)
    return r.stdout.decode().strip() if r.returncode == 0 else None


def safe_new_directory(argument, base=D):
    """Absolute, not-yet-existing plain directory path strictly inside D (no symlink, no traversal, no existing path)."""
    path = Path(os.path.abspath(Path(argument) if Path(argument).is_absolute() else base / argument))
    if D not in path.parents:
        raise SystemExit("refusing output outside " + str(D))
    if os.path.lexists(path):
        raise SystemExit("refusing existing path (directory, file or symlink): " + str(path))
    walk = D
    for part in path.relative_to(D).parts[:-1]:
        walk = walk / part
        if walk.is_symlink() or not walk.is_dir():
            raise SystemExit("refusing symlink or missing parent: " + str(walk))
    return path


def existing_plain_directory(argument):
    p = Path(os.path.abspath(Path(argument) if Path(argument).is_absolute() else D / argument))
    if D not in p.parents or p.is_symlink() or not p.is_dir():
        raise SystemExit("not a plain directory inside " + str(D))
    return p


def candidate_rows():
    plan = load(B / "main-plan.json")
    rows = [dict(path=x["path"], sha256=x["sha256"]) for x in plan["handoff"]["files"] if x["path"].startswith("evas/tests/")]
    assert len(rows) == 20, len(rows)
    return rows


def guard():
    """Real-workspace guard: HEAD, index/config/packed-refs hashes, status, 20 old-candidate file hashes."""
    head = git("rev-parse", "HEAD", text=True).strip()
    status = git("status", "--porcelain=v1", "-uall", text=True)
    state = {}
    for p in (GD / "HEAD", GD / "index", GD.parents[1] / "config", GD.parents[1] / "packed-refs"):
        if p.is_file():
            state[str(p)] = sha_file(p)[0]
    files = {}
    for row in candidate_rows():
        files[row["path"]] = sha((W / row["path"]).read_bytes())
    return dict(head=head, head_expected=REAL_HEAD, head_ok=head == REAL_HEAD, status_porcelain=status,
                git_state_sha256=state, candidate_sha256=files,
                candidates_match_main_plan=all(files[r["path"]] == r["sha256"] for r in candidate_rows()),
                config_sha256=state.get(str(GD.parents[1] / "config")),
                config_equals_accepted_baseline=state.get(str(GD.parents[1] / "config")) == CONFIG_ACCEPTED_BASELINE)
