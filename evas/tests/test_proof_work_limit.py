"""Request-level source-transition proof work limit (default 1e9, hard bound 1e13).

The limit is an implementation budget, not a correctness criterion or a performance
promise. Expected answers are independent of the kernel: the rate-limited output
of a held target is a piecewise-linear closed form evaluated with Fractions, and
the accepted/rejected value shapes follow the request contract written in
docs/reference/proof-work-limit.md.
"""
GUARDS = ["SLEW", "TIMED-OPERATOR", "DEV:scs-input"]

from fractions import Fraction as F
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evas import CompileError, KernelError, compile_sources, transient
from evas import limits
from evas.protocol import validate_response
from evas.runtime import _invoke
from evas.scs import load_scs, simulate_scs
from test_affine import KERNEL, instance, model

# A kernel built from main before this field existed (old-kernel contract). The two
# check_ methods that need it are explicit: discovery does not collect them, so CI
# records no skip. Run one by name with EVAS_TEST_MAIN_KERNEL set, for example
#   python3 -B -m unittest test_proof_work_limit.ProofWorkLimitKernel.check_kernel_without_the_field_rejects_it_explicitly
MAIN_KERNEL = os.environ.get('EVAS_TEST_MAIN_KERNEL')

BODY = 'V(y,r)<+slew(V(u,r)>0.5?1.0:0.0,1,-2);'
POINTS = [[0, 0], [1, 1], [2, 1]]


def program():
    return compile_sources({'proof_limit.va': model(BODY)}, [instance()])


def grid(n):
    # Strictly increasing dyadic-free grid on [0,2]; n evenly spaced requests.
    return [2 * i / (n - 1) for i in range(n)]


def expected(t):
    """u ramps 0->1 on [0,1] and selects target 1 once u>0.5, i.e. after t=1/2.

    slew(target,1,-2) is rate limited at +1 V/s while rising from 0, so
    y(t) = min(1, max(0, t - 1/2)) exactly (no use of the kernel).
    """
    return min(F(1), max(F(0), F(t) - F(1, 2)))


def run(n, **options):
    return transient(program(), {'u': POINTS}, grid(n), stop=2, max_step=2,
                     vabstol=1e-12, reltol=0, kernel=KERNEL, **options)


def controls(result):
    return result['observation_evidence']['effective_controls']


class Captured(Exception):
    pass


def capture_request(**options):
    """Run transient() up to the kernel call; return the request it would send."""
    with patch('evas.runtime._invoke', side_effect=Captured) as invoke:
        with unittest.TestCase().assertRaises(Captured):
            transient(program(), {'u': POINTS}, [0, 1, 2], stop=2, max_step=2,
                      kernel='unused', **options)
    return invoke.call_args.args[0]


class ProofWorkLimitFrontend(unittest.TestCase):
    def test_limits_are_the_designed_named_constants(self):
        # Literals, not the constants under test.
        self.assertEqual(getattr(limits, 'DEFAULT_PROOF_WORK_LIMIT', None), 1_000_000_000)
        self.assertEqual(getattr(limits, 'MAX_PROOF_WORK_LIMIT', None), 10_000_000_000_000)

    def test_unset_request_is_byte_identical_to_the_previous_request(self):
        request = capture_request()
        self.assertEqual(sorted(request['transient']),
                         ['max_step', 'output_times', 'pwl', 'stop'])
        self.assertEqual(request['tolerances'], dict(absolute=1e-12, relative=1e-10))
        self.assertEqual(request, capture_request(proof_work_limit=None))

    def test_set_value_is_sent_as_an_exact_integer(self):
        for value in (1, 1_000_000_000, 2_000_000_000_000, 10_000_000_000_000):
            with self.subTest(value=value):
                sent = capture_request(proof_work_limit=value)['transient']
                self.assertIs(type(sent['proof_work_limit']), int)
                self.assertEqual(sent['proof_work_limit'], value)
                self.assertEqual(json.dumps(sent['proof_work_limit']), str(value))

    def test_invalid_values_are_rejected_and_never_sent(self):
        bad = [0, -1, -10**13, True, False, 1.5, 2e12, float('nan'), float('inf'),
               10**13 + 1, 2**64, '5', b'5', [1], {'v': 1}]
        for value in bad:
            with self.subTest(value=value):
                with patch('evas.runtime._invoke') as invoke:
                    with self.assertRaisesRegex(ValueError, 'proof_work_limit'):
                        transient(program(), {'u': POINTS}, [0, 1, 2], stop=2,
                                  max_step=2, kernel='unused', proof_work_limit=value)
                invoke.assert_not_called()

    def test_integer_subclass_is_not_an_integer_request(self):
        class Wide(int):
            pass
        with patch('evas.runtime._invoke') as invoke:
            with self.assertRaisesRegex(ValueError, 'proof_work_limit'):
                transient(program(), {'u': POINTS}, [0, 1, 2], stop=2, max_step=2,
                          kernel='unused', proof_work_limit=Wide(5))
        invoke.assert_not_called()


