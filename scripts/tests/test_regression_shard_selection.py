"""The coverage job merges the newest attempt of each regression shard, never an older one that merely sorts later.

download-artifact keeps the artifact with the highest ID when several share a name, and IDs do not follow creation
time (run 40602342818, attempt 3). Every shard upload therefore carries its run attempt in its name, and the
selection step of regression-coverage is run here from the maintained workflow on synthetic artifact directories.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import git_fixture
import test_regression_admission as admission

ROOT = Path(__file__).resolve().parents[2]
STEP = 'Select the newest attempt of each regression shard'
RECEIPT = 'runs/regression-shard-selection.json'
UPLOAD_NAME = 'python-regression-shard-${{ matrix.shard }}-attempt-${{ github.run_attempt }}'


def artifact(shard, attempt):
    return 'python-regression-shard-%d-attempt-%d' % (shard, attempt)


class ShardSelectionTests(unittest.TestCase):
    workflow_job = admission.AdmissionIntegrationTests.workflow_job
    run_body = admission.AdmissionIntegrationTests.run_body

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def put(self, name, reports=('regression-evidence/report.json',), age=0):
        """One downloaded artifact directory; age (seconds) lowers its modification time."""
        for report in reports:
            path = self.root / 'runs/shards' / name / report
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'artifact': name}))
        stamp = 1_700_000_000 - age
        os.utime(self.root / 'runs/shards' / name, (stamp, stamp))

    def put_complete(self, attempts):
        for shard in range(4):
            for attempt in attempts.get(shard, (1,)):
                self.put(artifact(shard, attempt))

    def select(self, run_attempt=3):
        env = git_fixture.child_env(GITHUB_STEP_SUMMARY=str(self.root / 'summary.md'), GITHUB_RUN_ATTEMPT=str(run_attempt))
        result = subprocess.run(['bash', '-e', '-c', self.run_body('regression-coverage', STEP)],
                                cwd=self.root, env=env, capture_output=True, text=True)
        receipt = self.root / RECEIPT
        summary = self.root / 'summary.md'
        return (result, json.loads(receipt.read_text()) if receipt.exists() else None,
                summary.read_text() if summary.exists() else '')

    def refused(self, fragment, run_attempt=3):
        result, receipt, summary = self.select(run_attempt)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIsNotNone(receipt, 'a refused selection still leaves its receipt')
        self.assertFalse(receipt['valid'])
        self.assertEqual(receipt['selected'], [])
        self.assertTrue(any(fragment in error for error in receipt['errors']), receipt['errors'])
        self.assertIn(fragment, result.stderr + summary)

    def test_each_shard_has_one_attempt(self):
        self.put_complete({})
        result, receipt, summary = self.select(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(receipt['valid'])
        self.assertEqual(receipt['run_attempt'], 1)
        self.assertEqual([(item['shard'], item['attempt'], item['artifact']) for item in receipt['selected']],
                         [(shard, 1, artifact(shard, 1)) for shard in range(4)])
        self.assertEqual(receipt['superseded'], [])
        for item in receipt['selected']:
            report = self.root / item['report']
            self.assertEqual(json.loads(report.read_text()), {'artifact': item['artifact']})
            self.assertEqual(item['report_sha256'], hashlib.sha256(report.read_bytes()).hexdigest())
        for shard in range(4):
            self.assertIn(artifact(shard, 1), summary)

    def test_a_rerun_of_one_shard_replaces_only_that_shard(self):
        self.put_complete({2: (1, 2, 3)})
        result, receipt, summary = self.select(3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([(item['shard'], item['attempt']) for item in receipt['selected']], [(0, 1), (1, 1), (2, 3), (3, 1)])
        self.assertEqual(json.loads((self.root / receipt['selected'][2]['report']).read_text()),
                         {'artifact': artifact(2, 3)})
        self.assertEqual([(item['shard'], item['attempt'], item['artifact']) for item in receipt['superseded']],
                         [(2, 1, artifact(2, 1)), (2, 2, artifact(2, 2))])
        self.assertIn(artifact(2, 3), summary)
        self.assertIn(artifact(2, 1), summary)

    def test_attempt_number_decides_not_directory_age_or_name_order(self):
        # The newest attempt is neither the last created nor the last in name order, and 10 sorts before 9 as text.
        for attempt, age in ((9, 0), (10, 3600), (2, -3600), (3, 7200)):
            self.put(artifact(1, attempt), age=age)
        self.put(artifact(0, 1))
        self.put(artifact(2, 1))
        self.put(artifact(3, 1))
        result, receipt, _summary = self.select(10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([(item['shard'], item['attempt']) for item in receipt['selected']], [(0, 1), (1, 10), (2, 1), (3, 1)])
        self.assertEqual([item['attempt'] for item in receipt['superseded']], [2, 3, 9])

    def test_a_missing_shard_fails(self):
        for shard in range(3):
            self.put(artifact(shard, 1))
        self.refused('shard 3')
        self.refused('shard 3')  # a second run overwrites the receipt rather than appending

    def test_a_shard_without_any_valid_name_is_missing(self):
        for shard in range(3):
            self.put(artifact(shard, 1))
        self.put('python-regression-shard-3')
        self.refused('shard 3')

    def test_illegal_artifact_names_fail_even_beside_a_complete_set(self):
        for name in ('python-regression-shard-3', 'python-regression-shard-4-attempt-1', 'python-regression-shard--1-attempt-1',
                     'python-regression-shard-1-attempt-0', 'python-regression-shard-1-attempt-01',
                     'python-regression-shard-1-attempt-x', 'python-regression-shard-1-attempt-2-extra',
                     'python-regression-shard-01-attempt-1', 'Python-Regression-Shard-1-attempt-9',
                     'python-regression-shard-1-attempt-', 'python-regression-shard-1-attempt-٢',
                     'python-regression-shard-10-attempt-1', 'python-regression-shard-1_attempt-1'):
            with self.subTest(name=name):
                self.setUp()
                self.put_complete({})
                self.put(name)
                self.refused(name)

    def test_a_loose_file_among_the_artifacts_fails(self):
        self.put_complete({})
        (self.root / 'runs/shards/stray.json').write_text('{}')
        self.refused('stray.json')

    def test_a_legally_named_symlink_or_plain_file_is_not_an_artifact(self):
        self.put_complete({})
        elsewhere = self.root / 'elsewhere/regression-evidence/report.json'
        elsewhere.parent.mkdir(parents=True)
        elsewhere.write_text('{}')
        (self.root / 'runs/shards' / artifact(2, 2)).symlink_to(self.root / 'elsewhere', target_is_directory=True)
        self.refused(artifact(2, 2))
        (self.root / 'runs/shards' / artifact(2, 2)).unlink()
        (self.root / 'runs/shards' / artifact(3, 2)).write_text('{}')
        self.refused(artifact(3, 2))

    def test_two_reports_in_one_artifact_fail(self):
        self.put_complete({})
        self.put(artifact(1, 1), reports=('regression-evidence/report.json', 'copy/regression-evidence/report.json'))
        self.refused(artifact(1, 1))

    def test_an_artifact_without_a_report_fails(self):
        self.put_complete({})
        self.put(artifact(3, 2), reports=('regression-identity.json',))
        self.refused(artifact(3, 2))

    def test_an_attempt_newer_than_this_run_fails(self):
        self.put_complete({2: (1, 5)})
        self.refused(artifact(2, 5), run_attempt=4)

    def test_the_artifact_name_carries_the_attempt_and_nothing_else_names_the_old_one(self):
        regression = self.workflow_job('regression')
        self.assertEqual(re.findall(r'(?m)^          name: (python-regression-shard-.*)$', regression), [UPLOAD_NAME])
        coverage = self.workflow_job('regression-coverage')
        self.assertEqual(re.findall(r'(?m)^          pattern: (.*)$', coverage), ['python-regression-shard-*'])
        self.assertNotIn('merge-multiple', coverage)
        self.assertIn('runs/regression-shard-selection.json', coverage.split('name: python-regression-timings')[1])
        # Spellings the attempt-less name cannot hide in: the pattern, the upload name, the step's own regex and fixtures.
        attempt_less = re.compile(r'python-regression-shard-(?!\*|\$\{\{ matrix\.shard \}\}-attempt-\$\{\{ github\.run_attempt \}\}'
                                  r'|\(\[0-3\]\)-attempt-|%d-attempt-|[0-3]-attempt-)')
        users = []
        for base in ('.github', 'scripts'):
            for path in sorted((ROOT / base).rglob('*')):
                if path.is_file() and path.suffix in ('.yml', '.yaml', '.py', '.sh', '.md', '.json') and path != Path(__file__):
                    if attempt_less.search(path.read_text()):
                        users.append(str(path.relative_to(ROOT)))
        self.assertEqual(users, [])


if __name__ == '__main__':
    unittest.main()
