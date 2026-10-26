"""Execute a regression comparator and baseline from one event-selected commit.

Run this bootstrap from trusted workflow code. PR checkouts supply observations
and an untrusted HEAD baseline proposal. The event-selected commit supplies the
comparator, transition API and authority baseline.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CODE_PATH = 'scripts/regression_gate.py'
BASELINE_PATH = 'evas/validation/baselines/regression-v1.json'
_WORKER = '''import json, runpy, sys
module = runpy.run_path(sys.argv[1], run_name="trusted_regression_gate")
for name in ("compare_report", "validate_report", "validate_baseline_transition"):
    if not callable(module.get(name)):
        raise ValueError("trusted comparator API is missing: " + name)
with open(sys.argv[2]) as stream:
    report = json.load(stream)
with open(sys.argv[3]) as stream:
    baseline = json.load(stream)
if sys.argv[4] == "compare":
    comparison = module["compare_report"](report, baseline)
    result = {"comparison": comparison}
    if not comparison["merge_allowed"]:
        result["result"] = module["validate_baseline_transition"](report, baseline, None)
else:
    with open(sys.argv[5]) as stream:
        proposal = json.load(stream)
    result = module["validate_baseline_transition"](report, baseline, proposal)
print(json.dumps(result, allow_nan=False))
'''


def _git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError('trusted Git operation failed: ' + result.stderr.decode(errors='replace').strip())
    return result.stdout


def _full_commit(repo, value):
    if (not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', value)
            or set(value) == {'0'}):
        raise ValueError('trust source must contain a full nonzero hexadecimal commit ID')
    actual = _git(repo, 'rev-parse', '--verify', value + '^{commit}').decode().strip()
    if actual != value:
        raise ValueError('trust source does not identify an available exact commit')
    return value


def select_trusted_commit(repo, event_name, event, default_branch='main'):
    """Use event authority or a fresh default-branch fetch, never HEAD/inputs.base."""
    if not isinstance(event, dict):
        raise ValueError('CI event must be an object')
    if not isinstance(default_branch, str) or not default_branch:
        raise ValueError('configured default branch is empty')
    _git(repo, 'check-ref-format', 'refs/heads/' + default_branch)
    repository = event['repository']['full_name']
    if not isinstance(repository, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('event repository identity is missing or malformed')
    if event_name == 'pull_request':
        base = event['pull_request']['base']
        if base['ref'] != default_branch:
            raise ValueError('PR base is not the configured default branch')
        if base['repo']['full_name'] != repository:
            raise ValueError('PR base repository differs from event repository')
        return _full_commit(repo, base['sha']), 'event.pull_request.base.sha'
    if event_name == 'push':
        if event['ref'] != 'refs/heads/' + default_branch:
            raise ValueError('push is not to the configured default branch')
        return _full_commit(repo, event['before']), 'event.before'
    if event_name in ('schedule', 'workflow_dispatch'):
        # Fetch only the configured source into FETCH_HEAD. Empty refmap
        # avoids changing stale tracking refs and requires no forced updates.
        # A failed fetch never falls back to the previous FETCH_HEAD value.
        _git(repo, 'fetch', '--no-tags', '--refmap=', 'origin',
             'refs/heads/' + default_branch)
        commit = _git(repo, 'rev-parse', '--verify', 'FETCH_HEAD^{commit}').decode().strip()
        return _full_commit(repo, commit), 'fresh-fetch.origin/' + default_branch
    raise ValueError('unsupported CI event')


def _blob(repo, commit, path):
    structure = _git(repo, 'ls-tree', commit, '--', path).decode().strip().split()
    if len(structure) != 4 or structure[0] not in ('100644', '100755') or structure[1] != 'blob':
        raise ValueError('trusted source must be a regular Git blob: ' + path)
    value = _git(repo, 'show', commit + ':' + path)
    if not value.strip():
        raise ValueError('trusted source is empty: ' + path)
    return value


def _checked_result(result, report):
    if (not isinstance(result, dict) or type(result.get('valid')) is not bool
            or type(result.get('merge_allowed')) is not bool
            or result.get('raw_successful') != report.get('successful')
            or (result['merge_allowed'] and not result['valid'])):
        raise ValueError('trusted comparator returned an inconsistent result structure')
    return result


def compare_from_commit(repo, commit, report):
    """Compare first; only then read the fixed HEAD baseline as untrusted data."""
    commit = _full_commit(repo, commit)
    code = _blob(repo, commit, CODE_PATH)
    baseline = _blob(repo, commit, BASELINE_PATH)
    tree = ast.parse(code, filename=CODE_PATH)
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if not {'compare_report', 'validate_report', 'validate_baseline_transition'}.issubset(functions):
        raise ValueError('trusted gate lacks required public comparator/transition structure')
    decoded = json.loads(baseline)
    if (not isinstance(decoded, dict) or type(decoded.get('schema_version')) is not int
            or decoded['schema_version'] != 1 or not isinstance(decoded.get('contexts'), list)
            or not decoded['contexts']):
        raise ValueError('trusted baseline has unsupported or empty structure')
    trust = dict(trusted_commit=commit, code_path=CODE_PATH, baseline_path=BASELINE_PATH,
                 code_sha256=hashlib.sha256(code).hexdigest(),
                 transition_code_sha256=hashlib.sha256(code).hexdigest(),
                 baseline_sha256=hashlib.sha256(baseline).hexdigest(),
                 candidate_baseline=dict(evaluated=False, is_authority=False, path=BASELINE_PATH))
    with tempfile.TemporaryDirectory(prefix='trusted-regression-gate-') as directory:
        root = Path(directory)
        (root / 'gate.py').write_bytes(code)
        (root / 'baseline.json').write_bytes(baseline)
        (root / 'report.json').write_text(json.dumps(report, allow_nan=False))

        def worker(phase):
            process = subprocess.run([sys.executable, '-I', '-c', _WORKER, str(root / 'gate.py'),
                                      str(root / 'report.json'), str(root / 'baseline.json'), phase,
                                      str(root / 'head-proposal.json')],
                                     cwd=root, capture_output=True, text=True)
            if process.returncode:
                raise ValueError('trusted comparator failed: ' + process.stderr.strip())
            return json.loads(process.stdout)

        first = worker('compare')
        comparison = _checked_result(first['comparison'], report)
        if not comparison['merge_allowed']:
            # Preserve the real authority refusal without even resolving HEAD.
            result = _checked_result(first['result'], report)
        else:
            candidate = trust['candidate_baseline']
            candidate['evaluated'] = True
            proposal = None
            try:
                head = _git(repo, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
                candidate['commit'] = _full_commit(repo, head)
                raw = _blob(repo, head, BASELINE_PATH)
                candidate['sha256'] = hashlib.sha256(raw).hexdigest()
                proposal = json.loads(raw)
                candidate['loaded'] = True
            except (ValueError, OSError) as error:
                candidate.update(loaded=False, error=str(error))
            (root / 'head-proposal.json').write_text(json.dumps(proposal, allow_nan=False))
            result = _checked_result(worker('transition'), report)
        if (result.get('trusted_comparison') != comparison
                or not isinstance(result.get('transition'), dict)
                or (result['merge_allowed'] and not result['transition'].get('accepted'))):
            raise ValueError('trusted transition returned inconsistent comparison facts')
    result['trust'] = trust
    return result


def evaluate_event(repo, report, event_name, event, default_branch='main'):
    """Return the trusted comparator result plus its immutable source facts."""
    commit, source = select_trusted_commit(repo, event_name, event, default_branch)
    result = compare_from_commit(repo, commit, report)
    result['trust']['source'] = source
    result['trust']['default_branch'] = default_branch
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--default-branch', default='main')
    args = parser.parse_args(argv)
    report = None
    try:
        report = json.loads(args.report.read_text())
        if not isinstance(report, dict):
            raise ValueError('report must be an object')
        event_name = os.environ['GITHUB_EVENT_NAME']
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        result = evaluate_event(args.repo, report, event_name, event, args.default_branch)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result['merge_allowed'] else 1
    except (OSError, ValueError, TypeError, KeyError, SyntaxError) as error:
        print(json.dumps(dict(merge_allowed=False,
                              raw_successful=report.get('successful') if isinstance(report, dict) else None,
                              error=str(error)), indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
