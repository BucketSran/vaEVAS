"""Exercise workspace visibility and handoff reporting with real temporary Git repos."""
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote


SCRIPT = Path(__file__).resolve().parents[1] / "check_workspaces.py"


class WorkspaceChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project"
        self.primary = self.project / "current"
        self.visible = self.project / "worktrees"
        self.primary.mkdir(parents=True)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_OPTIONAL_LOCKS="0")
        self.git(self.primary, "init", "--initial-branch=main")
        self.git(self.primary, "config", "user.name", "Workspace test")
        self.git(self.primary, "config", "user.email", "workspace@example.invalid")
        (self.primary / "source.txt").write_text("baseline\n")
        (self.primary / ".gitignore").write_text("/runs/\n")
        self.git(self.primary, "add", ".")
        self.git(self.primary, "commit", "-m", "baseline")

    def git(self, directory, *args):
        return subprocess.run(["git", "-C", str(directory), *args], env=self.env,
                              text=True, capture_output=True, check=True).stdout

    def worktree(self, path=None):
        path = path or self.root / "hidden" / "task"
        self.git(self.primary, "worktree", "add", "-b", "task", str(path))
        return path

    def register(self, worktree, name="task", navigate=True):
        self.visible.mkdir(exist_ok=True)
        entry = self.visible / name
        if entry != worktree:
            entry.symlink_to(worktree, target_is_directory=True)
        (self.visible / "README.md").write_text(
            f"# Temporary work\n\n[{name}]({quote(name)}/) — current task; integration pending.\n")
        if navigate:
            (self.project / "README.md").write_text(
                "# Project\n\n[Temporary work](worktrees/README.md)\n")
        return entry

    def run_check(self, repo=None, *args):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo",
                                 str(repo or self.primary), "--json", *args], env=self.env,
                                text=True, capture_output=True)
        self.assertTrue(result.stdout, result.stderr)
        return result, json.loads(result.stdout)

    def test_primary_only_needs_no_registry_and_ignores_archive_copies(self):
        (self.project / "local" / "cleanup-archives" / "old-source").mkdir(parents=True)
        result, report = self.run_check()
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(len(report["worktrees"]), 1)
        self.assertEqual(report["primary"], str(self.primary))

    def test_hidden_worktree_fails_then_visible_navigation_passes_without_mutation(self):
        worktree = self.worktree()
        (worktree / "source.txt").write_text("unfinished work\n")
        before = self.git(worktree, "status", "--porcelain")
        result, report = self.run_check(worktree)
        self.assertEqual(result.returncode, 1)
        self.assertIn("HIDDEN_WORKTREE", [e["code"] for e in report["errors"]])
        self.register(worktree, navigate=False)
        result, report = self.run_check(worktree)
        self.assertEqual(result.returncode, 1)
        self.assertIn("MISSING_NAVIGATION", [e["code"] for e in report["errors"]])
        (self.project / "README.md").write_text("[Temporary work](worktrees/README.md)\n")
        result, report = self.run_check(worktree)
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(report["primary"], str(self.primary))
        self.assertEqual(self.git(worktree, "status", "--porcelain"), before)
        self.assertTrue(report["worktrees"][1]["changes"])
        self.assertEqual(report["worktrees"][1]["visible_entry"], str(self.visible / "task"))

    def test_reports_changes_ignored_material_and_commits_against_named_base(self):
        worktree = self.worktree()
        self.register(worktree)
        (worktree / "source.txt").write_text("new behavior\n")
        self.git(worktree, "commit", "-am", "task change")
        (worktree / "new.txt").write_text("untracked\n")
        (worktree / "runs").mkdir()
        (worktree / "runs" / "evidence.txt").write_text("local evidence\n")
        result, report = self.run_check()
        self.assertEqual(result.returncode, 0, report)
        row = report["worktrees"][1]
        self.assertEqual(row["commits_not_in_base"], 1)
        self.assertIn("new.txt", [c["path"] for c in row["changes"]])
        self.assertIn("runs/", row["ignored"])
        self.assertEqual(report["base"]["ref"], "refs/heads/main")

    def test_visible_directory_still_needs_an_index_entry(self):
        worktree = self.worktree(self.visible / "task")
        result, report = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.register(worktree)
        result, report = self.run_check()
        self.assertEqual(result.returncode, 0, report)

    def test_stale_link_after_retirement_fails(self):
        worktree = self.worktree()
        entry = self.register(worktree)
        self.git(self.primary, "worktree", "remove", str(worktree))
        result, report = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("STALE_ENTRY", [e["code"] for e in report["errors"]])
        self.assertTrue(entry.is_symlink())

    def test_stale_link_without_trailing_slash_or_symlink_fails(self):
        worktree = self.worktree()
        entry = self.register(worktree)
        (self.visible / "README.md").write_text("[Task](task)\n")
        result, report = self.run_check()
        self.assertEqual(result.returncode, 0, report)
        self.git(self.primary, "worktree", "remove", str(worktree))
        entry.unlink()
        result, report = self.run_check()
        self.assertEqual(result.returncode, 1, report)
        self.assertIn("STALE_ENTRY", [e["code"] for e in report["errors"]])

    def test_comments_and_code_do_not_provide_visible_navigation(self):
        worktree = self.worktree()
        self.register(worktree)
        wrappers = [
            "<!-- {} -->\n", "<!--\n{}\n-->\n", "<!-- {}",
            "```md\n{}\n```\n", "~~~markdown\n{}\n~~~\n", "```\n{}\n",
            "`{}`\n", "``{}``\n", "    {}\n", "\t{}\n",
        ]
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper):
                (self.project / "README.md").write_text(
                    wrapper.format("[Temporary work](worktrees/README.md)"))
                (self.visible / "README.md").write_text(wrapper.format("[Task](task/)"))
                result, report = self.run_check()
                self.assertEqual(result.returncode, 1, report)
                codes = [e["code"] for e in report["errors"]]
                self.assertIn("MISSING_NAVIGATION", codes)
                self.assertIn("HIDDEN_WORKTREE", codes)
        (self.project / "README.md").write_text("[Temporary work](worktrees/README.md)\n")
        (self.visible / "README.md").write_text("[Task](task/)\n")
        result, report = self.run_check()
        self.assertEqual(result.returncode, 0, report)

    def test_index_can_link_draft_documents_beside_worktree_entries(self):
        worktree = self.worktree()
        self.register(worktree)
        with (self.visible / "README.md").open("a") as out:
            out.write("\n[Draft](task/source.txt)\n")
        result, report = self.run_check()
        self.assertEqual(result.returncode, 0, report)

    def test_paths_with_spaces_and_unicode_are_supported(self):
        worktree = self.worktree(self.root / "hidden 外" / "task space")
        self.register(worktree, name="task 外 space")
        self.git(worktree, "mv", "source.txt", "renamed 外.txt")
        result, report = self.run_check(worktree)
        self.assertEqual(result.returncode, 0, report)
        row = report["worktrees"][1]
        self.assertEqual(row["changes"][0]["path"], "renamed 外.txt")
        self.assertEqual(row["changes"][0]["original_path"], "source.txt")

    def test_direct_external_link_does_not_replace_visible_project_entry(self):
        worktree = self.worktree()
        self.visible.mkdir()
        (self.visible / "README.md").write_text(f"[Task]({worktree}/)\n")
        (self.project / "README.md").write_text("[Temporary work](worktrees/README.md)\n")
        result, report = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("HIDDEN_WORKTREE", [e["code"] for e in report["errors"]])

    def test_invalid_requested_base_fails(self):
        result, report = self.run_check(None, "--base", "missing-ref")
        self.assertEqual(result.returncode, 2)
        self.assertIn("INSPECTION_FAILED", [e["code"] for e in report["errors"]])

    def test_assets_find_duplicate_local_content_without_changing_assets_or_index(self):
        (self.primary / '.gitignore').write_text('/runs/\n/evas/rust_core/target/\n')
        self.git(self.primary, 'commit', '-am', 'ignore generated assets')
        worktree = self.worktree()
        self.register(worktree)
        for root in (self.primary, worktree):
            (root / 'source.txt').write_text('same local change\n')
            (root / 'new.txt').write_text('same untracked asset\n')
        cache = worktree / 'evas/rust_core/target'
        cache.mkdir(parents=True)
        (cache / 'binary').write_bytes(b'x' * 2048)
        runs = worktree / 'runs'; runs.mkdir()
        (runs / 'evidence').write_bytes(b'y' * 3072)
        index = Path(self.git(worktree, 'rev-parse', '--path-format=absolute', '--git-path', 'index').strip())
        before = index.read_bytes()
        result, report = self.run_check(None, '--assets')
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(index.read_bytes(), before)
        row = report['worktrees'][1]['assets']
        self.assertEqual(row['recommendation']['code'], 'preserve_local_changes')
        self.assertIn('new.txt', [f['path'] for f in row['files']])
        self.assertEqual(row['disk']['build']['logical_bytes'], 2048)
        self.assertEqual(row['disk']['runs']['logical_bytes'], 3072)
        self.assertTrue(row['complete'])
        groups = report['asset_summary']['matching_source_states']
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0]['worktrees']), {str(self.primary), str(worktree)})
        self.assertEqual((runs / 'evidence').read_bytes(), b'y' * 3072)

    def test_assets_keep_staged_changes_even_if_working_file_matches_head(self):
        worktree = self.worktree(); self.register(worktree)
        (worktree / 'source.txt').write_text('staged only\n')
        self.git(worktree, 'add', 'source.txt')
        (worktree / 'source.txt').write_text('baseline\n')
        result, report = self.run_check(None, '--assets')
        self.assertEqual(result.returncode, 0, report)
        row = report['worktrees'][1]['assets']
        self.assertTrue(row['staged_diff_sha256'])
        self.assertEqual(row['recommendation']['code'], 'preserve_local_changes')
        self.assertEqual(report['asset_summary']['matching_source_states'], [])

    def test_assets_mark_patch_equivalence_as_candidate_not_integration(self):
        worktree = self.worktree(); self.register(worktree)
        for root, message in ((worktree, 'worker change'), (self.primary, 'independent main change')):
            (root / 'source.txt').write_text('same change\n')
            self.git(root, 'commit', '-am', message)
        result, report = self.run_check(None, '--assets')
        self.assertEqual(result.returncode, 0, report)
        row = report['worktrees'][1]
        self.assertEqual(row['commits_not_in_base'], 1)
        self.assertTrue(row['assets']['commits'][0]['patch_equivalent_in_base'])
        self.assertEqual(row['assets']['recommendation']['code'], 'review_commits')

    def test_assets_do_not_follow_links_or_count_hardlinks_twice(self):
        worktree = self.worktree(); self.register(worktree)
        runs = worktree / 'runs'; runs.mkdir()
        outside = self.root / 'outside'; outside.mkdir()
        (outside / 'large').write_bytes(b'o' * 16384)
        (runs / 'external').symlink_to(outside, target_is_directory=True)
        (runs / 'one').write_bytes(b'a' * 1024)
        os.link(runs / 'one', runs / 'two')
        result, report = self.run_check(None, '--assets')
        self.assertEqual(result.returncode, 0, report)
        disk = report['worktrees'][1]['assets']['disk']['runs']
        self.assertEqual(disk['symlinks'], 1)
        self.assertEqual(disk['logical_bytes'], 1024 + len(os.fsencode(outside)))
        self.assertEqual(disk['hardlinks_skipped'], 1)

    def test_asset_limits_remain_unknown_and_suppress_exact_duplicate_claims(self):
        worktree = self.worktree(); self.register(worktree)
        for root in (self.primary, worktree):
            (root / 'new.txt').write_text('unhashed data')
        result, report = self.run_check(None, '--assets', '--hash-limit-mib', '0', '--scan-seconds', '0')
        self.assertEqual(result.returncode, 2, report)
        self.assertEqual(report['errors'], [])
        row = report['worktrees'][1]['assets']
        self.assertFalse(row['complete'])
        self.assertIsNone(row['source_state_sha256'])
        self.assertEqual(row['recommendation']['code'], 'inspect_incomplete')
        self.assertFalse(row['disk']['other']['complete'])
        self.assertEqual(report['asset_summary']['matching_source_states'], [])

    def test_git_hidden_changes_cannot_become_matching_or_retirement_candidates(self):
        worktree = self.worktree(); self.register(worktree)
        for flag in ('assume-unchanged', 'skip-worktree'):
            with self.subTest(flag=flag):
                self.git(worktree, 'update-index', '--' + flag, 'source.txt')
                (worktree / 'source.txt').write_text('unique hidden result\n')
                result, report = self.run_check(None, '--assets')
                self.assertEqual(result.returncode, 2, report)
                row = report['worktrees'][1]['assets']
                self.assertEqual(row['index_hidden_paths'], ['source.txt'])
                self.assertIsNone(row['source_state_sha256'])
                self.assertEqual(row['recommendation']['code'], 'inspect_incomplete')
                self.assertEqual(report['asset_summary']['matching_source_states'], [])
                self.git(worktree, 'update-index', '--no-' + flag, 'source.txt')

    def test_directory_replacement_during_scan_never_reads_external_target(self):
        spec = importlib.util.spec_from_file_location('workspace_probe', SCRIPT)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        folder = self.primary / 'switched'; folder.mkdir()
        (folder / 'local').write_bytes(b'l' * 1024)
        outside = self.root / 'outside'; outside.mkdir()
        (outside / 'external').write_bytes(b'e' * 16384)
        inode = folder.stat().st_ino
        original = os.scandir
        switched = False

        def replacing(path):
            nonlocal switched
            target = os.fstat(path).st_ino == inode if isinstance(path, int) else Path(path) == folder
            if target and not switched:
                switched = True
                folder.rename(self.primary / 'retained')
                folder.symlink_to(outside, target_is_directory=True)
            return original(path)

        with patch.object(module.os, 'scandir', side_effect=replacing) as mocked:
            with patch.object(module.os, 'supports_fd', os.supports_fd | {mocked}):
                result = module.disk_usage(self.primary, 5)
        self.assertTrue(switched)
        self.assertFalse(result['complete'])
        self.assertLess(result['logical_bytes'], 16384)

    def test_absent_hidden_paths_do_not_flood_overlap_but_real_deletions_remain(self):
        worktree = self.worktree(); self.register(worktree)
        for root in (self.primary, worktree):
            self.git(root, 'update-index', '--skip-worktree', 'source.txt')
            (root / 'source.txt').unlink()
            (root / '.gitignore').unlink()
        result, report = self.run_check(None, '--assets')
        self.assertEqual(result.returncode, 2, report)
        for row in report['worktrees']:
            assets = row['assets']
            self.assertEqual(assets['index_hidden_paths'], [])
            self.assertEqual(assets['index_hidden_path_count'], 1)
            self.assertEqual(assets['index_hidden_missing_count'], 1)
            self.assertEqual([f['path'] for f in assets['files']], ['.gitignore'])
            self.assertIsNone(assets['source_state_sha256'])
        self.assertEqual([g['path'] for g in report['asset_summary']['overlapping_paths']], ['.gitignore'])

    def test_untracked_mutation_after_hashing_invalidates_source_match(self):
        spec = importlib.util.spec_from_file_location('workspace_probe', SCRIPT)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        (self.primary / 'new.txt').write_text('original')
        original = module.disk_usage

        def changing(*args, **kwargs):
            (self.primary / 'new.txt').write_text('changed after hash')
            return original(*args, **kwargs)

        with patch.object(module, 'disk_usage', side_effect=changing):
            report = module.inspect(self.primary, assets=True)
        row = report['worktrees'][0]['assets']
        self.assertIsNone(row['source_state_sha256'])
        self.assertFalse(row['complete'])


if __name__ == "__main__":
    unittest.main()
