"""The CI workflows name fixed runner, interpreter and tool versions; no simulator runs here."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / '.github/workflows'


class CiVersionPins(unittest.TestCase):
    def test_hosted_runners_name_one_ubuntu_release(self):
        for path in sorted(WORKFLOWS.glob('*.yml')):
            text = path.read_text()
            with self.subTest(workflow=path.name):
                self.assertNotIn('ubuntu-latest', text)
                for label in re.findall(r'runs-on: (\S+)', text):
                    self.assertIn(label, ('ubuntu-24.04', '${{'))

    def test_python_versions_name_a_patch_release(self):
        versions = [v for path in sorted(WORKFLOWS.glob('*.yml'))
                    for v in re.findall(r"python(?:-version)?: '([^']+)'", path.read_text())]
        self.assertTrue(versions)
        for version in versions:
            self.assertRegex(version, r'^3\.[0-9]+\.[0-9]+$')

    def test_ngspice_nightly_build_and_package_rust_are_pinned(self):
        assurance = (WORKFLOWS / 'numerical-assurance.yml').read_text()
        self.assertIn('apt-get install -y ngspice=42+ds-3build1', assurance)
        self.assertTrue(re.findall(r'nightly-[0-9]{4}-[0-9]{2}-[0-9]{2}', assurance))
        self.assertNotRegex(assurance, r'\bnightly\b(?!-[0-9]{4}-[0-9]{2}-[0-9]{2})')
        package = (WORKFLOWS / 'package-install.yml').read_text()
        self.assertIn('pip install build==1.6.1', package)
        self.assertRegex(package, r"(?m)^env:\n  RUSTUP_TOOLCHAIN: '[0-9]+\.[0-9]+\.[0-9]+'$")
        self.assertNotRegex(package, r'rustup toolchain install stable|\+stable')


if __name__ == '__main__':
    unittest.main()
