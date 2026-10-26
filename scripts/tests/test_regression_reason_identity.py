"""Bounded observations from actual stdlib assertions, without a simulator."""
from fractions import Fraction
import hashlib
import inspect
import ast
import copy
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent


def fraction_failure(actual, expected):
    unittest.TestCase().assertGreaterEqual(actual, expected)


def diagnostic_producer(elapsed,kind):
    started=time.monotonic()
    record={'outcome':'event_fail','failure_kind':kind,
            'mismatches':[{'actual':6,'expected':5}],'expectation':{'value':Fraction(1,3)}}
    time.sleep(elapsed)
    record['elapsed_s']=round(time.monotonic()-started,3)
    return record


def timing_failure(elapsed, kind='duplicate_event', actual='event_fail', expected='pass'):
    msg=diagnostic_producer(elapsed,kind)
    unittest.TestCase().assertEqual(actual, expected, msg)


def handcrafted_timing_failure():
    msg={'elapsed_s':0.019,'failure_kind':'same_key_but_user_data'}
    unittest.TestCase().assertEqual('actual','expected',msg)


def changed_return_failure(copy_record=False):
    returned=diagnostic_producer(.001,'duplicate_event')
    msg=dict(returned) if copy_record else returned
    if not copy_record:
        msg['elapsed_s']+=1.0
    unittest.TestCase().assertEqual('actual','expected',msg)


def collision_failure(msg):
    unittest.TestCase().assertEqual('actual','expected',msg)


def temp_failure(suffix='/dut.va:2:86: division by zero', needle='nonzero divisor'):
    with tempfile.TemporaryDirectory() as tmp:
        unittest.TestCase().assertIn(needle, tmp + suffix)


def unproven_temp_failure():
    tmp='/tmp/looks_like_a_tempdir'
    unittest.TestCase().assertIn('missing',tmp+'/dut.va:2:86: division by zero')


def structured_msg_failure(msg):
    unittest.TestCase().assertEqual('actual','expected',msg)


def neighboring_assertions(first):
    if first:
        unittest.TestCase().assertGreaterEqual(Fraction(1,2),Fraction(2,3))
    unittest.TestCase().assertGreaterEqual(Fraction(1,2),Fraction(2,3))


def opaque_failure():
    unittest.TestCase().assertIn(object(), ['known'])


def resolved_temp_failure():
    with tempfile.TemporaryDirectory() as tmp:
        unittest.TestCase().assertIn('expected diagnostic', str(Path(tmp).resolve()) + '/dut.va:2:86: actual diagnostic')


def combined_case():
    class Case(unittest.TestCase):
        def test_combined(self):
            with self.subTest(expression='1/0'), tempfile.TemporaryDirectory() as tmp:
                self.generated_root=tmp
                self.assertIn('nonzero divisor',tmp+'/dut.va:2:86: division by zero')
    return Case


class AssertionIdentityTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('assertion_identity', ROOT.parent/'regression_reason_identity.py')
        self.api=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.api)

    def same_reason(self, before, after):
        # Exercise the maintained full gate, not the prototype comparator.
        spec = importlib.util.spec_from_file_location('reason_gate_fixture', ROOT / 'test_regression_gate.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        gate = fixture.load_gate()
        reports = []
        for reason in (before, after):
            report = fixture.report()
            reason = copy.deepcopy(reason)
            if reason.get('comparison_state') == 'unselected':
                reason.pop('comparison_complete', None)
                reason.pop('comparison_state', None)
            report['tests'][0]['conditions'][0]['reason'] = reason
            reports.append(report)
        try:
            baseline = gate.propose_baseline(reports[0], {'fixture': 'actual-native-assertion'}, fixture.REVIEW)
            return gate.compare_report(reports[1], baseline)['merge_allowed']
        except ValueError:
            return False

    def test_custom_failure_exception_diagnostic_cannot_be_replaced_by_operands(self):
        class SemanticFailure(AssertionError):
            diagnostic = 'semantic A'

            def __str__(self):
                return super().__str__() + ': ' + self.diagnostic

        native = self.policy('native-assertion', fraction_failure)
        original = unittest.TestCase.failureException
        try:
            unittest.TestCase.failureException = SemanticFailure
            before = self.api.observe_failure(lambda: fraction_failure(Fraction(1, 2), Fraction(2, 3)),
                                              site_policy=native)
            SemanticFailure.diagnostic = 'semantic B'
            after = self.api.observe_failure(lambda: fraction_failure(Fraction(1, 2), Fraction(2, 3)),
                                             site_policy=native)
        finally:
            unittest.TestCase.failureException = original
        self.assertNotEqual(before['message'], after['message'])
        self.assertFalse(self.same_reason(before, after))
        self.assertFalse(before['comparison_complete'])
        self.assertFalse(after['comparison_complete'])

    def test_dynamic_failure_lookup_cannot_forge_native_failure_semantics(self):
        Case = combined_case()
        native = self.policy('native-assertion', Case.test_combined)
        temp = self.policy('temporary-directory-root', Case.test_combined)

        def lookup(instance, name):
            if name == 'fail':
                def fail(_message):
                    raise AssertionError(object.__getattribute__(instance, 'diagnostic'))
                return fail
            return object.__getattribute__(instance, name)

        Case.__getattribute__ = lookup
        reasons = []
        for text in ('semantic A', 'semantic B'):
            case = Case('test_combined')
            case.diagnostic = text
            api = self.api
            with api.ObservationSession(site_policy=native, tempdir_policy=temp) as session:
                class Result(unittest.TestResult):
                    def addSubTest(self, test, subtest, err):
                        reasons.append(session.capture(err))
                        super().addSubTest(test, subtest, err)
                case.run(Result())
        self.assertNotEqual(reasons[0]['message'], reasons[1]['message'])
        self.assertFalse(self.same_reason(*reasons))
        self.assertTrue(all(not reason['comparison_complete'] for reason in reasons))

    def test_rejected_custom_exception_formatter_cannot_break_collection(self):
        class UnprintableFailure(AssertionError):
            def __str__(self):
                raise RuntimeError('custom diagnostic unavailable')

        native = self.policy('native-assertion', fraction_failure)
        original = unittest.TestCase.failureException
        try:
            unittest.TestCase.failureException = UnprintableFailure
            reason = self.api.observe_failure(lambda: fraction_failure(Fraction(1, 2), Fraction(2, 3)),
                                             site_policy=native)
        finally:
            unittest.TestCase.failureException = original
        self.assertFalse(reason['comparison_complete'])
        self.assertNotIn('comparison_identity', reason)

    def policy(self, kind, function):
        tree=ast.parse(Path(__file__).read_text())
        function_node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==function.__name__)
        operation=next(n.func.attr for n in ast.walk(function_node) if isinstance(n,ast.Call)
                       and isinstance(n.func,ast.Attribute) and n.func.attr in ('assertEqual','assertIn','assertGreaterEqual'))
        call=min((n for n in ast.walk(function_node) if isinstance(n,ast.Call)
                  and isinstance(n.func,ast.Attribute) and n.func.attr==operation),key=lambda n:n.lineno)
        value=dict(schema_version=1,id=kind+'-fixture',version=1,kind=kind,
                   source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   function=function.__qualname__, assertion_line=call.lineno, operation=operation)
        if kind=='diagnostic-duration':
            producer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='diagnostic_producer')
            assignment=next(n for n in producer.body if isinstance(n,ast.Assign)
                            and isinstance(n.targets[0],ast.Subscript))
            value.update(operation='assertEqual',message_path=['elapsed_s'],role='duration-seconds',
                         producer={'source_sha256':value['source_sha256'],
                                   'function':'diagnostic_producer','assignment_line':assignment.lineno})
        elif kind=='temporary-directory-root':
            value.update(target='tmp')
        return value

    def test_proven_temp_root_stable_but_suffix_diagnostic_and_member_stay_semantic(self):
        native=self.policy('native-assertion',temp_failure)
        temp=self.policy('temporary-directory-root',temp_failure)
        before=self.api.observe_failure(temp_failure,site_policy=native,tempdir_policy=temp)
        after=self.api.observe_failure(temp_failure,site_policy=native,tempdir_policy=temp)
        self.assertTrue(before['comparison_complete'],before)
        self.assertNotEqual(before['message'],after['message'])
        self.assertTrue(self.same_reason(before,after))
        for suffix in ('/other.va:2:86: division by zero','/dut.va:3:86: division by zero',
                       '/dut.va:2:87: division by zero','/dut.va:2:86: different diagnostic'):
            changed=self.api.observe_failure(lambda:temp_failure(suffix),site_policy=native,tempdir_policy=temp)
            self.assertFalse(self.same_reason(before,changed))
        changed=self.api.observe_failure(lambda:temp_failure(needle='different expected text'),
                                          site_policy=native,tempdir_policy=temp)
        self.assertFalse(self.same_reason(before,changed))
        unproven=self.api.observe_failure(unproven_temp_failure,
                       site_policy=self.policy('native-assertion',unproven_temp_failure),
                       tempdir_policy=self.policy('temporary-directory-root',unproven_temp_failure))
        self.assertFalse(unproven['comparison_complete'])
        self.assertNotIn('comparison_identity',unproven)

    def test_combined_subtest_captures_exception_bound_proof_after_directory_exit(self):
        Case=combined_case()
        native=self.policy('native-assertion',Case.test_combined)
        temp=self.policy('temporary-directory-root',Case.test_combined)
        api=self.api
        def execute():
            class Result(unittest.TestResult):
                def addSubTest(self,test,subtest,err):
                    self.directory_already_removed=not Path(test.generated_root).exists()
                    self.reason=session.capture(err)
                    super().addSubTest(test,subtest,err)
            with api.ObservationSession(site_policy=native,tempdir_policy=temp) as session:
                result=Result()
                Case('test_combined').run(result)
            self.assertTrue(result.directory_already_removed)
            self.assertTrue(result.reason['comparison_complete'],result.reason)
            return result.reason
        before=execute();after=execute()
        self.assertNotEqual(before['message'],after['message'])
        self.assertTrue(self.same_reason(before,after))

    def test_timed_result_retains_proof_after_subtest_unwind(self):
        spec = importlib.util.spec_from_file_location('reason_runner', ROOT.parent / 'run_regression.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        Case = combined_case()
        policy = dict(source_path='scripts/tests/test_regression_reason_identity.py',
                      site_policy=self.policy('native-assertion', Case.test_combined),
                      tempdir_policy=self.policy('temporary-directory-root', Case.test_combined))
        observations = []
        for _ in range(2):
            journal = io.StringIO()
            result = runner.TimedResult(unittest.runner._WritelnDecorator(io.StringIO()), True, 0,
                                        journal=journal, reason_policies=[policy])
            case = Case('test_combined')
            case.run(result)
            self.assertFalse(Path(case.generated_root).exists())
            condition = result.timings[0]['conditions'][0]
            self.assertTrue(condition['identity_complete'], condition)
            self.assertTrue(condition['reason']['comparison_complete'], condition)
            observations.append(condition['reason'])
        self.assertNotEqual(observations[0]['message'], observations[1]['message'])
        self.assertTrue(self.same_reason(*observations))

    def test_proven_filesystem_alias_of_temporary_root(self):
        native = self.policy('native-assertion', resolved_temp_failure)
        policy = self.policy('temporary-directory-root', resolved_temp_failure)
        with tempfile.TemporaryDirectory() as base:
            real = Path(base) / 'real'
            real.mkdir()
            alias = Path(base) / 'alias'
            alias.symlink_to(real, target_is_directory=True)
            prior = tempfile.tempdir
            try:
                tempfile.tempdir = str(alias)
                first = self.api.observe_failure(resolved_temp_failure, site_policy=native, tempdir_policy=policy)
                second = self.api.observe_failure(resolved_temp_failure, site_policy=native, tempdir_policy=policy)
            finally:
                tempfile.tempdir = prior
        self.assertTrue(first['comparison_complete'], first)
        self.assertTrue(self.same_reason(first, second))

    def test_internal_looking_userdata_remains_an_ordinary_typed_dictionary(self):
        native=self.policy('native-assertion',structured_msg_failure)
        payload={'type':'diagnostic-role','role':'duration-seconds','value_type':'float'}
        reason=self.api.observe_failure(lambda:structured_msg_failure(payload),site_policy=native)
        self.assertTrue(reason['comparison_complete'])
        self.assertEqual(reason['comparison_identity']['message']['type'],'dict')
        changed=dict(payload,value_type='int')
        after=self.api.observe_failure(lambda:structured_msg_failure(changed),site_policy=native)
        self.assertFalse(self.same_reason(reason,after))

    def test_other_assertion_in_same_method_keeps_exact_message_policy(self):
        native=self.policy('native-assertion',neighboring_assertions)
        selected=self.api.observe_failure(lambda:neighboring_assertions(True),site_policy=native)
        other=self.api.observe_failure(lambda:neighboring_assertions(False),site_policy=native)
        self.assertTrue(selected['comparison_complete'],selected)
        self.assertEqual(other['comparison_state'],'unselected')
        self.assertNotIn('comparison_identity',other)

    def test_unknown_policy_opaque_operand_and_wrong_site_cannot_be_complete(self):
        opaque=self.api.observe_failure(opaque_failure,site_policy=self.policy('native-assertion',opaque_failure))
        self.assertEqual(opaque['comparison_state'],'incomplete')
        self.assertNotIn('comparison_identity',opaque)
        native=self.policy('native-assertion',fraction_failure)
        for field,value in [('schema_version',2),('assertion_line',native['assertion_line']+1),
                            ('source_sha256','0'*64),('operation','assertEqual')]:
            bad=dict(native);bad[field]=value
            reason=self.api.observe_failure(lambda:fraction_failure(Fraction(1,2),Fraction(2,3)),site_policy=bad)
            self.assertFalse(reason['comparison_complete'])
            self.assertNotIn('comparison_identity',reason)
        reason=self.api.observe_failure(lambda:fraction_failure(Fraction(1,2),Fraction(2,3)),site_policy=native)
        unknown=copy.deepcopy(reason);unknown['comparison_identity']['schema_version']=99
        self.assertFalse(self.same_reason(unknown,unknown))

    def test_existing_trace_and_profile_callbacks_are_preserved_and_selected_temp_refused(self):
        native=self.policy('native-assertion',temp_failure)
        temp=self.policy('temporary-directory-root',temp_failure)
        for setter,getter in ((sys.settrace,sys.gettrace),(sys.setprofile,sys.getprofile)):
            calls=[]
            def callback(frame,event,arg):
                calls.append(event)
                return callback
            original=getter()
            try:
                setter(callback)
                reason=self.api.observe_failure(temp_failure,site_policy=native,tempdir_policy=temp)
                self.assertIs(getter(),callback)
                self.assertEqual(reason['comparison_state'],'incomplete')
                self.assertNotIn('comparison_identity',reason)
                self.assertTrue(calls)
            finally:
                setter(original)
            self.assertIs(getter(),original)

    def test_old_exception_cannot_reuse_previous_session_temp_proof(self):
        Case=combined_case()
        native=self.policy('native-assertion',Case.test_combined)
        temp=self.policy('temporary-directory-root',Case.test_combined)
        class Result(unittest.TestResult):
            def addSubTest(inner,test,subtest,err):
                inner.err=err
                inner.reason=session.capture(err)
                super().addSubTest(test,subtest,err)
        with self.api.ObservationSession(site_policy=native,tempdir_policy=temp) as session:
            result=Result();Case('test_combined').run(result)
        self.assertTrue(result.reason['comparison_complete'])
        with self.api.ObservationSession(site_policy=native,tempdir_policy=temp) as another:
            replay=another.capture(result.err)
        self.assertFalse(replay['comparison_complete'])
        self.assertNotIn('comparison_identity',replay)

    def test_forged_producer_filename_and_qualname_do_not_prove_source_code(self):
        original=globals()['diagnostic_producer']
        source=inspect.getsource(original).replace('round(time.monotonic()-started,3)','0.019')
        fake_source='\n'*(original.__code__.co_firstlineno-1)+source
        namespace=dict(globals())
        exec(compile(fake_source,original.__code__.co_filename,'exec'),namespace)
        forged=namespace['diagnostic_producer']
        self.assertEqual(forged.__code__.co_filename,original.__code__.co_filename)
        self.assertEqual(forged.__code__.co_qualname,original.__code__.co_qualname)
        native=self.policy('native-assertion',timing_failure)
        duration=self.policy('diagnostic-duration',timing_failure)
        globals()['diagnostic_producer']=forged
        try:
            reason=self.api.observe_failure(lambda:timing_failure(.001),site_policy=native,timing_policy=duration)
        finally:
            globals()['diagnostic_producer']=original
        self.assertFalse(reason['comparison_complete'])
        self.assertNotIn('comparison_identity',reason)

    def test_fraction_property_patch_does_not_run_during_slot_capture(self):
        expected=Fraction(10**5000+1,3)
        native=self.policy('native-assertion',fraction_failure)
        try:
            fraction_failure(Fraction(1,2),expected)
        except AssertionError:
            captured=sys.exc_info()
        calls=[]
        original=Fraction.__dict__['numerator']
        def forbidden(value):
            calls.append(value)
            raise RuntimeError('user Fraction property callback')
        Fraction.numerator=property(forbidden)
        try:
            reason=self.api.capture_reason(captured,site_policy=native)
        finally:
            Fraction.numerator=original
        self.assertTrue(reason['comparison_complete'],reason)
        self.assertEqual(calls,[])

    def test_copied_or_mutated_return_dict_cannot_claim_observed_duration(self):
        native=self.policy('native-assertion',changed_return_failure)
        duration=self.policy('diagnostic-duration',changed_return_failure)
        for copied in (False,True):
            reason=self.api.observe_failure(lambda:changed_return_failure(copied),
                                           site_policy=native,timing_policy=duration)
            self.assertFalse(reason['comparison_complete'])
            self.assertNotIn('comparison_identity',reason)

    def test_nonstring_elapsed_collision_key_causes_no_collector_equality_callback(self):
        calls=[]
        class Key:
            def __hash__(self): return hash('elapsed_s')
            def __eq__(self,other):
                calls.append(other)
                return True
        msg={Key():.019}
        calls.clear()
        reason=self.api.observe_failure(lambda:collision_failure(msg),
                       site_policy=self.policy('native-assertion',collision_failure),
                       timing_policy=self.policy('diagnostic-duration',collision_failure))
        self.assertFalse(reason['comparison_complete'])
        self.assertNotIn('comparison_identity',reason)
        self.assertEqual(calls,[])

    def test_handcrafted_elapsed_field_cannot_claim_producer_duration_role(self):
        native=self.policy('native-assertion',handcrafted_timing_failure)
        duration=self.policy('diagnostic-duration',handcrafted_timing_failure)
        reason=self.api.observe_failure(handcrafted_timing_failure,site_policy=native,timing_policy=duration)
        self.assertFalse(reason['comparison_complete'])
        self.assertNotIn('comparison_identity',reason)
        self.assertIn('0.019',reason['message'])

    def test_timing_policy_changes_only_explicit_diagnostic_duration(self):
        native=self.policy('native-assertion',timing_failure)
        duration=self.policy('diagnostic-duration',timing_failure)
        before=self.api.observe_failure(lambda:timing_failure(.001),site_policy=native,timing_policy=duration)
        after=self.api.observe_failure(lambda:timing_failure(.080),site_policy=native,timing_policy=duration)
        self.assertTrue(before['comparison_complete'],before)
        self.assertNotEqual(before['message'],after['message'])
        self.assertTrue(self.same_reason(before,after))
        for callback in (lambda:timing_failure(.080,kind='different_failure'),
                         lambda:timing_failure(.080,actual='different_actual'),
                         lambda:timing_failure(.080,expected='different_expected')):
            changed=self.api.observe_failure(callback,site_policy=native,timing_policy=duration)
            self.assertFalse(self.same_reason(before,changed))
        raw_before=self.api.observe_failure(lambda:timing_failure(.001))
        raw_after=self.api.observe_failure(lambda:timing_failure(.080))
        self.assertEqual(raw_before['comparison_state'],'unselected')
        self.assertFalse(self.same_reason(raw_before,raw_after))
        malformed=copy.deepcopy(duration);malformed['schema_version']=2
        result=self.api.observe_failure(lambda:timing_failure(.080),site_policy=native,timing_policy=malformed)
        self.assertFalse(result['comparison_complete'])
        self.assertNotIn('comparison_identity',result)

    def test_huge_fraction_actual_safe_repr_fallback_is_lossless_and_stable(self):
        expected1=Fraction(10**5000+1,3)
        expected2=Fraction(10**5000+1,3)
        policy=self.policy('native-assertion',fraction_failure)
        before=self.api.observe_failure(lambda:fraction_failure(Fraction(1,2),expected1),site_policy=policy)
        after=self.api.observe_failure(lambda:fraction_failure(Fraction(1,2),expected2),site_policy=policy)
        self.assertIn('<fractions.Fraction object at 0x',before['message'])
        self.assertNotEqual(before['message'],after['message'])
        self.assertTrue(before['comparison_complete'],before)
        self.assertTrue(self.same_reason(before,after))
        operand=before['comparison_identity']['operands']['b']
        self.assertEqual(int(operand['numerator'],16),expected1.numerator)
        self.assertEqual(int(operand['denominator'],16),expected1.denominator)
        changed=self.api.observe_failure(lambda:fraction_failure(Fraction(1,2),Fraction(10**5000+4,3)),site_policy=policy)
        self.assertFalse(self.same_reason(before,changed))
        changed=self.api.observe_failure(lambda:fraction_failure(Fraction(2,3),expected2),site_policy=policy)
        self.assertFalse(self.same_reason(before,changed))
        self.assertIn('Traceback',before['traceback'])
        raw_before=self.api.observe_failure(lambda:fraction_failure(Fraction(1,2),expected1))
        raw_after=self.api.observe_failure(lambda:fraction_failure(Fraction(1,2),expected2))
        self.assertFalse(self.same_reason(raw_before,raw_after))


if __name__=='__main__':
    unittest.main()
