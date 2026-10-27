"""Apply one workflow mutation at a time to a scratch copy and run test_ci_pins.py; record pass/fail."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

D = Path(__file__).resolve().parent
SOURCE = Path(sys.argv[1])
PY = sys.argv[2]
NA, BE, PI = '.github/workflows/numerical-assurance.yml', '.github/workflows/benchmark-evidence.yml', '.github/workflows/package-install.yml'
MUTANTS = {
    'original': [],
    'benchmark python double-quoted minor': [(BE, "python-version: '3.12.15'", 'python-version: "3.12"', 1)],
    'package matrix double-quoted minor': [(PI, "python: '3.10.22'", 'python: "3.10"', 1)],
    'double-quoted major': [(NA, "python-version: '3.12.15'", 'python-version: "3"', 1)],
    'bare minor': [(NA, "python-version: '3.12.15'", 'python-version: 3.12', 1)],
    'python-version-file': [(NA, "python-version: '3.12.15'", 'python-version-file: .python-version', 1)],
    'setup-python without version': [(NA, "          python-version: '3.12.15'\n", '', 1)],
    'matrix runner macos-latest': [(PI, 'runner: macos-14', 'runner: macos-latest', 1)],
    'runs-on ubuntu-latest': [(NA, 'runs-on: ubuntu-24.04', 'runs-on: ubuntu-latest', 1)],
    'runs-on other matrix key': [(PI, 'runs-on: ${{ matrix.runner }}', 'runs-on: ${{ matrix.os }}', 1)],
    'ngspice floating with pinned comment': [(NA, 'sudo apt-get install -y ngspice=42+ds-3build1', 'sudo apt-get install -y ngspice  # ngspice=42+ds-3build1', 1)],
    'ngspice floating with comment line': [(NA, '      - run: sudo apt-get update && sudo apt-get install -y ngspice=42+ds-3build1',
                                            '      # sudo apt-get install -y ngspice=42+ds-3build1\n      - run: sudo apt-get update && sudo apt-get install -y ngspice', 1)],
    'build floating with pinned comment': [(PI, 'pip install build==1.6.1', 'pip install build  # build==1.6.1', 1)],
    'nightly floating': [(NA, 'rustup toolchain install nightly-2026-10-27', 'rustup toolchain install nightly', 1)],
    'package rustup stable': [(PI, 'rustup toolchain install "$RUSTUP_TOOLCHAIN"', 'rustup toolchain install stable', 1)],
    'package env floating': [(PI, "RUSTUP_TOOLCHAIN: '1.99.1'", 'RUSTUP_TOOLCHAIN: stable', 1)],
    'pinned value with trailing comment (valid)': [(NA, "python-version: '3.12.15'", "python-version: '3.12.15' # interpreter", 1)],
}
results = {}
for name, edits in MUTANTS.items():
    work = D / 'scratch-mutants' / name.replace(' ', '-')
    if work.exists():
        shutil.rmtree(work)
    (work / 'scripts/tests').mkdir(parents=True)
    shutil.copytree(SOURCE / '.github', work / '.github')
    shutil.copyfile(D / 'test_ci_pins.py', work / 'scripts/tests/test_ci_pins.py')
    for path, old, new, count in edits:
        text = (work / path).read_text()
        assert text.count(old) >= count, (name, old)
        (work / path).write_text(text.replace(old, new, count))
    run = subprocess.run([PY, '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_ci_pins.py'],
                         cwd=work, capture_output=True, text=True)
    results[name] = {'returncode': run.returncode, 'tail': run.stderr.strip().splitlines()[-1]}
expected_pass = {'original', 'pinned value with trailing comment (valid)'}
summary = {name: ('PASS' if r['returncode'] == 0 else 'REJECT') for name, r in results.items()}
ok = all((summary[n] == 'PASS') == (n in expected_pass) for n in summary)
(D / 'pin-mutants.json').write_text(json.dumps({'source': str(SOURCE), 'results': results, 'summary': summary, 'as_expected': ok}, indent=1) + '\n')
print(json.dumps(summary, indent=1)); print('as_expected', ok)
