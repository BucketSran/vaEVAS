"""The CI workflows name fixed runner, interpreter and tool versions; no simulator runs here.

This module owns the runner labels, the Python patch releases, the ngspice package and the build tool. It says nothing
about Rust: every Rust toolchain selection (the one pinned value, the whitelist of selections, the reusable-workflow
input, fuzz-smoke's single dated nightly) is judged by scripts/tests/test_discover_rust.py, so the two never repeat
or contradict each other.
"""
from pathlib import Path
import re
import shlex
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / '.github/workflows'
RUNNERS = ('ubuntu-24.04', 'macos-14')
PATCH_RELEASE = re.compile(r'3\.[0-9]+\.[0-9]+')
WATCHED = {'runs-on', 'runner', 'python-version', 'python-version-file', 'python'}
KEY_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*')
BLOCK_HEADER = re.compile(r'([|>])([+-]?)([0-9]*)$')


def code(path):
    """Workflow lines without whole-line YAML or shell comments, so a comment cannot satisfy a pin."""
    return [line for line in path.read_text().splitlines() if not line.lstrip().startswith('#')]


class _WorkflowText:
    """Workflow YAML subset. Unknown structure raises instead of skipping a watched key."""

    def __init__(self, text):
        if '\t' in text or text.startswith('\ufeff'):
            raise AssertionError('unsupported YAML whitespace')
        self.lines = text.splitlines()
        self.n = len(self.lines)
        self.i = 0
        self.watched = []
        self.runs = []

    def parse(self):
        self._block(-1)
        self._skip()
        if self.i < self.n:
            raise AssertionError('unparsed YAML at line %d: %r' % (self.i + 1, self.lines[self.i]))
        return self.watched, self.runs

    def _skip(self):
        while self.i < self.n:
            if self.lines[self.i].strip() == '' or self.lines[self.i].lstrip().startswith('#'):
                self.i += 1
                continue
            return

    def _indent(self):
        return len(self.lines[self.i]) - len(self.lines[self.i].lstrip(' '))

    def _block(self, minimum):
        self._skip()
        if self.i >= self.n or self._indent() <= minimum:
            return None
        indent = self._indent()
        content = self.lines[self.i][indent:]
        if content == '-' or content.startswith('- '):
            return self._sequence(indent)
        return self._mapping(indent)

    def _mapping(self, indent):
        found = {}
        while True:
            self._skip()
            if self.i >= self.n or self._indent() != indent:
                return found
            content = self.lines[self.i][indent:]
            if content == '-' or content.startswith('- '):
                raise AssertionError('sequence item where a key was required at line %d' % (self.i + 1))
            key, value = self._entry(indent)
            found[key] = value

    def _entry(self, indent):
        content = self.lines[self.i][indent:]
        key, rest = self._key(content, required=True)
        self.i += 1
        value = self._value(rest, indent)
        self._capture(key, value)
        return key, value

    def _sequence(self, indent):
        items = []
        while True:
            self._skip()
            if self.i >= self.n or self._indent() != indent:
                return items
            content = self.lines[self.i][indent:]
            if content != '-' and not content.startswith('- '):
                return items
            items.append(self._item(indent))

    def _item(self, indent):
        content = self.lines[self.i][indent:]
        if content == '-' or content.startswith('-#'):
            self.i += 1
            return self._block(indent)
        if not content.startswith('- '):
            raise AssertionError('unsupported sequence marker at line %d' % (self.i + 1))
        body = content[2:]
        column = indent + 2
        if body.strip() == '' or body.lstrip().startswith('#'):
            self.i += 1
            return self._block(indent)
        self.i += 1
        if body[0] in '{[':
            return self._flow(body)
        if body[0] in '|>' and BLOCK_HEADER.fullmatch(body.split('#', 1)[0].strip()):
            return self._literal(body, indent)
        key, rest = self._key(body, required=False)
        if key is None:
            return self._scalar(body)
        value = self._value(rest, column)
        self._capture(key, value)
        found = {key: value}
        found.update(self._mapping(column))
        return found

    def _key(self, content, required):
        if content[:1] in "'\"":
            try:
                key, rest = self._quoted(content)
            except AssertionError:
                if required:
                    raise
                return None, content
            tail = rest.lstrip(' ')
            if tail.startswith(':'):
                return key, tail[1:]
            if required:
                raise AssertionError('unsupported quoted key %r' % content)
            return None, content
        match = re.match(r'([A-Za-z_][A-Za-z0-9_-]*):(.*)$', content)
        if match and KEY_NAME.fullmatch(match.group(1)):
            return match.group(1), match.group(2)
        if required:
            raise AssertionError('unsupported key form: %r' % content)
        return None, content

    def _value(self, rest, indent):
        text = rest.lstrip(' ')
        if text == '' or text.startswith('#'):
            return self._block(indent)
        if text[0] in '|>' and BLOCK_HEADER.fullmatch(text.split('#', 1)[0].strip()):
            return self._literal(text, indent)
        if text[0] in '{[':
            return self._flow(text)
        if text[0] in "'\"":
            value, tail = self._quoted(text)
            self._tail(tail)
            return value
        if text[0] in '&*!?' :
            raise AssertionError('unsupported YAML value: %r' % text)
        return self._plain(text)

    def _literal(self, header, key_indent):
        token = header.split('#', 1)[0].strip()
        match = BLOCK_HEADER.fullmatch(token)
        if not match:
            raise AssertionError('unsupported block scalar %r' % header)
        style, chomp, width = match.groups()
        explicit = int(width) if width else None
        raw = []
        content_indent = None
        while self.i < self.n:
            line = self.lines[self.i]
            if line.strip() == '':
                raw.append('')
                self.i += 1
                continue
            indent = len(line) - len(line.lstrip(' '))
            if indent <= key_indent:
                break
            if content_indent is None:
                content_indent = key_indent + explicit if explicit is not None else indent
            if indent < content_indent:
                break
            raw.append(line[content_indent:])
            self.i += 1
        if style == '|':
            text = '\n'.join(raw) + ('\n' if raw else '')
        else:
            text = _fold(raw)
        if chomp == '-':
            return text.rstrip('\n')
        if chomp == '+':
            return text
        stripped = text.rstrip('\n')
        return stripped + ('\n' if stripped else '')

    def _flow(self, first):
        text = self._take_flow(first)
        value, index = self._flow_node(text, 0)
        self._tail(text[index:])
        return value

    def _take_flow(self, first):
        chunks = [first]
        text = first
        while not _flow_closed(text):
            if self.i >= self.n:
                raise AssertionError('unclosed flow collection')
            chunks.append(self.lines[self.i])
            self.i += 1
            text = '\n'.join(chunks)
        return text

    def _flow_node(self, text, index):
        index = _flow_space(text, index)
        if index >= len(text):
            raise AssertionError('missing flow value')
        mark = text[index]
        if mark == '{':
            return self._flow_map(text, index)
        if mark == '[':
            return self._flow_list(text, index)
        if mark in "'\"":
            value, rest = self._quoted(text[index:])
            return value, index + len(text[index:]) - len(rest)
        if mark in '&*!?':
            raise AssertionError('unsupported flow node')
        return _flow_plain(text, index)

    def _flow_map(self, text, index):
        index += 1
        found = {}
        while True:
            index = _flow_space(text, index)
            if index < len(text) and text[index] == '}':
                return found, index + 1
            key, index = self._flow_key(text, index)
            index = _flow_space(text, index)
            if index >= len(text) or text[index] != ':':
                raise AssertionError('flow mapping is missing a colon')
            value, index = self._flow_node(text, index + 1)
            self._capture(key, value)
            found[key] = value
            index = _flow_space(text, index)
            if index < len(text) and text[index] == ',':
                index += 1
                continue
            if index < len(text) and text[index] == '}':
                return found, index + 1
            raise AssertionError('unsupported flow mapping near %r' % text[index:index + 24])

    def _flow_list(self, text, index):
        index += 1
        items = []
        while True:
            index = _flow_space(text, index)
            if index < len(text) and text[index] == ']':
                return items, index + 1
            value, index = self._flow_node(text, index)
            items.append(value)
            index = _flow_space(text, index)
            if index < len(text) and text[index] == ',':
                index += 1
                continue
            if index < len(text) and text[index] == ']':
                return items, index + 1
            raise AssertionError('unsupported flow sequence near %r' % text[index:index + 24])

    def _flow_key(self, text, index):
        index = _flow_space(text, index)
        if index >= len(text):
            raise AssertionError('missing flow key')
        if text[index] in "'\"":
            key, rest = self._quoted(text[index:])
            return key, index + len(text[index:]) - len(rest)
        start = index
        while index < len(text) and text[index] not in ':{}\n,#[]':
            index += 1
        key = text[start:index].strip()
        if not KEY_NAME.fullmatch(key):
            raise AssertionError('unsupported flow key %r' % key)
        return key, index

    def _quoted(self, text):
        quote = text[0]
        chars = []
        index = 1
        while index < len(text):
            char = text[index]
            if quote == "'":
                if char == "'":
                    if index + 1 < len(text) and text[index + 1] == "'":
                        chars.append("'")
                        index += 2
                        continue
                    return ''.join(chars), text[index + 1:]
                chars.append(char)
                index += 1
                continue
            if char == '\\':
                if index + 1 >= len(text):
                    raise AssertionError('unsupported split double-quoted scalar')
                escaped = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '"': '"', '/': '/'}.get(text[index + 1])
                if escaped is None:
                    raise AssertionError('unsupported YAML escape \\%s' % text[index + 1])
                chars.append(escaped)
                index += 2
                continue
            if char == '"':
                return ''.join(chars), text[index + 1:]
            chars.append(char)
            index += 1
        raise AssertionError('unclosed quoted scalar')

    def _plain(self, text):
        chars = []
        for index, char in enumerate(text):
            if char == '#' and (index == 0 or text[index - 1] == ' '):
                break
            chars.append(char)
        return ''.join(chars).strip()

    def _scalar(self, body):
        if body[0] in "'\"":
            value, tail = self._quoted(body)
            self._tail(tail)
            return value
        if body[0] in '&*!?':
            raise AssertionError('unsupported YAML scalar %r' % body)
        return self._plain(body)

    def _tail(self, tail):
        rest = tail.strip()
        if rest and not rest.startswith('#'):
            raise AssertionError('unsupported trailing YAML %r' % rest)

    def _capture(self, key, value):
        if key in WATCHED:
            if not isinstance(value, str):
                raise AssertionError('unsupported %s form' % key)
            self.watched.append((key, value))
        elif key == 'run':
            if not isinstance(value, str):
                raise AssertionError('unsupported run form')
            self.runs.append(value)


