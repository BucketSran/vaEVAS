"""Apply the PR273 review-r1 fixes to an export of 6bfa35ea: pin test, inventory version check, package comment."""
from pathlib import Path
import shutil
import sys

D = Path(__file__).resolve().parent
S = Path(sys.argv[1])


def replace(path, old, new):
    target = S / path
    text = target.read_text()
    assert text.count(old) == 1, (path, old[:60])
    target.write_text(text.replace(old, new))


replace('scripts/capabilities/collect_ci_inventory.py',
        "                         '${{ steps.changes.outputs.head }}': 'CI_INVENTORY_HEAD'}\n",
        "                         '${{ steps.changes.outputs.head }}': 'CI_INVENTORY_HEAD'}\n"
        "PYTHON_RELEASE = re.compile(r'([0-9]+)\\.([0-9]+)(?:\\.[0-9]+)?')\n")
replace('scripts/capabilities/collect_ci_inventory.py',
        "    if declared and (len(declared) != 1 or '.'.join(declared[0].split('.')[:2]) != actual):\n",
        "    release = PYTHON_RELEASE.fullmatch(declared[0]) if len(declared) == 1 else None\n"
        "    if declared and (release is None or release[1] + '.' + release[2] != actual):\n")
replace('scripts/tests/test_ci_inventory.py',
        "        for declared in (['%d.%d.1' % (sys.version_info[0], sys.version_info[1] + 1)], [current, current]):\n"
        "            entry = dict(start='scripts/tests', pattern='test*.py', namespace='maintenance',\n"
        "                         environment_overrides={}, declared_python_versions=declared)\n"
        "            with self.assertRaisesRegex(ValueError, 'major/minor'):\n"
        "                inventory.child(self.root, entry, 1)\n",
        "        other_minor = '%d.%d.1' % (sys.version_info[0], sys.version_info[1] + 1)\n"
        "        for declared in ([other_minor], [current, current], [current + '.not-a-version'], [current + '.'],\n"
        "                         [current + '.15.extra'], [str(sys.version_info[0])], [current + 'x']):\n"
        "            entry = dict(start='scripts/tests', pattern='test*.py', namespace='maintenance',\n"
        "                         environment_overrides={}, declared_python_versions=declared)\n"
        "            with patch.object(inventory.subprocess, 'run') as run, self.assertRaisesRegex(ValueError, 'major/minor'):\n"
        "                inventory.child(self.root, entry, 1)\n"
        "            run.assert_not_called()\n")
replace('.github/workflows/package-install.yml',
        "# Same fixed Rust toolchain as numerical-assurance.yml; the sdist build uses it through rustup.\n",
        "# Fixed Rust toolchain for the sdist build, which uses it through rustup.\n")
shutil.copyfile(D / 'test_ci_pins.py', S / 'scripts/tests/test_ci_pins.py')
print('applied')
