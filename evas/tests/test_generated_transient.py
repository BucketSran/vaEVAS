"""Bounded generated timer sample/hold and integral cases with exact oracles.

Expected values are derived independently of the kernel: every generated time
is a multiple of 1/4 and every value a multiple of 1/2, so the held signal and
its exact areas are binary64-exact and the oracle uses ``Fraction`` arithmetic
plus hand-derived answers for one fixed case.  The generator
(evas/validation/generated_transient.py) is validation-side tooling: it only
reuses the public compile/transient boundary and classifies outcomes honestly
(a rejection is never accepted; see the negative controls below).
"""
# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["TIMER", "DYNAMICS", "COMPOSE"]

import importlib.util
from contextlib import redirect_stdout
import io
import json
from fractions import Fraction as Q
import pathlib
import tempfile
import unittest
import copy
from unittest.mock import patch

from test_affine import KERNEL

_spec = importlib.util.spec_from_file_location(
    "generated_transient", pathlib.Path(__file__).resolve().parents[1] / "validation/generated_transient.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

# Fixed hand case: q0=1/2, timers (1,-1) and (2,1/2), stop 3.  Sample grid
# 0, .5, 1, 1.5, 2, 2.5, 3 with post-event observations.
HAND_HOLD = gen.fixed_case("hold", Q(1, 2), 0, [(1, -1), (2, Q(1, 2))], 3)
HAND_INTEGRAL = gen.fixed_case("integral", Q(1, 2), Q(1, 4), [(1, -1), (2, Q(1, 2))], 3)


class GeneratedOracleContracts(unittest.TestCase):
    def test_generation_is_deterministic_and_bounded(self):
        base = gen.generate_case(5)
        for seed in (5, 5):
            case = gen.generate_case(seed)
            self.assertEqual(case, base)
            self.assertEqual(case["digest"], base["digest"])
        for case in map(gen.generate_case, range(1, 15)):
            times = [Q(e["time"]) for e in case["events"]]
            self.assertLessEqual(len(times), gen.MAX_TIMERS)
            self.assertTrue(all(a < b for a, b in zip(times, times[1:])))
            self.assertTrue(all(Q(0) < t < Q(case["stop"]) <= 10 for t in times))
            self.assertLessEqual(len(gen.output_times(case)), gen.MAX_OUTPUT_TIMES)
            # Dyadic values keep the Fraction oracle binary64-exact.
            for value in [Q(case["q0"]), Q(case["ic"])] + [Q(e["value"]) for e in case["events"]]:
                self.assertEqual(Q(float(value)), value)
        self.assertIn("hold", {gen.generate_case(s)["template"] for s in range(1, 15)})
        self.assertIn("integral", {gen.generate_case(s)["template"] for s in range(1, 15)})

    def test_hand_case_answers_match_closed_forms(self):
        # Hold: post-event piecewise-constant samples.
        self.assertEqual([gen.exact_output(HAND_HOLD, t) for t in gen.output_times(HAND_HOLD)],
                         [Q(1, 2), Q(1, 2), -1, -1, Q(1, 2), Q(1, 2), Q(1, 2)])
        # Integral of the same signal with ic=1/4: exact areas of a
        # piecewise-constant function, computed by hand:
        # y(0)=1/4, y(.5)=1/4+1/2*.5=1/2, y(1)=3/4, y(1.5)=1/4,
        # y(2)=-1/4, y(2.5)=-1/4+.5*.5=0, y(3)=-1/4+.5=1/4.
        self.assertEqual([gen.exact_output(HAND_INTEGRAL, t) for t in gen.output_times(HAND_INTEGRAL)],
                         [Q(1, 4), Q(1, 2), Q(3, 4), Q(1, 4), Q(-1, 4), 0, Q(1, 4)])

    def test_expected_event_records_and_states_are_exact(self):
        want = gen.expected(HAND_INTEGRAL)
        self.assertEqual(want["times"], [Q(t) for t in (0, Q(1, 2), 1, Q(3, 2), 2, Q(5, 2), 3)])
        self.assertEqual([e["time"] for e in want["events"]], [1, 2])
        self.assertEqual([e["after"] for e in want["events"]], [[-1, 1], [Q(1, 2), 2]])
        self.assertEqual([e["kind"] for e in want["events"]], ["timer", "timer"])
        self.assertEqual(want["states"],
                         [[Q(1, 2), 0], [Q(1, 2), 0], [-1, 1], [-1, 1], [Q(1, 2), 2], [Q(1, 2), 2], [Q(1, 2), 2]])
        self.assertEqual(want["nodes"]["nc"], [0, 0, 1, 1, 2, 2, 2])


class GeneratedKernelContracts(unittest.TestCase):
    """Focused runs through the public boundary with the fixed baseline kernel."""

    def test_generated_cases_match_exact_oracles(self):
        outcomes = {}
        for seed in range(1, 7):
            case = gen.generate_case(seed)
            outcome = gen.run_case(case, KERNEL)
            outcomes[case["template"]] = outcome["outcome"]
            self.assertEqual(outcome["outcome"], "pass", outcome)
            self.assertIsNone(outcome["failure_kind"])
        self.assertEqual(outcomes, {"hold": "pass", "integral": "pass"})

    def test_corrupted_oracles_are_not_silently_accepted(self):
        # Checker calibration: wrong value, missing event row and duplicated
        # event row must each produce mismatches against a real passing result.
        for case in (HAND_HOLD, HAND_INTEGRAL):
            with self.subTest(template=case["template"]):
                result = gen.execute(case, KERNEL)
                self.assertEqual(gen.check(case, result, gen.output_times(case)), [])
                report = gen.calibrate(case, result, gen.output_times(case))
                self.assertEqual({mode: entry["detected"] for mode, entry in report.items()},
                                 {"wrong_value": True, "missing_event": True, "duplicate_event": True})

    def test_model_side_event_defects_are_diagnosed_not_accepted(self):
        case = HAND_INTEGRAL
        for mutation, kind in (({"drop_timer": 0}, "missing_event"),
                               ({"duplicate_timer": 0}, "duplicate_event")):
            with self.subTest(mutation=mutation):
                outcome = gen.run_case(case, KERNEL, mutation=mutation)
                self.assertEqual(outcome["outcome"], "event_fail", outcome)
                self.assertEqual(outcome["failure_kind"], kind)
                self.assertTrue(outcome["mismatches"])

    def test_unsupported_rejection_is_classified_not_accepted(self):
        outcome = gen.run_case(HAND_INTEGRAL, KERNEL, mutation={"unsupported_feedback": True})
        self.assertEqual(outcome["outcome"], "unsupported", outcome)
        self.assertEqual(outcome["failure_kind"], "unsupported_operator")

    def test_numerical_defect_is_reported_as_value_mismatch(self):
        outcome = gen.run_case(HAND_INTEGRAL, KERNEL, mutation={"ic_bias": Q(1, 1024)})
        self.assertEqual(outcome["outcome"], "numerical_fail", outcome)
        self.assertEqual(outcome["failure_kind"], "value_mismatch:y")
        self.assertTrue(any(m["type"] == "value" and m["node"] == "y" for m in outcome["mismatches"]))

    def test_kernel_error_categories_map_to_honest_outcomes(self):
        from evas.errors import KernelError as KE
        for kind, category, outcome in [("unsupported_operator", "unsupported", "unsupported"),
                                        ("kernel_timeout", "resource", "resource"),
                                        ("invalid_response", "protocol", "protocol"),
                                        ("waveform_accuracy", "numerical", "numerical")]:
            with self.subTest(kind=kind):
                error = KE({"kind": kind, "message": "probe"})
                self.assertEqual(error.diagnostic["category"], category)
                self.assertEqual(gen.KERNEL_OUTCOMES[category], outcome)


class FailureReductionContracts(unittest.TestCase):
    def test_reduction_preserves_seed_and_diagnosed_failure(self):
        case = gen.generate_case(5)
        mutation = {"ic_bias": Q(1, 1024)}
        failure = gen.run_case(case, KERNEL, mutation=mutation)
        self.assertEqual(failure["outcome"], "numerical_fail")
        reduction = gen.reduce_failure(case, failure, KERNEL, mutation=mutation)
        self.assertEqual(reduction["seed"], case["seed"])
        self.assertTrue(reduction["attempts"])
        self.assertIn("candidate_outcome",reduction["attempts"][0])
        self.assertIn("candidate",reduction["attempts"][0])
        self.assertIsNotNone(reduction["reduced"])
        reduced = reduction["reduced"]
        self.assertLess(len(reduced["events"]), len(case["events"]))
        replay = gen.run_case(reduced, KERNEL, mutation=mutation)
        self.assertEqual((replay["outcome"], replay["failure_kind"]),
                         (failure["outcome"], failure["failure_kind"]))

    def test_reduction_rejects_candidates_that_change_the_failure_class(self):
        # Bias only the *last* timer's value: the first reduction (timer prefix)
        # removes the biased event entirely and passes, so it must be rejected;
        # the zeroed full-timer case keeps the defect and is accepted.
        case = gen.fixed_case("hold", 1, 0, [(1, 1), (2, 1), (3, 1)], 4)
        mutation = {"value_bias": {"index": 2, "eps": Q(1, 64)}}
        failure = gen.run_case(case, KERNEL, mutation=mutation)
        self.assertEqual(failure["outcome"], "numerical_fail")
        self.assertFalse(gen.same_failure(failure, {"outcome": "pass", "failure_kind": None}))
        reduction = gen.reduce_failure(case, failure, KERNEL, mutation=mutation)
        self.assertEqual(reduction["seed"], case["seed"])
        rejected = [a for a in reduction["attempts"] if not a["preserved"]]
        self.assertTrue(rejected, reduction["attempts"])
        self.assertIsNotNone(reduction["reduced"])
        self.assertEqual(len(reduction["reduced"]["events"]), len(case["events"]))

    def test_missing_event_failure_reduces_with_class_preserved(self):
        case = gen.generate_case(5)
        mutation = {"drop_timer": 0}
        failure = gen.run_case(case, KERNEL, mutation=mutation)
        self.assertEqual((failure["outcome"], failure["failure_kind"]), ("event_fail", "missing_event"))
        reduction = gen.reduce_failure(case, failure, KERNEL, mutation=mutation)
        self.assertIsNotNone(reduction["reduced"])
        replay = gen.run_case(reduction["reduced"], KERNEL, mutation=mutation)
        self.assertEqual((replay["outcome"], replay["failure_kind"]),
                         (failure["outcome"], failure["failure_kind"]))

    def test_non_failure_outcomes_are_not_reduced(self):
        case = gen.generate_case(5)
        passing = gen.run_case(case, KERNEL)
        reduction = gen.reduce_failure(case, passing, KERNEL)
        self.assertIsNone(reduction["reduced"])
        self.assertIn("not a checker failure", reduction["note"])


class BatchOutcomeContracts(unittest.TestCase):
    def test_existing_output_and_duplicate_seeds_are_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            sentinel = folder / 'seed-1.json'
            sentinel.write_bytes(b'original evidence\n')
            with patch.object(gen, 'run_case', return_value={'outcome': 'pass', 'failure_kind': None}) as execute:
                with self.assertRaises(FileExistsError):
                    gen.run_batch([1], KERNEL, folder)
                self.assertEqual(sentinel.read_bytes(), b'original evidence\n')
                for seeds in ([1, 1], []):
                    fresh = folder / 'fresh'
                    with self.assertRaises(ValueError):
                        gen.run_batch(seeds, KERNEL, fresh)
                    self.assertFalse(fresh.exists())
                execute.assert_not_called()

    def test_batch_preserves_seed_ids_and_separates_machine_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp) / 'run'
            summary = gen.run_batch([1, 5], KERNEL, folder, reduce_failures=False)
            names = sorted(p.name for p in folder.glob("seed-*.json"))
            self.assertEqual(names, ["seed-1.json", "seed-5.json"])
            self.assertEqual(len(summary["seeds"]), 2)
            self.assertEqual(summary["counts"], {"pass": 2})
            self.assertIn("sha256", summary["kernel"])
            for path in folder.glob("seed-*.json"):
                record = json.loads(path.read_text())
                self.assertEqual(record["seed_id"], path.stem)
                self.assertEqual(record["outcome"]["outcome"], "pass")
                self.assertIn("source", record)
                self.assertIn("case", record)