def _fold(lines):
    parts = []
    paragraph = []

    def flush():
        if paragraph:
            parts.append(' '.join(paragraph))
            paragraph.clear()

    for line in lines:
        if line == '':
            flush()
            parts.append('')
        else:
            paragraph.append(line.strip())
    flush()
    text = []
    for part in parts:
        if part == '':
            if text and not text[-1].endswith('\n'):
                text.append('\n')
            text.append('\n')
        else:
            if text and not text[-1].endswith('\n'):
                text.append('\n')
            text.append(part)
    result = ''.join(text)
    if lines:
        result += '\n'
    return result


def _flow_space(text, index):
    while index < len(text):
        if text[index] in ' \t\r\n':
            index += 1
            continue
        if text[index] == '#' and (index == 0 or text[index - 1] in ' \t\r\n'):
            newline = text.find('\n', index)
            if newline < 0:
                return len(text)
            index = newline + 1
            continue
        return index
    return index


def _flow_closed(text):
    depth = 0
    quote = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote == "'":
            if char == "'" and index + 1 < len(text) and text[index + 1] == "'":
                index += 2
                continue
            if char == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if char == '\\':
                index += 2
                continue
            if char == '"':
                quote = None
            index += 1
            continue
        if char in "'\"":
            quote = char
            index += 1
            continue
        if char == '#' and (index == 0 or text[index - 1] in ' \t\n'):
            newline = text.find('\n', index)
            if newline < 0:
                return False
            index = newline
            continue
        if char in '{[':
            depth += 1
        elif char in '}]':
            depth -= 1
            if depth == 0:
                return True
        index += 1
    return False