class ProofWorkLimitProtocol(unittest.TestCase):
    """The echoed effective limit is validated against the request that was sent."""

    @classmethod
    def setUpClass(cls):
        cls.program = program()
        cls.times = [0, 1, 2]
        cls.base = _invoke(dict(program=cls.program.to_dict(), driven=['u'], samples=[],
                                transient=dict(pwl=[POINTS], output_times=cls.times,
                                               stop=2, max_step=2),
                                tolerances=dict(absolute=1e-12, relative=1e-10)), KERNEL)

    def check(self, mutate, requested=None):
        response = copy.deepcopy(self.base)
        mutate(controls(response))
        return validate_response(response, self.program, 3, self.times,
                                 strobetimes=[], proof_work_limit=requested)

    def test_default_request_echoes_the_default_limit(self):
        self.assertEqual(controls(self.base)['proof_work_limit'], 1_000_000_000)
        self.check(lambda c: None)

    def test_echo_must_equal_a_requested_limit(self):
        self.check(lambda c: c.update(proof_work_limit=2_000_000_000_000), 2_000_000_000_000)
        with self.assertRaisesRegex(KernelError, 'proof work limit'):
            self.check(lambda c: c.update(proof_work_limit=1_000_000_000), 2_000_000_000_000)

    def test_requested_limit_cannot_be_silently_dropped(self):
        with self.assertRaisesRegex(KernelError, 'proof work limit'):
            self.check(lambda c: c.pop('proof_work_limit'), 2_000_000_000_000)

    def test_unrequested_echo_must_be_the_default(self):
        with self.assertRaisesRegex(KernelError, 'proof work limit'):
            self.check(lambda c: c.update(proof_work_limit=2_000_000_000_000))

    def test_old_kernel_without_the_echo_is_still_accepted_without_a_request(self):
        self.check(lambda c: c.pop('proof_work_limit'))

    def test_malformed_echoes_are_invalid_responses(self):
        for value in (0, -1, True, 1.5, 1e9, '1000000000', None, 10**13 + 1):
            with self.subTest(value=value), self.assertRaisesRegex(KernelError, 'proof work limit'):
                self.check(lambda c: c.update(proof_work_limit=value))

    def test_c8_comparison_requires_the_echoed_default_before_removing_it(self):
        # history_migration_contract.response_body maps a schema-33 response onto the
        # C8 baseline, which predates the echo. The echoed default is the only mapped
        # difference: it must be present as the integer 1e9, never merely tolerated.
        from history_migration_contract import response_body
        engine = self.base['engine']
        body = response_body(self.base, 33, engine)
        self.assertNotIn('proof_work_limit', controls(body))
        self.assertEqual(controls(body), {k: v for k, v in controls(self.base).items()
                                          if k != 'proof_work_limit'})
        for name, mutate in (('missing', lambda c: c.pop('proof_work_limit')),
                             ('other limit', lambda c: c.update(proof_work_limit=2_000_000_000_000)),
                             ('float', lambda c: c.update(proof_work_limit=1e9))):
            response = copy.deepcopy(self.base)
            mutate(controls(response))
            with self.subTest(echo=name), self.assertRaises(AssertionError):
                response_body(response, 33, engine)


