"""Fault fixtures at the finite paper runner's stage/result boundary."""
from pathlib import Path
import tempfile
import unittest
from runner import stage_failure, result_state, allocation_check

class RunnerContracts(unittest.TestCase):
    def test_successful_exit_without_artifact_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            done={'stage':'compile','status':'completed','returncode':0,'timeout':False,
                  'cleanup':{'complete':True}}
            self.assertEqual(result_state([done],work,'waveform.txt','dut.osdi')['status'],'missing_compile_artifact')
            (work/'dut.osdi').write_bytes(b'fixture')
            self.assertEqual(result_state([done],work,'waveform.txt','dut.osdi')['status'],'missing_waveform')

    def test_cleanup_failure_overrides_zero_exit_and_aborts(self):
        row={'stage':'simulate','status':'completed','returncode':0,'timeout':False,
             'cleanup':{'complete':False}}
        self.assertEqual(stage_failure(row)['status'],'cleanup_incomplete')
        self.assertTrue(stage_failure(row)['abort_batch'])

    def test_compile_failure_and_timeout_keep_stage_and_different_states(self):
        base={'stage':'compile','status':'completed','returncode':2,'timeout':False,'cleanup':{'complete':True}}
        self.assertEqual(stage_failure(base)['status'],'compile_failed')
        self.assertEqual(stage_failure({**base,'timeout':True})['status'],'compile_timeout')

    def test_allocation_must_bind_frozen_inputs_and_profile(self):
        a={'backend':'spectre','input_manifest_sha256':'a','tool_profile_sha256':'b',
           'max_simulation_launches':12,'max_compilation_launches':12,'stage_timeout_s':90,
           'license_timeout_s':30,'memory_limit_bytes':4*1024**3,'file_limit_bytes':32*1024**2,'threads':1}
        allocation_check(a,'spectre','a','b')
        with self.assertRaisesRegex(ValueError,'identity'):
            allocation_check(a,'spectre','changed','b')

    def test_raw_parser_error_retains_invalid_observation_state(self):
        from observations import read_native
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'broken.csv'
            path.write_text('time,out\n0,0\nnot-time,1\n')
            with self.assertRaises(ValueError):
                read_native(path,'evas')

    def test_owned_container_is_checked_after_success_and_failed_removal(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from runner import container_stage
        environment=SimpleNamespace(container=lambda *args: (['podman','run','image','tool'],'owned-fixture'),
                                    podman=lambda: ['podman'])
        base={'stage':'simulate','status':'completed','returncode':0,'timeout':False,'cleanup':{'complete':True}}
        a={'stage_timeout_s':90,'memory_limit_bytes':4*1024**3,'file_limit_bytes':32*1024**2,'threads':1}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('runner.stage',side_effect=[dict(base,cleanup={'complete':True}),base,{**base,'returncode':1}]) as fake:
                result=container_stage(environment,'image','tool',[],Path(tmp),'simulate',a)
                self.assertTrue(result['container_cleanup']['complete'])
                self.assertEqual(fake.call_args_list[-1].args[0],['podman','container','exists','owned-fixture'])
                self.assertIn('--ulimit=fsize=33554432:33554432',fake.call_args_list[0].args[0])
        with tempfile.TemporaryDirectory() as tmp:
            with patch('runner.stage',side_effect=[dict(base,cleanup={'complete':True}),{**base,'returncode':2},base]):
                result=container_stage(environment,'image','tool',[],Path(tmp),'simulate',a)
                self.assertEqual(result['status'],'cleanup_incomplete')
                self.assertTrue(stage_failure(result)['abort_batch'])
