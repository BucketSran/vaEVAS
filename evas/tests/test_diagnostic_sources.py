"""Audited failure origins retain their actual source and failure class."""
GUARDS = ['LANG', 'TIMER']

import unittest
from evas import CompileError, compile_sources
from test_affine import model, instance


class DiagnosticSources(unittest.TestCase):
    def test_undeclared_node_has_real_source(self):
        source = model('V(y,r)<+V(missing,r);')
        with self.assertRaises(CompileError) as caught:
            compile_sources({'nodes.va': source}, [instance()])
        error = caught.exception.diagnostic
        self.assertEqual(error['code'], 'undeclared_node')
        self.assertEqual(error['category'], 'invalid_input')
        self.assertEqual(error['stage'], 'lowering')
        self.assertEqual(error['location']['source'], 'nodes.va')
        self.assertEqual(error['instance'], 'dut')
        self.assertEqual(error['location'], dict(source='nodes.va', line=1, column=source.index('V(missing,r)') + 1))
        self.assertEqual(error['message'], f"nodes.va:1:{source.index('V(missing,r)') + 1}: undeclared electrical node in V(missing,r)")

    def test_duplicate_module_and_connection_mismatch_are_input_failures(self):
        source = model('V(y,r)<+V(u,r);')
        with self.assertRaises(CompileError) as duplicate:
            compile_sources({'first.va': source, 'second.va': source}, [instance()])
        error = duplicate.exception.diagnostic
        self.assertEqual(error['code'], 'duplicate_module')
        self.assertEqual(error['category'], 'invalid_input')
        self.assertEqual(error['location']['source'], 'second.va')
        self.assertEqual(error['location']['line'], 1)
        bad = instance()
        from evas import Instance
        with self.assertRaises(CompileError) as missing:
            compile_sources({'ports.va': source}, [Instance(bad.name, bad.module, {'u': 'u'})])
        error = missing.exception.diagnostic
        self.assertEqual(error['code'], 'connection_mismatch')
        self.assertEqual(error['category'], 'invalid_input')
        self.assertEqual(error['instance'], 'dut')
        self.assertNotIn('location', error)  # Manifest has no fabricated VA token.
        from test_hierarchy import top, LEAF
        with self.assertRaises(CompileError) as child:
            compile_sources({'top.va': top('gain child(u,y);'), 'gain.va': LEAF}, [instance(module='top')])
        error = child.exception.diagnostic
        self.assertEqual(error['code'], 'connection_mismatch')
        self.assertEqual(error['location']['source'], 'top.va')
        self.assertEqual(error['instance'], 'dut/child')

    def test_real_expansion_limits_are_resources(self):
        from test_user_functions import PREFIX
        from test_hierarchy import top, LEAF
        call = 'V(u,r)'
        for _ in range(20):
            call = f'transfer({call})'
        function = PREFIX.replace('tmp=gain*x; transfer=tmp+1;', 'transfer=x+x;')
        cases = [
            ('token', {'tokens.va': '+' * 100001}, instance(), 'source token budget'),
            ('macro', {'macros.va': '`define F(x) ((x)+(x))\n' + model('V(y,r)<+' + '`F(' * 20 + '1' + ')' * 20 + ';')}, instance(), 'preprocessor token expansion budget'),
            ('function', {'functions.va': function + 'analog begin V(y,r)<+' + call + '; end endmodule'}, instance(), 'function expansion'),
            ('genvar', {'loops.va': model('for(i=0;i<5000;i=i+1) V(y,r)<+1;', 'genvar i;')}, instance(), 'static loop'),
            ('hierarchy', {'top.va': top(' '.join(f'gain a{i}(u,y,r);' for i in range(4096))), 'gain.va': LEAF}, instance(module='top'), 'hierarchical instance'),
            ('array', {'arrays.va': model('V(y,r)<+1;', 'real a[0:4096];')}, instance(), 'total array element'),
        ]
        for name, sources, inst, reason in cases:
            with self.subTest(origin=name), self.assertRaises(CompileError) as caught:
                compile_sources(sources, [inst])
            error = caught.exception.diagnostic
            with self.subTest(origin=name):
                self.assertIn(reason, error['message'])
                self.assertEqual(error['message'], str(caught.exception))
                self.assertEqual(error['code'], 'resource_budget')
                self.assertEqual(error['category'], 'resource')
                self.assertEqual(error['capability'], 'LANG')
                self.assertIn(error['location']['source'], sources)
                if name == 'hierarchy':
                    self.assertEqual(error['location']['source'], 'top.va')
                    self.assertEqual(error['instance'], 'dut/a4095')

    def test_nonconvergence_keeps_the_kernel_reason(self):
        from evas import KernelError, solve
        from test_affine import KERNEL
        program = compile_sources({'roots.va': model('V(y,r)<+V(y,r)-(pow(V(y,r),4)-V(y,r)+1);')}, [instance()])
        with self.assertRaises(KernelError) as nonlinear:
            solve(program, ['u'], [[0]], kernel=KERNEL)
        error = nonlinear.exception
        self.assertEqual(error.detail['kind'], 'nonconvergence')
        self.assertEqual(error.diagnostic['category'], 'numerical')
        self.assertEqual(error.diagnostic['sample'], 0)
        self.assertIn('roots.va:', error.diagnostic['message'])

    def test_finite_input_overflow_is_numerical_not_unsupported(self):
        from evas import KernelError, solve
        from test_affine import KERNEL
        program = compile_sources({'overflow.va': model('V(y,r)<+pow(V(u,r),3);')}, [instance()])
        with self.assertRaises(KernelError) as caught:
            solve(program, ['u'], [[1e200]], kernel=KERNEL)
        error = caught.exception
        self.assertEqual(error.detail['kind'], 'nonfinite_arithmetic')
        self.assertEqual(error.diagnostic['code'], 'kernel.nonfinite_arithmetic')
        self.assertEqual(error.diagnostic['stage'], 'kernel')
        self.assertEqual(error.diagnostic['category'], 'numerical')
        self.assertEqual(error.diagnostic['sample'], 0)
        self.assertEqual(error.diagnostic['message'], error.detail['message'])
        self.assertIn('nonfinite', error.detail['message'])

    def test_runtime_integer_range_is_an_implementation_boundary(self):
        from evas import KernelError
        from test_timer import run_timer, timer_source
        with self.assertRaises(KernelError) as caught:
            run_timer(timer_source('0,0,0.001', initial=2147483647), stop=1, times=[0, 1])
        error = caught.exception
        self.assertEqual(error.detail['kind'], 'state_range')
        self.assertEqual(error.diagnostic['code'], 'kernel.state_range')
        self.assertEqual(error.diagnostic['stage'], 'kernel')
        self.assertEqual(error.diagnostic['category'], 'unsupported')
        self.assertIn('exact signed 32-bit integer', error.diagnostic['message'])
        self.assertEqual(error.diagnostic['message'], error.detail['message'])

    def test_real_kernel_categories_survive_machine_cli(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        from test_affine import KERNEL
        from test_timer import timer_source
        cases = [
            ('solve', model('V(y,r)<+pow(V(u,r),3);'),
             dict(samples=[[1e200]]), 'nonfinite_arithmetic', 'numerical'),
            ('transient', timer_source('0,0,0.001', initial=2147483647),
             dict(transient=dict(sources={'u': [[0, 0], [1, 0]]}, output_times=[0, 1], stop=1, max_step=1)),
             'state_range', 'unsupported'),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'sim.json'
            for action, source, request, kind, category in cases:
                with self.subTest(kind=kind):
                    (root / 'm.va').write_text(source)
                    manifest.write_text(json.dumps(dict(models=['m.va'],
                        instances=[dict(name='dut', module='m', connections=dict(u='u', y='y', r='0'))],
                        driven=['u'], **request)))
                    result = subprocess.run([sys.executable, '-B', '-m', 'evas', action, str(manifest),
                                             '--kernel', str(KERNEL)], capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, '')
                    error = json.loads(result.stderr)
                    self.assertEqual(error['diagnostic_version'], 1)
                    self.assertEqual(error['kind'], kind)
                    self.assertEqual(error['code'], 'kernel.' + kind)
                    self.assertEqual(error['category'], category)
                    self.assertEqual(error['stage'], 'kernel')

    def test_worker_panic_is_internal_with_no_claim_of_real_trigger(self):
        from evas import KernelError
        raw = dict(kind='worker_failure', message='static worker panicked', future=42)
        error = KernelError(raw)
        self.assertEqual(error.diagnostic['category'], 'internal')
        self.assertEqual(error.detail, raw)
        self.assertEqual(error.diagnostic['future'], 42)
        future = KernelError(dict(raw, diagnostic_version=2))
        self.assertEqual(future.diagnostic['category'], 'unknown')

    def test_event_calendar_limit_is_a_resource(self):
        from evas import KernelError
        from test_timer import run_timer, timer_source
        with self.assertRaises(KernelError) as events:
            run_timer(timer_source('0,1e-12,1e-18'), stop=1, times=[0, 1])
        self.assertEqual(events.exception.detail['kind'], 'event_budget')
        self.assertEqual(events.exception.diagnostic['category'], 'resource')

    def test_kernel_io_failure_survives_the_cli(self):
        import json
        import os
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        from test_affine import KERNEL
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'm.va').write_text(model('V(y,r)<+V(u,r);'))
            manifest = dict(models=['m.va'], instances=[dict(name='dut', module='m', connections=dict(u='u', y='y', r='0'))], driven=['u'], samples=[[0]])
            path = root / 'sim.json'
            path.write_text(json.dumps(manifest))
            result = subprocess.run([sys.executable, '-B', '-m', 'evas', 'solve', str(path), '--kernel', str(KERNEL)],
                                    capture_output=True, text=True, timeout=15,
                                    env=dict(os.environ, EVAS_DIAGNOSTICS_PATH=str(root)))
            self.assertEqual(result.returncode, 2)
            error = json.loads(result.stderr)
            self.assertEqual(error['code'], 'kernel.diagnostic_io')
            self.assertEqual(error['category'], 'infrastructure')
            self.assertEqual(error['diagnostic_version'], 1)
            self.assertEqual(result.stdout, '')

    def test_raw_kernel_stdin_io_failure_is_registered(self):
        import json
        import subprocess
        from evas import KernelError
        from test_affine import KERNEL
        result = subprocess.run([str(KERNEL)], input=b'\xff', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        raw = json.loads(result.stderr)
        self.assertEqual(raw['kind'], 'input_io')
        error = KernelError(raw)
        self.assertEqual(error.diagnostic['category'], 'infrastructure')
        self.assertEqual(error.detail, raw)

    def test_recursive_and_uncertain_origins_stay_unknown(self):
        cases = [
            {'recursive.va': '`define A `A\n' + model('V(y,r)<+`A;')},
            {'root.va': '`include "loop.vams"\n' + model('V(y,r)<+1;'), 'loop.vams': '`include "loop.vams"\n'},
            {'loop.va': model('for(i=0;i<2;i=i) V(y,r)<+1;', 'genvar i;')},
        ]
        for sources in cases:
            with self.subTest(sources=tuple(sources)), self.assertRaises(CompileError) as caught:
                compile_sources(sources, [instance()])
            self.assertEqual(caught.exception.diagnostic['category'], 'unknown')
            self.assertIn('location', caught.exception.diagnostic)
            self.assertEqual(caught.exception.diagnostic['message'], str(caught.exception))

    def test_worker_start_mapping_preserves_unexecuted_os_reason(self):
        # The OS thread-creation branch is source-audited, not forced by this test.
        from evas import KernelError
        raw = dict(kind='worker_start', message='OS refused a worker', extra={'errno': 11})
        error = KernelError(raw)
        self.assertEqual(error.diagnostic['category'], 'infrastructure')
        self.assertEqual(error.detail, raw)
        self.assertEqual(error.diagnostic['extra'], raw['extra'])
        unknown = KernelError(dict(kind='unsupported_future_reason', message='unreviewed'))
        self.assertEqual(unknown.diagnostic['category'], 'unknown')

    def test_deep_and_aggregate_resource_origins(self):
        from test_user_functions import PREFIX
        from test_hierarchy import top, LEAF
        headers = {f'h{i}.vams': f'`include "h{i+1}.vams"\n' for i in range(64)}
        headers['h64.vams'] = model('V(y,r)<+1;')
        modules = {f'm{i}.va': top(f'm{i+1} child(u,y,r);').replace('module top(', f'module m{i}(') for i in range(65)}
        modules['m65.va'] = LEAF.replace('module gain(', 'module m65(')
        functions = PREFIX[:PREFIX.index('analog function')]
        for i in range(64):
            rhs = '+'.join([f'f{i+1}(x)' if i < 63 else 'x'] + ['0'] * 12)
            functions += f'analog function real f{i}; input x; real x; begin f{i}={rhs}; end endfunction\n'
        cases = [
            ('include_depth', headers, instance(), 'recursive or over-budget source include'),
            ('hierarchy_depth', modules, instance(module='m0'), 'hierarchical instance count/depth budget'),
            ('function_depth', {'depth.va': functions + 'analog begin V(y,r)<+f0(V(u,r)); end endmodule'}, instance(), 'function expansion exceeds expression depth'),
            ('directives', {'conditional.va': '`ifndef X\n' * 65 + model('V(y,r)<+1;') + '\n`endif\n' * 65}, instance(), 'conditional directive nesting budget'),
            ('syntax', {'syntax.va': model('V(y,r)<+' + '(' * 65 + '1' + ')' * 65 + ';')}, instance(), 'syntax nesting limit'),
            ('total_iterations', {'iterations.va': model('for(i=0;i<65;i=i+1) for(j=0;j<65;j=j+1) begin end V(y,r)<+1;', 'genvar i,j;')}, instance(), 'total static iteration budget'),
            ('statements', {'statements.va': model('@(initial_step) n=0; for(i=0;i<2050;i=i+1) @(timer(i+1)) n=i; V(y,r)<+n;', 'genvar i; integer n;')}, instance(), 'elaborated statement budget'),
        ]
        for origin, sources, inst, reason in cases:
            with self.subTest(origin=origin), self.assertRaises(CompileError) as caught:
                compile_sources(sources, [inst])
            error = caught.exception.diagnostic
            with self.subTest(origin=origin):
                self.assertIn(reason, error['message'])
                self.assertEqual(error['code'], 'resource_budget')
                self.assertEqual(error['category'], 'resource')
                self.assertIn(error['location']['source'], sources)
                self.assertEqual(error['message'], str(caught.exception))

    def test_compile_cli_retains_the_same_source_diagnostic(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        sources = [model('V(y,r)<+V(missing,r);'),
                   '`define F(x) ((x)+(x))\n' + model('V(y,r)<+' + '`F(' * 20 + '1' + ')' * 20 + ';')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / 'm.va'
            path = root / 'sim.json'
            path.write_text(json.dumps(dict(models=['m.va'], instances=[dict(name='dut', module='m', connections=dict(u='u', y='y', r='0'))])))
            for source in sources:
                with self.subTest(source=source[:40]):
                    source_path.write_text(source)
                    with self.assertRaises(CompileError) as caught:
                        compile_sources({str(source_path.resolve()): source}, [instance()])
                    result = subprocess.run([sys.executable, '-B', '-m', 'evas', 'compile', str(path)], capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(json.loads(result.stderr), caught.exception.diagnostic)

    def test_declared_voltage_in_restricted_contexts_stays_unknown(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        bodies = [
            'V(y,r)<+transition(V(u,r),0,1,1);',
            'V(y,r)<+absdelay(V(u,r),V(u,r));',
            'V(y,r)<+idt(V(u,r),0,V(u,r));',
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source_path = root / 'declared.va'
            manifest = root / 'sim.json'
            manifest.write_text(json.dumps(dict(models=['declared.va'], instances=[dict(name='dut', module='m', connections=dict(u='u', y='y', r='0'))])))
            for body in bodies:
                with self.subTest(body=body):
                    source = model(body)
                    source_path.write_text(source)
                    with self.assertRaises(CompileError) as caught:
                        compile_sources({str(source_path): source}, [instance()])
                    diagnostic = caught.exception.diagnostic
                    result = subprocess.run([sys.executable, '-B', '-m', 'evas', 'compile', str(manifest)], capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(json.loads(result.stderr), diagnostic)
                    self.assertEqual(diagnostic['category'], 'unknown')
                    self.assertEqual(diagnostic['code'], 'compile_error')
                    self.assertIsNone(diagnostic['hint'])
                    self.assertEqual(diagnostic['instance'], 'dut')
                    self.assertEqual(diagnostic['location']['source'], str(source_path))
                    self.assertEqual(diagnostic['message'], str(caught.exception))

    def test_real_missing_node_in_nested_live_input_remains_invalid(self):
        for body in ('V(y,r)<+2*V(missing,r);', 'V(y,r)<+absdelay(V(missing,r),0);', 'V(missing,r)<+1;'):
            with self.subTest(body=body), self.assertRaises(CompileError) as caught:
                compile_sources({'missing.va': model(body)}, [instance()])
            error = caught.exception.diagnostic
            self.assertEqual(error['code'], 'undeclared_node')
            self.assertEqual(error['category'], 'invalid_input')
            self.assertEqual(error['location']['source'], 'missing.va')
            self.assertEqual(error['instance'], 'dut')

    def test_closed_child_parameters_and_cross_settings_stay_unknown(self):
        from test_hierarchy import top, LEAF
        cases = [
            ({'top.va': top('gain #(.g(V(u,r))) child(u,y,r);'), 'gain.va': LEAF}, instance(module='top'), 'top.va'),
            ({'cross.va': model('@(initial_step) n=0; @(cross(V(u,r),V(u,r),1e-9,1e-9)) n=n+1; V(y,r)<+n;', 'integer n;')}, instance(), 'cross.va'),
        ]
        for sources, inst, source_name in cases:
            with self.subTest(source=source_name), self.assertRaises(CompileError) as caught:
                compile_sources(sources, [inst])
            error = caught.exception.diagnostic
            self.assertEqual(error['category'], 'unknown')
            self.assertEqual(error['code'], 'compile_error')
            self.assertIsNone(error['hint'])
            self.assertEqual(error['location']['source'], source_name)
