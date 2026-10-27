"""DUT-free detector calibration. Historical raw output is a format control only."""
import ast
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / 'evas/src'), str(ROOT / 'evas/tests')]
import evas.runtime as runtime
import evas.program_real_validation as validator

MATH_METHODS = (
    'test_product_contains_independent_decimal_root_in_reported_box',
    'test_multinode_certificate_uses_same_original_constraint_system',
)
BOUND_METHODS = (
    'test_bound_caps_actual_nonlinear_integration_segments',
    'test_sampled_clock_activation_preserves_physics_and_caps_inner_segments',
)

def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read(name):
    return json.loads((HERE / 'fixtures' / name).read_bytes())


def load(name):
    # Keep original TestCase classes inside a local module object. Never export
    # them into this discover module or run a whole imported test module.
    spec = importlib.util.spec_from_file_location('calibration_target_' + name,
        ROOT / 'evas/tests' / ('test_' + name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def forbidden(*args, **kwargs):
    raise AssertionError('DUT/process execution forbidden in checker calibration')


class DetectorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for row in read('provenance.json'):
            data = (HERE / 'fixtures' / row['fixture']).read_bytes()
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise AssertionError('Frozen calibration fixture changed: ' + row['fixture'])

    def setUp(self):
        self.enterContext(patch('subprocess.run', side_effect=forbidden))
        self.enterContext(patch('subprocess.Popen', side_effect=forbidden))
        self.enterContext(patch.object(runtime, '_invoke', side_effect=forbidden))
        self.enterContext(patch.object(tempfile, 'tempdir', str(HERE)))

    def observe(self, case):
        result = unittest.TestResult()
        case.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertFalse(result.errors, result.errors)
        self.assertFalse(result.skipped)
        return result

    def math_control(self, method, mode):
        module = load('source_math')
        controls = read('source_math.json')
        correct = {canonical(x['request']): x for x in controls if x['mutation'] == 'correct'}
        wrong = {canonical(x['request']): x for x in controls
                 if x['mutation'] == 'wrong_representative_wide_box'}
        captures = []

        def invoke(request, *args, **kwargs):
            key = canonical(request)
            self.assertIn(key, correct, 'Request changed from frozen independent control')
            self.assertEqual(request['tolerances']['absolute'], 1e-12)
            self.assertEqual(request['tolerances']['relative'], 1e-10)
            response = copy.deepcopy((wrong if mode == 'wrong_wide' else correct)[key]['response'])
            idx = response['nodes'].index('y')
            for sample, bounds in zip(response['solutions'], response['observation_evidence']['voltage_bounds_V']):
                if mode == 'correct_wide':
                    bounds[idx] = [-1000., 1000.]
                elif mode.startswith(('upper_', 'lower_')):
                    center = Fraction.from_float(sample['voltages'][idx])
                    budget = Fraction.from_float(1e-12) + Fraction.from_float(1e-10) * abs(center)
                    upper = mode.startswith('upper_')
                    within = mode.endswith('_within')
                    exact = center + budget if upper else center - budget
                    edge = float(exact)
                    toward = -math.inf if upper else math.inf
                    while (Fraction.from_float(edge) > exact if upper else Fraction.from_float(edge) < exact):
                        edge = math.nextafter(edge, toward)
                    outside = math.nextafter(edge, -toward)
                    # Exact rationals, no added epsilon: adjacent binary64
                    # values straddle each original request budget boundary.
                    self.assertLessEqual(abs(Fraction.from_float(edge)-center), budget)
                    self.assertGreater(abs(Fraction.from_float(outside)-center), budget)
                    bounds[idx][1 if upper else 0] = edge if within else outside
            captures.append(key)
            return response

        with patch.object(runtime, '_invoke', side_effect=invoke):
            result = self.observe(module.SourceMath(method))
        expected_count = 6 if method == MATH_METHODS[0] else 1
        self.assertEqual(len(captures), expected_count)
        self.assertEqual(len(set(captures)), expected_count)
        reject = mode in ('wrong_wide', 'correct_wide', 'upper_over', 'lower_over')
        self.assertEqual(len(result.failures), expected_count if reject else 0, result.failures)
        self.calibration_observation = dict(family='SourceMath', method=method, mode=mode,
            request_sha256=captures, expected_reject=reject, observed_failures=len(result.failures),
            observed_errors=len(result.errors), assertion_denominator=expected_count)
        for _, trace in result.failures:
            # Reject at the targeted representative/box budget assertion,
            # never at parsing, enclosure, request identity or process guard.
            self.assertTrue('self.assertLessEqual(abs(actual-' in trace or
                            'self.assertLessEqual(max(abs(actual-lo)' in trace, trace)

    def deferred_control(self, mutant):
        module = load('deferred_rdist')
        tree = ast.parse(Path(validator.__file__).read_text())

        class RemoveLeafChecks(ast.NodeTransformer):
            def __init__(self):
                self.removed = []
                self.branches = 0

            def visit_If(self, node):
                self.generic_visit(node)
                if ast.unparse(node.test) == 'isinstance(value, UnsupportedSystemCall)':
                    self.branches += 1
                    retained = []
                    for statement in node.body:
                        if isinstance(statement, ast.If) and (
                            'value.op' in ast.unparse(statement.test) or
                            'owner is None' in ast.unparse(statement.test)):
                            self.removed.append(statement)
                        else:
                            retained.append(statement)
                    node.body = retained
                return node

        transform = RemoveLeafChecks()
        transformed = transform.visit(tree)
        self.assertEqual(transform.branches, 1)
        self.assertEqual(len(transform.removed), 2)
        # Pin precisely the two original signature and seed predicates.
        # Parse fixed predicate source with this interpreter before comparing ASTs.
        # ast.dump's omission of empty fields differs between Python versions.
        expected = [ast.dump(ast.parse(source).body[0], include_attributes=False)
                    for source in read('validator_predicates.json')]
        self.assertEqual([ast.dump(x, include_attributes=False) for x in transform.removed], expected)
        ast.fix_missing_locations(transformed)
        namespace = dict(validator.__dict__)
        exec(compile(transformed, validator.__file__, 'exec'), namespace)
        implementation = namespace['validate_program_ir'] if mutant else validator.validate_program_ir
        with patch.object(validator, 'validate_program_ir', implementation):
            result = self.observe(module.DeferredRdist('test_bad_raw_leaf_seed_and_signature_are_rejected'))
        self.assertEqual(len(result.failures), 3 if mutant else 0, result.failures)
        self.calibration_observation = dict(family='DeferredRdist', mode='exact_mutant' if mutant else 'original',
            expected_reject=mutant, observed_failures=len(result.failures), observed_errors=len(result.errors),
            assertion_denominator=3, removed_predicates=expected if mutant else [])
        for _, trace in result.failures:
            self.assertIn('CompileError not raised', trace)
        # The selected method first serializes an unchanged legal leaf at the
        # exact replacement position, then requires each specific error reason.

    def bound_control(self, method, mode):
        module = load('bound_step')
        captures = []

        def invoke(request, *args, diagnostics_path=None, **kwargs):
            index = len(captures)
            prefix = f'{method}--identity--{index}.'
            self.assertEqual(canonical(request), canonical(read(prefix + 'request.json')))
            response = read(prefix + 'original-response.json')
            if index == 0:
                if mode == 'drop_initial':
                    response['solutions'] = response['solutions'][1:]
                elif mode == 'wrong_times':
                    response['transient']['times'] = [x + 10 for x in response['transient']['times']]
                elif mode == 'wrong_voltage':
                    idx = response['nodes'].index('y')
                    response['solutions'][-1]['voltages'][idx] = 123.
                    response['observation_evidence']['voltage_bounds_V'][-1][idx] = [123., 123.]
            if diagnostics_path is not None:
                Path(diagnostics_path).write_bytes((HERE / 'fixtures' / (prefix + 'diagnostics.json')).read_bytes())
            captures.append(index)
            return response

        with patch.object(module, '_invoke', side_effect=invoke), patch.object(runtime, '_invoke', side_effect=invoke):
            result = unittest.TestResult()
            module.BoundStepContracts(method).run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertFalse(result.skipped)
        self.calibration_observation = dict(family='BoundStep', method=method, mode=mode,
            expected_reject=mode != 'identity', observed_failures=len(result.failures),
            observed_errors=len(result.errors), request_count=len(captures), assertion_denominator=1)
        if mode == 'identity':
            self.assertTrue(result.wasSuccessful(), (result.failures, result.errors))
            self.assertEqual(len(captures), 1 if method == BOUND_METHODS[0] else 2)
        elif mode == 'wrong_voltage':
            self.assertFalse(result.errors, result.errors)
            self.assertEqual(len(result.failures), 1)
            self.assertIn('self.assertLessEqual(abs(result' if method == BOUND_METHODS[0]
                          else 'self.assertAlmostEqual', result.failures[0][1])
        else:
            self.assertFalse(result.failures, result.failures)
            self.assertEqual(len(result.errors), 1)
            trace = result.errors[0][1]
            self.assertIn('validate_response', trace)
            self.assertIn('KernelError', trace)
            self.assertIn('solution count' if mode == 'drop_initial' else 'transient response identity mismatch', trace)


def _math_test(method, mode):
    def test(self):
        self.math_control(method, mode)
    return test


def _bound_test(method, mode):
    def test(self):
        self.bound_control(method, mode)
    return test


# Exactly22 discoverable tests. Each explicitly selects one historical target;
# imported suites and unrelated scientific candidates never enter discovery.
for _number, _method in enumerate(MATH_METHODS):
    for _mode in ('correct', 'wrong_wide', 'correct_wide', 'upper_within', 'upper_over', 'lower_within', 'lower_over'):
        setattr(DetectorControls, f'test_source_math_{_number}_{_mode}', _math_test(_method, _mode))
for _number, _method in enumerate(BOUND_METHODS):
    for _mode in ('identity', 'drop_initial' if _number == 0 else 'wrong_times', 'wrong_voltage'):
        setattr(DetectorControls, f'test_bound_step_{_number}_{_mode}', _bound_test(_method, _mode))

def _deferred_original(self):
    self.deferred_control(False)

def _deferred_mutant(self):
    self.deferred_control(True)

DetectorControls.test_deferred_original = _deferred_original
DetectorControls.test_deferred_exact_mutant = _deferred_mutant