def _skip_expression(text, index):
    depth = 0
    index += 2
    while index < len(text):
        if text[index] == '{':
            depth += 1
        elif text[index] == '}':
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise AssertionError('unclosed ${{ }} expression')


def _flow_plain(text, index):
    start = index
    while index < len(text):
        if text.startswith('${{', index):
            index = _skip_expression(text, index)
            continue
        char = text[index]
        if char in '}],':
            break
        if char == '#' and (index == start or text[index - 1] in ' \t\n'):
            break
        if char in '{[':
            raise AssertionError('unsupported flow scalar')
        index += 1
    value = text[start:index].strip()
    if value == '':
        raise AssertionError('empty flow scalar')
    return value, index


def load_text(text):
    """Watched keys and run scalars; an unreadable form fails the caller."""
    parser = _WorkflowText(text)
    parser.parse()
    return parser.watched, parser.runs


def values(path, *keys):
    """Every value of the given keys. Quoted keys, flow maps and flow lists are included."""
    watched, _runs = load_text(path.read_text())
    return [(key, value) for key, value in watched if key in keys]


def _logical_lines(script):
    """Join a continued apt/pip line; leave every other line untouched."""
    lines = []
    pending = None
    for line in script.splitlines():
        current = line if pending is None else pending + ' ' + line.strip()
        stripped = current.rstrip()
        continued = (len(stripped) - len(stripped.rstrip('\\'))) % 2 == 1
        interesting = pending is not None or 'apt-get' in current or 'pip' in current
        if interesting and continued:
            pending = stripped[:-1]
            continue
        if interesting:
            lines.append(current)
        pending = None
    if pending is not None:
        lines.append(pending)
    return lines


def run_commands(scripts):
    """Shell words of apt-get and pip lines inside real run scripts."""
    commands_found = []
    for script in scripts:
        for line in _logical_lines(script):
            try:
                words = shlex.split(line, comments=True)
            except ValueError as exc:
                raise AssertionError('unparsed shell command: %r' % line) from exc
            if words:
                commands_found.append(words)
    return commands_found


