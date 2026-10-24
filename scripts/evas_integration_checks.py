"""Small regression contracts for representation changes and new proof work.

This module checks the selected source tree. It never edits that tree, changes
solver limits, or turns a focused result into delivery acceptance.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


CHECKS = ('representation', 'integer-budget', 'initial-budget')


class NeedsRuntime(AssertionError):
    """An intentional route change needs its matching consumer, not identical IR."""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def representation(kernel=None, *, require_runtime=False):
    from evas import Instance, compile_sources, transient

    def model(body, name='m'):
        return ('`include "disciplines.vams"\nmodule '+name+
                '(u,y);input u;output y;electrical u,y;real q;analog begin '+
                body+' end endmodule')

    cases = (
        ('clamped-ratio', model('@(timer(0.25))q=(V(u)/0.9>1.0?1.0:V(u)/0.9);V(y)<+q;'),
         [Instance('D', 'm', {'u': 'u', 'y': 'y'})], .9),
        ('joint-input', model('V(y)<+1.5*V(u);', 'driver')+
         model('@(initial_step)q=0;@(timer(0.25))q=(V(u)>0.5?1.0:0.0);V(y)<+q;'),
         [Instance('A', 'driver', {'u': 'u', 'y': 'z'}),
          Instance('B', 'm', {'u': 'z', 'y': 'y'})], .5),
    )

    def selects(value):
        if isinstance(value, dict):
            return int(value.get('op') == 'select')+sum(map(selects, value.values()))
        return sum(map(selects, value)) if isinstance(value, (list, tuple)) else 0

    results = []
    for name, source, instances, voltage in cases:
        program = compile_sources({'integration.va': source}, instances)
        count = selects(program.to_dict()['events'])
        if (count or require_runtime) and kernel is None:
            raise NeedsRuntime(f'{name}: '+('small existing event changed to RHS Select; ' if count
                               else 'kernel consumer/build changed; ')+
                               'supply the matching --kernel to qualify its consumers')
        row = dict(case=name, rhs_selects=count)
        if kernel is not None:
            response = transient(program, {'u': [[0, voltage], [1, voltage]]}, [0, .5, 1],
                                 stop=1, max_step=.125, kernel=kernel,
                                 vabstol=1e-12, reltol=0)
            values = [s['voltages'][response['nodes'].index('y')]
                      for s in response['solutions']]
            if values != [0, 1, 1]:
                raise AssertionError(f'{name}: consumer values {values}, expected [0,1,1]')
            row['values'] = values
        results.append(row)
    return dict(cases=results, runtime_checked=kernel is not None,
                scope='two small legacy consumer shapes; not all IR transformations')


def integer_budget():
    from evas.frontend import parse_sources
    from evas import event_index_domains as domains
    from evas.integer_invariants import ProofWork, proof_parameters, verify_candidate

    def body(statement):
        source = ('`include "disciplines.vams"\nmodule m(u,y);input u;output y;'
                  'electrical u,y;integer n;integer q[0:127];analog begin '
                  '@(timer(1))begin '+statement*1000+' end V(y)<+0;end endmodule')
        return parse_sources({'budget.va': source})['m'].analog[0].body

    results = []
    for name, statement in (('array-read', 'n=q[0];'), ('array-write', 'q[n]=0;')):
        environment = {'n': (0, 0), **{f'q[{k}]': (0, 0) for k in range(128)}}
        work, visits, errors = ProofWork(), [0], []
        original = domains.hull

        def counted(a, b):
            visits[0] += 1
            return original(a, b)

        statements = body(statement)
        domains.hull = counted
        try:
            for _ in range(2):
                try:
                    verify_candidate([statements], environment, environment,
                                     arrays={'q': tuple(range(128))},
                                     parameters=proof_parameters(lambda _: 0, work))
                except ValueError as error:
                    if 'budget' not in str(error).lower():
                        raise
                    errors.append(str(error))
        finally:
            domains.hull = original
        if len(errors) != 2 or visits[0] >= 100000:
            raise AssertionError(f'{name}: uncharged slot work or renewed allowance: '
                                 f'hulls={visits[0]}, charged={work.used}, refusals={len(errors)}')
        results.append(dict(case=name, hull_calls=visits[0], charged=work.used,
                            budget_refusals=len(errors)))
    return dict(cases=results, scope='array-slot work and same-request exhaustion')


def budget_owners(source):
    """Count production allocation owners, excluding cfg(test) items.

    This is a structural guard for the known optional-proof module, not a proof
    of all aggregate work. Caller/loop accounting remains a separate obligation.
    """
    from diagnostic_inventory import rust_tokens, closing
    tokens, owners = rust_tokens(source), {}

    def scan(begin, finish, prefix=''):
        i, attributes = begin, []
        while i < finish:
            if tokens[i:i+2] == ['#', '[']:
                end = closing(tokens, i+1)
                attributes.extend(tokens[i:end+1])
                i = end+1
                continue
            if tokens[i] == 'fn':
                name = prefix+tokens[i+1]
                start = next(j for j in range(i+2, finish) if tokens[j] in ('{', ';'))
                end = closing(tokens, start) if tokens[start] == '{' else start
                if 'cfg ( test )' not in ' '.join(attributes):
                    sites = sum(tokens[j:j+2] == ['Budget', '('] for j in range(start, end))
                    if sites:
                        owners[name] = sites
                attributes = []
                i = end+1
                continue
            if tokens[i] == '{':
                end = closing(tokens, i)
                if 'cfg ( test )' not in ' '.join(attributes):
                    # Recurse into production mod/impl bodies; distinct block
                    # locations prevent equal method names from hiding owners.
                    scan(i+1, end, prefix+f'block@{i}::')
                attributes = []
                i = end+1
                continue
            if tokens[i] == ';':
                attributes = []
            i += 1

    scan(0, len(tokens))
    return owners


def initial_budget(path):
    source = path.read_text()
    owners = budget_owners(source)
    if len(owners) != 1 or sum(owners.values()) > 2:
        raise AssertionError(f'optional proof has independent allowance owners {owners}; '
                             'new fallback must consume an existing remainder')
    # Compile the actual production primitive, not a reimplementation of take().
    begin = source.index('struct Budget(')
    impl = source.index('impl Budget', begin)
    start = source.index('{', impl)
    depth, end = 1, start+1
    while depth and end < len(source):
        depth += (source[end] == '{')-(source[end] == '}')
        end += 1
    if depth:
        raise ValueError('unsupported Budget implementation; review this check')
    declaration = source[begin:impl].strip()
    support = ''
    if re.fullmatch(r'struct\s+Budget\s*\(\s*usize\s*\)\s*;', declaration):
        constructor = 'Budget(3)'
    elif re.fullmatch(r'struct\s+Budget\s*\(\s*usize\s*,\s*'
                      r'Option<crate::transition_source_plan::Work>\s*\)\s*;', declaration):
        constructor = 'Budget(3,None)'
        # This probe tests the production local remainder with no external Work.
        # An uninhabited type satisfies the optional dependency without inventing
        # debit behavior. Real Work accounting is covered by the kernel tests.
        support = ('mod transition_source_plan {pub enum Work {} '
                   'impl Work {pub fn debit(&self,_slot:usize,_n:u64)->Result<(),()> '
                   '{match *self {}}}}\n')
    else:
        raise ValueError('unsupported Budget fields; review this check')
    rustc = shutil.which('rustc')
    if rustc is None:
        raise OSError('rustc is required for the selected budget primitive check')
    with tempfile.TemporaryDirectory(prefix='evas-proof-budget-') as temporary:
        directory = Path(temporary)
        code, binary = directory/'budget.rs', directory/'budget-check'
        code.write_text(support+source[begin:end]+'\nfn main(){let mut b='+constructor+';'
                        'assert!(b.take(4).is_none());assert!(b.take(1).is_none());}\n')
        build = subprocess.run([rustc, '--edition=2021', str(code), '-o', str(binary)],
                               capture_output=True, text=True, timeout=30)
        if build.returncode:
            raise RuntimeError('budget primitive did not compile: '+build.stderr)
        execution = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        if execution.returncode:
            raise AssertionError('exhausted production Budget recovered on retry: '+execution.stderr)
    return dict(allocation_owners=owners, exhausted_retry='refused',
                primitive_external_work='absent; no external debit behavior is simulated',
                scope='single allocation owner and sticky primitive; aggregate caller work still needs review')


def run(root, *, python_root=None, kernel=None, checks=None, absent_is_inapplicable=False, require_runtime=False):
    root = Path(root).resolve()
    python_root = Path(python_root).resolve() if python_root else root/'evas/src'
    kernel = Path(kernel).resolve() if kernel else None
    selected = list(checks) if checks is not None else list(CHECKS)
    if not selected:
        raise ValueError('early check selection must be nonempty')
    unknown = set(selected)-set(CHECKS)
    if unknown:
        raise ValueError(f'unknown early checks: {sorted(unknown)}')
    source_identity = {str(p): digest(p) for p in sorted((python_root/'evas').rglob('*.py'))}
    kernel_identity = digest(kernel) if kernel else None
    sys.path.insert(0, str(python_root))
    existing = sys.modules.get('evas')
    if existing and not Path(existing.__file__).resolve().is_relative_to(python_root):
        raise ValueError('candidate import already bound to another source tree; use a fresh process')
    rows = []
    for check in selected:
        paths = ([python_root/'evas/instance_compiler.py'] if check == 'representation' else
                 [python_root/'evas/integer_invariants.py', python_root/'evas/event_index_domains.py']
                 if check == 'integer-budget' else
                 [root/'evas/rust_core/src/initial_state_invariance.rs'])
        absent = [str(p) for p in paths if not p.is_file()]
        if absent:
            rows.append(dict(check=check, status='blocked' if checks is not None and not absent_is_inapplicable else 'not-applicable',
                             reason='target mechanism absent', missing=absent))
            continue
        if check == 'initial-budget' and not re.search(
                r'fn\s+unchanged_(?:at_inputs|with_inputs)\b', paths[0].read_text()):
            rows.append(dict(check=check, status='blocked' if checks is not None and not absent_is_inapplicable else 'not-applicable',
                             reason='no input-aware optional proof extension in this tree'))
            continue
        identity = {str(p): digest(p) for p in paths}
        try:
            result = (representation(kernel, require_runtime=require_runtime) if check == 'representation' else
                      integer_budget() if check == 'integer-budget' else initial_budget(paths[0]))
            rows.append(dict(check=check, status='passed', identity=identity, result=result))
        except NeedsRuntime as error:
            rows.append(dict(check=check, status='needs-runtime', identity=identity, reason=str(error)))
        except (AssertionError, OSError, ValueError, RuntimeError, ImportError,
                KeyError, AttributeError, TypeError, subprocess.SubprocessError) as error:
            rows.append(dict(check=check, status='failed', identity=identity,
                             reason=f'{type(error).__name__}: {error}'))
        if any(digest(Path(p)) != h for p, h in identity.items()):
            raise ValueError('source changed during early checks')
    if any(digest(Path(p)) != h for p, h in source_identity.items()):
        raise ValueError('Python source changed during early checks')
    if kernel and digest(kernel) != kernel_identity:
        raise ValueError('kernel changed during early checks')
    return dict(source_root=str(root), python_root=str(python_root),
                python_source_identity=source_identity, kernel_sha256=kernel_identity,
                checks=rows, passed=all(r['status'] in ('passed', 'not-applicable') for r in rows),
                needs_runtime=any(r['status'] == 'needs-runtime' for r in rows),
                acceptance_complete=False, full400=False)
