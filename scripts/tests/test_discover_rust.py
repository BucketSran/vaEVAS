"""Actual CLI plumbing with fake tools/harnesses; no Rust compilation or science."""
import hashlib
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import re
import textwrap
import unittest

import git_fixture

HELPER = Path(__file__).resolve().parents[1] / 'capabilities/discover_rust.py'


MAIN_WORKFLOW = '.github/workflows/numerical-assurance.yml'
CACHE_ACTION = '.github/actions/rust-cache/action.yml'
# Authoritative references: the single pinned literal is reached only through these.
AUTHORITATIVE = frozenset(['$RUSTUP_TOOLCHAIN', '${RUSTUP_TOOLCHAIN}', '${{ inputs.rust_toolchain }}',
                           '${{ needs.selection.outputs.rust_toolchain }}', '${{ env.RUSTUP_TOOLCHAIN }}'])
CACHE_EXPANSION = '${CI_RUST_TOOLCHAIN:++"$CI_RUST_TOOLCHAIN"}'
TOOLS = ('cargo', 'rustc', 'rustdoc', 'rustfmt', 'cargo-clippy', 'cargo-fmt', 'clippy-driver')
RUSTUP_NO_SELECTION = frozenset(['component', 'target', 'show', 'which', 'self', 'set', 'doc', 'man', 'completions',
                                 'check', 'update', '--version', '-V', 'help', '-h', '--help', 'toolchain-list'])
PIN_LINE = re.compile(r"^  RUSTUP_TOOLCHAIN: '[0-9]+\.[0-9]+\.[0-9]+'$")


def _plain(value):
    return value.strip().strip('\'"').strip()


def toolchain_selection_violations(texts, root_files=()):
    """Every way CI can choose a Rust toolchain, checked against a whitelist.

    texts maps a repo-relative workflow or composite-action path to its text. A selection is allowed only
    as an authoritative reference (${RUSTUP_TOOLCHAIN}, the reusable input, the selection output, the
    workflow env), as the one pinned literal under the top-level env, or as nightly in the fuzz-smoke job
    through exactly `rustup toolchain install nightly`, `cargo +nightly` and `toolchain: nightly`.
    Anything else that selects a toolchain, and anything this scanner cannot classify, is reported.
    root_files lists repo files named like rust-toolchain, which also select a toolchain.
    """
    found = [f'{name}: toolchain file' for name in root_files]
    for name, text in sorted(texts.items()):
        lines = text.split('\n')
        fuzz = set()
        if name == MAIN_WORKFLOW:
            start = next((i for i, line in enumerate(lines) if line == '  fuzz-smoke:'), None)
            if start is not None:
                end = next((i for i in range(start + 1, len(lines)) if re.match(r'  [A-Za-z0-9_-]+:\s*$', lines[i])), len(lines))
                fuzz = set(range(start, end))

        def report(index, reason):
            found.append(f'{name}:{index + 1}: {reason}: {lines[index].strip()}')

        def allowed(index, value, form):
            value = _plain(value)
            if value in AUTHORITATIVE or (value == '${{ inputs.toolchain }}' and name == CACHE_ACTION):
                return True
            return value == 'nightly' and index in fuzz and form in ('rustup-install', 'cargo-plus', 'with-toolchain')

        for index, raw in enumerate(lines):
            line = re.sub(r'\s+#.*$', '', raw)
            if not line.strip() or line.lstrip().startswith('#') or re.match(r'\s*(?:-\s+)?(?:name|description):', line):
                continue
            approved_nightly = False
            for match in re.finditer(r'(?<![\w./-])rustup\b(?![-\w])([^\n;&|]*)', line):
                tokens = [_plain(token) for token in match.group(1).split()]
                words = [token for token in tokens if not token.startswith('-')]
                picked = []
                for position, token in enumerate(tokens):
                    if token.startswith('+'):
                        picked.append((token[1:], 'rustup-plus'))
                    elif token == '--toolchain' and position + 1 < len(tokens):
                        picked.append((tokens[position + 1], 'rustup-flag'))
                    elif token.startswith('--toolchain='):
                        picked.append((token.split('=', 1)[1], 'rustup-flag'))
                sub = words[0] if words else ''
                rest = words[1:]
                if sub in ('install', 'default', 'run', 'uninstall'):
                    picked.append((rest[0] if rest else '', 'rustup-' + sub))
                elif sub == 'override':
                    if rest[:1] == ['set']:
                        picked.append((rest[1] if len(rest) > 1 else '', 'rustup-override'))
                    elif rest[:1] != ['unset']:
                        report(index, 'unrecognised rustup override form')
                elif sub == 'toolchain':
                    if rest[:1] in (['list'],):
                        pass
                    elif rest[:1] == ['install']:
                        picked.append((rest[1] if len(rest) > 1 else '', 'rustup-install'))
                    else:
                        picked.append((rest[1] if len(rest) > 1 else '', 'rustup-toolchain-' + (rest[0] if rest else '')))
                elif sub and sub not in RUSTUP_NO_SELECTION:
                    report(index, 'unrecognised rustup form')
                for value, form in picked:
                    if allowed(index, value, form):
                        approved_nightly = approved_nightly or _plain(value) == 'nightly'
                    else:
                        report(index, f'rustup selects {value!r}')
            for match in re.finditer(r'(?<![\w./$-])(' + '|'.join(TOOLS) + r')\b[ \t]+(\S+)', line):
                token = _plain(match.group(2))
                if token.startswith('+'):
                    token = '+' + _plain(token[1:])
                    if token[1:] in AUTHORITATIVE or (token[1:] == 'nightly' and index in fuzz and match.group(1) == 'cargo'):
                        approved_nightly = approved_nightly or token[1:] == 'nightly'
                    else:
                        report(index, f'{match.group(1)} selects {token[1:]!r}')
                elif '${' in token and '+' in token:
                    if not (token == CACHE_EXPANSION and name == CACHE_ACTION):
                        report(index, 'unrecognised toolchain expansion')
            for match in re.finditer(r'^\s*(?:-\s+)?([A-Za-z_-]*(?:toolchain|channel|rust[-_]version)[A-Za-z_-]*|RUSTUP_TOOLCHAIN)\s*:\s*(.*)$', line, re.I):
                key, value = match.group(1), _plain(match.group(2))
                if value == '':
                    indent = len(line) - len(line.lstrip())
                    if key not in ('toolchain', 'rust_toolchain'):
                        report(index, f'unrecognised {key} declaration')
                    for later in lines[index + 1:]:
                        if later.strip() and len(later) - len(later.lstrip()) <= indent:
                            break
                        default = re.match(r'\s*default:\s*(.*)$', later)
                        if default and (key == 'rust_toolchain' or _plain(default.group(1)) != ''):
                            report(index, f'{key} input has a default')
                elif key == 'RUSTUP_TOOLCHAIN' and PIN_LINE.match(raw) and name == MAIN_WORKFLOW and index and lines[index - 1] == 'env:':
                    pass
                elif allowed(index, value, 'with-toolchain' if key == 'toolchain' else 'assign'):
                    approved_nightly = approved_nightly or value == 'nightly'
                else:
                    report(index, f'{key} selects {value!r}')
            for match in re.finditer(r'RUSTUP_TOOLCHAIN[ \t]*=[ \t]*([^\s"\';&|]*)', line):
                if _plain(match.group(1)) not in AUTHORITATIVE:
                    report(index, f'RUSTUP_TOOLCHAIN assigned {match.group(1)!r}')
            uses = re.match(r'\s*(?:-\s+)?uses:\s*(\S+)', line)
            if uses and uses.group(1) != './.github/actions/rust-cache' and re.search(r'(?i)rust|toolchain|cargo|maturin', uses.group(1)):
                report(index, f'unrecognised toolchain action {uses.group(1)}')
            if re.search(r'(?i)\b(nightly|stable|beta)\b', line) and not approved_nightly:
                report(index, 'channel name outside an approved nightly use')
    return found