def run_scripts(path):
    _watched, runs = load_text(path.read_text())
    return runs


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
                self.assertNotIn('python-version-file', [key for key, _value in found])
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

    def test_ngspice_and_build_tool_are_pinned(self):
        _watched, assurance_runs = load_text((WORKFLOWS / 'numerical-assurance.yml').read_text())
        ngspice = [word for words in run_commands(assurance_runs) if 'apt-get' in words and 'install' in words for word in words if word.startswith('ngspice')]
        self.assertTrue(ngspice)
        self.assertEqual(set(ngspice), {'ngspice=42+ds-3build1'})
        builds = [word for words in run_commands(run_scripts(WORKFLOWS / 'package-install.yml')) if 'pip' in words for word in words if re.match(r'build\b', word)]
        self.assertEqual(builds, ['build==1.6.1'])

    def test_quoted_flow_and_decoy_forms_cannot_hide_a_pin(self):
        """Keys in quotes or flow collections are read; comments and step names are not commands."""
        samples = {
            'quoted-matrix-python-key': ('"python": "3.10"\n', [('python', '3.10')]),
            'quoted-matrix-runner-key': ('"runner": macos-latest\n', [('runner', 'macos-latest')]),
            'quoted-runs-on-key': ('"runs-on": ubuntu-latest\n', [('runs-on', 'ubuntu-latest')]),
            'single-quoted-runner-key': ("'runner': 'macos-latest'\n", [('runner', 'macos-latest')]),
            'flow-matrix-row': (
                'include:\n  - {runner: ubuntu-latest, arch: x86_64, python: "3.10"}\n',
                [('runner', 'ubuntu-latest'), ('python', '3.10')],
            ),
            'flow-sequence-row': (
                'include:\n  - [{runner: ubuntu-latest, python: "3.10"}]\n',
                [('runner', 'ubuntu-latest'), ('python', '3.10')],
            ),
            'flow-setup-step': (
                '- {uses: actions/setup-python@abc, with: {"python-version": "3.12"}}\n',
                [('python-version', '3.12')],
            ),
            'quoted-fixed-values': (
                'runs-on: "ubuntu-24.04"\npython-version: \'3.12.15\' # pinned\npython: 3.12.15\n',
                [('runs-on', 'ubuntu-24.04'), ('python-version', '3.12.15'), ('python', '3.12.15')],
            ),
        }
        for name, (text, expected) in samples.items():
            with self.subTest(form=name):
                watched, _runs = load_text(text)
                self.assertEqual(watched, expected)
        for name, text in {
            'anchor': 'runs-on: &label ubuntu-24.04\n',
            'alias': 'runs-on: *label\n',
            'complex-key': '? runs-on\n: ubuntu-24.04\n',
            'non-scalar': 'python: [3.12.15]\n',
        }.items():
            with self.subTest(form=name):
                with self.assertRaises(AssertionError):
                    load_text(text)
        decoy = (
            'steps:\n'
            '  - name: apt-get install ngspice=42+ds-3build1\n'
            '    run: "sudo apt-get update && sudo apt-get install -y ngspice"\n'
        )
        ngspice = [word for words in run_commands(load_text(decoy)[1]) if 'apt-get' in words and 'install' in words for word in words if word.startswith('ngspice')]
        self.assertEqual(ngspice, ['ngspice'])
        comment = 'run: sudo apt-get install -y ngspice # ngspice=42+ds-3build1\n'
        commented = [word for words in run_commands(load_text(comment)[1]) for word in words if word.startswith('ngspice')]
        self.assertEqual(commented, ['ngspice'])
        folded = 'run: >-\n  sudo apt-get install -y\n  ngspice=42+ds-3build1\n'
        folded_words = [word for words in run_commands(load_text(folded)[1]) for word in words if word.startswith('ngspice')]
        self.assertEqual(folded_words, ['ngspice=42+ds-3build1'])
        continued = 'run: |\n  sudo apt-get install -y \\\n    ngspice=42+ds-3build1\n'
        continued_words = [word for words in run_commands(load_text(continued)[1]) for word in words if word.startswith('ngspice')]
        self.assertEqual(continued_words, ['ngspice=42+ds-3build1'])
        build = 'steps:\n  - name: pip install build==1.6.1\n    run: "python -m pip install build"\n'
        builds = [word for words in run_commands(load_text(build)[1]) if 'pip' in words for word in words if re.match(r'build\b', word)]
        self.assertEqual(builds, ['build'])
        hidden = '# runs-on: ubuntu-latest\nruns-on: ubuntu-24.04\n'
        self.assertEqual(load_text(hidden)[0], [('runs-on', 'ubuntu-24.04')])


if __name__ == '__main__':
    unittest.main()
