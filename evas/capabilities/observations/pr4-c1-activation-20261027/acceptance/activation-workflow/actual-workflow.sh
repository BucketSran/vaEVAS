mkdir -p runs
python3 -I - <<'PYTHON'
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

# Fill only after the inactive bootstrap has actually merged to reviewed main.
BOOTSTRAP_COMMIT = "72f1c2e4c22d8a2f743da8ec23101d022a3096d5"
BOOTSTRAP_SHA256 = "30cb19e469db4ea26b00ca4959e68c4aa1196be15a9051452ff491210619aa63"
BOOTSTRAP_PATH = "scripts/run_trusted_regression_gate.py"
repo = Path.cwd().resolve()
report = repo / "runs/python-regression.json"
admission = repo / "runs/regression-admission.json"
source_path = repo / "runs/regression-bootstrap-source.json"
bundle_source_path = repo / "runs/regression-bundle-source.json"
bundle_source_path.write_text(json.dumps(dict(schema_version=1, requested=False,
                                             materialized=False)) + "\n")
source = dict(schema_version=1, source="fixed-reviewed-main-commit",
              bootstrap_commit=BOOTSTRAP_COMMIT, bootstrap_path=BOOTSTRAP_PATH,
              expected_loader_sha256=BOOTSTRAP_SHA256, loaded=False, execution_cwd="isolated-temporary-directory")
status = 2

# Only the verified loader selects authority. Resolve the bundle lazily:
# compare_from_commit asks for its path only after the ordinary C0 gate.
consumer = '''
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

loader, repo, report_path, receipt = map(Path, sys.argv[1:])
facts = dict(schema_version=1, requested=False, materialized=False)
report = None
status = 2
try:
    api = runpy.run_path(str(loader))
    report = json.loads(report_path.read_text())
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    commit, source = api["select_trusted_commit"](repo, os.environ["GITHUB_EVENT_NAME"], event)
    facts["trusted_commit"] = commit

    class RegistrationBundle:
        def __fspath__(self):
            if not facts["materialized"]:
                facts["requested"] = True
                pointer_path = "scripts/context-registration-bundle.json"
                helper_path = "scripts/materialize_registration_bundle.py"
                pointer = api["_blob"](repo, commit, pointer_path)
                helper = api["_blob"](repo, commit, helper_path)
                facts.update(pointer_path=pointer_path, helper_path=helper_path,
                             pointer_sha256=hashlib.sha256(pointer).hexdigest(),
                             helper_sha256=hashlib.sha256(helper).hexdigest())
                manifest = loader.parent / "bundle-pointer.json"
                script = loader.parent / "materialize.py"
                manifest.write_bytes(pointer)
                script.write_bytes(helper)
                process = subprocess.run([sys.executable, "-I", str(script), "--repo", str(repo),
                                          "--manifest", str(manifest), "--output", str(bundle)],
                                         cwd=loader.parent, capture_output=True)
                if process.returncode:
                    raise ValueError("trusted bundle materializer failed: " +
                                     process.stdout.decode(errors="replace") +
                                     process.stderr.decode(errors="replace"))
                inventory = json.loads(process.stdout)
                if not isinstance(inventory, dict) or inventory.get("materialized") is not True:
                    raise ValueError("trusted materializer returned no inventory")
                facts.update(materialized=True, inventory=inventory)
            return str(bundle)

    bundle = loader.parent / "registration-bundle"
    result = api["compare_from_commit"](repo, commit, report, RegistrationBundle())
    result["trust"].update(source=source, default_branch="main")
    status = 0 if result["merge_allowed"] else 1
except (OSError, ValueError, TypeError, KeyError, SyntaxError) as error:
    facts["error"] = str(error)
    result = dict(merge_allowed=False,
                  raw_successful=report.get("successful") if isinstance(report, dict) else None,
                  error=str(error))
finally:
    receipt.write_text(json.dumps(facts, indent=2) + "\\n")
print(json.dumps(result, indent=2, allow_nan=False))
raise SystemExit(status)
'''

def git(*args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip())
    return result.stdout

try:
    if (not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", BOOTSTRAP_COMMIT)
            or set(BOOTSTRAP_COMMIT) == {"0"}):
        raise ValueError("a fixed full reviewed bootstrap commit is required")
    resolved = git("rev-parse", "--verify", BOOTSTRAP_COMMIT + "^{commit}").decode().strip()
    if resolved != BOOTSTRAP_COMMIT:
        raise ValueError("bootstrap pin must name an exact commit")
    entries = [item for item in git("ls-tree", "-z", BOOTSTRAP_COMMIT, "--", BOOTSTRAP_PATH).split(b"\0") if item]
    if len(entries) != 1:
        raise ValueError("fixed bootstrap source is missing")
    metadata, name = entries[0].split(b"\t", 1)
    mode, kind, blob = metadata.decode().split()
    if mode not in ("100644", "100755") or kind != "blob" or name.decode() != BOOTSTRAP_PATH:
        raise ValueError("fixed bootstrap source must be a regular Git blob")
    content = git("show", BOOTSTRAP_COMMIT + ":" + BOOTSTRAP_PATH)
    if not content.strip():
        raise ValueError("fixed bootstrap source is empty")
    observed = hashlib.sha256(content).hexdigest()
    source.update(bootstrap_blob=blob, bootstrap_mode=mode, loader_sha256=observed)
    if not re.fullmatch(r"[0-9a-f]{64}", BOOTSTRAP_SHA256) or observed != BOOTSTRAP_SHA256:
        raise ValueError("fixed bootstrap SHA256 mismatch")
    tree = ast.parse(content, filename=BOOTSTRAP_PATH)
    functions = {item.name for item in tree.body if isinstance(item, ast.FunctionDef)}
    if not {"main", "select_trusted_commit", "evaluate_event", "compare_from_commit"} <= functions:
        raise ValueError("fixed bootstrap source lacks its public entry structure")
    source["loaded"] = True
    with tempfile.TemporaryDirectory(prefix="regression-bootstrap-") as directory:
        isolated = Path(directory)
        loader = isolated / "trusted-loader.py"
        loader.write_bytes(content)
        process = subprocess.run([sys.executable, "-I", "-c", consumer, str(loader), str(repo),
                                  str(report), str(bundle_source_path)], cwd=isolated,
                                 capture_output=True)
    if process.stderr:
        sys.stderr.buffer.write(process.stderr)
    result = json.loads(process.stdout)
    if (not isinstance(result, dict) or type(result.get("merge_allowed")) is not bool
            or (process.returncode == 0) != result["merge_allowed"]):
        raise ValueError("trusted bootstrap exit/result mismatch")
    admission.write_bytes(process.stdout)
    source["bootstrap_exit"] = process.returncode
    trust = result.get("trust")
    if isinstance(trust, dict):
        source["event_trusted_commit"] = trust.get("trusted_commit")
        source["event_trust_source"] = trust.get("source")
    status = process.returncode
except (OSError, ValueError, TypeError, KeyError, SyntaxError) as error:
    source["error"] = str(error)
    admission.write_text(json.dumps(dict(merge_allowed=False, raw_successful=None,
                                        bootstrap_error=str(error)), indent=2) + "\n")
finally:
    source_path.write_text(json.dumps(source, indent=2) + "\n")
    print(json.dumps(source))
raise SystemExit(status)
PYTHON
