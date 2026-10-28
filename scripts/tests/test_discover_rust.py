"""Actual CLI plumbing with fake tools/harnesses; no Rust compilation or science."""
import hashlib
import contextlib
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
FUZZ_JOB = 'fuzz-smoke'
# GitHub runs workflows named *.yml or *.yaml and composite actions defined in action.yml or action.yaml.
WORKFLOW_SUFFIXES = ('.yml', '.yaml')
ACTION_NAMES = ('action.yml', 'action.yaml')
# Authoritative references: the single pinned literal is reached only through these.
AUTHORITATIVE = frozenset(['$RUSTUP_TOOLCHAIN', '${RUSTUP_TOOLCHAIN}', '${{ inputs.rust_toolchain }}',
                           '${{ needs.selection.outputs.rust_toolchain }}', '${{ env.RUSTUP_TOOLCHAIN }}'])
CACHE_EXPANSION = '${CI_RUST_TOOLCHAIN:++"$CI_RUST_TOOLCHAIN"}'
TOOLS = ('cargo', 'rustc', 'rustdoc', 'rustfmt', 'cargo-clippy', 'cargo-fmt', 'clippy-driver')


def ci_files(root):
    """Every file CI runs: .github/workflows/*.yml and *.yaml, and action.yml / action.yaml under .github/actions."""
    root = Path(root)
    found = []
    if (root / '.github/workflows').is_dir():
        found.extend(path for path in (root / '.github/workflows').iterdir()
                     if path.is_file() and path.suffix in WORKFLOW_SUFFIXES)
    if (root / '.github/actions').is_dir():
        found.extend(path for path in (root / '.github/actions').rglob('*') if path.is_file() and path.name in ACTION_NAMES)
    return sorted(found)


def ci_texts(root):
    """Repo-relative path -> text of every CI file under root."""
    root = Path(root)
    return {str(path.relative_to(root)): path.read_text() for path in ci_files(root)}


class CiYamlError(ValueError):
    """CI uses YAML this reader does not analyse. The guard reports it instead of skipping the file."""


class _Str(str):
    """A parsed scalar that remembers how it was written: plain, single, double, literal (|) or folded (>)."""
    style = 'plain'


class _Map(dict):
    flow = False


def _scalar(value, style):
    result = _Str(value)
    result.style = style
    return result


def _skip_expression(text, index):
    """Index after the ${{ ... }} expression that starts at text[index].

    GitHub reads an expression as one unit, so a comma, colon or hash inside it never ends a scalar here.
    A strict YAML parser would split some of these scalars (or refuse them); the reader is only more
    permissive than YAML for text that is not a valid workflow anyway.
    """
    depth = 0
    index += 3
    while index < len(text):
        char = text[index]
        if char == "'":
            index += 1
            while index < len(text) and (text[index] != "'" or text[index + 1:index + 2] == "'"):
                index += 2 if text[index] == "'" else 1
        elif char == '{':
            depth += 1
        elif char == '}':
            if depth:
                depth -= 1
            elif text.startswith('}}', index):
                return index + 2
        index += 1
    raise CiYamlError('unclosed ${{ }} expression')


def _outside_expressions(text):
    """Yield (index, character) of text outside ${{ }} expressions."""
    index = 0
    while index < len(text):
        if text.startswith('${{', index):
            index = _skip_expression(text, index)
            continue
        yield index, text[index]
        index += 1


class _Yaml:
    """The YAML subset GitHub workflows use: block and flow collections, quoted, plain and block scalars.

    Anchors, aliases, tags, complex keys, merge keys, duplicate keys, tabs and several documents are errors.
    Every scalar stays a string, so nothing is silently reinterpreted.
    """

    def __init__(self, text):
        if text.startswith('\ufeff') or '\r' in text:
            raise CiYamlError('byte order mark or carriage return')
        self.lines = text.split('\n')
        # One leading `---` only opens the single document; any other marker or directive is refused.
        first = next((n for n, line in enumerate(self.lines) if line.strip() and not line.lstrip(' ').startswith('#')), None)
        if first is not None and self.lines[first].rstrip() == '---':
            self.lines[first] = ''
        for number, line in enumerate(self.lines, 1):
            if re.match(r' *\t', line):
                raise CiYamlError(f'line {number}: tab in indentation')
            if line.startswith(('---', '...', '%')):
                raise CiYamlError(f'line {number}: YAML document marker or directive')
        self.n = len(self.lines)
        self.i = 0

    def fail(self, why):
        raise CiYamlError(f'line {min(self.i + 1, self.n)}: {why}')

    def parse(self):
        value = self.node(-1)
        self.skip()
        if self.i < self.n:
            self.fail('content outside the document structure')
        return value

    def skip(self):
        while self.i < self.n and (not self.lines[self.i].strip() or self.lines[self.i].lstrip(' ').startswith('#')):
            self.i += 1

    def indent(self):
        line = self.lines[self.i]
        return len(line) - len(line.lstrip(' '))

    # ---- block structure -------------------------------------------------------------------------
    def node(self, parent):
        self.skip()
        if self.i >= self.n or self.indent() <= parent:
            return None
        indent = self.indent()
        text = self.lines[self.i][indent:]
        if text == '-' or text.startswith('- '):
            return self.sequence(indent)
        if self.split_key(text) is not None:
            return self.mapping(indent)
        self.i += 1
        return self.inline(text, parent)

    def sequence(self, indent):
        items = []
        while True:
            self.skip()
            if self.i >= self.n or self.indent() < indent:
                return items
            if self.indent() > indent:
                self.fail('unexpected indentation in a sequence')
            text = self.lines[self.i][indent:]
            if not (text == '-' or text.startswith('- ')):
                return items
            rest = text[1:]
            body = rest.lstrip(' ')
            if not body or body.startswith('#'):
                self.i += 1
                items.append(self.node(indent))
            else:
                self.lines[self.i] = ' ' * (indent + 1 + len(rest) - len(body)) + body
                items.append(self.node(indent))

    def mapping(self, indent):
        found = _Map()
        while True:
            self.skip()
            if self.i >= self.n or self.indent() < indent:
                return found
            if self.indent() > indent:
                self.fail('unexpected indentation in a mapping')
            text = self.lines[self.i][indent:]
            if text == '-' or text.startswith('- '):
                self.fail('sequence item where a mapping key was required')
            parsed = self.split_key(text)
            if parsed is None:
                self.fail('mapping key expected')
            key, rest = parsed
            if key == '<<':
                self.fail('merge key')
            if key in found:
                self.fail(f'duplicate key {key!r}')
            self.i += 1
            found[key] = self.value(rest, indent)

    def value(self, rest, parent):
        text = rest.strip(' ')
        if not text or text.startswith('#'):
            self.skip()
            if self.i < self.n and self.indent() == parent:
                line = self.lines[self.i][parent:]
                if line == '-' or line.startswith('- '):
                    return self.sequence(parent)
            return self.node(parent)
        return self.inline(text, parent)

    def split_key(self, text):
        """(key, text after the colon) when text starts a mapping entry, else None."""
        first = text[:1]
        if first in '"\'':
            try:
                key, tail = self.quoted_line(text)
            except CiYamlError:
                return None
            tail = tail.lstrip(' ')
            if tail[:1] == ':' and (len(tail) == 1 or tail[1] == ' '):
                return key, tail[1:]
            return None
        if first in '&*!':
            raise CiYamlError('anchor, alias or tag in a mapping key')
        if first == '?' and (len(text) == 1 or text[1] == ' '):
            raise CiYamlError('complex mapping key')
        if first in '[{|>%@`#':
            return None
        for index, char in _outside_expressions(text):
            if char == '#' and index and text[index - 1] == ' ':
                return None
            if char == ':' and (index + 1 == len(text) or text[index + 1] == ' '):
                key = text[:index].rstrip(' ')
                if not key:
                    return None
                return _scalar(key, 'plain'), text[index + 1:]
        return None

    # ---- scalars ---------------------------------------------------------------------------------
    def inline(self, text, parent):
        first = text[0]
        if first in '&*!':
            self.fail('anchor, alias or tag')
        if first in '|>':
            return self.block_scalar(text, parent)
        if first in '{[':
            return self.flow(text)
        if first in '\'"':
            return self.quoted_block(text)
        return self.plain_block(text, parent)

    def plain_block(self, text, parent):
        parts = []
        done = False
        while True:
            body, comment = self.plain_line(text)
            parts.append(body)
            if comment:
                done = True
            if done:
                break
            blanks = 0
            probe = self.i
            while probe < self.n and not self.lines[probe].strip():
                blanks += 1
                probe += 1
            if probe >= self.n or self.lines[probe].lstrip(' ').startswith('#'):
                break
            line = self.lines[probe]
            if len(line) - len(line.lstrip(' ')) <= parent:
                break
            parts.extend([''] * blanks)
            self.i = probe + 1
            text = line.strip(' ')
        return _scalar(self.fold(parts), 'plain')

    def plain_line(self, text):
        end = len(text)
        comment = False
        for index, char in _outside_expressions(text):
            if char == '#' and index and text[index - 1] == ' ':
                end, comment = index, True
                break
            if char == ':' and (index + 1 == len(text) or text[index + 1] == ' '):
                self.fail('mapping value in a plain scalar')
        return text[:end].rstrip(' '), comment

    @staticmethod
    def fold(parts):
        result = ''
        pending = 0
        for part in parts:
            if part == '':
                pending += 1
                continue
            if result:
                result += '\n' * pending if pending else ' '
            result += part
            pending = 0
        return result

    def quoted_line(self, text):
        """(value, text after the closing quote) for a quoted scalar that ends on this line."""
        value, rest = self.quoted(text)
        return value, rest

    def quoted_block(self, text):
        joined = text
        while True:
            try:
                value, rest = self.quoted(joined)
                break
            except CiYamlError as error:
                if 'unclosed' not in str(error) or self.i >= self.n:
                    raise
                joined += '\n' + self.lines[self.i]
                self.i += 1
        tail = rest.strip(' ')
        if tail and not tail.startswith('#'):
            self.fail('text after a quoted scalar')
        return _scalar(value, 'single' if text[0] == "'" else 'double')

    @staticmethod
    def quoted(text):
        quote = text[0]
        chars = []
        index = 1
        while index < len(text):
            char = text[index]
            if char == '\n':
                while chars and chars[-1] in ' ':
                    chars.pop()
                blanks = 0
                while index < len(text) and text[index] in '\n ':
                    blanks += text[index] == '\n'
                    index += 1
                chars.append('\n' * (blanks - 1) if blanks > 1 else ' ')
                continue
            if quote == "'":
                if char == "'":
                    if text[index + 1:index + 2] == "'":
                        chars.append("'")
                        index += 2
                        continue
                    return ''.join(chars), text[index + 1:]
                chars.append(char)
                index += 1
                continue
            if char == '\\':
                nxt = text[index + 1:index + 2]
                if nxt == '\n':
                    index += 2
                    while index < len(text) and text[index] in ' ':
                        index += 1
                    continue
                escaped = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '"': '"', '/': '/', '0': '\0', ' ': ' ',
                           '_': ' ', 'a': '\a', 'b': '\b', 'e': '\x1b', 'f': '\f', 'v': '\v'}.get(nxt)
                if nxt in ('x', 'u', 'U'):
                    width = {'x': 2, 'u': 4, 'U': 8}[nxt]
                    digits = text[index + 2:index + 2 + width]
                    if len(digits) != width or not re.fullmatch('[0-9A-Fa-f]+', digits):
                        raise CiYamlError('bad YAML escape')
                    chars.append(chr(int(digits, 16)))
                    index += 2 + width
                    continue
                if escaped is None:
                    raise CiYamlError('unsupported YAML escape')
                chars.append(escaped)
                index += 2
                continue
            if char == '"':
                return ''.join(chars), text[index + 1:]
            chars.append(char)
            index += 1
        raise CiYamlError('unclosed quoted scalar')

    def block_scalar(self, header, parent):
        match = re.fullmatch(r'([|>])(?:([1-9])([+-]?)|([+-]?)([1-9]?))\s*(?:#.*)?', header)
        if not match:
            self.fail(f'unsupported block scalar header {header!r}')
        style = match.group(1)
        digit = match.group(2) or match.group(5)
        chomp = match.group(3) if match.group(2) else match.group(4)
        content = max(parent, 0) + int(digit) if digit else None
        raw = []
        while self.i < self.n:
            line = self.lines[self.i]
            if not line.strip():
                raw.append(('', 0))
                self.i += 1
                continue
            indent = len(line) - len(line.lstrip(' '))
            if content is None:
                if indent <= parent:
                    break
                content = indent
            if indent < content:
                break
            raw.append((line[content:], indent))
            self.i += 1
        # Blank lines after the last content line belong to the chomping, not to the scalar body.
        body = [text for text, _indent in raw]
        trailing = 0
        while body and body[-1] == '':
            body.pop()
            trailing += 1
        kind = 'literal' if style == '|' else 'folded'
        text = '\n'.join(body) if style == '|' else self.fold_block(body)
        if not body:
            return _scalar('\n' * trailing if chomp == '+' else '', kind)
        if chomp == '-':
            return _scalar(text, kind)
        if chomp == '+':
            return _scalar(text + '\n' * (1 + trailing), kind)
        return _scalar(text + '\n', kind)

    @staticmethod
    def fold_block(lines):
        result = ''
        previous = None
        pending = 0
        for line in lines:
            if line == '':
                pending += 1
                continue
            if previous is not None:
                spaced = line[:1] in ' \t' or previous[:1] in ' \t'
                if pending:
                    result += '\n' * (pending + (1 if spaced else 0))
                else:
                    result += '\n' if spaced else ' '
            result += line
            previous = line
            pending = 0
        return result

    # ---- flow collections -------------------------------------------------------------------------
    def flow(self, first):
        text = first
        while not self.flow_closed(text):
            if self.i >= self.n:
                self.fail('unclosed flow collection')
            text += '\n' + self.lines[self.i]
            self.i += 1
        value, index = self.flow_node(text, 0)
        index = self.flow_space(text, index)
        if index < len(text):
            self.fail('text after a flow collection')
        return value

    @staticmethod
    def flow_closed(text):
        depth = 0
        quote = None
        index = 0
        while index < len(text):
            char = text[index]
            if quote == "'":
                if char == "'":
                    if text[index + 1:index + 2] == "'":
                        index += 2
                        continue
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
            if text.startswith('${{', index):
                index = _skip_expression(text, index)
                continue
            if char in '\'"':
                quote = char
            elif char == '#' and (index == 0 or text[index - 1] in ' \t\n'):
                newline = text.find('\n', index)
                if newline < 0:
                    return False
                index = newline
                continue
            elif char in '{[':
                depth += 1
            elif char in '}]':
                depth -= 1
                if depth == 0:
                    return True
            index += 1
        return False

    @staticmethod
    def flow_space(text, index):
        while index < len(text):
            if text[index] in ' \t\n':
                index += 1
            elif text[index] == '#' and (index == 0 or text[index - 1] in ' \t\n'):
                newline = text.find('\n', index)
                index = len(text) if newline < 0 else newline + 1
            else:
                break
        return index

    def flow_node(self, text, index):
        index = self.flow_space(text, index)
        if index >= len(text):
            raise CiYamlError('missing flow value')
        mark = text[index]
        if mark == '{':
            return self.flow_map(text, index + 1)
        if mark == '[':
            return self.flow_list(text, index + 1)
        if mark in '\'"':
            value, rest = self.quoted(text[index:])
            return _scalar(value, 'single' if mark == "'" else 'double'), len(text) - len(rest)
        if mark in '&*!?|>%@`':
            raise CiYamlError('unsupported flow node')
        return self.flow_plain(text, index)

    def flow_plain(self, text, index):
        start = index
        while index < len(text):
            if text.startswith('${{', index):
                index = _skip_expression(text, index)
                continue
            char = text[index]
            if char in ',]}':
                break
            if char == ':' and (index + 1 == len(text) or text[index + 1] in ' \n,]}'):
                break
            if char == '#' and text[index - 1] in ' \t\n':
                break
            if char in '{[':
                raise CiYamlError('unsupported flow scalar')
            index += 1
        value = re.sub(r'\s*\n\s*', ' ', text[start:index].strip())
        if not value:
            raise CiYamlError('empty flow scalar')
        return _scalar(value, 'plain'), index

    def flow_map(self, text, index):
        found = _Map()
        found.flow = True
        while True:
            index = self.flow_space(text, index)
            if index < len(text) and text[index] == '}':
                return found, index + 1
            key, index = self.flow_node(text, index)
            if not isinstance(key, str):
                raise CiYamlError('unsupported flow mapping key')
            index = self.flow_space(text, index)
            value = None
            if index < len(text) and text[index] == ':':
                index = self.flow_space(text, index + 1)
                if index < len(text) and text[index] not in ',}':
                    value, index = self.flow_node(text, index)
            if key in found:
                raise CiYamlError(f'duplicate key {key!r}')
            found[key] = value
            index = self.flow_space(text, index)
            if index < len(text) and text[index] == ',':
                index += 1
                continue
            if index < len(text) and text[index] == '}':
                return found, index + 1
            raise CiYamlError('unsupported flow mapping')

    def flow_list(self, text, index):
        items = []
        while True:
            index = self.flow_space(text, index)
            if index < len(text) and text[index] == ']':
                return items, index + 1
            value, index = self.flow_node(text, index)
            items.append(value)
            index = self.flow_space(text, index)
            if index < len(text) and text[index] == ',':
                index += 1
                continue
            if index < len(text) and text[index] == ']':
                return items, index + 1
            raise CiYamlError('unsupported flow sequence')


def parse_ci_yaml(text):
    """The document as nested dict / list / str; CiYamlError for anything outside the supported subset."""
    return _Yaml(text).parse()


AUTHORITATIVE_CHANNEL = re.compile(r'(?i)\b(nightly|stable|beta)\b')
TOOLCHAIN_KEY = re.compile(r'(?i)[A-Za-z_-]*(?:toolchain|channel|rust[-_]version)[A-Za-z_-]*')
TOOLCHAIN_ACTION = re.compile(r'(?i)rust|toolchain|cargo|maturin')
RUSTUP_ASSIGNMENT = re.compile(r'(?<![\w])RUSTUP_TOOLCHAIN[ \t]*=[ \t]*["\']?((?:\$\{\{.*?\}\}|[^\s"\';&|])*)', re.S)
GITHUB_EXPRESSION = re.compile(r'\$\{\{\s*(.*?)\s*\}\}', re.S)
ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\+?=')
SHELL_KEYWORDS = frozenset(['if', 'then', 'elif', 'else', 'fi', 'do', 'done', 'while', 'until', '!', '{', '}', 'case',
                            'esac', 'select', 'function', 'for', 'in'])
SHELLS = frozenset(['sh', 'bash', 'zsh', 'dash', 'ksh', 'ash'])
WRAPPERS = frozenset(['command', 'exec', 'builtin', 'sudo', 'nohup', 'nice', 'time', 'stdbuf', 'ionice', 'setsid', 'timeout',
                      'xargs', 'watch', 'unbuffer', 'doas', 'chroot', 'flock', 'script', 'caffeinate', 'find', 'parallel'])