class StrictEvidenceCalibration(unittest.TestCase):
    def test_calibration_cli_reports_a_classified_failure_as_portable_json(self):
        failure = gen.run_case(HAND_INTEGRAL, KERNEL, mutation={'ic_bias': Q(1, 1024)})
        self.assertEqual(failure['outcome'], 'numerical_fail')
        stream = io.StringIO()
        with patch.object(gen, 'run_case', return_value=failure), redirect_stdout(stream):
            code = gen.main(['--calibrate-only', '--seeds', '1', '--kernel', str(KERNEL)])
        self.assertEqual(code, 1)
        report = json.loads(stream.getvalue())
        self.assertEqual(report['outcome'], 'numerical_fail')
        self.assertEqual(report['failure_kind'], 'value_mismatch:y')
        self.assertEqual(report['expectation'], gen._portable(failure['expectation']))

    def test_missing_malformed_and_nonfinite_response_is_not_a_pass(self):
        case=HAND_INTEGRAL; original=gen.execute(case,KERNEL);times=gen.output_times(case)
        mutations=[lambda r:r.update(transient=None),
                   lambda r:r['transient'].update(events=None),
                   lambda r:r['transient']['events'].__setitem__(0,None),
                   lambda r:r.update(solutions=[]),
                   lambda r:r['solutions'].pop(),
                   lambda r:r['solutions'].append(r['solutions'][-1]),
                   lambda r:r['transient']['states'].pop(),
                   lambda r:r['transient']['states'][0].pop(),
                   lambda r:r['solutions'][0]['voltages'].pop(),
                   lambda r:r['transient']['times'].__setitem__(0,.001),
                   lambda r:r['solutions'][0]['voltages'].__setitem__(0,float('nan')),
                   lambda r:r['transient']['states'][0].__setitem__(0,float('inf')),
                   lambda r:r['transient']['events'][0]['before'].pop(),
                   lambda r:r['transient']['events'][0].update(time=float('nan'))]
        for i,mutate in enumerate(mutations):
            with self.subTest(i=i):
                result=copy.deepcopy(original);mutate(result)
                self.assertTrue(gen.check(case,result,times))
                with patch.object(gen,'execute',return_value=result):
                    outcome=gen.run_case(case,KERNEL)
                self.assertEqual(outcome['outcome'],'protocol',outcome)
                json.dumps(gen._portable(outcome),allow_nan=False)

    def test_event_identity_and_state_witness_are_not_exchangeable(self):
        r=gen.execute(HAND_INTEGRAL,KERNEL)
        r['transient']['events'][0]['event']=1
        self.assertIn('event_identity',{m['type'] for m in gen.check(HAND_INTEGRAL,r,gen.output_times(HAND_INTEGRAL))})
        outcomes=[]
        for index in (0,2):
            r=gen.execute(HAND_INTEGRAL,KERNEL);r['transient']['states'][index][0]+=1
            with patch.object(gen,'execute',return_value=r):outcomes.append(gen.run_case(HAND_INTEGRAL,KERNEL))
        self.assertEqual(outcomes[0]['failure_kind'],'state_mismatch')
        self.assertFalse(gen.same_failure(*outcomes))
        outcomes=[]
        for state in (0,1):
            r=gen.execute(HAND_INTEGRAL,KERNEL);r['transient']['events'][0]['before'][state]+=.125
            with patch.object(gen,'execute',return_value=r):outcomes.append(gen.run_case(HAND_INTEGRAL,KERNEL))
        self.assertFalse(gen.same_failure(*outcomes))
        with patch.object(gen,'execute',return_value=[]):
            self.assertEqual(gen.run_case(HAND_INTEGRAL,KERNEL)['outcome'],'protocol')

    def test_before_state_is_checked(self):
        r=gen.execute(HAND_INTEGRAL,KERNEL)
        r['transient']['events'][0]['before'][0]+=1
        self.assertIn('event_before',{m['type'] for m in gen.check(HAND_INTEGRAL,r,gen.output_times(HAND_INTEGRAL))})

    def test_failure_witness_and_complexity_must_be_preserved(self):
        failure=dict(outcome='numerical_fail',failure_kind='value_mismatch:y',witness=['value','y',1.,1])
        for witness in (['value','y',2.,1],['value','h',1.,1],['value','y',1.,-1],None):
            self.assertFalse(gen.same_failure(failure,dict(failure,witness=witness)))
        zero=gen.fixed_case('hold',0,0,[(1,0)],2)
        self.assertTrue(all(gen.complexity(c)<gen.complexity(zero) for c in gen.reduction_candidates(zero)))

    def test_batch_saves_fraction_reduction_and_original_before_reducer_failure(self):
        case=HAND_INTEGRAL
        failure=gen.run_case(case,KERNEL,mutation={'ic_bias':Q(1,1024)})
        for raises in (False,True):
            with self.subTest(raises=raises),tempfile.TemporaryDirectory() as tmp:
                folder=pathlib.Path(tmp)/'run'
                originals=[]
                def reducer(*args,**kwargs):
                    originals.append((folder/'seed-0.json').read_bytes())
                    record=json.loads((folder/'seed-0.json').read_text())
                    self.assertEqual(record['outcome']['outcome'],'numerical_fail')
                    self.assertIn('response',record['outcome']);self.assertIn('expectation',record['outcome'])
                    self.assertIn('sha256',record['kernel']);self.assertIn('requested_settings',record)
                    if raises:raise RuntimeError('injected reducer failure')
                    return dict(reduced=case,original_failure=failure,original_digest=case['digest'])
                with patch.object(gen,'generate_case',return_value=case),patch.object(gen,'run_case',return_value=failure),patch.object(gen,'reduce_failure',side_effect=reducer):
                    gen.run_batch([0],KERNEL,folder)
                self.assertEqual((folder/'seed-0.json').read_bytes(),originals[0])
                record=json.loads((folder/'seed-0.json').read_text())
                reduced=json.loads((folder/'seed-0-reduction.json').read_text())
                self.assertIn('reduction_error' if raises else 'reduction',reduced)
                self.assertEqual(record['outcome']['digest'],case['digest'])

if __name__ == "__main__":
    unittest.main()
