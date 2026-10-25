"""Reuse successful regression evidence only for the same complete tracked inputs and tools."""

import argparse
import hashlib
import json
import importlib.util
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys

# File-based importing also supports callers using spec_from_file_location,
# where scripts/ is deliberately absent from sys.path.
try:
    from regression_gate import cacheable_report, validate_report
except ModuleNotFoundError as error:
    if error.name != 'regression_gate':
        raise
    _spec = importlib.util.spec_from_file_location(
        'ci_evidence_regression_gate', Path(__file__).with_name('regression_gate.py'))
    _gate = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_gate)
    cacheable_report, validate_report = _gate.cacheable_report, _gate.validate_report

REPORT_SCHEMA_VERSION = 3
EVIDENCE_SCHEMA_VERSION = 3

# Audited workflow prose and generated registration are checked separately.
# Unknown Markdown remains an input: fixtures may use arbitrary extensions.
EXCLUDED = {
    "evas/docs/development/diagnostic-inventory.json",
    "AGENTS.md", "CONTRIBUTING.md", "docs/contributing/workspaces.md",
    "docs/contributing/evidence.md",
    *('.agents/skills/' + skill + '/SKILL.md' for skill in (
        'evas-develop', 'evas-validate', 'vaevas-workflow',
        'vaevas-prepare-pr', 'vaevas-review-pr',
    )),
}
KERNEL_SELECTORS = (
    'EVAS_BRANCH_KERNEL',
    'EVAS_CAUSAL_KERNEL',
    'EVAS_CERTIFICATE_KERNEL',
    'EVAS_COMPACT_SOURCE_KERNEL',
    'EVAS_DAE_EVENT_KERNEL',
    'EVAS_DC_FACTOR_KERNEL',
    'EVAS_DC_TARGET_KERNEL',
    'EVAS_DEADLINE_KERNEL',
    'EVAS_EVENT_BODY_ALIAS_KERNEL',
    'EVAS_HELD_PROOF_KERNEL',
    'EVAS_HELD_TIME_KERNEL',
    'EVAS_INITIAL_OBSERVER_KERNEL',
    'EVAS_INITIAL_SEED_KERNEL',
    'EVAS_KERNEL',
    'EVAS_PASSIVE_HISTORY_KERNEL',
    'EVAS_PASSIVE_KERNEL',
    'EVAS_RATIONAL_PROBE_KERNEL',
    'EVAS_SOURCE_SLEW_DC_KERNEL',
    'EVAS_SOURCE_SLEW_KERNEL',
    'EVAS_STATISTICS_KERNEL',
    'EVAS_TEST_BASELINE_KERNEL',
    'EVAS_TEST_KERNEL',
    'FORCING_POINT_KERNEL',
    'FORCING_SHAPE_KERNEL',
)
EVIDENCE_OUTPUTS = (
    'EVAS_ORIGINAL079_EVIDENCE_DIR',
    'EVAS_PASSIVE_HISTORY_EVIDENCE',
    'EVAS_RAMP_EVIDENCE_DIR',
    'EVAS_TEST_HISTORY_EVIDENCE_DIR',
    'EVAS_DIAGNOSTICS_PATH',
)
ENVIRONMENT = (
    *KERNEL_SELECTORS,
    *EVIDENCE_OUTPUTS,
    "EVAS_TEST_BASELINE_SHA256", "EVAS_TEST_CANDIDATE_SHA256", "EVAS_TEST_CANDIDATE_ENGINE",
    "EVAS_STATIC_THREADS", "EVAS_DIAGNOSTICS_RECORDS", "EVAS_DIAGNOSTICS_BYTES",
    "EVAS_PROFILE_INPUTS", "PATH",
    "RUSTFLAGS",
    "CARGO_ENCODED_RUSTFLAGS",
    "CARGO_BUILD_TARGET",
    "CARGO_PROFILE_DEV_OPT_LEVEL",
    "CARGO_PROFILE_DEV_DEBUG_ASSERTIONS",
    "CARGO_PROFILE_DEV_OVERFLOW_CHECKS",
    "CC",
    "CXX",
    "AR",
    "LD",
    "PYTHONHASHSEED",
    "PYTHONPATH",
    "ImageOS",
    "ImageVersion",
)


def fingerprint(repo, environment):
    raw = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=repo)
    entries = []
    for row in raw.split(b"\0"):
        if not row:
            continue
        metadata, name = row.split(b"\t", 1)
        mode, _, stage = metadata.decode().split()
        name = os.fsdecode(name)
        if stage != "0" or mode not in ("100644", "100755"):
            raise ValueError("unsupported/conflicted tracked input: " + name)
        if name in EXCLUDED:
            continue
        path = repo / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("tracked input is not a regular file: " + name)
        entries.append(
            [
                name,
                mode,
                stat.S_IMODE(info.st_mode),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ]
        )
    if not entries:
        raise ValueError("no tracked inputs")
    payload = dict(version=EVIDENCE_SCHEMA_VERSION, report_schema_version=REPORT_SCHEMA_VERSION,
                   files=entries, environment=environment)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return dict(
        key=digest,
        report_schema_version=REPORT_SCHEMA_VERSION,
        evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
        input_count=len(entries),
        environment=environment,
        excluded=sorted(EXCLUDED),
    )