RUST_PROXIES = TOOLS + ('rust-analyzer', 'rust-gdb', 'rust-lldb', 'cargo-miri', 'miri', 'rls')
RUSTUP_FLAGS = frozenset(['--force', '--no-self-update', '--allow-downgrade', '--force-non-host', '--verbose', '-v', '--quiet',
                          '-q', '--help', '-h', '--version', '-V'])
RUSTUP_VALUE_OPTIONS = frozenset(['--profile', '-c', '--component', '-t', '--target', '--toolchain', '--path',
                                  '--default-host', '--default-toolchain'])
# Subcommands whose positional arguments name toolchains, and how many leading positionals are not toolchains.
RUSTUP_TOOLCHAIN_ARGUMENTS = {'install': 'install', 'uninstall': 'other', 'update': 'other', 'default': 'default'}
RUSTUP_NO_SELECTION = frozenset(['component', 'target', 'show', 'which', 'self', 'set', 'doc', 'man', 'completions', 'check',
                                 'help', '--version', '-V', '-h', '--help'])
MAX_NESTING = 8
STANDARD_INPUT_FILES = frozenset(['-', '/dev/stdin', '/dev/fd/0', '/proc/self/fd/0'])
# Positional parameters: the exact spellings that are bound to the arguments of `sh -c script arg0 arg1 ...`, and
# every spelling that names one.
POSITIONAL_EXACT = re.compile(r'"?\$(?:([@*])|([0-9])|\{(?:([@*])|([0-9]+))\})"?')
VARIABLE_EXACT = re.compile(r'"?\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})"?')
POSITIONAL_NAMED = re.compile(r'\$(?:[@*0-9]|\{[@*0-9])')
BRACE_EXPANSION = re.compile(r'(?<!\$)\{[^{}$]*(?:,|\.\.)[^{}$]*\}')
# The file through which a step hands environment variables to the steps after it.
ENVIRONMENT_FILE = re.compile(r'(?<![\w])GITHUB_ENV(?![\w])')
ENVIRONMENT_LINE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)(=|<<)(.*)\Z', re.S)
PRINTF_SPECIFICATION = re.compile(r'%(?:%|[-+ #0]*(?:\*|[0-9]+)?(?:\.(?:\*|[0-9]+))?[A-Za-z])')
RUST_TOOLING = re.compile(r'(?<![\w-])(?:rustup|cargo(?:-[a-z]+)?|rustc|rustdoc|rustfmt|clippy-driver|RUSTUP_TOOLCHAIN)(?![\w-])')


def _plain(value):
    return value.strip().strip('\'"').strip()


def _normal(value):
    """A selection with its GitHub expressions in one canonical spelling."""
    return GITHUB_EXPRESSION.sub(lambda match: '${{ ' + re.sub(r'\s+', ' ', match.group(1)) + ' }}', _plain(value))


class _Word:
    """One shell word: value with quotes resolved, ${{ }} and ${..} expansions kept whole.

    `visible` is the value without the bodies of command substitutions, which are read as scripts of their own.
    """
    __slots__ = ('value', 'raw', 'expands', 'quoted', 'visible')

    def __init__(self, value, raw, expands, quoted, visible=None):
        self.value, self.raw, self.expands, self.quoted = value, raw, expands, quoted
        self.visible = value if visible is None else visible


class _Command:
    """One simple command: its words, redirection targets (split by direction), here-documents and here-strings.

    `piped` is set when the command reads the output of a pipe; `source` is the command that writes into that pipe.
    """
    __slots__ = ('words', 'targets', 'heredocs', 'continued', 'inputs', 'outputs', 'herestrings', 'piped', 'source')

    def __init__(self):
        self.words, self.targets, self.heredocs, self.continued = [], [], [], False
        self.inputs, self.outputs, self.herestrings, self.piped, self.source = [], [], [], False, None


_ESCAPE = re.compile(r"\\(?:([abeEfnrtv\\'\"?])|([0-7]{1,3})|x([0-9A-Fa-f]{1,2})|u([0-9A-Fa-f]{1,4})|U([0-9A-Fa-f]{1,8})|c(.)|(.?))", re.S)
_SIMPLE_ESCAPES = {'a': '\a', 'b': '\b', 'e': '\x1b', 'E': '\x1b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t', 'v': '\v'}


def _escapes(text):
    """The text with backslash escapes resolved as bash does in $'...', echo -e and printf formats.

    An unknown escape stays as written; a NUL ends the string, as it does in a shell word.
    """
    def one(match):
        simple, octal, hexa, short, long_, control, other = match.groups()
        if simple is not None:
            return _SIMPLE_ESCAPES.get(simple, simple)
        if octal is not None:
            return chr(int(octal, 8) & 0xFF)
        if hexa is not None:
            return chr(int(hexa, 16))
        for digits in (short, long_):
            if digits is not None:
                return chr(int(digits, 16)) if int(digits, 16) <= 0x10FFFF else match.group(0)
        if control is not None:
            return chr(ord(control) & 0x1F)
        return match.group(0)

    return _ESCAPE.sub(one, text).split('\x00', 1)[0]


def _ansi_c(script, index):
    """(text, index after the closing quote) of the $'...' string whose body starts at script[index]."""
    end = index
    while end < len(script) and script[end] != "'":
        end += 2 if script[end] == '\\' else 1
    if end >= len(script):
        raise CiYamlError("unclosed $'...' quote in a shell script")
    return _escapes(script[index:end]), end + 1


def _balanced(script, index, opener, closer):
    """Index after the closer that matches the opener at script[index]; quotes and nesting are respected."""
    depth = 0
    while index < len(script):
        char = script[index]
        if script.startswith('${{', index):
            index = _skip_expression(script, index)
            continue
        if char == '\\':
            index += 2
            continue
        if char == '$' and script.startswith("$'", index):
            index = _ansi_c(script, index + 2)[1]
            continue
        if char == "'":
            end = script.find("'", index + 1)
            if end < 0:
                raise CiYamlError('unclosed single quote in a shell script')
            index = end + 1
            continue
        if char == '"':
            index += 1
            while index < len(script) and script[index] != '"':
                if script[index] == '\\':
                    index += 1
                elif script.startswith('${{', index):
                    index = _skip_expression(script, index) - 1
                index += 1
            index += 1
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise CiYamlError(f'unclosed {opener} in a shell script')


def _dollar(script, index):
    """(literal text, new index, nested script or None) for the expansion that starts at script[index] == '$'."""
    if script.startswith('${{', index):
        end = _skip_expression(script, index)
        return script[index:end], end, None
    if script.startswith('$((', index):
        end = _balanced(script, index + 1, '(', ')')
        return script[index:end], end, None
    if script.startswith('$(', index):
        end = _balanced(script, index + 1, '(', ')')
        return script[index:end], end, script[index + 2:end - 1]
    if script.startswith('${', index):
        end = _balanced(script, index + 1, '{', '}')
        return script[index:end], end, None
    match = re.compile(r'\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-])').match(script, index)
    if match:
        return match.group(0), match.end(), None
    return '$', index + 1, None


def lex_shell(script):
    """(commands, nested scripts) of a shell script. Raises CiYamlError when it cannot be read exactly."""
    commands, nested = [], []
    command = _Command()
    cur = None
    redirect = None
    pending = []

    def start():
        nonlocal cur
        if cur is None:
            cur = {'value': [], 'raw': [], 'visible': [], 'expands': False, 'quoted': False}
        return cur

    def put(word, value, raw, visible=None):
        word['value'].append(value)
        word['raw'].append(raw)
        word['visible'].append(value if visible is None else visible)

    def end_word():
        nonlocal cur, redirect
        if cur is None:
            return
        word = _Word(''.join(cur['value']), ''.join(cur['raw']), cur['expands'], cur['quoted'], ''.join(cur['visible']))
        cur = None
        if redirect is None:
            command.words.append(word)
        elif redirect in ('heredoc', 'heredoc-strip'):
            pending.append((command, len(command.heredocs), word.value, redirect == 'heredoc-strip'))
            command.heredocs.append('')
            command.targets.append(word)
        else:
            command.targets.append(word)
            {'input': command.inputs, 'output': command.outputs, 'herestring': command.herestrings}.get(redirect, []).append(word)
        redirect = None

    def end_command():
        # An empty command keeps its pipe mark, so `echo x |<newline> bash` still reads the pipe.
        nonlocal command
        end_word()
        carried = command if command.piped and not (command.words or command.targets or command.heredocs) else None
        if command.words or command.targets or command.heredocs:
            commands.append(command)
        command = _Command()
        if carried is not None:
            command.piped, command.source = True, carried.source

    i, n = 0, len(script)
    while i < n:
        char = script[i]
        if char == '\n':
            end_command()
            i += 1
            while pending:
                owner, slot, delimiter, strip = pending.pop(0)
                body = []
                while i < n:
                    end = script.find('\n', i)
                    end = n if end < 0 else end
                    line = script[i:end]
                    i = min(end + 1, n)
                    if (line.lstrip('\t') if strip else line) == delimiter:
                        break
                    body.append(line)
                owner.heredocs[slot] = '\n'.join(body)
            continue
        if char in ' \t':
            end_word()
            i += 1
            continue
        if char == '\\':
            if script[i + 1:i + 2] == '\n':
                command.continued = True
                i += 2
                continue
            if i + 1 >= n:
                raise CiYamlError('trailing backslash in a shell script')
            word = start()
            put(word, script[i + 1], script[i:i + 2])
            word['quoted'] = True
            i += 2
            continue
        if char == "'":
            end = script.find("'", i + 1)
            if end < 0:
                raise CiYamlError('unclosed single quote in a shell script')
            word = start()
            put(word, script[i + 1:end], script[i:end + 1])
            word['quoted'] = True
            i = end + 1
            continue
        if char == '"':
            word = start()
            word['quoted'] = True
            j = i + 1
            text, visible = [], []
            while True:
                if j >= n:
                    raise CiYamlError('unclosed double quote in a shell script')
                c = script[j]
                if c == '"':
                    break
                if c == '\\':
                    nxt = script[j + 1:j + 2]
                    if nxt == '\n':
                        j += 2
                        continue
                    piece = nxt if nxt in ('\\', '"', '$', '`') else c + nxt
                    text.append(piece)
                    visible.append(piece)
                    j += 2
                    continue
                if c == '$':
                    literal, j, inner = _dollar(script, j)
                    text.append(literal)
                    visible.append(literal if inner is None else '')
                    word['expands'] = word['expands'] or literal != '$'
                    if inner is not None:
                        nested.append(inner)
                    continue
                if c == '`':
                    end = script.find('`', j + 1)
                    if end < 0:
                        raise CiYamlError('unclosed backtick in a shell script')
                    nested.append(script[j + 1:end])
                    text.append(script[j:end + 1])
                    visible.append('')
                    word['expands'] = True
                    j = end + 1
                    continue
                text.append(c)
                visible.append(c)
                j += 1
            put(word, ''.join(text), script[i:j + 1], ''.join(visible))
            i = j + 1
            continue
        if char == '$' and script.startswith("$'", i):
            text, j = _ansi_c(script, i + 2)
            word = start()
            put(word, text, script[i:j])
            word['quoted'] = True
            i = j
            continue
        if char == '$' and script.startswith('$"', i):
            i += 1  # a locale-translated string reads like a double-quoted one
            continue
        if char == '$':
            literal, j, inner = _dollar(script, i)
            word = start()
            put(word, literal, literal, literal if inner is None else '')
            word['expands'] = word['expands'] or literal != '$'
            if inner is not None:
                nested.append(inner)
            i = j
            continue
        if char == '`':
            end = script.find('`', i + 1)
            if end < 0:
                raise CiYamlError('unclosed backtick in a shell script')
            nested.append(script[i + 1:end])
            word = start()
            put(word, script[i:end + 1], script[i:end + 1], '')
            word['expands'] = True
            i = end + 1
            continue
        if char == '#' and cur is None:
            end = script.find('\n', i)
            i = n if end < 0 else end
            continue
        if script.startswith('||', i):
            end_command()
            i += 2
            continue
        if char == '|':
            end_command()
            command.piped = True
            command.source = commands[-1] if commands and commands[-1] is not command else None
            i += 2 if script[i + 1:i + 2] == '&' else 1
            continue
        if char in ';|()':
            end_command()
            i += 1
            continue
        if char == '&':
            if script[i + 1:i + 2] == '>':
                end_word()
                i += 2
                if script[i:i + 1] == '>':
                    i += 1
                redirect = 'output'
                continue
            end_command()
            i += 1
            continue
        if char in '<>' and script.startswith('(', i + 1):
            raise CiYamlError('process substitution in a shell script')
        if char in '<>':
            descriptor = ''
            if cur is not None and re.fullmatch(r'[0-9]+', ''.join(cur['raw'])):
                descriptor = ''.join(cur['raw'])
                cur = None
            else:
                end_word()
            match = re.compile(r'<<<|<<-|<<|>>|>\||[<>]&?').match(script, i)
            operator = match.group(0)
            i = match.end()
            if operator.startswith('<<') and operator != '<<<':
                redirect = 'heredoc-strip' if operator == '<<-' else 'heredoc'
            elif operator == '<<<':
                redirect = 'herestring'
            elif operator.startswith('<'):
                redirect = 'input' if descriptor in ('', '0') else 'file'
            else:
                redirect = 'output'
            continue
        word = start()
        put(word, char, char)
        i += 1
    end_command()
    return commands, nested


