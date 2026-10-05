"""Exercise workspace visibility and handoff reporting with real temporary Git repos."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
