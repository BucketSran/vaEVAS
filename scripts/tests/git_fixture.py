"""Keep scripts/tests Git fixtures inside the scratch directory that owns them.

Inherited repository location and config injection are removed before a fixture
or the program under test runs Git. Explicit Git-dir, work-tree, and config
path redirects are resolved before Git runs, including during init. Only the
command forms these fixtures use are accepted.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlparse


class GitFixtureBoundary(RuntimeError):
    """A fixture Git operation would leave its scratch directory."""


_LOCATION = frozenset({
    'GIT_DIR',
    'GIT_WORK_TREE',
    'GIT_COMMON_DIR',
    'GIT_INDEX_FILE',
    'GIT_OBJECT_DIRECTORY',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
    'GIT_NAMESPACE',
    'GIT_PREFIX',
})
_EXPLICIT = ContextVar('git_fixture_explicit', default={})


def injected(name):
    """True for repository location variables and Git config injection."""
    return name in _LOCATION or name == 'GIT_CONFIG' or name.startswith('GIT_CONFIG_')


def _resolved(path):
    return Path(path).expanduser().resolve()


def _inside(path, scratch):
    try:
        _resolved(path).relative_to(_resolved(scratch))
    except ValueError:
        return False
    return True


def _require(path, scratch, label):
    if not _inside(path, scratch):
        raise GitFixtureBoundary(
            f'{label} escapes fixture scratch: {_resolved(path)} is outside {_resolved(scratch)}')
    return _resolved(path)


def build_env(source=None, explicit=None):
    """Drop inherited Git location and config injection, then apply explicit config."""
    base = os.environ if source is None else source
    env = {key: value for key, value in base.items() if not injected(key)}
    allowed = dict(_EXPLICIT.get())
    if explicit:
        for key in explicit:
            if key in _LOCATION:
                raise GitFixtureBoundary('explicit fixture config cannot redirect Git location: ' + key)
        allowed.update(explicit)
    env.update(allowed)
    return env


def child_env(source=None, **updates):
    """Environment for a program under test. Location variables cannot be reintroduced."""
    explicit = {}
    ordinary = {}
    for key, value in updates.items():
        if key in _LOCATION:
            raise GitFixtureBoundary('refusing to pass Git location variable ' + key)
        if injected(key):
            explicit[key] = value
        else:
            ordinary[key] = value
    env = build_env(source, explicit)
    env.update(ordinary)
    return env


@contextmanager
def explicit(**values):
    """Pass fixture config such as a host-policy GIT_CONFIG_GLOBAL for the duration."""
    for key in values:
        if key in _LOCATION:
            raise GitFixtureBoundary('explicit fixture config cannot redirect Git location: ' + key)
    current = dict(_EXPLICIT.get())
    current.update(values)
    token = _EXPLICIT.set(current)
    saved = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        _EXPLICIT.reset(token)
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


@contextmanager
def isolate(explicit_config=None):
    """Remove inherited Git location and config injection from this process."""
    token = None
    if explicit_config:
        current = dict(_EXPLICIT.get())
        current.update(explicit_config)
        token = _EXPLICIT.set(current)
    saved = os.environ.copy()
    try:
        for key in list(os.environ):
            if injected(key):
                del os.environ[key]
        os.environ.update(_EXPLICIT.get())
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)
        if token is not None:
            _EXPLICIT.reset(token)


def bind(case, scratch):
    """Isolate the current test and remember the scratch that may contain its Git dirs."""
    case.git_scratch = Path(scratch)
    context = isolate()
    context.__enter__()
    case.addCleanup(context.__exit__, None, None, None)
    return case.git_scratch


class _Parsed:
    def __init__(self):
        self.start = None
        self.git_dir = None
        self.work_tree = None
        self.configs = []
        self.command = ''
        self.command_args = ()


def _take_value(args, index, token, attached):
    if attached:
        return token.split('=', 1)[1], index + 1
    if index + 1 >= len(args):
        raise GitFixtureBoundary('missing value for ' + token)
    return args[index + 1], index + 2


def parse_git_args(args):
    tokens = list(args)
    if tokens and tokens[0] == 'git':
        tokens = tokens[1:]
    parsed = _Parsed()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == '--':
            index += 1
            break
        attached = token.split('=', 1)[0] if token.startswith('--') and '=' in token else None
        name = attached or token
        if name in ('-C', '--git-dir', '--work-tree') or (
                token.startswith('-C') and token != '-C'):
            if token.startswith('-C') and token != '-C':
                value, index = token[2:], index + 1
                name = '-C'
            else:
                value, index = _take_value(tokens, index, token, attached is not None)
            if name == '-C':
                base = Path(parsed.start) if parsed.start is not None else Path.cwd()
                parsed.start = str((base / value).resolve() if not Path(value).is_absolute() else Path(value))
            elif name == '--git-dir':
                parsed.git_dir = value
            elif name == '--work-tree':
                parsed.work_tree = value
            continue
        if token == '-c' or (token.startswith('-c') and not token.startswith('-C')):
            if token == '-c':
                value, index = _take_value(tokens, index, token, False)
            else:
                value, index = token[2:], index + 1
            parsed.configs.append(value)
            continue
        if token.startswith('-') and token not in ('-', '--'):
            raise GitFixtureBoundary('unsupported Git option: ' + token)
        break
    if index >= len(tokens):
        raise GitFixtureBoundary('missing Git command')
    parsed.command = tokens[index]
    parsed.command_args = tuple(tokens[index + 1:])
    return parsed


def _absolute(value, base):
    path = Path(value)
    if not path.is_absolute():
        path = Path(base) / path
    return path


def _local_source(value):
    if '://' in value:
        parsed = urlparse(value)
        if parsed.scheme != 'file':
            raise GitFixtureBoundary('fixture clone source must be a local path')
        return Path(unquote(parsed.path))
    return Path(value)


def _interpret_dotgit(git_path, repo):
    if git_path.is_symlink():
        return git_path.resolve()
    if git_path.is_file():
        line = git_path.read_text().strip()
        if not line.startswith('gitdir:'):
            raise GitFixtureBoundary('invalid .git file')
        raw = Path(line.split(':', 1)[1].strip())
        if not raw.is_absolute():
            raw = repo / raw
        return raw.resolve()
    if git_path.is_dir():
        return git_path.resolve()
    raise GitFixtureBoundary('unsupported .git entry')


def _common_dir(git_dir):
    marker = git_dir / 'commondir'
    if marker.is_symlink() or marker.is_file():
        raw = Path(marker.read_text().strip())
        if not raw.is_absolute():
            raw = git_dir / raw
        return raw.resolve()
    return git_dir.resolve()


def _work_tree(git_dir, start):
    pointer = git_dir / 'gitdir'
    if pointer.is_file() and not pointer.is_symlink():
        raw = Path(pointer.read_text().strip())
        if not raw.is_absolute():
            raw = git_dir / raw
        return raw.resolve().parent
    if git_dir.name == '.git':
        return git_dir.parent
    if (git_dir / 'HEAD').exists() and git_dir.suffix == '.git':
        return None
    return Path(start).resolve()


def _discover(start, scratch):
    current = Path(start).resolve()
    root = _resolved(scratch)
    while True:
        git_path = current / '.git'
        if git_path.is_symlink() or git_path.exists():
            return _interpret_dotgit(git_path, current)
        if current == root or current.parent == current:
            return None
        parent = current.parent
        try:
            parent.relative_to(root)
        except ValueError:
            return None
        current = parent


def _reject_linked_storage(git_dir, common, scratch):
    objects = common / 'objects'
    if objects.is_symlink():
        _require(objects, scratch, 'object directory')
    alternates = objects / 'info' / 'alternates'
    if alternates.is_symlink():
        _require(alternates, scratch, 'alternates file')
    if alternates.is_file():
        for line in alternates.read_text().splitlines():
            raw = line.strip()
            if not raw or raw.startswith('#'):
                continue
            path = Path(raw)
            if not path.is_absolute():
                path = objects / path
            _require(path, scratch, 'alternates entry')
    index = git_dir / 'index'
    if index.is_symlink():
        _require(index, scratch, 'index')


_PATH_CONFIG = {'core.worktree': 'work tree', 'core.hooksPath': 'hooks path'}
_SET_CONFIG = {'user.email', 'user.name', 'commit.gpgsign', 'uploadpack.allowFilter', 'core.hooksPath'}
_OVERRIDE_CONFIG = {'user.name', 'user.email', 'commit.gpgsign', 'core.hooksPath'}
_QUERY_CONFIG = {'commit.gpgsign', 'core.hooksPath', 'user.name', 'user.email'}


def _split_args(args, valued):
    flags = []
    positionals = []
    values = {}
    index = 0
    while index < len(args):
        token = args[index]
        if token == '--':
            positionals.extend(args[index + 1:])
            break
        attached = token.split('=', 1)[0] if token.startswith('--') and '=' in token else None
        name = attached or token
        if name in valued:
            if attached:
                values.setdefault(name, []).append(token.split('=', 1)[1])
                index += 1
            else:
                if index + 1 >= len(args):
                    raise GitFixtureBoundary('missing value for ' + token)
                values.setdefault(name, []).append(args[index + 1])
                index += 2
            continue
        if token.startswith('-') and token != '-':
            flags.append(token)
            index += 1
            continue
        positionals.append(token)
        index += 1
    return flags, positionals, values


def _guard_assignment(text, base, scratch):
    if '=' not in text:
        raise GitFixtureBoundary('fixture config override must be key=value')
    key, value = text.split('=', 1)
    if key in _PATH_CONFIG:
        _require(_absolute(value, base), scratch, _PATH_CONFIG[key])
    if key == 'core.worktree':
        raise GitFixtureBoundary('unsupported fixture config redirect: core.worktree')
    if key not in _OVERRIDE_CONFIG:
        raise GitFixtureBoundary('unsupported fixture config override: ' + key)


def _guard_explicit_locations(parsed, base, scratch):
    """Check command redirects before init or any other command can return early."""
    for item in parsed.configs:
        _guard_assignment(item, base, scratch)
    if parsed.git_dir is not None:
        git_dir = _require(_absolute(parsed.git_dir, base), scratch, 'git dir')
        if git_dir.exists():
            common = _require(_common_dir(git_dir), scratch, 'common dir')
            if parsed.work_tree is None:
                tree = _work_tree(git_dir, base)
                if tree is not None:
                    _require(tree, scratch, 'work tree')
            _reject_linked_storage(git_dir, common, scratch)
    if parsed.work_tree is not None:
        _require(_absolute(parsed.work_tree, base), scratch, 'work tree')


def _existing_git_dir(target, scratch):
    git_path = target / '.git'
    if git_path.is_symlink() or git_path.exists():
        git_dir = _require(_interpret_dotgit(git_path, target), scratch, 'existing git dir')
        common = _require(_common_dir(git_dir), scratch, 'common dir')
        _reject_linked_storage(git_dir, common, scratch)
        return git_dir
    return None


def _guard_init(args, base, scratch):
    flags, positionals, values = _split_args(
        args, {'-b', '--initial-branch', '--object-format', '--separate-git-dir'})
    separate = values.pop('--separate-git-dir', None)
    if separate:
        for value in separate:
            _require(_absolute(value, base), scratch, 'separate git dir')
        raise GitFixtureBoundary('unsupported init option: --separate-git-dir')
    if any(flag != '-q' for flag in flags) or set(values) - {'-b', '--initial-branch', '--object-format'}:
        raise GitFixtureBoundary('unsupported init option')
    if '-b' in values and '--initial-branch' in values:
        raise GitFixtureBoundary('unsupported init option')
    if len(positionals) > 1:
        raise GitFixtureBoundary('unsupported init arguments')
    target = _absolute(positionals[0], base) if positionals else Path(base)
    _require(target, scratch, 'init target')
    _existing_git_dir(target, scratch)


def _guard_clone(args, base, scratch):
    flags, positionals, values = _split_args(
        args, {'--filter', '--separate-git-dir', '--origin', '--branch', '-b', '--template',
               '--reference', '--depth'})
    separate = values.pop('--separate-git-dir', None)
    if separate:
        for value in separate:
            _require(_absolute(value, base), scratch, 'separate git dir')
        raise GitFixtureBoundary('unsupported clone option: --separate-git-dir')
    bare = flags == ['--bare'] and not values and len(positionals) == 2
    partial = (flags == ['--no-checkout'] and values == {'--filter': ['blob:none']}
               and len(positionals) == 2)
    if not bare and not partial:
        raise GitFixtureBoundary('unsupported clone arguments')
    source = _local_source(positionals[0])
    if not source.is_absolute():
        source = Path(base) / source
    destination = _absolute(positionals[1], base)
    _require(source, scratch, 'clone source')
    _require(destination, scratch, 'clone destination')


def _guard_config(args, base, scratch):
    kept = []
    index = 0
    while index < len(args):
        token = args[index]
        name = token.split('=', 1)[0] if token.startswith('--') and '=' in token else token
        if name in ('--file', '-f'):
            value, index = _take_value(args, index, token, name != token)
            _require(_absolute(value, base), scratch, 'config file')
            raise GitFixtureBoundary('unsupported fixture config file redirect')
        kept.append(token)
        index += 1
    if len(kept) == 3 and kept[0] in ('--global', '--local') and kept[1] == '--get':
        if kept[2] not in _QUERY_CONFIG:
            raise GitFixtureBoundary('unsupported config query: ' + kept[2])
        return
    if len(kept) == 2 and not str(kept[0]).startswith('-'):
        key, value = kept
        if key in _PATH_CONFIG:
            _require(_absolute(value, base), scratch, _PATH_CONFIG[key])
        if key == 'core.worktree':
            raise GitFixtureBoundary('unsupported fixture config redirect: core.worktree')
        if key in _SET_CONFIG:
            return
        raise GitFixtureBoundary('unsupported fixture config key: ' + key)
    raise GitFixtureBoundary('unsupported fixture config command')


def _guard_worktree(args, base, scratch):
    """The add destination is the path, never a trailing commit-ish such as HEAD."""
    if not args:
        raise GitFixtureBoundary('unsupported worktree command')
    subcommand = args[0]
    rest = args[1:]
    if subcommand == 'remove':
        if len(rest) != 1 or str(rest[0]).startswith('-'):
            raise GitFixtureBoundary('unsupported worktree remove arguments')
        _require(_absolute(rest[0], base), scratch, 'worktree path')
        return
    if subcommand != 'add':
        raise GitFixtureBoundary('unsupported worktree command: ' + subcommand)
    path = None
    extra = []
    unknown = []
    index = 0
    while index < len(rest):
        token = rest[index]
        if token in ('-b', '-B'):
            if index + 1 >= len(rest):
                raise GitFixtureBoundary('missing worktree branch name')
            index += 2
            continue
        if str(token).startswith('-'):
            unknown.append(token)
            index += 1
            continue
        if path is None:
            path = token
        else:
            extra.append(token)
        index += 1
    if path is None:
        raise GitFixtureBoundary('worktree add requires a path')
    _require(_absolute(path, base), scratch, 'worktree path')
    if unknown or extra:
        raise GitFixtureBoundary('unsupported worktree add arguments')


def _exact(flags, positionals, values, expected_flags, count):
    return flags == expected_flags and not values and len(positionals) == count


def _guard_supported(parsed, base, scratch):
    args = parsed.command_args
    command = parsed.command
    if command == 'init':
        _guard_init(args, base, scratch)
        return
    if command == 'clone':
        _guard_clone(args, base, scratch)
        return
    if command == 'config':
        _guard_config(args, base, scratch)
        return
    if command == 'worktree':
        _guard_worktree(args, base, scratch)
        return
    flags, positionals, values = _split_args(args, set())
    if command == 'add' and (
            _exact(flags, positionals, values, ['-A'], 0)
            or _exact(flags, positionals, values, [], len(positionals)) and positionals):
        return
    if command == 'commit' and (
            _exact(flags, positionals, values, ['-qm'], 1)
            or _exact(flags, positionals, values, ['-am'], 1)
            or _exact(flags, positionals, values, ['-m'], 1)):
        return
    if command == 'checkout' and (
            _exact(flags, positionals, values, ['-qb'], 1)
            or _exact(flags, positionals, values, ['-b'], 1)
            or _exact(flags, positionals, values, ['--detach'], 1)
            or _exact(flags, positionals, values, [], 1)):
        return
    if command == 'merge' and _exact(flags, positionals, values, ['--ff-only'], 1):
        return
    if command == 'reset' and _exact(flags, positionals, values, ['--hard'], 1):
        return
    if command == 'status' and _exact(flags, positionals, values, ['--porcelain'], 0):
        return
    if command == 'diff' and _exact(flags, positionals, values, ['--name-only'], 2):
        return
    if command == 'rev-parse' and _exact(flags, positionals, values, [], 1):
        return
    if command == 'rev-parse':
        parsed_flags, parsed_positionals, parsed_values = _split_args(args, {'--path-format', '--git-path'})
        if (not parsed_flags and not parsed_positionals
                and parsed_values == {'--path-format': ['absolute'], '--git-path': ['index']}):
            return
    if command == 'rev-list':
        parsed_flags, parsed_positionals, parsed_values = _split_args(args, {'--missing'})
        if (parsed_flags == ['--objects'] and parsed_positionals == ['HEAD']
                and parsed_values == {'--missing': ['print']}):
            return
    if command == 'update-index':
        parsed_flags, parsed_positionals, parsed_values = _split_args(args, {'--chmod'})
        hidden = {'--assume-unchanged', '--skip-worktree', '--no-assume-unchanged', '--no-skip-worktree'}
        if (not parsed_flags and parsed_values == {'--chmod': ['+x']} and len(parsed_positionals) == 1):
            return
        if (len(parsed_flags) == 1 and parsed_flags[0] in hidden and not parsed_values
                and len(parsed_positionals) == 1):
            return
    if command == 'update-ref' and _exact(flags, positionals, values, [], 2):
        return
    if command == 'branch' and _exact(flags, positionals, values, ['-m'], 2):
        return
    if command == 'fetch' and _exact(flags, positionals, values, ['--no-tags'], 2):
        return
    if command == 'remote' and positionals[:1] == ['add'] and len(positionals) == 3 and not flags and not values:
        source = _local_source(positionals[2])
        if not source.is_absolute():
            source = Path(base) / source
        _require(source, scratch, 'remote path')
        return
    if command == 'mv' and _exact(flags, positionals, values, [], 2):
        return
    if command == 'rm' and _exact(flags, positionals, values, [], len(positionals)) and positionals:
        return
    raise GitFixtureBoundary('unsupported fixture Git command: ' + command)


def _actual_locations(git_dir, cwd, scratch, env, work_tree=None):
    # Git resolves stored core.worktree and config includes. A directory name
    # alone cannot establish which work tree an existing repository will use.
    command = ['git', '--no-optional-locks', '--git-dir=' + str(git_dir)]
    if work_tree is not None:
        command.append('--work-tree=' + str(work_tree))

    def query(*options):
        result = subprocess.run(command + ['rev-parse', *options], cwd=cwd,
                                env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise GitFixtureBoundary('cannot resolve fixture Git identity: ' + result.stderr.strip())
        return result.stdout.strip()

    _require(query('--absolute-git-dir'), scratch, 'actual git dir')
    _require(query('--path-format=absolute', '--git-common-dir'), scratch, 'actual common dir')
    if query('--is-bare-repository') != 'true':
        _require(query('--show-toplevel'), scratch, 'actual work tree')


def guard(args, cwd, scratch, env=None):
    """Refuse Git operations that would read or write a repository outside scratch."""
    parsed = parse_git_args(args)
    cwd = Path(cwd or Path.cwd())
    scratch = Path(scratch)
    identity_env = build_env() if env is None else env
    base = Path(parsed.start or cwd)
    _guard_explicit_locations(parsed, base, scratch)
    _guard_supported(parsed, base, scratch)
    if parsed.command == 'init':
        _, positions, _ = _split_args(parsed.command_args,
                                      {'-b', '--initial-branch', '--object-format'})
        target = _absolute(positions[0], base) if positions else base
        existing = (Path(_absolute(parsed.git_dir, base)) if parsed.git_dir is not None
                    else _existing_git_dir(target, scratch))
        if existing is not None and (existing / 'HEAD').is_file():
            _actual_locations(existing, base, scratch, identity_env,
                              _absolute(parsed.work_tree, base) if parsed.work_tree else None)
        return parsed
    if parsed.command == 'clone':
        return parsed
    if parsed.git_dir is not None:
        git_dir = _require(_absolute(parsed.git_dir, base), scratch, 'git dir')
    else:
        start = Path(parsed.start) if parsed.start is not None else cwd
        if not _inside(start, scratch):
            raise GitFixtureBoundary('Git command cwd escapes fixture scratch')
        discovered = _discover(start, scratch)
        if discovered is None:
            raise GitFixtureBoundary('Git command is not inside a fixture repository')
        git_dir = _require(discovered, scratch, 'git dir')
    common = _require(_common_dir(git_dir), scratch, 'common dir')
    if parsed.work_tree is not None:
        _require(_absolute(parsed.work_tree, base), scratch, 'work tree')
    else:
        work_tree = _work_tree(git_dir, base)
        if work_tree is not None:
            _require(work_tree, scratch, 'work tree')
    _reject_linked_storage(git_dir, common, scratch)
    _actual_locations(git_dir, base, scratch, identity_env,
                      _absolute(parsed.work_tree, base) if parsed.work_tree else None)
    return parsed


def run(args, *, cwd=None, scratch, env=None, explicit=None, **kwargs):
    """Run Git with a scrubbed environment after the scratch boundary check."""
    argv = list(args)
    if not argv or argv[0] != 'git':
        argv = ['git', *argv]
    command_cwd = Path(cwd or Path.cwd())
    execution_env = build_env(env, explicit)
    guard(argv, command_cwd, scratch, env=execution_env)
    completed = subprocess.run(argv, cwd=str(command_cwd), env=execution_env, **kwargs)
    return completed