class _CiScan:
    """The violations of one workflow or composite action, found from its parsed structure."""

    def __init__(self, name, names):
        self.name = name
        self.names = names
        self.found = []
        self.approved = set()
        self.rendered = set()
        self.variables = {}
        self.fuzz = False
        self.style = 'plain'

    def report(self, trail, reason, detail=''):
        where = '.'.join(f'[{part}]' if isinstance(part, int) else str(part) for part in trail).replace('.[', '[')
        self.found.append(f'{self.name}:{where}: {reason}' + (f': {detail}' if detail else ''))

    # ---- structure ---------------------------------------------------------------------------------
    def run(self, document):
        if not isinstance(document, dict):
            self.report((), 'workflow or action is not a mapping')
            return self.found
        self.visit(document, (), None)
        return self.found

    def visit(self, node, trail, step, shell=None):
        if isinstance(node, dict):
            # `defaults.run.shell` applies to the scripts below it; a step's own `shell` overrides it.
            defaults = node.get('defaults')
            if isinstance(defaults, dict) and isinstance(defaults.get('run'), dict) and isinstance(defaults['run'].get('shell'), str):
                shell = defaults['run']['shell']
            own = node.get('shell') if isinstance(node.get('shell'), str) else shell
            for key, value in node.items():
                here = trail + (key,)
                self.fuzz = self.name == MAIN_WORKFLOW and len(here) >= 2 and here[0] == 'jobs' and here[1] == FUZZ_JOB
                if AUTHORITATIVE_CHANNEL.search(key):
                    self.report(here, 'channel name used as a key')
                handled = self.check_key(key, value, here, node, step, own)
                if isinstance(value, (dict, list)):
                    self.visit(value, here, step, shell)
                elif isinstance(value, str) and not handled and key not in ('name', 'description'):
                    self.check_text(value, here)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                here = trail + (index,)
                inside_steps = bool(trail) and trail[-1] == 'steps' and isinstance(item, dict)
                if isinstance(item, (dict, list)):
                    self.visit(item, here, item if inside_steps else step, shell)
                elif isinstance(item, str) and not (trail and trail[-1] in ('name', 'description')):
                    self.check_text(item, here)

    def check_text(self, value, trail):
        if AUTHORITATIVE_CHANNEL.search(value):
            self.report(trail, 'channel name outside an approved nightly use', value.strip())

    def allowed(self, selection, kind):
        selection = _normal(selection)
        if selection in AUTHORITATIVE or (selection == '${{ inputs.toolchain }}' and self.name == CACHE_ACTION):
            return True
        return selection == 'nightly' and self.fuzz and kind in ('rustup-install', 'cargo-plus', 'with-toolchain')

    def check_key(self, key, value, trail, owner, step, shell=None):
        """Apply the key-specific rules; True when the value was fully judged here."""
        if key == 'run' and isinstance(value, dict) and len(trail) >= 2 and trail[-2] == 'defaults':
            return False
        if key == 'run':
            if not isinstance(value, str):
                self.report(trail, 'run is not a script string')
                return True
            if shell is not None and not re.match(r'(?:ba)?sh(?:\s|$)', shell.strip()) and RUST_TOOLING.search(value):
                self.report(trail, 'script of a shell other than bash or sh mentions Rust tooling and cannot be analysed', shell)
            self.check_script(value, trail, 0, getattr(value, 'style', 'plain'))
            return True
        if key in ('image', 'container') and isinstance(value, str) and re.search(r'(?i)rust', value):
            self.report(trail, 'container image selects a Rust toolchain', _plain(value))
            return True
        if key == 'uses' and isinstance(value, str):
            self.check_uses(value, trail)
            return False
        if TOOLCHAIN_KEY.fullmatch(key):
            self.check_selection_key(key, value, trail, owner, step)
            return True
        return False

    def check_uses(self, value, trail):
        target = _plain(value)
        if target.startswith('./'):
            base = target[2:].rstrip('/')
            candidates = [base] if base.endswith(WORKFLOW_SUFFIXES) else [f'{base}/{name}' for name in ACTION_NAMES]
            if not any(candidate in self.names for candidate in candidates):
                self.report(trail, 'local workflow or action is not among the scanned CI files', target)
        if target != './.github/actions/rust-cache' and TOOLCHAIN_ACTION.search(target):
            self.report(trail, 'unrecognised toolchain action', target)

    def check_selection_key(self, key, value, trail, owner, step):
        if value is None or (isinstance(value, str) and not value.strip()):
            if key not in ('toolchain', 'rust_toolchain'):
                self.report(trail, f'unrecognised {key} declaration')
            return
        if isinstance(value, dict):
            if key not in ('toolchain', 'rust_toolchain'):
                self.report(trail, f'unrecognised {key} declaration')
            elif 'default' in value:
                default = value['default']
                if key == 'rust_toolchain' or not isinstance(default, str) or default.strip():
                    self.report(trail, f'{key} input has a default')
            return
        if not isinstance(value, str):
            self.report(trail, f'{key} is not a single value')
            return
        pin = (self.name == MAIN_WORKFLOW and trail == ('env', key) and key == 'RUSTUP_TOOLCHAIN'
               and value.style == 'single' and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', value)
               and not getattr(owner, 'flow', False))
        if pin:
            return
        uses = step.get('uses') if isinstance(step, dict) else None
        kind = 'assign'
        if key == 'toolchain' and len(trail) >= 2 and trail[-2] == 'with' and uses == './.github/actions/rust-cache':
            kind = 'with-toolchain'
        if self.allowed(value, kind):
            return
        self.report(trail, f'{key} selects {_plain(value)!r}')

    # ---- shell -------------------------------------------------------------------------------------
    def check_script(self, script, trail, depth=0, style='plain', top=True, positional=None, variables=None):
        """Check one script.

        `positional` binds $0, $1 ... when it is the text of `sh -c` with arguments (`set -- words` binds them for the
        commands after it); `variables` holds the literal variables set before a command substitution.
        """
        if depth == 0:
            self.style = style
        if depth > MAX_NESTING:
            self.report(trail, 'shell nesting too deep to analyse')
            return
        try:
            commands, nested = lex_shell(script)
        except CiYamlError as error:
            self.report(trail, 'unanalysable shell', str(error))
            return
        known, outer = dict(variables or {}), self.variables
        for command in commands:
            self.variables = known
            self.command(command, self.bind(command.words, positional), trail, depth, top)
            self.environment_file(command, trail)
            positional = self.remember(command, known, positional)
        self.variables = outer
        for command in commands:
            for word in [*command.words, *command.targets]:
                self.check_word(word, trail)
            for body in command.heredocs:
                self.check_here_document(body, trail)
        for inner in nested:
            self.check_script(inner, trail, depth + 1, positional=positional, variables=known)
        shells = any(basename(w) in SHELLS for c in commands for w in c.words[:1])
        if shells:
            for command in commands:
                for body in command.heredocs:
                    self.check_script(body, trail, depth + 1)

    def check_word(self, word, trail):
        # The words of an echo or printf whose text was rendered and read line by line are judged there, as that text.
        for match in () if id(word) in self.rendered else RUSTUP_ASSIGNMENT.finditer(word.value):
            if _normal(match.group(1)) not in AUTHORITATIVE:
                self.report(trail, 'RUSTUP_TOOLCHAIN assigned', match.group(1))
        if id(word) not in self.approved and AUTHORITATIVE_CHANNEL.search(word.visible):
            self.report(trail, 'channel name outside an approved nightly use', word.value)

    def check_here_document(self, body, trail):
        for match in RUSTUP_ASSIGNMENT.finditer(body):
            if _normal(match.group(1)) not in AUTHORITATIVE:
                self.report(trail, 'RUSTUP_TOOLCHAIN assigned in a here-document', match.group(1))
        if AUTHORITATIVE_CHANNEL.search(body):
            self.report(trail, 'channel name in a here-document')

    def command(self, command, words, trail, depth, top=False):
        index = 0
        assigned = False
        while index < len(words):
            word = words[index]
            if ASSIGNMENT.match(word.raw):
                assigned = True
                index += 1
            elif not word.quoted and word.value in SHELL_KEYWORDS:
                index += 1
            else:
                break
        if index >= len(words):
            return
        name, arguments = words[index], words[index + 1:]
        match = VARIABLE_EXACT.fullmatch(name.raw)
        if match is not None and (match.group(1) or match.group(2)) in self.variables:
            value = _Word(self.variables[match.group(1) or match.group(2)], name.raw, False, name.raw.startswith('"'))
            pieces = [value] if value.quoted else self.split_unquoted(value)
            if not pieces:
                return
            name, arguments = pieces[0], [*pieces[1:], *arguments]
        base = basename(name)
        if self.positional_named(name):
            self.report(trail, 'a command taken from a positional parameter cannot be resolved', name.value)
            return
        if not name.quoted and BRACE_EXPANSION.search(name.raw):
            self.report(trail, 'a command built by brace expansion cannot be resolved', name.value)
            return
        if base == 'env':
            position = 0
            while position < len(arguments):
                value = arguments[position].value
                if value in ('-S', '--split-string'):
                    self.report(trail, 'unanalysable env -S command string')
                    return
                if value in ('-u', '--unset', '-C', '--chdir'):
                    position += 2
                elif value.startswith('-') or ASSIGNMENT.match(value):
                    position += 1
                else:
                    break
            self.command(command, arguments[position:], trail, depth, False)
        elif base in WRAPPERS:
            known = set(RUST_PROXIES) | SHELLS | WRAPPERS | {'rustup', 'env', 'eval'}
            for position, argument in enumerate(arguments):
                if basename(argument) in known:
                    self.command(command, arguments[position:], trail, depth, False)
                    break
            else:
                forwarded = next((argument for argument in arguments if self.positional_named(argument)), None)
                if forwarded is not None:
                    self.report(trail, 'a command forwarded from positional parameters cannot be resolved', forwarded.value)
        elif base in SHELLS:
            self.shell(command, arguments, trail, depth)
        elif base in ('source', '.'):
            operands = [argument for argument in arguments if not argument.value.startswith('-')]
            if operands and operands[0].value in STANDARD_INPUT_FILES:
                self.standard_input(command, trail, depth)
        elif base == 'eval':
            if any(argument.expands for argument in arguments):
                self.report(trail, 'eval of a string built by expansion cannot be analysed', ' '.join(a.value for a in arguments))
            self.check_script(' '.join(argument.value for argument in arguments), trail, depth + 1, top=False)
        elif base == 'rustup':
            self.rustup(arguments, trail, depth, command, self.spelled_exactly(command, words[index], assigned, top, 'rustup'))
        elif base in RUST_PROXIES:
            self.tool(base, name, arguments, trail, self.spelled_exactly(command, words[index], assigned, top, 'cargo'))
        elif base == 'alias':
            for argument in arguments:
                if '=' in argument.value:
                    self.check_script(argument.value.split('=', 1)[1], trail, depth + 1, top=False)
        elif name.expands and any(argument.value.startswith('+') for argument in arguments):
            self.report(trail, 'command that cannot be resolved selects a toolchain', name.value)
        elif name.expands and not top:
            self.report(trail, 'a command run through a wrapper or string cannot be resolved', name.value)

    @staticmethod
    def positional_named(word):
        return word.expands and bool(POSITIONAL_NAMED.search(word.visible))

    @staticmethod
    def bind(words, positional):
        """The words with $@, $*, $0 ... replaced by the arguments of `sh -c script arg0 arg1 ...` (None: nothing is bound)."""
        if positional is None:
            return words
        bound = []
        for word in words:
            match = POSITIONAL_EXACT.fullmatch(word.raw)
            if match is None:
                bound.append(word)
                continue
            if match.group(1) or match.group(3):
                chosen = positional[1:]
            else:
                number = int(match.group(2) or match.group(4))
                chosen = positional[number:number + 1]
            for value in chosen:
                bound.extend(_CiScan.split_unquoted(value) if not word.raw.startswith('"') else [value])
        return bound

    @staticmethod
    def split_unquoted(word):
        """The words an unquoted expansion of this word becomes: it splits where it has whitespace."""
        pieces = word.value.split()
        if len(pieces) == 1 and pieces[0] == word.value:
            return [word]
        return [_Word(piece, piece, word.expands, False) for piece in pieces]

    @staticmethod
    def remember(command, variables, positional):
        """Update what is known after one command: literal variables (VAR=text, export VAR=text) and `set -- words`."""
        words = command.words
        start = 0
        if words and basename(words[0]) in ('export', 'declare', 'typeset', 'readonly', 'local'):
            start = 1
            while start < len(words) and words[start].value.startswith('-'):
                start += 1
        rest = words[start:]
        if start == 0 and rest and not all(ASSIGNMENT.match(word.raw) for word in rest):
            if basename(rest[0]) == 'set' and len(rest) > 1 and rest[1].value == '--':
                return [_Word('', '', False, True), *rest[2:]]
            return positional
        for word in rest:
            if not ASSIGNMENT.match(word.raw):
                continue
            name, _, value = word.value.partition('=')
            name = name.rstrip('+')
            if word.expands or word.raw.split('=', 1)[0].endswith('+'):
                variables.pop(name, None)
            else:
                variables[name] = value
        return positional

    def shell(self, command, arguments, trail, depth):
        """A shell: its `-c` string with the arguments that follow it as $0, $1 ..., or else the script it reads from stdin.

        A shell with a command string reads no stdin. Otherwise, unless it names a script file as an operand (that
        file is not analysed), the here-documents and here-strings are its script, a script piped in is analysed when
        the pipe is fed by echo, printf or cat, and a script read from a pipe or file that cannot be read here, or
        from a process substitution, is reported. /dev/stdin and `-` as the operand mean standard input.
        """
        for position, argument in enumerate(arguments):
            if re.fullmatch(r'-[A-Za-z]*c[A-Za-z]*', argument.value) and position + 1 < len(arguments):
                self.check_script(arguments[position + 1].value, trail, depth + 1, top=False, positional=arguments[position + 2:])
                return
        operands = self.leading_operands(arguments)
        if operands and operands[0].value not in STANDARD_INPUT_FILES and not any(
                re.fullmatch(r'-[A-Za-z]*s[A-Za-z]*', a.value) for a in arguments[:len(arguments) - len(operands)]):
            for body in command.heredocs:
                self.check_script(body, trail, depth + 1, top=False)
            for text in command.herestrings:
                self.check_script(text.value, trail, depth + 1, top=False)
            return
        self.standard_input(command, trail, depth)

    def standard_input(self, command, trail, depth):
        """The script a shell (or `source /dev/stdin`) reads from its standard input."""
        for body in command.heredocs:
            self.check_script(body, trail, depth + 1, top=False)
        for text in command.herestrings:
            self.check_script(text.value, trail, depth + 1, top=False)
        for word in command.inputs:
            self.report(trail, 'a shell reads its script from a file that cannot be analysed', word.value)
        if command.piped:
            text = self.produced_text(command.source)
            if text is None:
                self.report(trail, 'a shell reads its script from a pipe that cannot be analysed')
            else:
                self.check_script(text, trail, depth + 1, top=False)

    @staticmethod
    def leading_operands(arguments):
        """The words of a shell's command line from its first operand on; options (and their values) come before."""
        position = 0
        while position < len(arguments):
            value = arguments[position].value
            if value == '--':
                position += 1
                break
            if not value.startswith(('-', '+')) or value in ('-', '+'):
                break
            position += 2 if value in ('-o', '+o', '-O', '+O') else 1
        return arguments[position:]

    def produced_text(self, command):
        """The text a command writes, when it is echo, printf or a cat of its own input; None when it cannot be read."""
        if command is None:
            return None
        start = 0
        while start < len(command.words) and (ASSIGNMENT.match(command.words[start].raw)
                                              or (not command.words[start].quoted and command.words[start].value in SHELL_KEYWORDS)):
            start += 1
        words = command.words[start:]
        if not words:
            return None
        base, arguments = basename(words[0]), words[1:]
        if base in ('echo', 'printf'):
            self.rendered.update(id(argument) for argument in arguments)
        if base == 'echo':
            skip = 0
            while skip < len(arguments) and re.fullmatch(r'-[neE]+', arguments[skip].value):
                skip += 1
            return _escapes(' '.join(argument.value for argument in arguments[skip:]))
        if base == 'printf':
            return self.printed(arguments)
        if base == 'cat' and not [a for a in arguments if not a.value.startswith('-') or a.value == '-']:
            text = [*command.heredocs, *(word.value for word in command.herestrings)]
            if command.piped:
                earlier = self.produced_text(command.source)
                if earlier is None:
                    return None
                text.append(earlier)
            if command.inputs:
                return None
            return '\n'.join(text)
        return None

    @staticmethod
    def printed(arguments):
        """What printf writes for its format and arguments (a conversion's value is its argument as written)."""
        skip = 0
        while skip < len(arguments) and arguments[skip].value in ('--',):
            skip += 1
        if skip >= len(arguments) or arguments[skip].value.startswith('-'):
            return None
        format_text = _escapes(arguments[skip].value)
        values = [word.value for word in arguments[skip + 1:]]
        conversions = [m for m in PRINTF_SPECIFICATION.finditer(format_text) if m.group(0) != '%%']
        out = []
        used = 0
        while True:
            last = 0
            for match in PRINTF_SPECIFICATION.finditer(format_text):
                out.append(format_text[last:match.start()])
                last = match.end()
                if match.group(0) == '%%':
                    out.append('%')
                elif '*' in match.group(0):
                    return None
                else:
                    value = values[used] if used < len(values) else ''
                    used += 1
                    out.append(_escapes(value) if match.group(0).endswith('b') else value)
            out.append(format_text[last:])
            if not conversions or used >= len(values):
                return ''.join(out)

    def environment_file(self, command, trail):
        """Writes to $GITHUB_ENV, which later steps inherit: each line must be a NAME=value this reader can see.

        The writer must be echo, printf or cat of text it can read (also through tee); every line must name its
        variable literally, and RUSTUP_TOOLCHAIN may only be given an authoritative reference. Any other command
        that writes the file, and any other use of the file's name than a redirect or a tee argument, is reported.
        """
        start = 0
        while start < len(command.words) and (ASSIGNMENT.match(command.words[start].raw)
                                              or (not command.words[start].quoted and command.words[start].value in SHELL_KEYWORDS)):
            start += 1
        words = command.words[start:]
        base = basename(words[0]) if words else ''
        arguments = words[1:]
        written = any(ENVIRONMENT_FILE.search(word.value) for word in command.outputs)
        if base == 'tee':
            written = written or any(ENVIRONMENT_FILE.search(word.value) for word in arguments if not word.value.startswith('-'))
        elif base not in ('echo', 'printf'):
            for word in [*arguments, *(w for w in command.words if ASSIGNMENT.match(w.raw))]:
                if ENVIRONMENT_FILE.search(word.value):
                    self.report(trail, 'the environment file is passed to a command that cannot be analysed', word.value)
        if not written:
            return
        if base in ('echo', 'printf', 'cat'):
            text = self.produced_text(command)
        elif base == 'tee':
            text = self.produced_text(command.source) if command.piped else ''
            if text is not None:
                text = '\n'.join([text, *command.heredocs, *(word.value for word in command.herestrings)])
        else:
            text = None
        if text is None:
            self.report(trail, 'something that cannot be analysed is written to the environment file', base or 'compound command')
            return
        lines = text.split('\n')
        index = 0
        while index < len(lines):
            line = lines[index]
            index += 1
            if not line.strip():
                continue
            match = ENVIRONMENT_LINE.match(line)
            if match is None:
                self.report(trail, 'a line written to the environment file does not start with a literal NAME=', line)
                continue
            key, operator, rest = match.groups()
            if operator == '<<':
                while index < len(lines) and lines[index] != rest:
                    index += 1
                index += 1
                if key == 'RUSTUP_TOOLCHAIN':
                    self.report(trail, 'RUSTUP_TOOLCHAIN written to the environment file as a multi-line value')
            elif key == 'RUSTUP_TOOLCHAIN' and _normal(rest) not in AUTHORITATIVE:
                self.report(trail, 'RUSTUP_TOOLCHAIN written to the environment file', rest)

    def spelled_exactly(self, command, name, assigned, top, tool):
        """Whether the nightly exception may apply to this command: the bare tool name as the command word,
        with no assignment, wrapper, path, quoting or line continuation around it, in a plain, quoted or
        literal scalar (a folded scalar hides where its lines break)."""
        return top and not assigned and name.raw == tool and not command.continued and self.style != 'folded'

    def pick(self, word, kind, trail, what):
        if self.allowed(word.value, kind):
            if _normal(word.value) == 'nightly':
                self.approved.add(id(word))
            return
        self.report(trail, f'{what} selects {_plain(word.value)!r}')

    def tool(self, base, name, arguments, trail, exact):
        if not arguments:
            return
        first = arguments[0]
        if first.value.startswith('+'):
            selection = _Word(first.value[1:], first.value[1:], first.expands, first.quoted)
            if self.allowed(selection.value, 'cargo-plus' if base == 'cargo' and exact else 'tool-plus'):
                if _normal(selection.value) == 'nightly':
                    self.approved.add(id(first))
                return
            self.report(trail, f'{base} selects {_plain(selection.value)!r}')
        elif first.expands and not (first.value == CACHE_EXPANSION and self.name == CACHE_ACTION):
            self.report(trail, 'unrecognised toolchain expansion', first.value)

    def rustup(self, arguments, trail, depth, command, exact):
        """Every toolchain a rustup invocation selects: +toolchain, --toolchain, and each toolchain argument."""
        picks = []
        position = 0
        if arguments and arguments[0].value.startswith('+'):
            picks.append((_Word(arguments[0].value[1:], '', arguments[0].expands, True), 'rustup-plus'))
            position = 1
        words = arguments[position:]
        subcommand_at = next((k for k, w in enumerate(words) if not w.value.startswith('-')), None)
        if subcommand_at is None:
            self.rustup_options(words, picks, trail, strict=False)
            self.finish_rustup(picks, trail)
            return
        self.rustup_options(words[:subcommand_at], picks, trail, strict=True)
        subcommand = words[subcommand_at].value
        rest = words[subcommand_at + 1:]
        kind = None
        if subcommand == 'toolchain':
            nested = rest[0].value if rest and not rest[0].value.startswith('-') else None
            if nested == 'list':
                self.rustup_options(rest[1:], picks, trail, strict=False)
                self.finish_rustup(picks, trail)
                return
            if nested in ('install', 'uninstall', 'remove'):
                kind = 'install' if nested == 'install' else 'other'
                rest = rest[1:]
            else:
                self.report(trail, 'unrecognised or unauthorised rustup toolchain form', nested or '')
                return
        elif subcommand == 'override':
            nested = rest[0].value if rest and not rest[0].value.startswith('-') else None
            if nested == 'set':
                kind, rest = 'default', rest[1:]
            elif nested in ('unset', 'list'):
                self.rustup_options(rest[1:], picks, trail, strict=False)
                self.finish_rustup(picks, trail)
                return
            else:
                self.report(trail, 'unrecognised rustup override form', nested or '')
                return
        elif subcommand == 'run':
            options, tail = self.leading_options(rest)
            self.rustup_options(options, picks, trail, strict=True)
            if not tail:
                self.report(trail, 'rustup run names no toolchain')
            else:
                picks.append((tail[0], 'rustup-run'))
                self.finish_rustup(picks, trail)
                self.command(command, tail[1:], trail, depth, False)
                return
        elif subcommand in RUSTUP_TOOLCHAIN_ARGUMENTS:
            kind = RUSTUP_TOOLCHAIN_ARGUMENTS[subcommand]
        elif subcommand in RUSTUP_NO_SELECTION:
            self.rustup_options(rest, picks, trail, strict=False)
            self.finish_rustup(picks, trail)
            return
        else:
            self.report(trail, 'unrecognised rustup form', subcommand)
            return
        options, positionals = self.split_options(rest)
        self.rustup_options(options, picks, trail, strict=True)
        if kind == 'default':
            if not positionals:
                self.report(trail, 'rustup names no toolchain', subcommand)
            picks.extend((word, 'rustup-' + subcommand) for word in positionals[:1])
            if len(positionals) > 1:
                self.report(trail, 'unrecognised rustup arguments', ' '.join(w.value for w in positionals[1:]))
        else:
            if kind == 'install' and not positionals:
                self.report(trail, 'rustup toolchain install names no toolchain')
            # nightly is excused only for a lone `rustup [toolchain] install nightly`; every other argument is judged alone.
            lone = exact and kind == 'install' and len(positionals) == 1
            picks.extend((word, 'rustup-install' if lone else 'rustup-' + subcommand) for word in positionals)
        self.finish_rustup(picks, trail)

    @staticmethod
    def leading_options(words):
        """(option words incl. their values, the words from the first non-option on)."""
        position = 0
        while position < len(words) and words[position].value.startswith('-') and not words[position].quoted:
            position += 2 if words[position].value in RUSTUP_VALUE_OPTIONS else 1
        return words[:position], words[position:]

    def split_options(self, words):
        """(option words incl. their values, positional words) of a rustup subcommand's arguments."""
        options, positionals = [], []
        position = 0
        while position < len(words):
            word = words[position]
            if word.value.startswith('-') and not word.quoted or word.value in RUSTUP_FLAGS:
                options.append(word)
                if word.value in RUSTUP_VALUE_OPTIONS and position + 1 < len(words):
                    options.append(words[position + 1])
                    position += 1
            else:
                positionals.append(word)
            position += 1
        return options, positionals

    def rustup_options(self, words, picks, trail, strict):
        position = 0
        while position < len(words):
            value = words[position].value
            if value == '--toolchain' and position + 1 < len(words):
                picks.append((words[position + 1], 'rustup-flag'))
                position += 2
            elif value.startswith('--toolchain='):
                picks.append((_Word(value.split('=', 1)[1], '', words[position].expands, True), 'rustup-flag'))
                position += 1
            elif value in RUSTUP_VALUE_OPTIONS:
                position += 2
            elif value in RUSTUP_FLAGS or value.split('=', 1)[0] in RUSTUP_VALUE_OPTIONS or not value.startswith('-'):
                position += 1
            else:
                if strict:
                    self.report(trail, 'unrecognised rustup option', value)
                position += 1

    def finish_rustup(self, picks, trail):
        for word, kind in picks:
            if kind == 'rustup-plus' or word.value:
                self.pick(word, kind, trail, 'rustup')
            else:
                self.report(trail, 'rustup selects an empty toolchain')


