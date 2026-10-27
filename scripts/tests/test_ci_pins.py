"""The CI workflows name fixed runner, interpreter and tool versions; no simulator runs here."""
from pathlib import Path
import re
import shlex
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / '.github/workflows'
RUNNERS = ('ubuntu-24.04', 'macos-14')
PATCH_RELEASE = re.compile(r'3\.[0-9]+\.[0-9]+')
KEY = re.compile(r'\s*(?:-\s+)?(runs-on|runner|python-version|python-version-file|python):(.*)')
VALUE = re.compile(r"""\s*(?:'([^']*)'|"([^"]*)"|([^\s'"#](?:[^#]*[^\s#])?))\s*(?:#.*)?""")


def code(path):
    """Workflow lines without whole-line YAML or shell comments, so a comment cannot satisfy a pin."""
    return [line for line in path.read_text().splitlines() if not line.lstrip().startswith('#')]


def values(path, *keys):
    """Every value of the given keys, single-quoted, double-quoted or bare; any other form fails."""
    found = []
    for line in code(path):
        match = KEY.fullmatch(line)
        if match and match[1] in keys:
            value = VALUE.fullmatch(match[2])
            if not value:
                raise AssertionError('unsupported %s form in %s: %r' % (match[1], path.name, line))
            found.append((match[1], next(v for v in value.groups() if v is not None)))
    return found


def commands(path, word):
    """Shell words, trailing comments removed, of every line that names the command word."""
    return [shlex.split(line, comments=True) for line in code(path) if re.search(r'(?<![\w.-])' + re.escape(word) + r'(?![\w.-])', line)]


class CiVersionPins(unittest.TestCase):
    def test_hosted_runners_name_fixed_labels(self):
        for path in sorted(WORKFLOWS.glob('*.yml')):
            with self.subTest(workflow=path.name):
                found = values(path, 'runs-on', 'runner')
                matrix = [value for key, value in found if key == 'runner']
                for key, value in found:
                    if key == 'runs-on' and value == '${{ matrix.runner }}':
                        self.assertTrue(matrix)
                    else:
                        self.assertIn(value, RUNNERS)

    def test_every_setup_python_names_a_patch_release(self):
        steps = 0
        for path in sorted(WORKFLOWS.glob('*.yml')):
            with self.subTest(workflow=path.name):
                setups = sum('uses: actions/setup-python@' in line for line in code(path))
                found = values(path, 'python-version', 'python-version-file', 'python')
                declared = [value for key, value in found if key == 'python-version']
                matrix = [value for key, value in found if key == 'python']
                self.assertNotIn('python-version-file', [key for key, _ in found])
                self.assertEqual(len(declared), setups)
                for value in declared:
                    if value == '${{ matrix.python }}':
                        self.assertTrue(matrix)
                    else:
                        self.assertTrue(PATCH_RELEASE.fullmatch(value), value)
                for value in matrix:
                    self.assertTrue(PATCH_RELEASE.fullmatch(value), value)
                steps += setups
        self.assertTrue(steps)

    def test_ngspice_nightly_build_and_package_rust_are_pinned(self):
        assurance = WORKFLOWS / 'numerical-assurance.yml'
        ngspice = [w for words in commands(assurance, 'apt-get') if 'install' in words for w in words if w.startswith('ngspice')]
        self.assertTrue(ngspice)
        self.assertEqual(set(ngspice), {'ngspice=42+ds-3build1'})
        nightly = [w for line in code(assurance) for w in re.findall(r'\bnightly[^\s"\']*', line)]
        self.assertTrue(nightly)
        for word in nightly:
            self.assertRegex(word, r'^nightly-[0-9]{4}-[0-9]{2}-[0-9]{2}$')
        package = WORKFLOWS / 'package-install.yml'
        builds = [w for words in commands(package, 'pip') for w in words if re.match(r'build\b', w)]
        self.assertEqual(builds, ['build==1.6.1'])
        self.assertRegex(package.read_text(), r"(?m)^env:\n  RUSTUP_TOOLCHAIN: '[0-9]+\.[0-9]+\.[0-9]+'$")
        rust = commands(package, 'rustup') + commands(package, 'cargo')
        self.assertTrue(any('$RUSTUP_TOOLCHAIN' in words for words in rust))
        for words in rust:
            self.assertFalse([w for w in words if w == 'stable' or w.startswith('+')], words)


if __name__ == '__main__':
    unittest.main()