def valid_receipt(receipt, identity, shard):
    return (
        isinstance(receipt, dict)
        and receipt.get("report_schema_version") == REPORT_SCHEMA_VERSION
        and receipt.get("evidence_schema_version") == EVIDENCE_SCHEMA_VERSION
        and receipt.get("identity") == identity
        and receipt.get("shard") == shard
        and receipt.get("successful") is True
        and isinstance(receipt.get("report_sha256"), str)
    )


def selected_kernels():
    """Fingerprint the files selected by supported consumer overrides."""
    selected = {}
    for name in KERNEL_SELECTORS:
        if name not in os.environ:
            continue
        # Consumers pass these values directly to Path, including an empty
        # value. A missing/non-file target cannot establish cache provenance.
        path = Path(os.environ[name])
        if not path.is_file():
            raise ValueError(name + ' does not select an available kernel file')
        selected[name] = dict(path=os.environ[name], resolved_path=str(path.resolve()),
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                              mode=stat.S_IMODE(path.stat().st_mode))
    return selected


def environment(repo):
    if 'EVAS_PROFILE_INPUTS' in os.environ:
        raise ValueError('EVAS_PROFILE_INPUTS requires a separate performance-profile execution; regression cache does not support it')
    return dict(
        kernel_overrides=selected_kernels(),
        kernel_mode=stat.S_IMODE((repo / "evas/rust_core/target/debug/evas-kernel").stat().st_mode),
        python=sys.version,
        platform=platform.platform(),
        machine=platform.machine(),
        kernel_sha256=hashlib.sha256(
            (repo / "evas/rust_core/target/debug/evas-kernel").read_bytes()
        ).hexdigest(),
        rustc=subprocess.check_output(["rustc", "+stable", "-vV"], text=True).strip(),
        cargo=subprocess.check_output(
            ["cargo", "+stable", "--version"], text=True
        ).strip(),
        variables={k: os.environ.get(k) for k in ENVIRONMENT},
    )


def bound_report(report, identity, shard):
    """Bind one complete observation scope to its full execution fingerprint."""
    validation = validate_report(report)
    if not validation['valid']:
        raise ValueError('invalid report: ' + '; '.join(validation['errors']))
    if (identity.get('report_schema_version') != REPORT_SCHEMA_VERSION
            or identity.get('evidence_schema_version') != EVIDENCE_SCHEMA_VERSION):
        raise ValueError('obsolete evidence identity format')
    if report.get('merged') is True:
        raise ValueError('cache evidence must describe one original execution scope')
    expected_shard = str(report['shard_index']) + '-of-' + str(report['shard_count'])
    if shard != expected_shard:
        raise ValueError('report shard differs from execution identity')
    source = report.get('source_identity')
    if not isinstance(source, dict) or source.get('execution_identity') != identity:
        raise ValueError('report lacks matching complete execution identity')
    payload = {key: report[key] for key in ('metadata', 'source_identity', 'selected_test_ids')}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if report.get('input_identity') != digest:
        raise ValueError('report input_identity does not bind its actual inputs')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['identity', 'verify', 'record', 'collect'])
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--shard', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--raw-exit', type=int, choices=(0, 1))
    args = parser.parse_args(argv)
    if args.operation != 'identity' and args.report is None:
        parser.error('--report is required for this operation')
    if args.operation in ('record', 'verify') and args.receipt is None:
        parser.error('--receipt is required for this operation')
    if args.operation == 'collect' and args.raw_exit is None:
        parser.error('--raw-exit is required for collect')
    try:
        current = fingerprint(args.repo, dict(**environment(args.repo), shard=args.shard))
        if args.operation == 'identity':
            args.identity.parent.mkdir(parents=True, exist_ok=True)
            args.identity.write_text(json.dumps(current, indent=2) + '\n')
            if args.output:
                with args.output.open('a') as stream:
                    stream.write('key=' + current['key'] + '\n')
            return 0
        identity = json.loads(args.identity.read_text())
        raw_report = args.report.read_bytes()
        report = json.loads(raw_report)
        if current != identity:
            raise ValueError('actual inputs or toolchain changed during execution')
        bound_report(report, identity, args.shard)
        report_hash = hashlib.sha256(raw_report).hexdigest()
        cacheable = cacheable_report(report) and not any(
            current['environment'].get('variables', {}).get(key) is not None for key in EVIDENCE_OUTPUTS)
        if args.operation == 'collect':
            expected_exit = 0 if report['successful'] else 1
            if args.raw_exit != expected_exit:
                raise ValueError('raw exit disagrees with report successful')
            facts = dict(valid=True, raw_successful=report['successful'], raw_exit=args.raw_exit,
                         cacheable=cacheable, report_sha256=report_hash, identity_key=identity['key'],
                         report_schema_version=REPORT_SCHEMA_VERSION,
                         evidence_schema_version=EVIDENCE_SCHEMA_VERSION)
            print(json.dumps(facts, indent=2))
            if args.output:
                args.output.write_text(json.dumps(facts, indent=2) + '\n')
            return 0
        if not cacheable:
            raise ValueError('only complete nonempty actual-pass evidence is cacheable')
        if args.operation == 'verify':
            receipt = json.loads(args.receipt.read_text())
            if not (valid_receipt(receipt, identity, args.shard)
                    and receipt['report_sha256'] == report_hash):
                raise ValueError('receipt does not match report and execution identity')
        else:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(dict(
                identity=identity, shard=args.shard, successful=True,
                report_schema_version=REPORT_SCHEMA_VERSION,
                evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
                report_sha256=report_hash,
                producer_run=os.environ.get('GITHUB_RUN_ID', 'local-unpublished'),
            ), indent=2) + '\n')
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