def toolchain_files(root):
    """rust-toolchain and rust-toolchain.toml files in the repository, ignoring build output and Git data."""
    found = []
    for directory, names, files in os.walk(root):
        names[:] = [name for name in names if name not in ('.git', 'target', 'node_modules', '__pycache__')]
        found.extend(os.path.relpath(os.path.join(directory, name), root) for name in files
                     if name in ('rust-toolchain', 'rust-toolchain.toml'))
    return sorted(found)


SELECTION_VALUES = ('nightly', 'stable', '1.99.0')
# The only forms through which fuzz-smoke may name nightly (the same ones the real job uses).
FUZZ_NIGHTLY_FORMS = ('rustup-toolchain-install', 'rustup-in-block-scalar', 'cargo-plus', 'cargo-plus-in-block-scalar',
                       'with-toolchain-input')
# Each form is (indent -> list of YAML lines for one workflow step). {v} is the injected toolchain.
STEP_FORMS = {
    'rustup-toolchain-install': lambda i, v: [f'{i}- run: rustup toolchain install {v} --profile minimal'],
    'rustup-default': lambda i, v: [f'{i}- run: rustup default {v}'],
    'rustup-override-set': lambda i, v: [f'{i}- run: rustup override set {v}'],
    'rustup-run': lambda i, v: [f'{i}- run: rustup run {v} cargo test'],
    'rustup-toolchain-link': lambda i, v: [f'{i}- run: rustup toolchain link custom {v}'],
    'rustup-unrecognised': lambda i, v: [f'{i}- run: rustup frobnicate {v}'],
    'rustup-in-compound-command': lambda i, v: [f'{i}- run: cd evas && rustup default {v} && cargo test'],
    'rustup-in-block-scalar': lambda i, v: [f'{i}- run: |', f'{i}    set -e', f'{i}    rustup toolchain install {v}'],
    'cargo-plus': lambda i, v: [f'{i}- run: cargo +{v} test --locked'],
    'rustc-plus': lambda i, v: [f'{i}- run: rustc +{v} -vV'],
    'cargo-clippy-plus': lambda i, v: [f'{i}- run: cargo-clippy +{v}'],
    'cargo-plus-in-block-scalar': lambda i, v: [f'{i}- run: |', f'{i}    cargo +{v} build'],
    'shell-env-assignment': lambda i, v: [f'{i}- run: RUSTUP_TOOLCHAIN={v} cargo test'],
    'shell-export': lambda i, v: [f'{i}- run: export RUSTUP_TOOLCHAIN={v}'],
    'github-env-file': lambda i, v: [f'{i}- run: echo "RUSTUP_TOOLCHAIN={v}" >> "$GITHUB_ENV"'],
    'step-env': lambda i, v: [f'{i}- run: cargo test', f'{i}  env:', f'{i}    RUSTUP_TOOLCHAIN: {v}'],
    'step-env-quoted': lambda i, v: [f'{i}- run: cargo test', f'{i}  env:', f'{i}    RUSTUP_TOOLCHAIN: "{v}"'],
    'with-toolchain-input': lambda i, v: [f'{i}- uses: ./.github/actions/rust-cache', f'{i}  with:', f'{i}    toolchain: {v}',
                                          f'{i}    lane: x'],
    'dtolnay-action': lambda i, v: [f'{i}- uses: dtolnay/rust-toolchain@{v}'],
    'dtolnay-action-with': lambda i, v: [f'{i}- uses: dtolnay/rust-toolchain@master', f'{i}  with:', f'{i}    toolchain: {v}'],
    'actions-rs': lambda i, v: [f'{i}- uses: actions-rs/toolchain@v1', f'{i}  with:', f'{i}    toolchain: {v}'],
}
# Forms that can sit at other structural positions than a step.
BLOCK_FORMS = {
    'job-env': lambda i, v: [f'{i}env:', f'{i}  RUSTUP_TOOLCHAIN: {v}'],
    'job-env-quoted': lambda i, v: [f'{i}env:', f"{i}  RUSTUP_TOOLCHAIN: '{v}'"],
}