class ProofWorkLimitKernel(unittest.TestCase):
    def raw(self, field, kernel=KERNEL):
        request = dict(program=program().to_dict(), driven=['u'], samples=[],
                       transient=dict(pwl=[POINTS], output_times=[0, 1, 2], stop=2, max_step=2),
                       tolerances=dict(absolute=1e-12, relative=0))
        request['transient'].update(field)
        return request

    def test_kernel_rejects_every_invalid_shape_as_invalid_inputs(self):
        # JSON text is written by hand: Python would normalise 2e12 and True.
        template = json.dumps(self.raw({})).replace('"stop": 2', '"stop": 2, "proof_work_limit": %s')
        for text in ('0', '10000000000001', '-1', '2000000000000.0', '2e12', '1.5',
                     'true', '"5"', 'null', '18446744073709551616'):
            with self.subTest(text=text):
                result = subprocess.run([str(KERNEL)], input=template % text,
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 2, result.stdout)
                error = json.loads(result.stderr)
                self.assertEqual(error['kind'], 'invalid_inputs')
                self.assertIn('proof_work_limit', error['message'])

    def test_kernel_accepts_the_exact_boundaries(self):
        for value in (1, 10**13):
            with self.subTest(value=value):
                try:
                    response = _invoke(self.raw({'proof_work_limit': value}), KERNEL)
                except KernelError as error:
                    # A tiny ledger may legitimately exhaust, but never as a bad request.
                    self.assertEqual(error.detail['kind'], 'step_budget')
                else:
                    self.assertEqual(controls(response)['proof_work_limit'], value)

    def check_kernel_without_the_field_rejects_it_explicitly(self):
        self.assertTrue(MAIN_KERNEL, 'EVAS_TEST_MAIN_KERNEL must name a kernel built from main')
        with self.assertRaises(KernelError) as caught:
            _invoke(self.raw({'proof_work_limit': 2_000_000_000_000}), MAIN_KERNEL)
        self.assertEqual(caught.exception.detail['kind'], 'invalid_request')
        self.assertIn('proof_work_limit', caught.exception.detail['message'])

    def check_default_request_response_equals_main_except_the_echoed_default(self):
        self.assertTrue(MAIN_KERNEL, 'EVAS_TEST_MAIN_KERNEL must name a kernel built from main')
        request = self.raw({})
        old = _invoke(request, MAIN_KERNEL)
        new = _invoke(request, KERNEL)
        self.assertEqual(new['observation_evidence']['effective_controls'].pop('proof_work_limit'),
                         1_000_000_000)
        self.assertEqual(json.dumps(new, sort_keys=True), json.dumps(old, sort_keys=True))

    def test_explicit_default_is_the_same_ledger_as_unset(self):
        request = self.raw({})
        unset = _invoke(request, KERNEL)
        explicit = _invoke(self.raw({'proof_work_limit': 1_000_000_000}), KERNEL)
        self.assertEqual(json.dumps(unset, sort_keys=True), json.dumps(explicit, sort_keys=True))


class ProofWorkLimitEndToEnd(unittest.TestCase):
    """Natural exhaustion of the real source-transition ledger, no fake debit."""

    def test_a_lower_request_limit_exhausts_the_same_request_that_default_completes(self):
        result = run(1000)
        self.assertEqual(controls(result)['proof_work_limit'], 1_000_000_000)
        with self.assertRaises(KernelError) as caught:
            run(1000, proof_work_limit=50_000_000)
        self.assertEqual(caught.exception.detail['kind'], 'step_budget')
        # The message reports the limit that was actually in force.
        self.assertRegex(caught.exception.detail['message'], r'used \d+ \+ \d+ exceeds 50000000$')

    def test_default_exhausts_naturally_and_a_larger_limit_completes_with_exact_answers(self):
        n = 3000
        with self.assertRaises(KernelError) as caught:
            run(n)
        self.assertEqual(caught.exception.detail['kind'], 'step_budget')
        self.assertRegex(caught.exception.detail['message'], r'exceeds 1000000000$')
        result = run(n, proof_work_limit=10_000_000_000)
        self.assertEqual(controls(result)['proof_work_limit'], 10_000_000_000)
        y = result['nodes'].index('y')
        times = grid(n)
        self.assertEqual(len(result['solutions']), n)
        for t, row in zip(times, result['solutions']):
            self.assertLessEqual(abs(F(row['voltages'][y]) - expected(t)), F(1, 10**11), t)

    def test_failed_reservations_are_not_refunded_so_a_retry_cannot_launder_the_ledger(self):
        # Two independent requests share nothing, but within one request the
        # exhausted owner stays exhausted: the first error is the only outcome
        # and it reports used > limit - amount (the failed reservation is kept).
        with self.assertRaises(KernelError) as caught:
            run(1000, proof_work_limit=50_000_000)
        message = caught.exception.detail['message']
        used, amount = map(int, __import__('re').search(r'used (\d+) \+ (\d+)', message).groups())
        self.assertLessEqual(used, 50_000_000)
        self.assertGreater(used + amount, 50_000_000)


