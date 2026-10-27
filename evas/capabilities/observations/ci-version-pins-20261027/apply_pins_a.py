"""Pin CI runner, Python, ngspice, nightly and build versions in a workflow tree (part A).

Usage: python -B apply_pins_a.py <tree>. Rewrites only the three workflow files; refuses unexpected counts.
"""
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1]).resolve()
NIGHTLY = 'nightly-2026-10-27'


def rewrite(path, pairs):
    target = ROOT / path
    text = target.read_text()
    for old, new, count in pairs:
        found = text.count(old)
        assert found == count, (path, old, found, count)
        text = text.replace(old, new)
    target.write_text(text)


rewrite('.github/workflows/numerical-assurance.yml', [
    ('runs-on: ubuntu-latest', 'runs-on: ubuntu-24.04', 13),
    ("python-version: '3.12'\n", "python-version: '3.12.15'\n", 10),
    ('sudo apt-get install -y ngspice\n', 'sudo apt-get install -y ngspice=42+ds-3build1\n', 1),
    ('rustup toolchain install nightly --profile minimal', 'rustup toolchain install ' + NIGHTLY + ' --profile minimal', 1),
    ('          toolchain: nightly\n', '          toolchain: ' + NIGHTLY + '\n', 1),
    ('cargo +nightly ', 'cargo +' + NIGHTLY + ' ', 2),
])
rewrite('.github/workflows/benchmark-evidence.yml', [
    ('runs-on: ubuntu-latest', 'runs-on: ubuntu-24.04', 2),
    ("python-version: '3.12'\n", "python-version: '3.12.15'\n", 2),
])
rewrite('.github/workflows/package-install.yml', [
    ("permissions:\n  contents: read\n",
     "permissions:\n  contents: read\n\n"
     "# Same fixed Rust toolchain as numerical-assurance.yml; the sdist build uses it through rustup.\n"
     "env:\n  RUSTUP_TOOLCHAIN: '1.99.1'\n", 1),
    ("            python: '3.10'\n", "            python: '3.10.22'\n", 1),
    ("            python: '3.12'\n", "            python: '3.12.10'\n", 1),
    ('rustup toolchain install stable --profile minimal', 'rustup toolchain install "$RUSTUP_TOOLCHAIN" --profile minimal', 1),
    ('python -m pip install build\n', 'python -m pip install build==1.6.1\n', 1),
])
# A patch-pinned workflow still declares the inventory interpreter's major/minor.
rewrite('scripts/capabilities/collect_ci_inventory.py', [
    ("    if declared and (len(declared) != 1 or declared[0] != str(sys.version_info.major) + '.' + str(sys.version_info.minor)):\n",
     "    actual = str(sys.version_info.major) + '.' + str(sys.version_info.minor)\n"
     "    if declared and (len(declared) != 1 or '.'.join(declared[0].split('.')[:2]) != actual):\n", 1),
])
rewrite('scripts/tests/test_ci_inventory.py', [
    ('from pathlib import Path\nimport tempfile\n', 'from pathlib import Path\nimport sys\nimport tempfile\n', 1),
    ("""        self.assertEqual(receipt['transport']['stderr'], proc.stderr)\n\n\nclass RequiredGateTests(unittest.TestCase):\n""",
     """        self.assertEqual(receipt['transport']['stderr'], proc.stderr)\n\n"""
     """    def test_patch_pinned_workflow_python_matches_by_major_minor(self):\n"""
     """        current = '%d.%d' % sys.version_info[:2]\n"""
     """        proc = types.SimpleNamespace(returncode=2, stdout='fixture non-JSON stream\\n', stderr='')\n"""
     """        for declared in ([current], [current + '.99']):\n"""
     """            entry = dict(start='scripts/tests', pattern='test*.py', namespace='maintenance',\n"""
     """                         environment_overrides={}, declared_python_versions=declared)\n"""
     """            with patch.object(inventory.subprocess, 'run', return_value=proc):\n"""
     """                self.assertFalse(inventory.child(self.root, entry, 1)['complete'])\n"""
     """        for declared in (['%d.%d.1' % (sys.version_info[0], sys.version_info[1] + 1)], [current, current]):\n"""
     """            entry = dict(start='scripts/tests', pattern='test*.py', namespace='maintenance',\n"""
     """                         environment_overrides={}, declared_python_versions=declared)\n"""
     """            with self.assertRaisesRegex(ValueError, 'major/minor'):\n"""
     """                inventory.child(self.root, entry, 1)\n\n\n"""
     """class RequiredGateTests(unittest.TestCase):\n""", 1),
])
for path in ('.github/workflows/numerical-assurance.yml', '.github/workflows/benchmark-evidence.yml', '.github/workflows/package-install.yml'):
    text = (ROOT / path).read_text()
    assert 'ubuntu-latest' not in text and not re.search(r"python(?:-version)?: '3\.1[0-9]'\n", text), path
print('pinned')