def _insert_after(text, anchor_line, new_lines):
    lines = text.split('\n')
    index = lines.index(anchor_line)
    return '\n'.join(lines[:index + 1] + new_lines + lines[index + 1:])


def selection_variant_cases(texts):
    """(form, location, value, new texts, new toolchain files, expect_reject) for every injected selection.

    Each form is injected at each structural position of CI, once per toolchain value. Authoritative
    references and the one nightly use cargo-fuzz needs are the positive controls.
    """
    main, package, cache = MAIN_WORKFLOW, '.github/workflows/package-install.yml', CACHE_ACTION
    cases = []

    def add(form, location, value, changed, files=(), expect_reject=True):
        cases.append((form, location, value, changed, tuple(files), expect_reject))

    step_places = {
        'job-steps-rust-regression': (main, '  rust-regression:', '    steps:', '      '),
        'job-steps-regression': (main, '  regression:', '    steps:', '      '),
        'job-steps-selection': (main, '  selection:', '    steps:', '      '),
        'job-steps-fuzz-smoke': (main, '  fuzz-smoke:', '    steps:', '      '),
        'job-steps-ci-result': (main, '  ci-result:', '    steps:', '      '),
        'reusable-workflow-steps': (package, '  install:', '    steps:', '      '),
        'composite-action-steps': (cache, None, '  steps:', '    '),
    }

    def anchored(path, job, steps_anchor):
        lines = texts[path].split('\n')
        start = lines.index(job) if job else 0
        return start + lines[start:].index(steps_anchor)

    for value in SELECTION_VALUES:
        for form, build in STEP_FORMS.items():
            for location, (path, job, steps_anchor, indent) in step_places.items():
                lines = texts[path].split('\n')
                index = anchored(path, job, steps_anchor)
                changed = '\n'.join(lines[:index + 1] + build(indent, value) + lines[index + 1:])
                fuzz_nightly = (location == 'job-steps-fuzz-smoke' and value == 'nightly'
                                and form in FUZZ_NIGHTLY_FORMS)
                add(form, location, value, dict(texts, **{path: changed}), expect_reject=not fuzz_nightly)
            # A brand-new workflow and a brand-new composite action.
            add(form, 'new-workflow', value, dict(texts, **{'.github/workflows/new.yml': '\n'.join(
                ['name: n', 'on: push', 'jobs:', '  x:', '    runs-on: ubuntu-latest', '    steps:', *build('      ', value)]) + '\n'}))
            add(form, 'new-composite-action', value, dict(texts, **{'.github/actions/new/action.yml': '\n'.join(
                ['name: n', 'description: d', 'runs:', '  using: composite', '  steps:', *build('    ', value)]) + '\n'}))
        for form, build in BLOCK_FORMS.items():
            for location, (path, job) in {'job-level-rust-regression': (main, '  rust-regression:'),
                                          'job-level-fuzz-smoke': (main, '  fuzz-smoke:'),
                                          'job-level-reusable-workflow': (package, '  install:')}.items():
                if location == 'job-level-reusable-workflow':
                    # that job already has an env block: replace the authoritative value
                    changed = texts[path].replace('RUSTUP_TOOLCHAIN: ${{ inputs.rust_toolchain }}', f'RUSTUP_TOOLCHAIN: {value}', 1)
                else:
                    changed = _insert_after(texts[path], job, BLOCK_FORMS[form]('    ', value))
                add(form, location, value, dict(texts, **{path: changed}))
        # Top-level env: a second assignment, or the pin replaced.
        add('workflow-env-second', 'workflow-level', value, dict(texts, **{main: _insert_after(
            texts[main], "  RUSTUP_TOOLCHAIN: '1.99.1'", [f"  RUSTUP_TOOLCHAIN: '{value}'"])}))
        if value != '1.99.0':
            add('workflow-env-pin-replaced', 'workflow-level', value, dict(texts, **{main: texts[main].replace(
                "RUSTUP_TOOLCHAIN: '1.99.1'", f"RUSTUP_TOOLCHAIN: '{value}'", 1)}))
        else:
            add('workflow-env-pin-replaced', 'workflow-level', value, dict(texts, **{main: texts[main].replace(
                "RUSTUP_TOOLCHAIN: '1.99.1'", f"RUSTUP_TOOLCHAIN: '{value}'", 1)}), expect_reject=False)
        add('reusable-input-default', 'reusable-workflow-input', value, dict(texts, **{package: texts[package].replace(
            '        required: true\n', f'        required: true\n        default: {value}\n', 1)}))
        add('reusable-caller-passes-literal', 'package-job-with', value, dict(texts, **{main: texts[main].replace(
            'rust_toolchain: ${{ needs.selection.outputs.rust_toolchain }}', f'rust_toolchain: {value}', 1)}))
        add('selection-output-literal', 'selection-job', value, dict(texts, **{main: texts[main].replace(
            'rust_toolchain: ${{ env.RUSTUP_TOOLCHAIN }}', f'rust_toolchain: {value}', 1)}))
        add('composite-input-default', 'composite-action-input', value, dict(texts, **{cache: texts[cache].replace(
            "    default: ''\n  lane:", f"    default: {value}\n  lane:", 1)}))
        add('composite-env-literal', 'composite-action-step', value, dict(texts, **{cache: texts[cache].replace(
            'CI_RUST_TOOLCHAIN: ${{ inputs.toolchain }}', f'CI_RUST_TOOLCHAIN: {value}', 1)}))
        for name in ('rust-toolchain', 'rust-toolchain.toml'):
            add('toolchain-file', name, value, texts, files=[name])
            add('toolchain-file', 'evas/rust_core/' + name, value, texts, files=['evas/rust_core/' + name])
    # Positive controls: authoritative references anywhere, and fuzz-smoke's nightly.
    for location, (path, job, steps_anchor, indent) in step_places.items():
        for form, lines_for in {
            'authoritative-install': lambda i: [f'{i}- run: rustup toolchain install "$RUSTUP_TOOLCHAIN" --profile minimal'],
            'authoritative-input': lambda i: [f'{i}- uses: ./.github/actions/rust-cache', f'{i}  with:',
                                              f'{i}    toolchain: ${{{{ env.RUSTUP_TOOLCHAIN }}}}', f'{i}    lane: x'],
            'authoritative-cargo-plus': lambda i: [f'{i}- run: cargo +"$RUSTUP_TOOLCHAIN" test'],
        }.items():
            lines = texts[path].split('\n')
            index = anchored(path, job, steps_anchor)
            changed = '\n'.join(lines[:index + 1] + lines_for(indent) + lines[index + 1:])
            add(form, location, 'authoritative', dict(texts, **{path: changed}), expect_reject=False)
    fuzz_lines = texts[main].split('\n')
    index = anchored(main, '  fuzz-smoke:', '    steps:')
    for form, build in {'fuzz-cargo-plus-nightly': lambda i, v: [f'{i}- run: cargo +nightly --version'],
                        'fuzz-install-nightly': lambda i, v: [f'{i}- run: rustup toolchain install nightly --profile minimal'],
                        'fuzz-cache-toolchain-nightly': lambda i, v: [f'{i}- uses: ./.github/actions/rust-cache', f'{i}  with:',
                                                                      f'{i}    toolchain: nightly', f'{i}    lane: fuzz']}.items():
        changed = '\n'.join(fuzz_lines[:index + 1] + build('      ', 'nightly') + fuzz_lines[index + 1:])
        add(form, 'job-steps-fuzz-smoke', 'nightly', dict(texts, **{main: changed}), expect_reject=False)
    add('unchanged-current-ci', 'all', 'current', texts, expect_reject=False)
    return cases