class ProofWorkLimitSurfaces(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'm.va').write_text(model('V(y,r)<+gain*V(u,r);', 'parameter real gain=2 from (0:inf);'))
        self.path = self.root / 'tb.scs'
        self.path.write_text('simulator lang=spectre\nglobal 0\nahdl_include "m.va"\n'
                             'Vin (u 0) vsource type=pwl wave=[0 0 .5 1 1 0]\nDUT (u y 0) m gain=3\n'
                             'tran tran stop=1 maxstep=.25\nsave y u\n')

    def test_simulate_scs_forwards_and_echoes_the_limit(self):
        default = simulate_scs(self.path, kernel=KERNEL)
        self.assertEqual(controls(default)['proof_work_limit'], 1_000_000_000)
        raised = simulate_scs(self.path, kernel=KERNEL, proof_work_limit=2_000_000_000_000)
        self.assertEqual(controls(raised)['proof_work_limit'], 2_000_000_000_000)
        self.assertEqual(raised['saved'], default['saved'])
        with self.assertRaisesRegex(ValueError, 'proof_work_limit'):
            simulate_scs(self.path, kernel=KERNEL, proof_work_limit=True)

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'evas', *args, '--kernel', str(KERNEL)],
                              text=True, capture_output=True)

    def test_cli_simulate_accepts_a_digits_only_limit(self):
        child = self.cli('simulate', str(self.path), '--proof-work-limit', '2000000000000')
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(controls(json.loads(child.stdout))['proof_work_limit'], 2_000_000_000_000)

    def test_cli_rejects_malformed_values_before_running(self):
        for text in ('0', '-1', '1e9', '1.5', 'abc', '', '10000000000001', '+5', ' 5'):
            with self.subTest(text=text):
                child = self.cli('simulate', str(self.path), '--proof-work-limit', text)
                self.assertEqual(child.returncode, 2, child.stdout)
                report = json.loads(child.stderr)
                self.assertEqual(report['kind'], 'compile_error')
                self.assertIn('proof-work-limit', report['message'])
                self.assertNotIn('unrecognized', report['message'])
                self.assertEqual(child.stdout, '')

    def test_cli_transient_manifest_forwards_the_limit(self):
        manifest = dict(
            models=['m.va'],
            instances=[dict(name='DUT', module='m', connections=dict(u='u', y='y', r='0'),
                            parameters=dict(gain=3))],
            transient=dict(sources={'u': [[0, 0], [1, 1]]}, output_times=[0, 1], stop=1, max_step=1))
        (self.root / 'manifest.json').write_text(json.dumps(manifest))
        child = self.cli('transient', str(self.root / 'manifest.json'), '--proof-work-limit', '5000000000')
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(controls(json.loads(child.stdout))['proof_work_limit'], 5_000_000_000)
        # A limit written in the manifest as well is ambiguous and is refused.
        manifest['transient']['proof_work_limit'] = 7
        (self.root / 'manifest.json').write_text(json.dumps(manifest))
        child = self.cli('transient', str(self.root / 'manifest.json'), '--proof-work-limit', '5000000000')
        self.assertEqual(child.returncode, 2)
        self.assertIn('proof_work_limit', json.loads(child.stderr)['message'])

    def test_cli_flag_is_only_for_transient_and_simulate(self):
        for action in ('compile', 'solve', 'lint'):
            with self.subTest(action=action):
                child = subprocess.run([sys.executable, '-m', 'evas', action, str(self.path),
                                        '--proof-work-limit', '5'], text=True, capture_output=True)
                self.assertEqual(child.returncode, 2)
                message = json.loads(child.stderr)['message']
                self.assertIn('--proof-work-limit applies only to transient and simulate', message)


if __name__ == '__main__':
    unittest.main()