def basename(word):
    return word.value.rsplit('/', 1)[-1]


def toolchain_selection_violations(texts, root_files=()):
    """Every way CI can choose a Rust toolchain, checked against a whitelist.

    texts maps a repo-relative workflow or composite-action path to its text. Each file is parsed as YAML
    first (jobs, steps, env, with, uses and scalars); each run script is then read as shell words, with
    quotes, paths, line continuations and GitHub expressions resolved. A selection is allowed only as an
    authoritative reference (${RUSTUP_TOOLCHAIN}, the reusable input, the selection output, the workflow
    env), as the one pinned literal under the top-level env, or as nightly where jobs.fuzz-smoke of the
    main workflow installs it through `rustup toolchain install nightly`, `cargo +nightly` or the
    `toolchain: nightly` input of the cache action. Every selection is judged on its own, so one allowed
    command does not excuse another on the same line. Anything else that selects a toolchain, and
    anything this reader cannot parse or classify, is reported. root_files lists repo files named like
    rust-toolchain, which also select a toolchain.
    """
    found = [f'{name}: toolchain file' for name in root_files]
    names = set(texts)
    for name, text in sorted(texts.items()):
        try:
            document = parse_ci_yaml(text)
        except CiYamlError as error:
            found.append(f'{name}: unanalysable YAML: {error}')
            continue
        found.extend(_CiScan(name, names).run(document))
    return list(dict.fromkeys(found))


def toolchain_files(root):
    """rust-toolchain and rust-toolchain.toml files in the repository, ignoring build output and Git data."""
    found = []
    for directory, names, files in os.walk(root):
        names[:] = [name for name in names if name not in ('.git', 'target', 'node_modules', '__pycache__')]
        found.extend(os.path.relpath(os.path.join(directory, name), root) for name in files
                     if name in ('rust-toolchain', 'rust-toolchain.toml'))
    return sorted(found)


SELECTION_VALUES = ('nightly', 'stable', '1.99.0')
# The only spellings through which fuzz-smoke may name nightly (the ones the real job uses, plus the same
# command with its argument quoted or written as a quoted YAML scalar). Every other spelling is refused.
FUZZ_NIGHTLY_FORMS = ('rustup-toolchain-install', 'rustup-install-alias', 'rustup-in-block-scalar', 'cargo-plus',
                      'cargo-plus-in-block-scalar', 'cargo-quoted-selector', 'cargo-quoted-yaml',
                      'cargo-single-quoted-yaml', 'ansi-c-selector', 'cargo-subshell', 'cargo-after-conditional', 'cargo-in-pipeline',
                      'cargo-substitution', 'cargo-backticks', 'with-toolchain-input', 'with-flow', 'with-quoted-key',
                      'with-multiline-flow')
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
    'rustup-install-alias': lambda i, v: [f'{i}- run: rustup install {v} --profile minimal'],
    'rustup-update': lambda i, v: [f'{i}- run: rustup update {v}'],
    'rustup-multiple-installs': lambda i, v: [f'{i}- run: rustup toolchain install "$RUSTUP_TOOLCHAIN" {v}'],
    'rustup-multiple-updates': lambda i, v: [f'{i}- run: rustup update "$RUSTUP_TOOLCHAIN" {v}'],
    'rustup-component-flag': lambda i, v: [f'{i}- run: rustup component add clippy --toolchain {v}'],
    'rustup-target-equals': lambda i, v: [f'{i}- run: rustup target add wasm32-unknown-unknown --toolchain={v}'],
    'rustup-override-path': lambda i, v: [f'{i}- run: rustup override set --path . {v}'],
    'rustup-plus': lambda i, v: [f'{i}- run: rustup +{v} show active-toolchain'],
    'rustup-absolute-path': lambda i, v: [f'{i}- run: /opt/rust/bin/rustup default {v}'],
    'rustup-quoted-name': lambda i, v: [f'{i}- run: |', f'{i}    "rustup" default {v}'],
    'cargo-quoted-name': lambda i, v: [f'{i}- run: |', f'{i}    "cargo" +{v} test'],
    'cargo-quoted-selector': lambda i, v: [f'{i}- run: cargo "+{v}" test'],
    'cargo-env-path': lambda i, v: [f'{i}- run: |', f'{i}    "${{CARGO_HOME}}/bin/cargo" +{v} test'],
    'cargo-env-path-unquoted': lambda i, v: [f'{i}- run: ${{CARGO_HOME}}/bin/cargo +{v} test'],
    'cargo-absolute-path': lambda i, v: [f'{i}- run: /opt/rust/bin/cargo +{v} test'],
    'cargo-relative-path': lambda i, v: [f'{i}- run: ./tools/cargo +{v} test'],
    'cargo-backslash-newline': lambda i, v: [f'{i}- run: |', f'{i}    cargo \\', f'{i}      +{v} test'],
    'cargo-folded-block': lambda i, v: [f'{i}- run: >', f'{i}    cargo', f'{i}    +{v} test'],
    'cargo-quoted-yaml': lambda i, v: [f'{i}- run: "cargo +{v} test"'],
    'cargo-single-quoted-yaml': lambda i, v: [f"{i}- run: 'cargo +{v} test'"],
    'cargo-after-assignment': lambda i, v: [f'{i}- run: CARGO_TERM_COLOR=never cargo +{v} test'],
    'cargo-quoted-assignment': lambda i, v: [f'{i}- run: CARGO_TERM_COLOR="never" cargo +{v} test'],
    'cargo-env-wrapper': lambda i, v: [f'{i}- run: env cargo +{v} test'],
    'cargo-sudo-wrapper': lambda i, v: [f'{i}- run: sudo -E cargo +{v} test'],
    'cargo-bash-c': lambda i, v: [f"{i}- run: bash -c 'cargo +{v} test'"],
    'cargo-eval': lambda i, v: [f'{i}- run: eval "cargo +{v} test"'],
    'cargo-substitution': lambda i, v: [f'{i}- run: version=$(cargo +{v} --version)'],
    'cargo-backticks': lambda i, v: [f'{i}- run: version=`cargo +{v} --version`'],
    'cargo-subshell': lambda i, v: [f'{i}- run: (cargo +{v} test)'],
    'cargo-after-conditional': lambda i, v: [f'{i}- run: |', f'{i}    if true; then', f'{i}      cargo +{v} test', f'{i}    fi'],
    'cargo-in-pipeline': lambda i, v: [f'{i}- run: echo go | cargo +{v} test'],
    'cargo-in-heredoc-shell': lambda i, v: [f'{i}- run: |', f'{i}    bash <<EOF', f'{i}    cargo +{v} test', f'{i}    EOF'],
    'rustc-absolute-path': lambda i, v: [f'{i}- run: /opt/rust/bin/rustc +{v} -vV'],
    'rustup-run-cargo': lambda i, v: [f'{i}- run: rustup run "$RUSTUP_TOOLCHAIN" cargo +{v} test'],
    'unresolved-command': lambda i, v: [f'{i}- run: $CARGO +{v} test'],
    'selector-in-variable': lambda i, v: [f'{i}- run: |', f'{i}    tc=+{v}', f'{i}    cargo "$tc" test'],
    'cargo-expansion-first-argument': lambda i, v: [f'{i}- run: cargo ${{EXTRA_ARGS}} test # {v}'],
    'shell-env-argument': lambda i, v: [f'{i}- run: env "RUSTUP_TOOLCHAIN={v}" cargo test'],
    'shell-quoted-assignment': lambda i, v: [f'{i}- run: RUSTUP_TOOLCHAIN="{v}" cargo test'],
    'github-env-heredoc': lambda i, v: [f'{i}- run: |', f'{i}    cat >> "$GITHUB_ENV" <<EOF', f'{i}    RUSTUP_TOOLCHAIN={v}', f'{i}    EOF'],
    'step-env-flow': lambda i, v: [f'{i}- run: cargo test', f'{i}  env: {{RUSTUP_TOOLCHAIN: "{v}"}}'],
    'step-env-single-quoted-key': lambda i, v: [f'{i}- run: cargo test', f'{i}  env:', f"{i}    'RUSTUP_TOOLCHAIN': '{v}'"],
    'step-env-double-quoted-key': lambda i, v: [f'{i}- run: cargo test', f'{i}  env:', f'{i}    "RUSTUP_TOOLCHAIN": "{v}"'],
    'with-flow': lambda i, v: [f'{i}- uses: ./.github/actions/rust-cache', f'{i}  with: {{toolchain: "{v}"}}'],
    'with-quoted-key': lambda i, v: [f'{i}- uses: ./.github/actions/rust-cache', f'{i}  with:', f'{i}    "toolchain": "{v}"'],
    'with-multiline-flow': lambda i, v: [f'{i}- uses: ./.github/actions/rust-cache', f'{i}  with: {{lane: x,', f'{i}    toolchain: {v}}}'],
    'action-flow-mapping': lambda i, v: [f'{i}- {{uses: "dtolnay/rust-toolchain@{v}"}}'],
    'action-quoted-key': lambda i, v: [f'{i}- "uses": "dtolnay/rust-toolchain@{v}"'],
    # Input channels of the restricted shell subset: ANSI-C quoting, shell stdin, positional parameters, $GITHUB_ENV.
    'ansi-c-command': lambda i, v: [f"{i}- run: $'cargo' +{v} test"],
    'ansi-c-escaped-command': lambda i, v: [f"{i}- run: $'\\x63ar\\147o' +{v} test"],
    'ansi-c-selector': lambda i, v: [f"{i}- run: cargo $'+{v}' test"],
    'ansi-c-rustup': lambda i, v: [f"{i}- run: $'rustup' default {v}"],
    'ansi-c-assignment': lambda i, v: [f"{i}- run: RUSTUP_TOOLCHAIN=$'{v}' cargo test"],
    'ansi-c-in-bash-c': lambda i, v: [f"{i}- run: bash -c $'cargo +{v} test'"],
    'shell-here-string': lambda i, v: [f"{i}- run: bash <<< 'cargo +{v} test'"],
    'shell-here-string-double': lambda i, v: [f'{i}- run: sh <<< "rustup default {v}"'],
    'shell-here-string-stdin-flag': lambda i, v: [f"{i}- run: bash -s <<< 'rustc +{v} -vV'"],
    'shell-here-string-ansi-c': lambda i, v: [f"{i}- run: bash <<< $'cargo +{v} test'"],
    'shell-source-stdin': lambda i, v: [f"{i}- run: source /dev/stdin <<< 'cargo +{v} test'"],
    'shell-dot-stdin-heredoc': lambda i, v: [f'{i}- run: |', f'{i}    . /dev/stdin <<EOF', f'{i}    rustup default {v}', f'{i}    EOF'],
    'shell-operand-stdin': lambda i, v: [f"{i}- run: bash /dev/stdin <<< 'cargo +{v} test'"],
    'shell-dash-operand': lambda i, v: [f"{i}- run: bash - <<< 'cargo +{v} test'"],
    'shell-process-substitution': lambda i, v: [f"{i}- run: bash <(echo 'cargo +{v} test')"],
    'shell-source-process-substitution': lambda i, v: [f"{i}- run: source <(echo 'rustup default {v}')"],
    'shell-pipe-echo': lambda i, v: [f"{i}- run: echo 'cargo +{v} test' | bash"],
    'shell-pipe-printf': lambda i, v: [f"{i}- run: printf '%s\\n' 'rustup default {v}' | sh"],
    'shell-pipe-download': lambda i, v: [f"{i}- run: curl --proto '=https' -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain {v}"],
    'shell-input-file': lambda i, v: [f"{i}- run: bash < ./select.sh # {v}"],
    'wrapper-positional-forwarding': lambda i, v: [f"{i}- run: bash -c 'exec \"$@\"' _ cargo +{v} test"],
    'wrapper-positional-command': lambda i, v: [f"{i}- run: sh -c '\"$@\"' _ rustc +{v} -vV"],
    'wrapper-positional-selector': lambda i, v: [f"{i}- run: bash -c 'cargo \"$1\" test' _ +{v}"],
    'wrapper-positional-rustup': lambda i, v: [f"{i}- run: bash -c 'command \"$@\"' _ rustup default {v}"],
    'wrapper-positional-unbound': lambda i, v: [f'{i}- run: |', f'{i}    run() {{ "$@"; }}', f'{i}    run cargo +{v} test'],
    'wrapper-positional-unquoted-string': lambda i, v: [f"{i}- run: bash -c '$1' _ 'cargo +{v} test'"],
    'wrapper-set-positional': lambda i, v: [f'{i}- run: |', f'{i}    set -- cargo +{v} test', f'{i}    exec "$@"'],
    'wrapper-variable-command': lambda i, v: [f'{i}- run: |', f'{i}    tool="cargo +{v} test"', f'{i}    $tool'],
    'wrapper-exported-variable-command': lambda i, v: [f'{i}- run: |', f'{i}    export tool="rustup default {v}"', f'{i}    ${{tool}}'],
    'wrapper-brace-expansion': lambda i, v: [f'{i}- run: |', f'{i}    {{cargo,+{v},test}}'],
    'wrapper-eval-substitution': lambda i, v: [f'{i}- run: eval "$(echo cargo +{v} test)"'],
    'formatted-github-env': lambda i, v: [f'{i}- run: printf "%s=%s\\n" RUSTUP_TOOLCHAIN {v} >> "$GITHUB_ENV"'],
    'formatted-github-env-format-name': lambda i, v: [f"{i}- run: printf 'RUSTUP_TOOLCHAIN=%s\\n' {v} >> $GITHUB_ENV"],
    'formatted-github-env-tee': lambda i, v: [f"{i}- run: printf 'RUSTUP_TOOLCHAIN=%s\\n' {v} | tee -a \"$GITHUB_ENV\""],
    'github-env-echo-escapes': lambda i, v: [f"{i}- run: echo -e 'A=1\\nRUSTUP_TOOLCHAIN={v}' >> \"$GITHUB_ENV\""],
    'github-env-ansi-c': lambda i, v: [f"{i}- run: echo $'RUSTUP_TOOLCHAIN\\x3d{v}' >> \"$GITHUB_ENV\""],
    'github-env-dynamic-name': lambda i, v: [f'{i}- run: printf "%s=%s\\n" "$KEY" {v} >> "$GITHUB_ENV"'],
    'github-env-copied-file': lambda i, v: [f'{i}- run: cat selection.env >> "$GITHUB_ENV" # {v}'],
    'github-env-whole-environment': lambda i, v: [f'{i}- run: env >> "$GITHUB_ENV" # {v}'],
    'github-env-group': lambda i, v: [f'{i}- run: |', f'{i}    {{ echo A=1; }} >> "$GITHUB_ENV" # {v}'],
    'github-env-alias': lambda i, v: [f'{i}- run: |', f'{i}    target=$GITHUB_ENV # {v}', f'{i}    echo A=1 >> "$target"'],
    'toolchain-matrix-expression': lambda i, v: [f'{i}- uses: ./.github/actions/rust-cache', f'{i}  with:', f'{i}    toolchain: ${{{{ matrix.rust }}}} # {v}'],
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
            'authoritative-expression': lambda i: [f'{i}- run: cargo +${{{{ env.RUSTUP_TOOLCHAIN }}}} test'],
            'authoritative-expression-compact': lambda i: [f'{i}- run: cargo +${{{{env.RUSTUP_TOOLCHAIN}}}} test'],
            'authoritative-braced-quoted': lambda i: [f'{i}- run: cargo "+${{RUSTUP_TOOLCHAIN}}" test'],
            'authoritative-needs-output': lambda i: [f'{i}- run: rustup toolchain install ${{{{ needs.selection.outputs.rust_toolchain }}}}'],
            'authoritative-through-path': lambda i: [f'{i}- run: |', f'{i}    "${{CARGO_HOME}}/bin/cargo" +"$RUSTUP_TOOLCHAIN" test'],
            'authoritative-assignment': lambda i: [f'{i}- run: RUSTUP_TOOLCHAIN=${{{{ env.RUSTUP_TOOLCHAIN }}}} cargo test'],
            'authoritative-github-env': lambda i: [f'{i}- run: echo "RUSTUP_TOOLCHAIN=$RUSTUP_TOOLCHAIN" >> "$GITHUB_ENV"'],
            'authoritative-step-env-flow': lambda i: [f'{i}- run: cargo test',
                                                      f'{i}  env: {{"RUSTUP_TOOLCHAIN": "${{{{ env.RUSTUP_TOOLCHAIN }}}}"}}'],
            'authoritative-with-flow': lambda i: [f'{i}- uses: ./.github/actions/rust-cache',
                                                  f'{i}  with: {{toolchain: "${{{{ env.RUSTUP_TOOLCHAIN }}}}"}}'],
            'rust-commands-that-select-nothing': lambda i: [f'{i}- run: |', f'{i}    cargo test --locked', f'{i}    "cargo" fmt --check',
                                                              f'{i}    rustup component add clippy', f'{i}    rustup show active-toolchain',
                                                              f'{i}    rustup update'],
            'authoritative-here-string': lambda i: [f"{i}- run: bash <<< 'cargo +\"$RUSTUP_TOOLCHAIN\" test'"],
            'authoritative-positional': lambda i: [f"{i}- run: bash -c 'exec \"$@\"' _ cargo +\"$RUSTUP_TOOLCHAIN\" test"],
            'authoritative-positional-selector': lambda i: [f"{i}- run: bash -c 'cargo +\"$RUSTUP_TOOLCHAIN\" \"$@\"' _ test"],
            'authoritative-ansi-c-command': lambda i: [f"{i}- run: $'cargo' +\"$RUSTUP_TOOLCHAIN\" test"],
            'authoritative-pipe': lambda i: [f"{i}- run: printf 'cargo +%s test\\n' \"$RUSTUP_TOOLCHAIN\" | sh"],
            'authoritative-formatted-github-env': lambda i: [f'{i}- run: printf "%s=%s\\n" RUSTUP_TOOLCHAIN "$RUSTUP_TOOLCHAIN" >> "$GITHUB_ENV"'],
            'authoritative-formatted-github-env-expression': lambda i: [
                f"{i}- run: printf 'RUSTUP_TOOLCHAIN=%s\\n' '${{{{ env.RUSTUP_TOOLCHAIN }}}}' | tee -a \"$GITHUB_ENV\""],
            'github-env-unrelated-variables': lambda i: [f'{i}- run: |', f'{i}    printf "%s=%s\\n" CARGO_TERM_COLOR always >> "$GITHUB_ENV"',
                                                         f'{i}    echo "CI_LANE=fast" >> "$GITHUB_ENV"', f'{i}    echo "$HOME/bin" >> "$GITHUB_PATH"'],
            'shell-channels-that-select-nothing': lambda i: [f'{i}- run: |', f"{i}    bash <<< 'cargo test --locked'", f"{i}    echo 'cargo build' | sh",
                                                             f'{i}    bash -c \'exec "$@"\' _ cargo test', f'{i}    bash -c \'echo "$1"\' _ cargo',
                                                             f"{i}    printf '%s\\n' cargo +1.99.0 > notes.txt"],
            'text-that-is-not-a-command': lambda i: [f'{i}- run: |', f'{i}    echo "cargo +1.99.0 is spelled like this"',
                                                      f'{i}    # cargo +1.99.0 test', f'{i}    git log --grep "rustup default"',
                                                      f"{i}    echo $'cargo +1.99.0 is spelled like this'",
                                                      f"{i}    grep cargo <<< 'cargo +1.99.0 test'",
                                                      f'{i}    printf "%s\\n" "set RUSTUP_TOOLCHAIN in the workflow env"'],
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
    # A quoted job name is a distinct job: it never extends the fuzz-smoke exception to the jobs that follow.
    for spelling in ('  "review-other-job":', "  'review-other-job':", '  review-other-job:'):
        for value in ('nightly', 'stable'):
            job = f'{spelling}\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo +{value} test\n\n  package:\n'
            add('job-after-fuzz-smoke', 'quoted-job-key', value, dict(texts, **{main: texts[main].replace('  package:\n', job, 1)}))
    for name in ('fuzz-smoke-extra', '"fuzz-smoke-extra"', "'fuzz-smoke2'"):
        job = f'  {name}:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo +nightly test\n\n  package:\n'
        add('job-named-like-fuzz-smoke', 'similar-job-key', 'nightly', dict(texts, **{main: texts[main].replace('  package:\n', job, 1)}))
    add('fuzz-smoke-in-another-file', 'new-workflow', 'nightly', dict(texts, **{'.github/workflows/other.yml': '\n'.join(
        ['name: n', 'on: push', 'jobs:', '  fuzz-smoke:', '    runs-on: ubuntu-latest', '    steps:', '      - run: cargo +nightly test']) + '\n'}))
    add('fuzz-smoke-quoted-key-is-the-same-job', 'quoted-fuzz-job', 'nightly', dict(texts, **{main: texts[main].replace(
        '  fuzz-smoke:\n', '  "fuzz-smoke":\n', 1)}), expect_reject=False)
    # Every selection is judged alone: the excused command does not excuse another one in the same script or line.
    for second in ('"cargo" +1.98.0 test', 'cargo +1.98.0 test', '/opt/rust/bin/cargo +stable test', 'rustup update stable',
                   'rustup toolchain install nightly stable', 'rustc +beta -vV'):
        for template in ('cargo +nightly test; {}', 'cargo +nightly test && {}', '{} || cargo +nightly test', 'echo ok | {}'):
            command = template.format(second)
            lines = texts[main].split('\n')
            index = anchored(main, '  fuzz-smoke:', '    steps:')
            changed = '\n'.join(lines[:index + 1] + [f'      - run: {command}'] + lines[index + 1:])
            add('mixed-selections-on-one-line', 'job-steps-fuzz-smoke', command, dict(texts, **{main: changed}))
    add('unchanged-current-ci', 'all', 'current', texts, expect_reject=False)
    return cases