def historical_checked_calls(root):
    """Every call to checked() that sets or forwards `historical`, outside tests, as (path, function, values)."""
    import ast

    class Finder(ast.NodeVisitor):
        def __init__(self):
            self.stack, self.calls = ['<module>'], []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            if name == 'checked' and any(keyword.arg in ('historical', None) for keyword in node.keywords):
                self.calls.append((self.stack[-1], tuple(ast.unparse(keyword.value) for keyword in node.keywords)))
            self.generic_visit(node)

    calls = []
    for base in ('scripts', 'evas'):
        for path in sorted((root / base).rglob('*.py')):
            if 'target' in path.parts or path.name.startswith('test_') or path.name == 'git_fixture.py':
                continue
            finder = Finder()
            finder.visit(ast.parse(path.read_text()))
            calls.extend((str(path.relative_to(root)), function, values) for function, values in finder.calls)
    return sorted(calls)


class RustListingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        git_fixture.bind(self, Path(self.tmp.name))
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.write('.gitignore', 'runs/\nevas/rust_core/target/\n')
        self.write('evas/rust_core/Cargo.toml', '[package]\nname="evas-kernel"\nversion="0.25.0"\n[workspace]\nmembers=["ir"]\n')
        self.write('evas/rust_core/ir/Cargo.toml', '[package]\nname="evas-ir"\nversion="0.1.0"\n')
        self.write('evas/rust_core/Cargo.lock', 'version = 4\n')
        self.write('evas/rust_core/src/main.rs', 'fn main() {}\n')
        self.write('evas/rust_core/ir/src/lib.rs', '// source identity fixture only, not compiled\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'owned source fixture')
        self.commit = self.git('rev-parse', 'HEAD')
        self.target = self.repo / 'evas/rust_core/target'
        self.targets = []
        self.artifacts = []
        self.executables = []
        self.metadata = dict(packages=[], workspace_members=[], target_directory=str(self.target), version=1)
        for index, (name, version, folder, kind, src) in enumerate([
                ('evas-kernel', '0.25.0', '', 'bin', 'src/main.rs'),
                ('evas-ir', '0.1.0', 'ir', 'lib', 'src/lib.rs')]):
            crate = self.repo / 'evas/rust_core' / folder
            package = 'path+' + crate.as_uri() + '#' + name + '@' + version
            target = dict(name=name.replace('-', '_') if kind == 'lib' else name,
                          kind=[kind], src_path=str(crate / src), test=True)
            self.metadata['packages'].append(dict(id=package, name=name, version=version,
                manifest_path=str(crate / 'Cargo.toml'), targets=[target]))
            self.metadata['workspace_members'].append(package)
            executable = self.target / 'debug/deps' / ('fixture-harness-' + str(index))
            self.harness(executable, 'same: test\nignored: test\n\n2 tests, 0 benchmarks\n' if index == 0 else 'same: test\n\n1 test, 0 benchmarks\n',
                         'ignored: test\n\n1 test, 0 benchmarks\n' if index == 0 else '0 tests, 0 benchmarks\n')
            self.targets.append(target)
            self.executables.append(executable)
            self.artifacts.append(dict(reason='compiler-artifact', package_id=package, target=target,
                profile=dict(test=True, opt_level='1', debug_assertions=True, overflow_checks=True),
                executable=str(executable), fresh=False))
        tools = Path(self.tmp.name) / 'tools'
        tools.mkdir()
        self.metadata_path = Path(self.tmp.name) / 'metadata.json'
        self.metadata_path.write_text(json.dumps(self.metadata))
        for tool in ('cargo', 'rustc'):
            script = tools / tool
            if tool == 'cargo':
                body=('import pathlib,sys,os\n'
                      'if "metadata" in sys.argv:\n print(pathlib.Path('+repr(str(self.metadata_path))+').read_text())\n'
                      'elif "--no-run" in sys.argv:\n print(pathlib.Path('+repr(str(self.repo/'runs/build.jsonl'))+').read_text(),end="")\n raise SystemExit(int(os.environ.get("FIXTURE_BUILD_EXIT","0")))\n'
                      'else: print("cargo FAKE-fixture-not-Rust")\n')
            else:
                body='print("rustc FAKE-fixture-not-Rust\\nhost: fixture")\n'
            script.write_text('#!' + sys.executable + '\n' + body)
            script.chmod(0o755)
        self.env = git_fixture.child_env(PATH=str(tools) + os.pathsep + os.environ['PATH'],
                                         CARGO_PROFILE_DEV_OPT_LEVEL='1',
                                         CARGO_PROFILE_DEV_DEBUG_ASSERTIONS='true',
                                         CARGO_PROFILE_DEV_OVERFLOW_CHECKS='true')
        self.build = self.repo / 'runs/build.jsonl'
        self.report = self.repo / 'runs/listing.json'
        self.raw = self.repo / 'runs/listing'
        self.messages = self.artifacts + [dict(reason='build-finished', success=True)]
        self.write_messages()

    def git(self, *args):
        return git_fixture.run(['-C', str(self.repo), *args], scratch=Path(self.tmp.name),
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                               check=True).stdout.strip()

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def harness(self, path, listing, ignored, exit_code=0):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!' + sys.executable + '\nimport sys\n'
            + 'print(' + repr(ignored) + ' if "--ignored" in sys.argv else ' + repr(listing) + ',end="")\n'
            + 'raise SystemExit(' + str(exit_code) + ')\n')
        path.chmod(0o755)

    def write_messages(self):
        self.build.parent.mkdir(parents=True, exist_ok=True)
        self.build.write_text(''.join(json.dumps(row) + '\n' for row in self.messages))

    def run_helper(self, build_exit=0):
        result = subprocess.run([sys.executable, '-B', str(HELPER), '--repo', str(self.repo),
            '--build-messages', str(self.build), '--build-exit', str(build_exit),
            '--report', str(self.report), '--raw-directory', str(self.raw)], env=self.env,
            capture_output=True, text=True)
        payload = json.loads(self.report.read_text()) if self.report.exists() else None
        return result, payload

    def test_missing_duplicate_unknown_or_shared_executable_artifacts_refused(self):
        cases=[]
        missing=copy.deepcopy(self.messages);missing.pop(0);cases.append(missing)
        duplicate=copy.deepcopy(self.messages);duplicate.insert(0,copy.deepcopy(duplicate[0]));cases.append(duplicate)
        unknown=copy.deepcopy(self.messages);unknown[0]['target']['name']='not-an-owned-target';cases.append(unknown)
        shared=copy.deepcopy(self.messages);shared[1]['executable']=shared[0]['executable'];cases.append(shared)
        for rows in cases:
            self.messages=rows;self.write_messages()
            result,report=self.run_helper()
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(report['complete'])
            self.assertTrue(report['errors'])

    def test_compiler_failure_terminal_missing_and_truncated_json_refused(self):
        result,report=self.run_helper(9)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(report['binaries'],[])
        for rows in (self.artifacts, self.artifacts+[{'reason':'build-finished','success':False}],
                     self.messages+[{'reason':'surprise'}],
                     self.artifacts+[{'reason':'new-cargo-event'}]+[{'reason':'build-finished','success':True}]):
            self.messages=rows;self.write_messages()
            result,report=self.run_helper()
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(report['complete'])
        self.build.write_text('{"reason":')
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_summary_duplicates_unknown_stdout_and_nonzero_exit_retain_binary_receipt(self):
        for output,ignored,code in [
                ('same: test\n2 tests, 0 benchmarks\n','0 tests, 0 benchmarks\n',0),
                ('same: test\nsame: test\n2 tests, 0 benchmarks\n','0 tests, 0 benchmarks\n',0),
                ('unrecognized output\n1 test, 0 benchmarks\n','0 tests, 0 benchmarks\n',0),
                ('same: test\n1 test, 0 benchmarks\n','absent: test\n1 test, 0 benchmarks\n',0),
                ('same: test\n1 test, 0 benchmarks\n','0 tests, 0 benchmarks\n',4)]:
            self.harness(self.executables[0],output,ignored,code)
            result,report=self.run_helper()
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(report['complete'])
            self.assertEqual(report['binaries'][0]['binary_sha256'],hashlib.sha256(self.executables[0].read_bytes()).hexdigest())
            self.assertTrue(report['binaries'][0]['listing']['all']['argv'])
            self.assertTrue((self.raw/'00-all.stdout.txt').exists())

    def test_effective_artifact_profile_must_match_requested_ci_profile(self):
        self.messages[0]['profile']['overflow_checks']=False
        self.write_messages()
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_unknown_metadata_structures_refuse_with_error_report(self):
        missing=copy.deepcopy(self.metadata)
        missing['workspace_members'].append('path+file:///missing-owned-member#extra@0.1.0')
        malformed=copy.deepcopy(self.metadata);malformed['packages']=[None]
        for metadata in (malformed,missing):
            self.metadata_path.write_text(json.dumps(metadata))
            result,report=self.run_helper()
            self.assertNotEqual(result.returncode,0)
            self.assertIsNotNone(report)
            self.assertFalse(report['complete'])
            self.assertTrue(report['errors'])

    def test_empty_complete_listing_and_nonregular_or_outside_executable_refused(self):
        for exe in self.executables:
            self.harness(exe,'0 tests, 0 benchmarks\n','0 tests, 0 benchmarks\n')
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(report['tests_discovered'],0)
        self.assertFalse(report['complete'])
        original=self.executables[0].read_bytes()
        self.executables[0].unlink()
        outside=Path(self.tmp.name)/'outside-harness'
        outside.write_bytes(original);outside.chmod(0o755)
        self.executables[0].symlink_to(outside)
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])
        self.messages[0]['executable']=str(outside)
        self.write_messages()
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_binary_mutation_and_dirty_rust_source_refused(self):
        executable=self.executables[0]
        executable.write_text('#!'+sys.executable+'\nfrom pathlib import Path\nimport sys\n'
          + 'p=Path(__file__);p.write_text(p.read_text()+"\\n# mutated\\n")\n'
          + 'print("0 tests, 0 benchmarks" if "--ignored" in sys.argv else "same: test\\n1 test, 0 benchmarks")\n')
        executable.chmod(0o755)
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])
        self.write('evas/rust_core/src/main.rs','fn main() { panic!("changed"); }\n')
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_ci_uses_one_fixed_rust_toolchain(self):
        root=HELPER.parents[2]
        main=root/'.github/workflows/numerical-assurance.yml'
        text=main.read_text()
        pins=re.findall(r"^  RUSTUP_TOOLCHAIN: '([^']*)'$",text,re.M)
        self.assertEqual(len(pins),1)
        self.assertRegex(pins[0],r'^[0-9]+\.[0-9]+\.[0-9]+$')
        self.assertRegex(text,r"(?m)^env:\n  RUSTUP_TOOLCHAIN: '")
        # Every workflow, reusable workflow and composite action, not only the caller.
        ci=sorted([*(root/'.github/workflows').glob('*.yml'),*(root/'.github/actions').glob('**/action.yml')])
        self.assertIn(root/'.github/workflows/package-install.yml',ci)
        self.assertIn(root/'.github/actions/rust-cache/action.yml',ci)
        channel=(r'\+stable',r'(?:toolchain install|update|default|override set)\s+stable\b',
                 r'(?m)^\s*(?:- )?toolchain:\s*[\'"]?stable\b',r'RUSTUP_TOOLCHAIN:\s*[\'"]?stable\b')
        for path in [*ci,HELPER,root/'scripts/ci_evidence.py',root/'scripts/ci_lint.py']:
            with self.subTest(path=path.name):
                for pattern in channel:self.assertNotRegex(path.read_text(),pattern)
        # The one source line that still names the pre-pin channel admits historical receipts only.
        listing=(root/'evas/capabilities/rust_listing.py').read_text().splitlines()
        self.assertEqual([line.split(' =')[0] for line in listing if '+stable' in line],['HISTORICAL_TOOLCHAIN_ARGV'])
        # One authoritative literal: no other CI file repeats the version or assigns a version literal.
        self.assertEqual({path.name:path.read_text().count(pins[0]) for path in ci if pins[0] in path.read_text()},{main.name:1})
        for path in ci:
            if path!=main:
                with self.subTest(literal=path.name):
                    self.assertNotRegex(path.read_text(),r'RUSTUP_TOOLCHAIN:\s*[\'"]?[0-9]')
        # Allowed exception: fuzz-smoke installs and names nightly, which cargo-fuzz requires.
        for path in ci:
            installs=re.findall(r'rustup toolchain install (\S+)',path.read_text())
            with self.subTest(installs=path.name):
                self.assertTrue(all(name=='"$RUSTUP_TOOLCHAIN"' or (path==main and name=='nightly') for name in installs),installs)
        self.assertEqual(re.findall(r'rustup toolchain install (\S+)',text).count('nightly'),1)
        fuzz=re.search(r'^  fuzz-smoke:\n(.*?)(?=^  package:)',text,re.M|re.S).group(1)
        self.assertIn('rustup toolchain install nightly',fuzz)
        self.assertEqual(re.findall(r'\bcargo (?!\+nightly)\S+',fuzz),[])
        # Every toolchain selection anywhere in CI is an authoritative reference; see test_toolchain_selection_is_a_whitelist.

    def test_toolchain_selection_is_a_whitelist(self):
        root=HELPER.parents[2]
        paths=sorted([*(root/'.github/workflows').glob('*.yml'),*(root/'.github/actions').glob('**/action.yml')])
        texts={str(path.relative_to(root)):path.read_text() for path in paths}
        self.assertIn(CACHE_ACTION,texts)
        self.assertIn('.github/workflows/package-install.yml',texts)
        self.assertEqual(toolchain_selection_violations(texts,toolchain_files(root)),[])
        counts={}
        for form,location,value,changed,files,expect_reject in selection_variant_cases(texts):
            found=toolchain_selection_violations(changed,files)
            counts.setdefault(expect_reject,[0,0]);counts[expect_reject][0]+=1
            counts[expect_reject][1]+=bool(found)==expect_reject
            if bool(found)!=expect_reject:self.fail(f'{form} at {location} with {value}: expected reject={expect_reject}, got {found}')
        self.assertGreater(counts[True][0],500)
        self.assertGreater(counts[False][0],10)
        self.assertEqual({key:value[0]==value[1] for key,value in counts.items()},{True:True,False:True})

    def test_historical_toolchain_allowance_has_one_call_site(self):
        root=HELPER.parents[2]
        # Only reconcile reads a bound historical receipt; actual, generated and traced receipts use the strict default.
        self.assertEqual(historical_checked_calls(root),[('evas/capabilities/rust_listing.py','reconcile',('True',))])
        source=(root/'evas/capabilities/rust_listing.py').read_text()
        self.assertEqual(re.findall(r'checked\((\w+),historical=True\)',source),['expected_receipt'])
        self.assertEqual(re.findall(r'actual=checked\(receipt\)',source),['actual=checked(receipt)'])
        # The scanner sees a second call however it is spelled.
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Path(tmp)
            (fixture/'scripts').mkdir();(fixture/'evas').mkdir()
            (fixture/'scripts/new.py').write_text('import rl\ndef read(receipt):\n    return rl.checked(receipt, historical=True)\n')
            (fixture/'evas/more.py').write_text('def read(receipt, **options):\n    return checked(receipt, **options)\n'
                                                'def other(receipt, flag):\n    return checked(receipt, historical=flag)\n')
            self.assertEqual(historical_checked_calls(fixture),[('evas/more.py','other',('flag',)),('evas/more.py','read',('options',)),
                                                               ('scripts/new.py','read',('True',))])

    def test_reusable_workflows_take_the_fixed_toolchain_from_their_caller(self):
        root=HELPER.parents[2]
        main=(root/'.github/workflows/numerical-assurance.yml').read_text()
        # selection is the one job that reads the workflow-level env into an output.
        selection=re.search(r'^  selection:\n(.*?)(?=^  fast-checks:)',main,re.M|re.S).group(1)
        self.assertEqual(re.findall(r'^      rust_toolchain: (.*)$',selection,re.M),['${{ env.RUSTUP_TOOLCHAIN }}'])
        parts=re.split(r'(?m)^  ([a-z-]+):\n',main[main.index('\njobs:\n'):])
        jobs=dict(zip(parts[1::2],parts[2::2]))
        reusable=[path for path in sorted((root/'.github/workflows').glob('*.yml')) if re.search(r'(?m)^  workflow_call:',path.read_text())]
        self.assertIn('package-install.yml',[path.name for path in reusable])
        for path in reusable:
            text=path.read_text()
            if not re.search(r'\b(?:rustup|cargo|rustc|maturin)\b|rust-cache|python -m build|pip wheel',text):continue
            with self.subTest(workflow=path.name):
                block=re.search(r'^  workflow_call:\n    inputs:\n(.*?)(?=^    outputs:|^[a-z])',text,re.M|re.S)
                self.assertIsNotNone(block,'a Rust-using reusable workflow must declare the toolchain input')
                self.assertEqual(re.findall(r'^      ([a-z_]+):\n',block.group(1),re.M),['rust_toolchain'])
                self.assertNotIn('default:',block.group(1))
                self.assertIn('        required: true\n',block.group(1))
                self.assertEqual(re.findall(r'^ *RUSTUP_TOOLCHAIN: (.*)$',text,re.M),['${{ inputs.rust_toolchain }}'])
                self.assertEqual(re.findall(r'rustup toolchain install (\S+)',text),['"$RUSTUP_TOOLCHAIN"'])
                callers=[body for body in jobs.values() if '    uses: ./.github/workflows/'+path.name+'\n' in body]
                self.assertTrue(callers,'a reusable Rust workflow needs a caller that passes the toolchain')
                for body in callers:
                    self.assertIn('    with:\n      rust_toolchain: ${{ needs.selection.outputs.rust_toolchain }}\n',body)
                    self.assertRegex(body,r'(?m)^    needs: \[selection[,\]]')

    def test_real_workflow_listing_block_keeps_build_failure_and_raw_artifacts(self):
        workflow=HELPER.parents[2]/'.github/workflows/numerical-assurance.yml'
        text=workflow.read_text()
        job=re.search(r'^  rust-regression:\n(.*?)(?=^  regression:)',text,re.M|re.S).group(1)
        self.assertIn('run: cargo test --locked --workspace --manifest-path evas/rust_core/Cargo.toml',job)
        self.assertNotIn('continue-on-error',job)
        self.assertIn('if: always()',job)
        self.assertNotIn('target/debug/deps',job)
        self.assertIn('--require-catalog evas/capabilities/data',job)
        self.assertIn('--listing-profile linux-x86_64-regression-opt1-v1',job)
        self.assertIn('--source-repository vaevas=.',job)
        lines=job.splitlines()
        start=next(i for i,line in enumerate(lines) if line=='      - name: Collect actual owned Rust binary listing')
        run=next(i for i in range(start,len(lines)) if lines[i]=='        run: |')
        body=[]
        for line in lines[run+1:]:
            if line and not line.startswith('          '): break
            body.append(line)
        body=textwrap.dedent('\n'.join(body))+'\n'
        self.assertEqual(subprocess.run(['bash','-n'],input=body,text=True,capture_output=True).returncode,0)
        self.write('scripts/capabilities/discover_rust.py',HELPER.read_text())
        # This workflow plumbing fixture uses a labelled catalogue stub. The
        # independent catalogue tests exercise the real immutable-source protocol.
        self.write('evas/capabilities/registry.py', '''
import os
from pathlib import Path
class StubCatalog:
    def reconcile_rust_listing(self, receipt, *, profile):
        assert profile == 'linux-x86_64-regression-opt1-v1'
        if os.environ['FIXTURE_CATALOG_RECONCILED'] != 'true':
            raise ValueError('explicit fixture catalogue refusal')
        return {'reconciled': True, 'scope': 'fixture plumbing only'}
class StubRegistry:
    def catalog(self):
        return StubCatalog()
def load(data_dir, *, root, repositories):
    assert Path(data_dir) == Path('evas/capabilities/data')
    assert Path(root).resolve() == Path.cwd()
    assert repositories == {'vaevas': Path('.')}
    return StubRegistry()
''')
        for code, admitted in ((0,True),(9,True),(0,False)):
            result=subprocess.run(['bash','-e','-c',body],cwd=self.repo,
                                  env=dict(self.env,FIXTURE_BUILD_EXIT=str(code),
                                           FIXTURE_CATALOG_RECONCILED=str(admitted).lower()),capture_output=True,text=True)
            report=json.loads((self.repo/'runs/rust-test-listing.json').read_text())
            self.assertEqual(result.returncode,0 if code==0 and admitted else 1,result.stdout+result.stderr)
            self.assertEqual(report['complete'],code==0)
            self.assertEqual(report['catalog_reconciliation']['reconciled'],code==0 and admitted)
            self.assertTrue((self.repo/'runs/rust-test-build.jsonl').exists())
            self.assertTrue((self.repo/'runs/rust-test-build.stderr.txt').exists())
            self.assertEqual(report['test_body_execution'],'not_observed_by_this_helper')

    def test_custom_harness_manifest_cannot_claim_native_test_listing(self):
        path=self.repo/'evas/rust_core/Cargo.toml'
        path.write_text(path.read_text()+'[[bin]]\nname="evas-kernel"\nharness=false\n')
        self.git('add','evas/rust_core/Cargo.toml')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','custom unsupported harness')
        result,report=self.run_helper()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(report['complete'])

    def test_actual_fake_harness_listings_have_independent_binary_denominators(self):
        result, report = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report['complete'])
        self.assertTrue(report['listing_only'])
        self.assertEqual(report['test_body_execution'], 'not_observed_by_this_helper')
        self.assertEqual(report['tests_discovered'], 3)
        self.assertEqual(report['ignored_tests_discovered'], 1)
        self.assertEqual({row['id'] for row in report['tests']},{
            'rust:evas-kernel@0.25.0/bin/evas-kernel::same',
            'rust:evas-kernel@0.25.0/bin/evas-kernel::ignored',
            'rust:evas-ir@0.1.0/lib/evas_ir::same'})
        self.assertEqual(report['source']['commit'], self.commit)
        self.assertEqual(report['binaries'][0]['binary_sha256'], hashlib.sha256(self.executables[0].read_bytes()).hexdigest())
        self.assertTrue((self.raw / '00-all.stdout.txt').exists())
        self.assertIn('FAKE-fixture-not-Rust', report['toolchain']['cargo']['stdout'])


if __name__ == '__main__':
    unittest.main()