# The historical toolchain allowance of rust_listing.checked(...) is read in one place only: reconcile, for
# a receipt read back from a bound immutable source. The guard below owns these directories: every Python
# file under scripts/, evas/, experiments/ and benchmark/ (build output, Git data and virtual
# environments excluded) and the Python files at the repository root. Test modules (test_*.py) are exempt.
# The two loaders may hand the module to another owned file, so every owned file is also followed for what it does
# with checked: an alias (assignment, tuple, attribute store, getattr) that is called with `historical` or
# forwarded, the checked attribute of a parameter used as a value, and, in a file that mentions `historical`, a
# parameter's attribute chosen at run time. A plain alias that is only called strictly is allowed.
HISTORICAL_ROOTS = ('scripts', 'evas', 'experiments', 'benchmark')
HISTORICAL_SKIPPED_DIRECTORIES = frozenset(['.git', 'target', 'node_modules', '__pycache__', 'venv', '.venv', 'site-packages'])
LISTING_MODULE = 'evas/capabilities/rust_listing.py'
# The only files that may name the module: it defines checked(); the Registry loads it for reconcile; the
# catalogue generator loads it to apply the strict check to a new registration.
LISTING_LOADERS = frozenset(['evas/capabilities/asset_catalog.py', 'scripts/capabilities/generate_catalog.py'])
LISTING_REFERENCE = re.compile(r'(?<![\w])rust_listing(?:\.py)?(?![\w])')


def historical_python_files(root):
    """The Python files the historical guard owns, as absolute paths."""
    root = Path(root)
    found = sorted(path for path in root.glob('*.py') if path.is_file())
    for base in HISTORICAL_ROOTS:
        for directory, names, files in os.walk(root / base):
            names[:] = sorted(name for name in names if name not in HISTORICAL_SKIPPED_DIRECTORIES)
            found.extend(Path(directory) / name for name in sorted(files) if name.endswith('.py'))
    return found


def historical_checked_calls(root):
    """Everything that reaches checked() beyond its strict default, outside tests, as (path, function, details).

    It reports a call of checked that sets or forwards `historical`, whether checked is called by name, through an
    alias, or through a getattr; a partial() that binds `historical`; any file other than the module and its two
    loaders that names the rust_listing module, however it imports, aliases or loads it; in any file, an alias of
    checked that is called with `historical` or forwarded, the checked attribute of an object passed in as a
    parameter used as a value, and a parameter's attribute chosen at run time, in a file that mentions `historical`; and, in the module and the
    loaders, any use of checked that is not a plain call (an import under another name, an assignment, an
    argument, a string). A plain alias that is only called without `historical` is allowed. A file Python cannot
    parse that names the module or `historical` is reported rather than skipped.
    """
    import ast

    def refers(node, named=False, known=frozenset()):
        """Whether the expression is checked itself: x.checked, getattr(x, 'checked'), x.__dict__['checked'], a name
        already bound to one of these and, when the file may import it (named), the bare name checked."""
        if isinstance(node, ast.Attribute):
            return node.attr == 'checked' or '.' + node.attr in known
        if isinstance(node, ast.Name):
            return node.id in known or (named and node.id == 'checked')
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            if name == 'getattr' and len(node.args) >= 2:
                return isinstance(node.args[1], ast.Constant) and node.args[1].value == 'checked'
            if name in ('partial', 'partialmethod') and node.args:
                return refers(node.args[0], named, known)
            return False
        if isinstance(node, ast.Subscript):
            index = node.slice
            holder = node.value
            return (isinstance(index, ast.Constant) and index.value == 'checked'
                    and (isinstance(holder, ast.Attribute) and holder.attr == '__dict__'
                         or isinstance(holder, ast.Call) and getattr(holder.func, 'id', '') == 'vars'))
        if isinstance(node, ast.IfExp):
            return refers(node.body, named, known) or refers(node.orelse, named, known)
        if isinstance(node, ast.BoolOp):
            return any(refers(value, named, known) for value in node.values)
        return False

    def targets_of(node):
        """The names an assignment binds; an attribute target binds '.attribute'."""
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, ast.Attribute):
            return ['.' + node.attr]
        if isinstance(node, (ast.Tuple, ast.List)):
            return [name for element in node.elts for name in targets_of(element)]
        if isinstance(node, ast.Starred):
            return targets_of(node.value)
        return []

    def alias_assignments(tree, named):
        """(names bound to checked, ids of the expressions that are the right-hand side of such an alias)."""
        assignments = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                assignments.append((node.targets, node.value))
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
                assignments.append(([node.target], node.value))
        names, sides = set(), set()
        changed = True
        while changed:
            changed = False
            for targets, value in assignments:
                pairs = [(targets, value)]
                if (isinstance(value, (ast.Tuple, ast.List)) and len(targets) == 1
                        and isinstance(targets[0], (ast.Tuple, ast.List)) and len(targets[0].elts) == len(value.elts)):
                    pairs = [([target], element) for target, element in zip(targets[0].elts, value.elts)]
                for pair_targets, element in pairs:
                    if refers(element, named, names):
                        sides.add(id(element))
                        for name in (n for target in pair_targets for n in targets_of(target)):
                            if name not in names:
                                names.add(name)
                                changed = True
        return names, sides

    class Finder(ast.NodeVisitor):
        def __init__(self, strict, aliases, sides, undecidable):
            self.stack, self.calls, self.strict = ['<module>'], [], strict
            self.undecidable = undecidable
            self.aliases, self.sides = aliases, sides
            self.callees = set()
            self.parameters = [frozenset()]

        def note(self, *details):
            self.calls.append((self.stack[-1], tuple(details)))

        def enter(self, node, name):
            arguments = node.args
            names = {a.arg for a in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg]
                     if a is not None} - {'self', 'cls'}
            self.parameters.append(self.parameters[-1] | names)
            if name:
                self.stack.append(name)
            self.generic_visit(node)
            if name:
                self.stack.pop()
            self.parameters.pop()

        def visit_FunctionDef(self, node):
            self.enter(node, node.name)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Lambda(self, node):
            self.enter(node, None)

        def passed_in(self, node):
            return isinstance(node, ast.Name) and node.id in self.parameters[-1]

        def visit_Call(self, node):
            func = node.func
            self.callees.add(id(func))
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            forwards = any(keyword.arg in ('historical', None) for keyword in node.keywords)
            through_alias = (isinstance(func, ast.Name) and func.id in self.aliases
                             or isinstance(func, ast.Attribute) and '.' + func.attr in self.aliases)
            if (name == 'checked' or through_alias or refers(func, self.strict, self.aliases)) and forwards:
                self.note(*(ast.unparse(keyword.value) for keyword in node.keywords))
            elif name in ('partial', 'partialmethod') and forwards:
                self.note('partial binds historical')
            for value in [*node.args, *(keyword.value for keyword in node.keywords)]:
                value = value.value if isinstance(value, ast.Starred) else value
                if (isinstance(value, ast.Name) and value.id in self.aliases
                        or isinstance(value, ast.Attribute) and '.' + value.attr in self.aliases):
                    self.note('an alias of checked is passed on')
            if self.undecidable and name in ('getattr', 'hasattr') and len(node.args) >= 2 and self.passed_in(node.args[0]) \
                    and not (isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
                self.note('an attribute of a passed-in object is chosen at run time')
            if self.undecidable and name == 'vars' and node.args and self.passed_in(node.args[0]):
                self.note('the namespace of a passed-in object is read')
            self.generic_visit(node)

        def visit_Return(self, node):
            self.returned(node.value)
            self.generic_visit(node)

        def visit_Yield(self, node):
            self.returned(node.value)
            self.generic_visit(node)

        def returned(self, value):
            if (isinstance(value, ast.Name) and value.id in self.aliases
                    or isinstance(value, ast.Attribute) and '.' + value.attr in self.aliases):
                self.note('an alias of checked is returned')

        def visit_Name(self, node):
            if self.strict and node.id == 'checked' and id(node) not in self.callees:
                self.note('checked used as a value')

        def visit_Attribute(self, node):
            if node.attr == 'checked' and id(node) not in self.callees:
                if self.strict:
                    self.note('checked used as a value')
                elif self.passed_in(node.value) and id(node) not in self.sides:
                    self.note('checked of a passed-in object is used as a value')
            if self.undecidable and node.attr == '__dict__' and self.passed_in(node.value):
                self.note('the namespace of a passed-in object is read')
            self.generic_visit(node)

        def visit_alias(self, node):
            if self.strict and node.name in ('checked', '*') and node.asname:
                self.note('checked imported under another name')

        def visit_Constant(self, node):
            if self.strict and node.value == 'checked':
                self.note('checked named by a string')

    calls = []
    root = Path(root)
    for path in historical_python_files(root):
        if path.name.startswith('test_') or path.name == 'git_fixture.py':
            continue
        relative = str(path.relative_to(root))
        text = path.read_text(encoding='utf-8', errors='replace')
        names_module = relative != LISTING_MODULE and bool(LISTING_REFERENCE.search(text))
        if names_module and relative not in LISTING_LOADERS:
            calls.append((relative, '<module>', ('names the rust_listing module',)))
        strict = relative == LISTING_MODULE or relative in LISTING_LOADERS
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            if names_module or strict or 'historical' in text:
                calls.append((relative, '<module>', ('cannot be parsed',)))
            continue
        aliases, sides = alias_assignments(tree, strict)
        finder = Finder(strict, aliases, sides, 'historical' in text)
        finder.visit(tree)
        calls.extend((relative, function, details) for function, details in finder.calls)
    return sorted(set(calls))


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
        self.assert_one_fixed_rust_toolchain(HELPER.parents[2])

    def assert_one_fixed_rust_toolchain(self,root):
        helper=root/'scripts/capabilities/discover_rust.py'
        main=root/'.github/workflows/numerical-assurance.yml'
        text=main.read_text()
        pins=re.findall(r"^  RUSTUP_TOOLCHAIN: '([^']*)'$",text,re.M)
        self.assertEqual(len(pins),1)
        self.assertRegex(pins[0],r'^[0-9]+\.[0-9]+\.[0-9]+$')
        self.assertRegex(text,r"(?m)^env:\n  RUSTUP_TOOLCHAIN: '")
        # Every workflow, reusable workflow and composite action, not only the caller.
        ci=ci_files(root)
        self.assertIn(root/'.github/workflows/package-install.yml',ci)
        self.assertIn(root/'.github/actions/rust-cache/action.yml',ci)
        channel=(r'\+stable',r'(?:toolchain install|update|default|override set)\s+stable\b',
                 r'(?m)^\s*(?:- )?toolchain:\s*[\'"]?stable\b',r'RUSTUP_TOOLCHAIN:\s*[\'"]?stable\b')
        for path in [*ci,helper,root/'scripts/ci_evidence.py',root/'scripts/ci_lint.py']:
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
        self.assert_toolchain_selection_whitelist(HELPER.parents[2])
        self.assert_variant_matrix(ci_texts(HELPER.parents[2]))

    def assert_toolchain_selection_whitelist(self,root):
        texts=ci_texts(root)
        self.assertIn(CACHE_ACTION,texts)
        self.assertIn('.github/workflows/package-install.yml',texts)
        self.assertEqual(toolchain_selection_violations(texts,toolchain_files(root)),[])

    def assert_variant_matrix(self,texts):
        counts={}
        for form,location,value,changed,files,expect_reject in selection_variant_cases(texts):
            found=toolchain_selection_violations(changed,files)
            counts.setdefault(expect_reject,[0,0]);counts[expect_reject][0]+=1
            counts[expect_reject][1]+=bool(found)==expect_reject
            if bool(found)!=expect_reject:self.fail(f'{form} at {location} with {value}: expected reject={expect_reject}, got {found}')
        self.assertGreater(counts[True][0],1900)
        self.assertGreater(counts[False][0],100)
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
        self.assert_reusable_workflows_take_the_fixed_toolchain(HELPER.parents[2])

    def assert_reusable_workflows_take_the_fixed_toolchain(self,root):
        main=(root/'.github/workflows/numerical-assurance.yml').read_text()
        # selection is the one job that reads the workflow-level env into an output.
        selection=re.search(r'^  selection:\n(.*?)(?=^  fast-checks:)',main,re.M|re.S).group(1)
        self.assertEqual(re.findall(r'^      rust_toolchain: (.*)$',selection,re.M),['${{ env.RUSTUP_TOOLCHAIN }}'])
        parts=re.split(r'(?m)^  ([a-z-]+):\n',main[main.index('\njobs:\n'):])
        jobs=dict(zip(parts[1::2],parts[2::2]))
        reusable=[path for path in ci_files(root) if path.parent==root/'.github/workflows' and re.search(r'(?m)^  workflow_call:',path.read_text())]
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


class _StrictRun(unittest.TestCase):
    """Runs a guard body outside any subTest, so a failing assertion reaches the caller."""

    def runTest(self):
        pass

    def subTest(self, *args, **kwargs):
        return contextlib.nullcontext()


def _builtin(value):
    if isinstance(value, dict):
        return {str(key): _builtin(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_builtin(item) for item in value]
    return None if value is None else str(value)


WORKFLOW_PROBE = 'name: probe\non: push\njobs:\n  probe:\n    runs-on: ubuntu-latest\n    steps:\n      - run: {}\n'
ACTION_PROBE = 'name: probe\ndescription: probe\nruns:\n  using: composite\n  steps:\n    - shell: bash\n      run: {}\n'
REUSABLE_PROBE = ('name: probe\non:\n  workflow_call:\njobs:\n  probe:\n    runs-on: ubuntu-latest\n    steps:\n'
                  '      - run: rustup toolchain install "$RUSTUP_TOOLCHAIN"\n')


class CiEnumerationTests(unittest.TestCase):
    """The three CI guards read the same file set, and it holds both workflow extensions and both action names."""

    def write_tree(self, root, files):
        for relative, text in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)

    def copy_ci_root(self, destination):
        root = HELPER.parents[2]
        for relative in ('scripts/capabilities/discover_rust.py', 'scripts/ci_evidence.py', 'scripts/ci_lint.py',
                         'evas/capabilities/rust_listing.py'):
            self.write_tree(destination, {relative: (root / relative).read_text()})
        self.write_tree(destination, {str(path.relative_to(root)): path.read_text() for path in ci_files(root)})
        return destination

    def test_enumeration_is_the_one_set_of_workflow_and_action_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wanted = ['.github/actions/deep/er/action.yaml', '.github/actions/rust-cache/action.yml',
                      '.github/workflows/a.yml', '.github/workflows/b.yaml']
            ignored = ['.github/workflows/nested/c.yml', '.github/workflows/d.yml.disabled', '.github/workflows/README.md',
                       '.github/actions/rust-cache/other.yml', '.github/actions/rust-cache/action.yml.bak', 'docs/e.yml']
            self.write_tree(root, {name: 'name: x\n' for name in [*wanted, *ignored]})
            self.assertEqual([str(path.relative_to(root)) for path in ci_files(root)], wanted)
            self.assertEqual(sorted(ci_texts(root)), wanted)
        real = ci_texts(HELPER.parents[2])
        self.assertTrue({MAIN_WORKFLOW, CACHE_ACTION, '.github/workflows/package-install.yml'} <= set(real))

    def test_a_workflow_or_action_in_the_second_spelling_reaches_every_guard(self):
        strict = _StrictRun()
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_ci_root(Path(tmp) / 'repo')
            for name in ('assert_one_fixed_rust_toolchain', 'assert_toolchain_selection_whitelist',
                         'assert_reusable_workflows_take_the_fixed_toolchain'):
                getattr(RustListingTests, name)(strict, root)          # the untouched copy passes all three
            baseline = toolchain_selection_violations(ci_texts(root))
            self.assertEqual(baseline, [])
            probes = {
                'assert_toolchain_selection_whitelist': [
                    {'.github/workflows/review-probe.yaml': WORKFLOW_PROBE.format('cargo +nightly test')},
                    {'.github/actions/review-probe/action.yaml': ACTION_PROBE.format('cargo +nightly test'),
                     '.github/workflows/review-caller.yml': WORKFLOW_PROBE.format('true').replace(
                         '      - run: true', '      - uses: ./.github/actions/review-probe')},
                    {'.github/workflows/review-probe.yaml': WORKFLOW_PROBE.format('true').replace(
                        '      - run: true', '      - uses: ./.github/actions/missing')}],
                'assert_one_fixed_rust_toolchain': [
                    {'.github/workflows/review-probe.yaml': WORKFLOW_PROBE.format('rustup toolchain install 1.98.0')},
                    {'.github/actions/review-probe/action.yaml': ACTION_PROBE.format('rustup toolchain install 1.98.0')}],
                'assert_reusable_workflows_take_the_fixed_toolchain': [
                    {'.github/workflows/review-reusable.yaml': REUSABLE_PROBE}],
            }
            for guard, variants in probes.items():
                for files in variants:
                    with self.subTest(guard=guard, files=sorted(files)):
                        scratch = Path(tmp) / ('variant-' + hashlib.sha256(repr(sorted(files)).encode()).hexdigest()[:8])
                        self.copy_ci_root(scratch)
                        self.write_tree(scratch, files)
                        with self.assertRaises(AssertionError):
                            getattr(RustListingTests, guard)(strict, scratch)
            # The same probes in the first spelling are caught too, so the second spelling is not treated differently.
            scratch = Path(tmp) / 'first-spelling'
            self.copy_ci_root(scratch)
            self.write_tree(scratch, {'.github/workflows/review-probe.yml': WORKFLOW_PROBE.format('cargo +nightly test')})
            with self.assertRaises(AssertionError):
                RustListingTests.assert_toolchain_selection_whitelist(strict, scratch)


class CiYamlReaderTests(unittest.TestCase):
    """The reader that turns workflow text into structure: what it reads, and what it refuses instead of skipping."""

    READ = {
        'block-mapping-and-sequence': ('a:\n  b: 1\n  c:\n    - x\n    - y\n', {'a': {'b': '1', 'c': ['x', 'y']}}),
        'sequence-at-the-key-indent': ('steps:\n- run: a\n- run: b\nnext: 1\n', {'steps': [{'run': 'a'}, {'run': 'b'}], 'next': '1'}),
        'wide-dash': ('- name:   n\n  run:   r\n', [{'name': 'n', 'run': 'r'}]),
        'nested-dash': ('- - a\n  - b\n- c\n', [['a', 'b'], 'c']),
        'comments': ('# top\na: 1 # trailing\n# between\nb: "x # kept"\n', {'a': '1', 'b': 'x # kept'}),
        'empty-and-null': ('a:\nb: ""\nc: \'\'\n', {'a': None, 'b': '', 'c': ''}),
        'quoted-keys': ('"RUSTUP_TOOLCHAIN": "1.98.0"\n\'toolchain\': \'nightly\'\n', {'RUSTUP_TOOLCHAIN': '1.98.0', 'toolchain': 'nightly'}),
        'flow-mapping': ('env: {RUSTUP_TOOLCHAIN: "1.98.0", OTHER: x}\n', {'env': {'RUSTUP_TOOLCHAIN': '1.98.0', 'OTHER': 'x'}}),
        'flow-mapping-json-colon': ('env: {"RUSTUP_TOOLCHAIN":"1.98.0"}\n', {'env': {'RUSTUP_TOOLCHAIN': '1.98.0'}}),
        'flow-sequence-of-flow-mappings': ('include: [{a: 1}, {b: [2, 3]},]\n', {'include': [{'a': '1'}, {'b': ['2', '3']}]}),
        'flow-over-lines': ('with: {lane: x,\n  toolchain: nightly} # c\nnext: 1\n', {'with': {'lane': 'x', 'toolchain': 'nightly'}, 'next': '1'}),
        # An expression is one unit even where strict YAML would split or refuse the scalar around its punctuation.
        'flow-with-expression-comma': ('a: {k: "${{ format(\'{0},{1}\', a, b) }}"}\nb: [${{ fromJSON(x, y) }}, z]\n',
                                       {'a': {'k': "${{ format('{0},{1}', a, b) }}"}, 'b': ['${{ fromJSON(x, y) }}', 'z']}),
        'flow-uses': ('- {uses: "dtolnay/rust-toolchain@1.98.0"}\n', [{'uses': 'dtolnay/rust-toolchain@1.98.0'}]),
        'literal-block': ('run: |\n  a\n   b\n\n  c\nnext: 1\n', {'run': 'a\n b\n\nc\n', 'next': '1'}),
        'literal-strip-and-keep': ('a: |-\n  x\n\nb: |+\n  y\n\nc: 1\n', {'a': 'x', 'b': 'y\n\n', 'c': '1'}),
        'folded-block': ('run: >\n  cargo\n  +1.98.0 test\n\n  next\n', {'run': 'cargo +1.98.0 test\nnext\n'}),
        'folded-strip': ('run: >-\n  one\n  two\n', {'run': 'one two'}),
        'block-with-indent-indicator': ('run: |2\n    a\n  b\n', {'run': '  a\nb\n'}),
        'block-header-comment': ('run: | # note\n  a\n', {'run': 'a\n'}),
        'block-in-sequence': ('- |\n  a\n- b\n', ['a\n', 'b']),
        'plain-over-lines': ('a: one\n  two\n\n  three\nb: 1\n', {'a': 'one two\nthree', 'b': '1'}),
        'double-quoted-escapes': ('a: "x\\ny\\t\\"z\\"\\u0041"\n', {'a': 'x\ny\t"z"A'}),
        'double-quoted-over-lines': ('a: "one\n  two\n\n  three"\n', {'a': 'one two\nthree'}),
        'single-quoted-escape': ("a: 'it''s'\n", {'a': "it's"}),
        'expression-in-plain': ('if: ${{ a == \'b: c\' && x }}\n', {'if': "${{ a == 'b: c' && x }}"}),
        'colon-without-space': ('url: http://example.com/a:b\n', {'url': 'http://example.com/a:b'}),
        'key-with-dashes-and-dots': ('runs-on: ubuntu-24.04\nwith.x: 1\n', {'runs-on': 'ubuntu-24.04', 'with.x': '1'}),
        'leading-document-start': ('# header\n---\na: 1\n', {'a': '1'}),
        'indicator-lookalikes': ('a: -1.98.0\nb: +x\nc: ~\n', {'a': '-1.98.0', 'b': '+x', 'c': '~'}),
    }
    REFUSED = {
        'anchor': 'a: &x 1\n', 'alias': 'a: *x\n', 'tag': 'a: !!str 1\n', 'anchor-on-key': '&x a: 1\n',
        'complex-key': '? a\n: 1\n', 'merge-key': '<<: {a: 1}\n', 'duplicate-key': 'a: 1\na: 2\n',
        'duplicate-flow-key': 'a: {b: 1, b: 2}\n', 'tab-indent': 'a:\n\tb: 1\n', 'second-document': 'a: 1\n---\nb: 2\n',
        'document-end': 'a: 1\n...\n', 'directive': '%YAML 1.2\na: 1\n', 'carriage-return': 'a: 1\r\nb: 2\r\n',
        'byte-order-mark': '\ufeffa: 1\n', 'unclosed-double-quote': 'a: "x\n', 'unclosed-single-quote': "a: 'x\n",
        'unclosed-flow': 'a: {b: 1\n', 'unclosed-expression': 'a: ${{ x\n', 'bad-indentation': 'a:\n    b: 1\n  c: 2\n',
        'text-after-flow': 'a: {b: 1} x\n', 'text-after-quote': 'a: "x" y\n', 'mapping-in-plain-scalar': 'a: b: c\n',
        'unsupported-escape': 'a: "\\q"\n', 'bad-block-header': 'a: |x\n  b\n', 'flow-pair-in-sequence': 'a: [b: c]\n',
        'document-start-after-content': 'a: 1\n---\n', 'sequence-where-key-expected': 'a: 1\n- b\n', 'flow-anchor': 'a: [&x 1]\n', 'complex-flow-key': 'a: {[b]: 1}\n',
    }

    def test_supported_forms_read_as_the_structure_they_mean(self):
        for name, (text, expected) in self.READ.items():
            with self.subTest(form=name):
                self.assertEqual(_builtin(parse_ci_yaml(text)), expected)

    def test_unsupported_or_ambiguous_yaml_is_refused_not_skipped(self):
        for name, text in self.REFUSED.items():
            with self.subTest(form=name):
                with self.assertRaises(CiYamlError):
                    parse_ci_yaml(text)

    def test_a_scalar_remembers_how_it_was_written(self):
        document = parse_ci_yaml("a: 'x'\nb: \"x\"\nc: x\nd: |\n  x\ne: >\n  x\nf: {g: 'x'}\n")
        self.assertEqual([document[key].style for key in 'abcde'], ['single', 'double', 'plain', 'literal', 'folded'])
        self.assertTrue(document['f'].flow)
        self.assertFalse(parse_ci_yaml('f:\n  g: x\n')['f'].flow)

    def test_every_ci_file_is_read_and_unanalysable_files_are_reported(self):
        for name, text in ci_texts(HELPER.parents[2]).items():
            with self.subTest(file=name):
                self.assertIsInstance(parse_ci_yaml(text), dict)
        for name, text in self.REFUSED.items():
            with self.subTest(refused=name):
                found = toolchain_selection_violations({'.github/workflows/odd.yml': text})
                self.assertEqual(len(found), 1, found)
                self.assertIn('unanalysable YAML', found[0])


class CiShellReaderTests(unittest.TestCase):
    """Shell words as the shell would resolve them, then the selections they make, in both directions."""

    WORDS = {
        'plain': ('cargo +1.98.0 test', [['cargo', '+1.98.0', 'test']]),
        'quoted-name': ('"cargo" +1.98.0 test', [['cargo', '+1.98.0', 'test']]),
        'quoted-selector': ('cargo "+1.98.0" test', [['cargo', '+1.98.0', 'test']]),
        'single-quotes': ("cargo '+1.98.0' 'a b'", [['cargo', '+1.98.0', 'a b']]),
        'path-with-expansion': ('"${CARGO_HOME}/bin/cargo" +1.98.0', [['${CARGO_HOME}/bin/cargo', '+1.98.0']]),
        'continuation': ('cargo \\\n  +1.98.0 test', [['cargo', '+1.98.0', 'test']]),
        'continuation-inside-word': ('car\\\ngo test', [['cargo', 'test']]),
        'github-expression-whole': ('cargo +${{ env.RUSTUP_TOOLCHAIN }} test', [['cargo', '+${{ env.RUSTUP_TOOLCHAIN }}', 'test']]),
        'expression-with-quotes': ("echo ${{ format('{0} {1}', a, b) }} x", [['echo', "${{ format('{0} {1}', a, b) }}", 'x']]),
        'parameter-expansion': ('rustc ${CI_RUST_TOOLCHAIN:++"$CI_RUST_TOOLCHAIN"} -vV', [['rustc', '${CI_RUST_TOOLCHAIN:++"$CI_RUST_TOOLCHAIN"}', '-vV']]),
        'separators': ('a; b && c || d | e & f\ng', [['a'], ['b'], ['c'], ['d'], ['e'], ['f'], ['g']]),
        'comments': ('cargo test # cargo +nightly\n# cargo +beta\nls', [['cargo', 'test'], ['ls']]),
        'hash-inside-word': ('echo a#b', [['echo', 'a#b']]),
        'redirects-are-not-arguments': ('cargo test > out.txt 2>&1 &> all.txt', [['cargo', 'test']]),
        'here-document': ('python - <<EOF\nrustup +x\nEOF\nls', [['python', '-'], ['ls']]),
        'here-document-quoted-tab': ("cat <<-'EOF'\n\trustup +x\n\tEOF\nls", [['cat'], ['ls']]),
        'subshell-and-braces': ('(cargo test); { cargo build; }', [['cargo', 'test'], ['{', 'cargo', 'build'], ['}']]),
        'substitution-body-is-separate': ('v=$(cargo --version)', [['v=$(cargo --version)']]),
        'escaped-char': ('cargo \\+1.98.0', [['cargo', '+1.98.0']]),
    }
    BAD_SHELL = ['echo "unterminated', "echo 'unterminated", 'echo `unterminated', 'echo $(unterminated', 'echo ${unterminated',
                 'echo ${{ unterminated']

    def test_words_are_resolved_like_the_shell_resolves_them(self):
        for name, (script, expected) in self.WORDS.items():
            with self.subTest(form=name):
                commands, _nested = lex_shell(script)
                self.assertEqual([[word.value for word in command.words] for command in commands], expected)

    def test_a_script_the_reader_cannot_close_is_reported(self):
        with self.assertRaises(CiYamlError):
            lex_shell('echo trailing\\')
        for script in self.BAD_SHELL:
            with self.subTest(script=script):
                with self.assertRaises(CiYamlError):
                    lex_shell(script)
                found = self.violations(script)
                self.assertEqual(len(found), 1, found)
                self.assertIn('unanalysable shell', found[0])

    def test_continuation_and_nested_scripts_are_marked_for_the_nightly_exception(self):
        self.assertTrue(lex_shell('cargo \\\n +x')[0][0].continued)
        self.assertFalse(lex_shell('cargo +x')[0][0].continued)
        self.assertEqual(lex_shell('v=$(a b) `c d` "$(e f)"')[1], ['a b', 'c d', 'e f'])

    def violations(self, script, *, job='regression', name=MAIN_WORKFLOW, style='|'):
        text = f'jobs:\n  {job}:\n    steps:\n      - run: {style}\n'
        text += ''.join(f'          {line}\n' for line in script.split('\n'))
        return toolchain_selection_violations({name: text, CACHE_ACTION: 'name: c\n', '.github/workflows/package-install.yml': 'name: p\n'})

    ACCEPTED = [
        'cargo test --locked', 'cargo build --release', '"cargo" fmt --check', '${CARGO_HOME}/bin/cargo test',
        'cargo +$RUSTUP_TOOLCHAIN test', 'cargo +"$RUSTUP_TOOLCHAIN" test', 'cargo "+${RUSTUP_TOOLCHAIN}" test',
        'cargo +${{ env.RUSTUP_TOOLCHAIN }} test', 'cargo +${{env.RUSTUP_TOOLCHAIN}} test',
        'cargo +${{ inputs.rust_toolchain }} test', 'cargo +${{ needs.selection.outputs.rust_toolchain }} test',
        'rustup toolchain install "$RUSTUP_TOOLCHAIN" --profile minimal --component clippy --component rustfmt',
        'rustup toolchain install ${{ env.RUSTUP_TOOLCHAIN }}', 'rustup install "$RUSTUP_TOOLCHAIN"',
        'rustup update "$RUSTUP_TOOLCHAIN"', 'rustup update', 'rustup default "$RUSTUP_TOOLCHAIN"',
        'rustup override set --path . "$RUSTUP_TOOLCHAIN"', 'rustup run "$RUSTUP_TOOLCHAIN" cargo test',
        'rustup component add clippy', 'rustup component add clippy --toolchain "$RUSTUP_TOOLCHAIN"',
        'rustup target add wasm32-unknown-unknown', 'rustup show active-toolchain', 'rustup toolchain list',
        'rustup which cargo', 'rustup --version', 'rustup self update',
        'RUSTUP_TOOLCHAIN="$RUSTUP_TOOLCHAIN" cargo test', 'RUSTUP_TOOLCHAIN=${{ env.RUSTUP_TOOLCHAIN }} cargo test',
        'env RUSTUP_TOOLCHAIN=$RUSTUP_TOOLCHAIN cargo test', 'export RUSTUP_TOOLCHAIN="$RUSTUP_TOOLCHAIN"',
        'echo "RUSTUP_TOOLCHAIN=$RUSTUP_TOOLCHAIN" >> "$GITHUB_ENV"',
        'echo "cargo +1.99.0 is how a selection is spelled"', 'git log --grep "rustup default"', '# cargo +1.99.0 test',
        'cargo test # cargo +1.99.0', 'python3 -B scripts/x.py --toolchain-report out', 'ls +1.99.0',
        'cat <<EOF\ncargo +1.99.0\nEOF', 'python3 - <<\'PY\'\nprint("rustup default 1.99.0")\nPY',
        'v=$(rustc --version)', 'cargo test || rustup show', 'if cargo test; then rustup show; fi',
    ]
    REJECTED = [
        'cargo +1.98.0 test', '"cargo" +1.98.0 test', 'cargo "+1.98.0" test', '${CARGO_HOME}/bin/cargo +1.98.0 test',
        '"${CARGO_HOME}/bin/cargo" +1.98.0 test', '/opt/rust/bin/cargo +1.98.0 test', './tools/cargo +1.98.0 test',
        'cargo \\\n  +1.98.0 test', 'cargo +1.99.1x test', 'cargo + test', 'cargo ${EXTRA} test', 'cargo $tc test',
        'rustc +1.98.0 -vV', 'rustdoc +beta --version', 'rustfmt +stable --check', 'cargo-clippy +nightly',
        'rustup update 1.98.0', 'rustup update "$RUSTUP_TOOLCHAIN" 1.98.0', 'rustup toolchain install 1.98.0',
        'rustup toolchain install "$RUSTUP_TOOLCHAIN" 1.98.0', 'rustup toolchain install 1.98.0 "$RUSTUP_TOOLCHAIN"',
        'rustup toolchain install "$RUSTUP_TOOLCHAIN" --profile minimal 1.98.0', 'rustup install 1.98.0',
        'rustup toolchain install', 'rustup default', 'rustup default 1.98.0', 'rustup override set 1.98.0',
        'rustup override frobnicate', 'rustup run 1.98.0 cargo test', 'rustup run "$RUSTUP_TOOLCHAIN" cargo +1.98.0 test',
        'rustup component add clippy --toolchain 1.98.0', 'rustup target add x --toolchain=1.98.0', 'rustup +1.98.0 show',
        'rustup which --toolchain 1.98.0 cargo', 'rustup toolchain link custom /opt/tc', 'rustup toolchain frobnicate',
        'rustup frobnicate', 'rustup install --frobnicate "$RUSTUP_TOOLCHAIN"', 'rustup uninstall 1.98.0',
        'RUSTUP_TOOLCHAIN=1.98.0 cargo test', 'RUSTUP_TOOLCHAIN="1.98.0" cargo test', 'export RUSTUP_TOOLCHAIN=1.98.0',
        'env RUSTUP_TOOLCHAIN=1.98.0 cargo test', 'env "RUSTUP_TOOLCHAIN=1.98.0" cargo test',
        'echo "RUSTUP_TOOLCHAIN=1.98.0" >> "$GITHUB_ENV"', 'echo RUSTUP_TOOLCHAIN=${x} >> "$GITHUB_ENV"',
        'cat >> "$GITHUB_ENV" <<EOF\nRUSTUP_TOOLCHAIN=1.98.0\nEOF', 'echo "a RUSTUP_TOOLCHAIN=1.98.0 b"',
        'env cargo +1.98.0 test', 'sudo -E cargo +1.98.0 test', 'command cargo +1.98.0 test', 'time cargo +1.98.0 test',
        'FOO="x" cargo +1.98.0 test', 'FOO=x BAR=y cargo +1.98.0 test', 'bash -c \'cargo +1.98.0 test\'',
        'sh -ec "cargo +1.98.0 test"', 'eval "cargo +1.98.0 test"', 'eval cargo +1.98.0 test', 'v=$(cargo +1.98.0 --version)',
        'v=`cargo +1.98.0 --version`', 'v="$(cargo +1.98.0 --version)"', '(cargo +1.98.0 test)', '{ cargo +1.98.0 test; }',
        'if true; then cargo +1.98.0 test; fi', 'for t in 1; do cargo +1.98.0 test; done', 'echo go | cargo +1.98.0 test',
        'true && cargo +1.98.0 test', 'false || cargo +1.98.0 test', 'cargo test; cargo +1.98.0 test',
        'bash <<EOF\ncargo +1.98.0 test\nEOF', 'cat <<EOF | bash\ncargo +1.98.0 test\nEOF', "alias cargo='cargo +1.98.0'",
        'find . -name x -exec cargo +1.98.0 test {} \\;', 'parallel cargo +1.98.0 test ::: a b',
        'cmd="cargo +1.98.0 test"; eval "$cmd"', 'bash -c "$CMD"', 'env $TOOL test', 'bash -s <<EOF\nrustup default 1.98.0\nEOF',
        '$CARGO +1.98.0 test', '"$CARGO" +1.98.0 test', 'tc=+1.98.0; cargo "$tc" test', 'cargo "$@"',
        'env -S "cargo +1.98.0 test"', 'xargs cargo +1.98.0 test', 'rustup toolchain install $UNKNOWN_SELECTOR',
        'echo stable', 'echo nightly > file', 'for t in stable beta; do true; done', 'cat <<EOF\nstable\nEOF',
    ]

    def test_selections_that_are_not_authoritative_are_found(self):
        for script in self.REJECTED:
            with self.subTest(script=script):
                self.assertTrue(self.violations(script), script)

    def test_authoritative_and_unrelated_commands_are_not_rejected(self):
        for script in self.ACCEPTED:
            with self.subTest(script=script):
                self.assertEqual(self.violations(script), [], script)

    def test_scripts_of_other_shells_and_container_images_cannot_hide_a_selection(self):
        def document(step, defaults=''):
            return {MAIN_WORKFLOW: f'{defaults}jobs:\n  regression:\n    steps:\n      - {step}\n'}
        refused = [
            document('shell: python\n        run: |\n          import subprocess\n          subprocess.run(["cargo", "+1.98.0", "test"])'),
            document('shell: pwsh\n        run: cargo test'),
            document('run: cargo test', 'defaults:\n  run:\n    shell: python\n'),
            document('run: cargo test\n        shell: "python {0}"'),
            document('uses: ./.github/actions/rust-cache\n        with: {lane: x}\n        container: rust:1.98.0'),
            {MAIN_WORKFLOW: 'jobs:\n  regression:\n    container:\n      image: rust:1.98.0\n    steps: []\n'},
            {MAIN_WORKFLOW: 'jobs:\n  regression:\n    container: ghcr.io/rust-lang/rust:nightly\n    steps: []\n'},
        ]
        accepted = [
            document('shell: bash\n        run: cargo test --locked'),
            document('shell: "bash -e {0}"\n        run: cargo test --locked'),
            document('shell: sh\n        run: cargo test --locked'),
            document('shell: python\n        run: print("no rust tooling here")'),
            document('run: cargo test', 'defaults:\n  run:\n    shell: bash\n'),
            {MAIN_WORKFLOW: 'jobs:\n  regression:\n    container:\n      image: ubuntu:24.04\n    steps: []\n'},
        ]
        extra = {CACHE_ACTION: 'name: c\n', '.github/workflows/package-install.yml': 'name: p\n'}
        for texts in refused:
            with self.subTest(refused=texts[MAIN_WORKFLOW]):
                self.assertTrue(toolchain_selection_violations(dict(texts, **extra)))
        for texts in accepted:
            with self.subTest(accepted=texts[MAIN_WORKFLOW]):
                self.assertEqual(toolchain_selection_violations(dict(texts, **extra)), [])

    def test_the_same_scripts_behave_the_same_inside_every_yaml_scalar_style(self):
        for script in ('cargo +1.98.0 test', 'cargo +${{ env.RUSTUP_TOOLCHAIN }} test'):
            for style in ('|', '|-', '>', '>-'):
                if style.startswith('>') and '\n' in script:
                    continue
                with self.subTest(script=script, style=style):
                    found = self.violations(script, style=style)
                    self.assertEqual(bool(found), '1.98.0' in script)

    def test_nightly_is_excused_only_for_the_exact_command_of_jobs_fuzz_smoke(self):
        excused = ['cargo +nightly test', 'cargo "+nightly" test', 'rustup toolchain install nightly --profile minimal',
                   'rustup install nightly', 'cargo +nightly test; cargo +nightly fuzz run x', 'if x; then cargo +nightly test; fi',
                   'echo go | cargo +nightly test', 'v=$(cargo +nightly --version)']
        refused = ['cargo +nightly test; "cargo" +1.98.0 test', 'cargo +nightly test; cargo +stable test',
                   'rustup toolchain install nightly stable', 'rustup toolchain install "$RUSTUP_TOOLCHAIN" nightly',
                   'rustup default nightly', 'rustup update nightly', 'rustup run nightly cargo test', 'rustc +nightly -vV',
                   'rustup component add clippy --toolchain nightly', '"cargo" +nightly test', '/opt/rust/bin/cargo +nightly test',
                   'cargo \\\n +nightly test', 'env cargo +nightly test', 'bash -c "cargo +nightly test"', 'X=1 cargo +nightly test',
                   'cargo +nightly\\\ntest', 'echo nightly']
        for job, name, accepted in (('fuzz-smoke', MAIN_WORKFLOW, True), ('fuzz-smoke', '.github/workflows/other.yml', False),
                                    ('fuzz-smoke2', MAIN_WORKFLOW, False), ('regression', MAIN_WORKFLOW, False)):
            for script in excused:
                with self.subTest(job=job, file=name, script=script):
                    self.assertEqual(bool(self.violations(script, job=job, name=name)), not accepted)
            for script in refused:
                with self.subTest(job=job, file=name, script=script, refused=True):
                    self.assertTrue(self.violations(script, job=job, name=name))
        folded = self.violations('cargo\n+nightly test', job='fuzz-smoke', style='>')
        self.assertTrue(folded, 'a folded scalar hides where the command breaks, so it carries no exception')


class CiShellInputChannelTests(unittest.TestCase):
    """The ways a command or a toolchain choice reaches a shell without being spelled as a plain command word.

    The restricted shell subset is read as follows. Words: quotes, backslashes, ANSI-C quoting ($'...' with its
    escapes decoded), GitHub expressions and parameter expansions. A command word may be a variable the same script
    set to a literal (VAR=text, export VAR=text), which is expanded and, unquoted, split at whitespace; any other
    command word that is a positional parameter, or a command built by brace expansion, is refused. Input channels
    of a shell (sh, bash, ...) and of `source`: the -c string with the arguments that follow it bound to $0, $1, $@
    and $* (also by `set --`, and split at whitespace when unquoted); otherwise its here-documents and here-strings;
    a script piped in from echo, printf or cat is read as that text. A shell fed from any other pipe, from a file
    redirect or from a process substitution is refused, and so is eval of a string built by expansion. Writes to
    $GITHUB_ENV: echo, printf and cat of text that can be read (also through tee) are rendered and each line must be
    NAME=value with a literal NAME, where RUSTUP_TOOLCHAIN only takes an authoritative reference; any other writer,
    and any other use of the file name, is refused. Not read: a script file named as an operand, the data a pipe
    hands to xargs, variables whose value comes from the environment, a command or a computed variable name, and
    steps that are not shell (github-script and the like).
    """

    violations = CiShellReaderTests.violations

    DECODED = {
        'plain-letters': ("$'cargo' +1.98.0", [['cargo', '+1.98.0']]),
        'hex': ("$'\\x63argo' test", [['cargo', 'test']]),
        'octal': ("$'c\\141rgo'", [['cargo']]),
        'unicode': ("$'\\u0063argo'", [['cargo']]),
        'control-escapes': ("echo $'a\\tb\\nc'", [['echo', 'a\tb\nc']]),
        'escaped-quote-inside': ("echo $'it\\'s' x", [['echo', "it's", 'x']]),
        'joined-with-plain': ("ca$'rgo' $'+'1.98.0", [['cargo', '+1.98.0']]),
        'inside-double-quotes-is-literal': ('echo "$\'a\'"', [['echo', "$'a'"]]),
        'locale-string': ('echo $"cargo"', [['echo', 'cargo']]),
        'unknown-escape-stays': ("echo $'\\q'", [['echo', '\\q']]),
    }

    def test_ansi_c_quoting_is_resolved_like_the_shell_resolves_it(self):
        for name, (script, expected) in self.DECODED.items():
            with self.subTest(form=name):
                commands, _nested = lex_shell(script)
                self.assertEqual([[word.value for word in command.words] for command in commands], expected)
        with self.assertRaises(CiYamlError):
            lex_shell("echo $'unterminated")

    def test_redirections_are_kept_by_direction_and_pipes_know_their_source(self):
        commands, _ = lex_shell("bash <<< 'cargo +x' < in.sh > out.txt 2>> err.txt")
        command = commands[0]
        self.assertEqual([[w.value for w in field] for field in (command.words, command.herestrings, command.inputs, command.outputs)],
                         [['bash'], ['cargo +x'], ['in.sh'], ['out.txt', 'err.txt']])
        commands, _ = lex_shell('echo a | tee -a f |\n  bash || true')
        self.assertEqual([c.piped for c in commands], [False, True, True, False])
        self.assertIs(commands[1].source, commands[0])
        self.assertIs(commands[2].source, commands[1])
        self.assertEqual([[w.value for w in c.words] for c in commands], [['echo', 'a'], ['tee', '-a', 'f'], ['bash'], ['true']])

    CHANNEL_REJECTED = [
        # ANSI-C quoting
        "$'cargo' +1.98.0 test", "$'\\x63argo' +1.98.0 test", "cargo $'+1.98.0' test", "$'rustup' default 1.98.0",
        "$'rustup' toolchain install $'1.98.0'", "RUSTUP_TOOLCHAIN=$'1.98.0' cargo test", "export RUSTUP_TOOLCHAIN=$'1.98.0'",
        "env $'cargo' +1.98.0 test", "bash -c $'cargo +1.98.0 test'", "echo $'RUSTUP_TOOLCHAIN\\x3d1.98.0' >> \"$GITHUB_ENV\"",
        "$'cargo' +nightly test",
        # shell stdin: here-strings, pipes, redirects
        "bash <<< 'cargo +1.98.0 test'", 'sh <<< "rustup default 1.98.0"', "bash -s <<< 'cargo +stable test'",
        "bash <<< $'cargo +1.98.0 test'", "source /dev/stdin <<< 'cargo +1.98.0 test'", ". /dev/stdin <<< 'rustup default 1.98.0'",
        "bash /dev/stdin <<< 'cargo +1.98.0 test'", "bash - <<< 'cargo +1.98.0 test'", "bash <(echo 'cargo +1.98.0 test')",
        "source <(echo 'rustup default 1.98.0')", ". <(curl -sSf https://x)", "bash -s -- a <<< 'cargo +1.98.0 test'", 'bash <<< "cargo +${tc} test"', "bash <<< 'cargo +1.98.0 test; cargo test'",
        "bash <<< 'bash -c \"cargo +1.98.0 test\"'", "env bash <<< 'cargo +1.98.0 test'", "sudo bash <<< 'rustup default 1.98.0'",
        "echo 'cargo +1.98.0 test' | bash", "printf '%s\\n' 'rustup default 1.98.0' | sh", "echo 'cargo +1.98.0' | cat | bash",
        "cat <<< 'cargo +1.98.0 test' | sh", "echo 'cargo' +1.98.0 | sh -s",
        "curl -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain 1.98.0", "curl -sSf https://x | bash",
        "bash < select.sh", "sh 0< select.sh", "echo x |\n  curl y |\n  bash",
        # positional parameters
        "bash -c 'exec \"$@\"' _ cargo +1.98.0 test", "sh -c '\"$@\"' _ cargo +stable test", "bash -c 'cargo \"$1\" test' _ +1.98.0",
        "bash -c 'command \"$@\"' x rustup default 1.98.0", "bash -c 'env \"$@\"' _ cargo +1.98.0", "bash -c 'time $*' _ cargo +x",
        "bash -c 'exec \"${@}\"' _ cargo +1.98.0 test", "bash -c 'exec \"$0\" +1.98.0 test' cargo", "bash -c 'rustup default \"$1\"' _ 1.98.0",
        "bash -c 'cargo \"$@\"' _ +1.98.0 test", "bash -c 'bash -c \"exec \\\"\\$@\\\"\" _ \"$@\"' _ cargo +1.98.0",
        "exec \"$@\"", "run() { \"$@\"; }\nrun cargo +1.98.0 test", "command \"$@\"", "env \"$@\"", "exec ${@:1}", "$1 +1.98.0 test",
        "bash -c 'exec \"$@\"' _ cargo +nightly test",
        "bash -c '$1' _ 'cargo +1.98.0 test'", "bash -c 'exec $@' _ 'cargo +1.98.0 test'", "bash -c 'exec $*' _ 'rustup default 1.98.0'",
        "set -- cargo +1.98.0 test\nexec \"$@\"", "set -- rustup default 1.98.0\nexec $@",
        "cmd='cargo +1.98.0 test'; $cmd", "cmd=\"cargo +1.98.0 test\"\n${cmd}", "export cmd=\"rustup default 1.98.0\"\n$cmd",
        "cmd=$'cargo +1.98.0 test'\n$cmd", "cmd=cargo\n$cmd +1.98.0 test",
        # $GITHUB_ENV
        'printf "%s=%s\\n" RUSTUP_TOOLCHAIN 1.98.0 >> "$GITHUB_ENV"', "printf 'RUSTUP_TOOLCHAIN=%s\\n' 1.98.0 >> $GITHUB_ENV",
        "printf '%s\\n' 'RUSTUP_TOOLCHAIN=1.98.0' | tee -a \"$GITHUB_ENV\"", "echo -e 'A=1\\nRUSTUP_TOOLCHAIN=1.98.0' >> \"$GITHUB_ENV\"",
        'echo "$name=1.98.0" >> "$GITHUB_ENV"', 'printf "%s=%s\\n" "$k" "$v" >> "$GITHUB_ENV"', 'env >> "$GITHUB_ENV"',
        'sed s/a/b/ x >> "$GITHUB_ENV"', 'cat file >> "$GITHUB_ENV"', 'f=$GITHUB_ENV; echo x >> "$f"', '{ echo A=1; } >> "$GITHUB_ENV"',
        '( echo A=1 ) >> "$GITHUB_ENV"', 'exec >> "$GITHUB_ENV"', 'echo RUSTUP_TOOLCHAIN=${x} >> "$GITHUB_ENV"',
        'printf "RUSTUP_TOOLCHAIN=%s\\n" "$x" >> "$GITHUB_ENV"', 'printf "RUSTUP_%s=1.98.0\\n" TOOLCHAIN >> "$GITHUB_ENV"',
        'echo "RUSTUP_TOOLCHAIN<<EOF\\n1.98.0\\nEOF" >> "$GITHUB_ENV"', "echo 'a b c' >> \"$GITHUB_ENV\"",
        'printf "%s=%s\\n" RUSTUP_TOOLCHAIN "${x}" >> "${GITHUB_ENV}"', 'cp toolchain.env "$GITHUB_ENV"', 'dd of="$GITHUB_ENV"',
        'printf "%*s=%s\\n" 3 RUSTUP_TOOLCHAIN 1.98.0 >> "$GITHUB_ENV"', 'echo hi | tee "$GITHUB_ENV" "$other"; sed x f | tee -a "$GITHUB_ENV"',
        # brace expansion and eval
        '{cargo,+1.98.0,test}', '{rustup,default,1.98.0}', 'eval "$(echo cargo +1.98.0 test)"', 'eval "$cmd"',
    ]
    CHANNEL_ACCEPTED = [
        "$'cargo' test", "cargo $'--features=a b' test", "echo $'cargo +1.98.0 is spelled like this'",
        "$'cargo' +\"$RUSTUP_TOOLCHAIN\" test", "echo $'line one\\nline two'", "bash -c $'cargo test'",
        "bash <<< 'cargo test'", "source /dev/stdin <<< 'cargo test'", "source ~/.cargo/env", '. "$HOME/.cargo/env"', "bash /dev/stdin <<< 'cargo test'",
        "source ./env.sh <<< 'cargo +1.98.0 test'", "bash <<< 'cargo +\"$RUSTUP_TOOLCHAIN\" test'", "grep cargo <<< 'cargo +1.98.0 test'",
        "cat <<< 'cargo +1.98.0 test'", "bash <<< 'echo \"cargo +1.98.0 is syntax\"'", "bash script.sh <<< 'x'", "bash",
        "echo 'cargo test' | bash", "printf 'cargo +%s test\\n' \"$RUSTUP_TOOLCHAIN\" | sh", "echo hi | bash script.sh", "echo x |\n  bash",
        "echo 'cargo +1.98.0 test' | grep cargo", "echo 'cargo +1.98.0 test' | cat", "cat file.sh | wc -l", "bash -c 'echo ok' < /dev/null",
        "bash -c 'exec \"$@\"' _ cargo test", "bash -c 'echo \"$1\"' _ cargo", "bash -c 'cargo test \"$@\"' _ --locked",
        "bash -c 'cargo +\"$RUSTUP_TOOLCHAIN\" \"$@\"' _ test", "bash -c 'exec \"$@\"' _", "bash -c 'echo \"$0 $#\"' name",
        "bash -c 'exec \"$@\"' _ cargo +\"$RUSTUP_TOOLCHAIN\" test", "cargo test \"$@\"",
        "bash -c '\"$1\"' _ 'cargo +1.98.0 test'", "bash -c '$1' _ 'cargo test'", "set -- cargo test\nexec \"$@\"",
        "cmd=\"cargo test\"; $cmd", "cmd=\"cargo +1.98.0 test\"\n\"$cmd\"", "cmd=x; cmd=$(foo); $cmd", "cmd=\"cargo +1.98.0 test\"; echo $cmd", "echo \"$@\" \"$1\"", "ls \"$(dirname \"$0\")\"",
        'printf "%s=%s\\n" RUSTUP_TOOLCHAIN "$RUSTUP_TOOLCHAIN" >> "$GITHUB_ENV"',
        "printf 'RUSTUP_TOOLCHAIN=%s\\n' '${{ env.RUSTUP_TOOLCHAIN }}' | tee -a \"$GITHUB_ENV\"",
        'printf "%s=%s\\n" CARGO_TERM_COLOR always >> "$GITHUB_ENV"', 'echo "CI_LANE=fast" >> "$GITHUB_ENV"',
        'echo "RUSTUP_TOOLCHAIN=$RUSTUP_TOOLCHAIN" >> "$GITHUB_ENV"', 'echo "RUSTUP_TOOLCHAIN=${{ env.RUSTUP_TOOLCHAIN }}" >> "$GITHUB_ENV"',
        'echo "A=1" | tee -a "$GITHUB_ENV"', 'echo "$HOME/bin" >> "$GITHUB_PATH"', 'echo "GITHUB_ENV is a file name"',
        'printf "%s\\n" "set RUSTUP_TOOLCHAIN in the workflow env"', 'cat >> "$GITHUB_ENV" <<EOF\nCI_LANE=fast\nEOF',
        'echo "RUSTUP_TOOLCHAIN=$RUSTUP_TOOLCHAIN" | tee -a "$GITHUB_ENV" > /dev/null', "echo A=1 >> out.txt", "echo {a,b} \"{x}\"",
        "cargo test --features={a,b}", "echo ${HOME}", "x=$(echo cargo)", "echo \"$(cat file)\" > /dev/null",
    ]

    def test_every_input_channel_that_hides_a_selection_is_refused(self):
        for script in self.CHANNEL_REJECTED:
            with self.subTest(script=script):
                self.assertTrue(self.violations(script), script)

    def test_the_same_channels_with_nothing_to_hide_are_not_refused(self):
        for script in self.CHANNEL_ACCEPTED:
            with self.subTest(script=script):
                self.assertEqual(self.violations(script), [], script)

    def test_every_channel_is_refused_in_the_main_workflow_and_in_new_workflow_and_action_files(self):
        for script in ("$'cargo' +1.98.0 test", "bash <<< 'cargo +1.98.0 test'", "bash -c 'exec \"$@\"' _ cargo +1.98.0 test",
                       'printf "%s=%s\\n" RUSTUP_TOOLCHAIN 1.98.0 >> "$GITHUB_ENV"'):
            for name in (MAIN_WORKFLOW, '.github/workflows/new.yaml', '.github/actions/new/action.yaml'):
                for job in ('regression', 'fuzz-smoke'):
                    with self.subTest(script=script, file=name, job=job):
                        self.assertTrue(self.violations(script, job=job, name=name))

    write_tree = CiEnumerationTests.write_tree
    copy_ci_root = CiEnumerationTests.copy_ci_root

    def test_the_four_reported_forms_are_refused_by_the_whitelist_guard_on_a_real_tree(self):
        strict = _StrictRun()
        forms = {
            'ansi-c-command': "$'cargo' +1.98.0 test",
            'shell-here-string': "bash <<< 'cargo +1.98.0 test'",
            'wrapper-positional-forwarding': 'bash -c \'exec "$@"\' _ cargo +1.98.0 test',
            'formatted-github-env': 'printf "%s=%s\\n" RUSTUP_TOOLCHAIN 1.98.0 >> "$GITHUB_ENV"',
        }
        authoritative = {
            'ansi-c-command': "$'cargo' +\"$RUSTUP_TOOLCHAIN\" test",
            'shell-here-string': "bash <<< 'cargo +\"$RUSTUP_TOOLCHAIN\" test'",
            'wrapper-positional-forwarding': 'bash -c \'exec "$@"\' _ cargo +"$RUSTUP_TOOLCHAIN" test',
            'formatted-github-env': 'printf "%s=%s\\n" RUSTUP_TOOLCHAIN "$RUSTUP_TOOLCHAIN" >> "$GITHUB_ENV"',
        }
        for form in forms:
            self.assertIn(form, STEP_FORMS)
        with tempfile.TemporaryDirectory() as tmp:
            for form, script in forms.items():
                for label, command, refused in (('selection', script, True), ('authoritative', authoritative[form], False)):
                    with self.subTest(form=form, kind=label):
                        scratch = Path(tmp) / f'{form}-{label}'
                        self.copy_ci_root(scratch)
                        self.write_tree(scratch, {'.github/workflows/probe.yaml': WORKFLOW_PROBE.format(command)})
                        if refused:
                            with self.assertRaises(AssertionError):
                                RustListingTests.assert_toolchain_selection_whitelist(strict, scratch)
                        else:
                            RustListingTests.assert_toolchain_selection_whitelist(strict, scratch)


class HistoricalGuardTests(unittest.TestCase):
    """The historical toolchain allowance has one reader, however a second one would be imported, aliased or loaded."""

    SPELLINGS = {
        'module-attribute': 'import rust_listing as rl\ndef read(r):\n    return rl.checked(r, historical=True)\n',
        'bare-import': 'from rust_listing import checked\ndef read(r):\n    return checked(r, historical=True)\n',
        'import-alias': 'from rust_listing import checked as verify\ndef read(r):\n    return verify(r, historical=True)\n',
        'assignment-alias': 'import rust_listing as rl\nverify = rl.checked\ndef read(r):\n    return verify(r, historical=True)\n',
        'annotated-alias': 'import rust_listing as rl\nverify: object = rl.checked\n',
        'tuple-alias': 'import rust_listing as rl\nverify, other = rl.checked, None\n',
        'partial': 'from functools import partial\nimport rust_listing as rl\nverify = partial(rl.checked, historical=True)\n',
        'partial-on-a-passed-module': 'import functools\ndef bind(listing):\n    return functools.partial(listing.checked, historical=True)\n',
        'forwarded-keywords': 'import rust_listing as rl\ndef read(r, **kwargs):\n    return rl.checked(r, **kwargs)\n',
        'literal-keywords': 'import rust_listing as rl\ndef read(r):\n    return rl.checked(r, **{"historical": True})\n',
        'getattr-string': 'import rust_listing as rl\ndef read(r):\n    return getattr(rl, "checked")(r, historical=True)\n',
        'dict-lookup': "import rust_listing as rl\ndef read(r):\n    return rl.__dict__['checked'](r, historical=True)\n",
        'import-module': "import importlib\nrl = importlib.import_module('rust_listing')\n",
        'file-loader': "import importlib.util\nspec = importlib.util.spec_from_file_location('m', 'evas/capabilities/rust_listing.py')\n",
        'star-import': 'from rust_listing import *\n',
        'registry-loader': "def load(catalog):\n    return catalog._history_module('rust_listing')\n",
        'unparsable': 'import rust_listing as rl\ndef read(:\n',
        'unparsable-historical': 'def read(r:\n    return checked(r, historical=True)\n',
    }
    LOCATIONS = ('', 'scripts', 'scripts/tests', 'scripts/capabilities', 'evas', 'evas/tests', 'evas/capabilities',
                 'evas/validation/deeper', 'experiments', 'experiments/backends/a/b', 'benchmark', 'benchmark/material/x/y')
    EXEMPT = ('scripts/target/reader.py', 'evas/rust_core/target/reader.py', 'experiments/node_modules/m/reader.py',
              'scripts/__pycache__/reader.py', 'scripts/test_reader.py', 'evas/tests/git_fixture.py', 'docs/reader.py', 'runs/reader.py')

    def tree(self, tmp, files):
        root = Path(tmp)
        for relative, text in files.items():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text(text)
        return root

    def test_a_second_reader_is_found_whatever_its_spelling_and_directory(self):
        for spelling, text in self.SPELLINGS.items():
            for location in self.LOCATIONS:
                relative = f'{location}/reader.py' if location else 'reader.py'
                with self.subTest(spelling=spelling, path=relative):
                    with tempfile.TemporaryDirectory() as tmp:
                        found = historical_checked_calls(self.tree(tmp, {relative: text}))
                    self.assertTrue(found)
                    self.assertEqual({path for path, _function, _details in found}, {relative})

    def test_the_guard_owns_experiments_benchmark_and_the_repository_root_but_not_build_output_or_tests(self):
        self.assertEqual(HISTORICAL_ROOTS, ('scripts', 'evas', 'experiments', 'benchmark'))
        root = HELPER.parents[2]
        owned = {path.relative_to(root).parts[0] for path in historical_python_files(root)}
        self.assertTrue(set(HISTORICAL_ROOTS) <= owned, owned)
        self.assertTrue({LISTING_MODULE, *LISTING_LOADERS} <= {str(path.relative_to(root)) for path in historical_python_files(root)})
        spelling = self.SPELLINGS['module-attribute']
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(historical_checked_calls(self.tree(tmp, {name: spelling for name in self.EXEMPT})), [])

    def test_the_module_and_its_two_loaders_use_checked_only_as_a_strict_call(self):
        strict = {
            'evas/capabilities/asset_catalog.py': "class C:\n    def reconcile_rust_listing(self, receipt, *, profile):\n"
                                                  "        return self._history_module('rust_listing').reconcile(self, receipt, profile)\n",
            'scripts/capabilities/generate_catalog.py': "listing = owned('catalog_generation_rust_listing', root/'evas/capabilities/rust_listing.py')\n"
                                                        "listing.checked(raw)\nactual = listing.checked(raw)\n",
            LISTING_MODULE: "def checked(receipt, *, historical=False):\n    return receipt\n"
                            "def reconcile(catalog, receipt, profile):\n    actual = checked(receipt)\n"
                            "    return checked(receipt, historical=True)\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(historical_checked_calls(self.tree(tmp, strict)), [(LISTING_MODULE, 'reconcile', ('True',))])
        for path, extra in (('evas/capabilities/asset_catalog.py', 'verify = module.checked\n'),
                            ('scripts/capabilities/generate_catalog.py', 'from rust_listing import checked as verify\n'),
                            ('scripts/capabilities/generate_catalog.py', "name = 'checked'\n"),
                            ('scripts/capabilities/generate_catalog.py', 'pick(listing.checked)\n'),
                            ('scripts/capabilities/generate_catalog.py', 'from functools import partial\nverify = partial(listing.checked, historical=True)\n'),
                            (LISTING_MODULE, 'verify = checked\n')):
            with self.subTest(path=path, extra=extra):
                with tempfile.TemporaryDirectory() as tmp:
                    files = dict(strict)
                    files[path] = files[path] + extra
                    found = historical_checked_calls(self.tree(tmp, files))
                self.assertNotEqual(found, [(LISTING_MODULE, 'reconcile', ('True',))])
                self.assertIn(path, {name for name, _function, _details in found})

    # A module handed to a function as an argument never has to be named by the file that uses it: the guard follows
    # checked through assignments, tuples, attribute stores, getattr, partial and returns, and refuses what it cannot decide.
    PARAMETER_SPELLINGS = {
        'assignment-alias': 'def read(listing, receipt):\n    verify = listing.checked\n    return verify(receipt, historical=True)\n',
        'alias-of-an-alias': 'def read(listing, receipt):\n    first = listing.checked\n    second = first\n    return second(receipt, historical=True)\n',
        'tuple-alias': 'def read(listing, receipt):\n    verify, other = listing.checked, None\n    return verify(receipt, historical=True)\n',
        'annotated-alias': 'def read(listing, receipt):\n    verify: object = listing.checked\n    return verify(receipt, historical=True)\n',
        'walrus-alias': 'def read(listing, receipt):\n    if (verify := listing.checked):\n        return verify(receipt, historical=True)\n',
        'attribute-store-alias': 'class Reader:\n    def __init__(self, listing):\n        self.verify = listing.checked\n'
                                 '    def read(self, receipt):\n        return self.verify(receipt, historical=True)\n',
        'getattr-alias': 'def read(listing, receipt):\n    verify = getattr(listing, "checked")\n    return verify(receipt, historical=True)\n',
        'getattr-call': 'def read(listing, receipt):\n    return getattr(listing, "checked")(receipt, historical=True)\n',
        'dict-lookup': 'def read(listing, receipt):\n    return listing.__dict__["checked"](receipt, historical=True)\n',
        'vars-lookup': 'def read(listing, receipt):\n    return vars(listing)["checked"](receipt, historical=True)\n',
        'direct-call': 'def read(listing, receipt):\n    return listing.checked(receipt, historical=True)\n',
        'literal-keywords': 'def read(listing, receipt):\n    return listing.checked(receipt, **{"historical": True})\n',
        'alias-forwarded-keywords': 'def read(listing, receipt, **options):\n    verify = listing.checked\n    return verify(receipt, **options)\n',
        'alias-passed-on': 'def read(listing, receipt):\n    verify = listing.checked\n    return apply(verify, receipt)\n',
        'alias-returned': 'def pick(listing):\n    verify = listing.checked\n    return verify\n',
        'attribute-passed-on': 'def read(listing, receipt):\n    return apply(listing.checked, receipt)\n',
        'attribute-in-a-container': 'def table(listing):\n    return {"verify": listing.checked}\n',
        'attribute-returned': 'def pick(listing):\n    return listing.checked\n',
        'partial': 'import functools\ndef bind(listing):\n    return functools.partial(listing.checked, historical=True)\n',
        'partial-alias': 'from functools import partial\ndef bind(listing):\n    verify = partial(listing.checked)\n    return verify(historical=True)\n',
        'lambda': 'def bind(listing):\n    return lambda receipt: listing.checked(receipt, historical=True)\n',
        'nested-function': 'def bind(listing):\n    def read(receipt):\n        verify = listing.checked\n        return verify(receipt, historical=True)\n    return read\n',
        'attribute-chosen-at-run-time': 'def read(listing, receipt, name):\n    return getattr(listing, name)(receipt, historical=True)\n',
        'namespace-read': 'def read(listing, receipt):\n    return vars(listing).get("chec" + "ked")(receipt, historical=True)\n',
    }
    # The same spellings are fine when nothing reaches historical: a strict alias, an unrelated attribute named checked.
    STRICT_SPELLINGS = {
        'strict-alias': 'def read(listing, receipt):\n    verify = listing.checked\n    return verify(receipt)\n',
        'strict-direct-call': 'def read(listing, receipt):\n    return listing.checked(receipt)\n',
        'strict-alias-chain': 'def read(listing, receipt):\n    first = listing.checked\n    second = first\n    return second(receipt)\n',
        'strict-getattr-alias': 'def read(listing, receipt):\n    verify = getattr(listing, "checked")\n    return verify(receipt)\n',
        'strict-attribute-store': 'class Reader:\n    def __init__(self, listing):\n        self.verify = listing.checked\n'
                                  '    def read(self, receipt):\n        return self.verify(receipt)\n',
        'unrelated-attribute-value': 'def count(row, footprint):\n    original = row.rhs\n    checked = (*original.checked, footprint)\n    return len(original.checked) + len(checked)\n',
        'unrelated-method': 'class Audit:\n    def run(self, check):\n        self.checked(check)\n        return self.checked\n',
        'unrelated-key': 'def read(row, name):\n    return row["checked"], getattr(row, name)\n',
        'unrelated-historical-keyword': 'def read(registry, qualification):\n    return registry.qualified(qualification, historical=True)\n',
        'unrelated-dynamic-attribute': 'def read(obj, name):\n    return getattr(obj, name)(), vars(obj)\n',
    }

    def test_a_module_passed_in_as_an_argument_cannot_carry_checked_to_historical(self):
        for spelling, text in self.PARAMETER_SPELLINGS.items():
            for location in ('scripts', 'scripts/capabilities', 'evas/capabilities', 'experiments/x', 'benchmark/material/y', ''):
                relative = f'{location}/reader.py' if location else 'reader.py'
                with self.subTest(spelling=spelling, path=relative):
                    with tempfile.TemporaryDirectory() as tmp:
                        found = historical_checked_calls(self.tree(tmp, {relative: text}))
                    self.assertTrue(found)
                    self.assertEqual({path for path, _function, _details in found}, {relative})

    def test_strict_aliases_and_unrelated_names_in_any_file_are_not_refused(self):
        for spelling, text in self.STRICT_SPELLINGS.items():
            for location in ('scripts', 'evas/src/evas', 'experiments/x', 'benchmark/material/y', ''):
                relative = f'{location}/reader.py' if location else 'reader.py'
                with self.subTest(spelling=spelling, path=relative):
                    with tempfile.TemporaryDirectory() as tmp:
                        self.assertEqual(historical_checked_calls(self.tree(tmp, {relative: text})), [])

    def test_a_loader_that_hands_the_module_to_another_owned_file_is_judged_by_what_that_file_does_with_it(self):
        strict = {
            'evas/capabilities/asset_catalog.py': "class C:\n    def reconcile_rust_listing(self, receipt, *, profile):\n"
                                                  "        return self._history_module('rust_listing').reconcile(self, receipt, profile)\n",
            'scripts/capabilities/generate_catalog.py': "from context_reader import read\n"
                                                        "listing = owned('catalog_generation_rust_listing', root/'evas/capabilities/rust_listing.py')\n"
                                                        "listing.checked(raw)\n\ndef probe(listing_module, receipt):\n    return read(listing_module, receipt)\n",
            LISTING_MODULE: "def checked(receipt, *, historical=False):\n    return receipt\n"
                            "def reconcile(catalog, receipt, profile):\n    actual = checked(receipt)\n"
                            "    return checked(receipt, historical=True)\n",
        }
        single = [(LISTING_MODULE, 'reconcile', ('True',))]
        helpers = {
            'assignment-alias': ('def read(listing, receipt):\n    verify = listing.checked\n    return verify(receipt, historical=True)\n', False),
            'direct-call-control': ('def read(listing, receipt):\n    return listing.checked(receipt, historical=True)\n', False),
            'strict-alias-control': ('def read(listing, receipt):\n    verify = listing.checked\n    return verify(receipt)\n', True),
        }
        for name, (helper, passes) in helpers.items():
            with self.subTest(helper=name):
                with tempfile.TemporaryDirectory() as tmp:
                    found = historical_checked_calls(self.tree(tmp, dict(strict, **{'scripts/context_reader.py': helper})))
                if passes:
                    self.assertEqual(found, single)
                else:
                    self.assertIn('scripts/context_reader.py', {path for path, _function, _details in found})
                    self.assertNotEqual(found, single)

    def test_unrelated_names_are_not_mistaken_for_the_module_or_its_function(self):
        names = ("def checked(x):\n    return x\nvalue = checked(1)\nother = [checked, 'checked']\n"
                 "x = catalog.reconcile_rust_listing(receipt, profile=p)\ny = read_rust_listing(root, item)\n"
                 "z = importlib.util.spec_from_file_location('_rust_listing_registry', path)\n"
                 "registry.qualified(name, historical=True)\n")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(historical_checked_calls(self.tree(tmp, {'scripts/other.py': names, 'experiments/x/other.py': names})), [])


if __name__ == '__main__':
    unittest.main()
