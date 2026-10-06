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

    def test_container_allocation_cannot_claim_less_than_factory_memory(self):
        a={'backend':'gnucap_modelgen','input_manifest_sha256':'a','tool_profile_sha256':'b',
           'max_simulation_launches':12,'max_compilation_launches':12,'stage_timeout_s':90,
           'license_timeout_s':30,'memory_limit_bytes':1024**3,'file_limit_bytes':32*1024**2,'threads':1}
        with self.assertRaisesRegex(ValueError,'fixed 4GiB'):
            allocation_check(a,'gnucap_modelgen','a','b')

    def test_container_manifest_and_package_cannot_drift_together(self):
        import json
        from types import SimpleNamespace
        from runner import verify_tool
        from inputs import sha
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp); package=directory/'package'; package.mkdir()
            (directory/'environment.py').write_text('# pinned fixture\n')
            artifact=package/'fixture'; artifact.write_text('original')
            manifest=directory/'INPUT_MANIFEST.json'
            manifest.write_text(json.dumps({'fixture':sha(artifact)}))
            tool={'environment_sha256':sha(directory/'environment.py'),'environment_manifest_sha256':sha(manifest)}
            profile={'backend':'gnucap_modelgen','environment':str(directory)}
            verify_tool(tool,profile,SimpleNamespace(PACKAGE=package))
            artifact.write_text('changed')
            manifest.write_text(json.dumps({'fixture':sha(artifact)}))
            with self.assertRaisesRegex(ValueError,'manifest changed'):
                verify_tool(tool,profile,SimpleNamespace(PACKAGE=package))

    def test_request_echo_cannot_be_effective_evas_readback(self):
        import json
        from runner import effective_settings
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            (work/'requested_settings.json').write_text(json.dumps({'reltol':1e-5,'vabstol_V':1e-7,
                 'iabstol_A':1e-12,'stop_s':6e-6,'maxstep_s':2e-10}))
            (work/'effective.json').write_text(json.dumps({'reltol':1e-5,'vabstol':1e-7,
                 'stop':6e-6,'maxstep':2e-10,'engine':'fixture','accepted_steps':12}))
            result=effective_settings(work,'evas')
            self.assertEqual(result['status'],'I')
            self.assertEqual(result['actual']['maxstep'],'unknown')
            self.assertEqual(result['request_echo']['maxstep'],2e-10)
            self.assertEqual(result['observed_response']['engine'],'fixture')

    def test_drift_after_first_case_preserves_complete_lane_receipt(self):
        import json
        from unittest.mock import patch
        from types import SimpleNamespace
        from inputs import sha
        from runner import run
        for failure_function,phase in [('verify_sources','source_identity'),('verify_tool','tool_identity')]:
            with self.subTest(failure_function=failure_function), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); inputs=root/'inputs'; inputs.mkdir(); output=root/'output'
                (inputs/'INPUT_MANIFEST.json').write_text('{}')
                (inputs/'core.json').write_text(json.dumps({'units':{'T_s':1e-6},'shared_contract':{
                    'sample_gap_s':2e-10,'input_error_V':1e-5,'required_observation_error':{'time_s':1e-11,'voltage_V':5e-5}}}))
                plan=[]
                for i in range(12):
                    name=f'fixture-{i}'; work=inputs/name; work.mkdir()
                    (work/'dut.va').write_text('fixture source')
                    (work/'request.json').write_text('{}')
                    (work/'condition.json').write_text(json.dumps({'id':name,'observables':['out'],'stop_T':1,'observation_windows':[]}))
                    (work/'requested_settings.json').write_text(json.dumps({'reltol':1e-5,'vabstol_V':1e-7,'iabstol_A':1e-12,'stop_s':1e-6,'maxstep_s':2e-10}))
                    plan.append({'backend':'evas','condition':name,'work':name,'deck':'request.json'})
                profile=root/'profile.json'; profile.write_text('{"backend":"evas"}')
                allocation=root/'allocation.json'; allocation.write_text(json.dumps({'backend':'evas',
                    'input_manifest_sha256':sha(inputs/'INPUT_MANIFEST.json'),'tool_profile_sha256':sha(profile),
                    'selected_condition_ids':[f'fixture-{i}' for i in range(12)],
                    'max_simulation_launches':12,'max_compilation_launches':12,'stage_timeout_s':90,'license_timeout_s':30,
                    'memory_limit_bytes':4*1024**3,'file_limit_bytes':32*1024**2,'threads':1}))
                def fixture_stage(argv,work,name,a):
                    (work/'waveform.csv').write_text('time,out\n0,0\n1e-6,1\n')
                    (work/'worker-result.json').write_text('{"status":"waveform_available"}')
                    (work/'effective.json').write_text('{"engine":"fixture"}')
                    return {'stage':name,'status':'completed','returncode':0,'timeout':False,'cleanup':{'complete':True}}
                source_checks=[None,None,ValueError('source drift')] if failure_function=='verify_sources' else [None]*3
                tool_checks=[None,ValueError('tool drift')] if failure_function=='verify_tool' else [None]*2
                args=SimpleNamespace(inputs=inputs,output=output,backend='evas',tool_profile=profile,allocation=allocation)
                with patch('runner.verify',return_value=plan),patch('runner.preflight',return_value=({'kernel':'fixture'},None)),\
                     patch('runner.verify_sources',side_effect=source_checks),patch('runner.verify_tool',side_effect=tool_checks),\
                     patch('runner.stage',side_effect=fixture_stage):
                    with self.assertRaises(ValueError):
                        run(args)
                self.assertTrue((output/'EXECUTION.json').is_file())
                records=json.loads((output/'EXECUTION.json').read_text())
                self.assertEqual(len(records),12)
                self.assertEqual(records[0]['status'],'waveform_available')
                self.assertEqual(sum(r['status']=='not_run' for r in records),11)
                abort=json.loads((output/'BATCH_ABORTED.json').read_text())
                self.assertEqual(abort['failure_stage'],phase)
                self.assertEqual(len(abort['unrun']),11)
                self.assertTrue((output/'FILE_MANIFEST.json').is_file())

    def test_selected_plan_is_checked_against_actual_allocation_before_preflight(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from runner import run
        a={'backend':'spectre','input_manifest_sha256':'digest','tool_profile_sha256':'digest',
           'max_simulation_launches':12,'max_compilation_launches':12,'stage_timeout_s':90,
           'license_timeout_s':30,'memory_limit_bytes':4*1024**3,'file_limit_bytes':32*1024**2,'threads':1}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args=SimpleNamespace(inputs=root/'inputs',output=root/'output',backend='spectre',tool_profile=root/'profile',allocation=root/'allocation')
            plan=[{'backend':'spectre','condition':str(i)} for i in range(13)]
            with patch('runner.verify',return_value=plan),patch('runner.verify_sources'),patch('runner.sha',return_value='digest'),patch('runner.load',side_effect=[{},a]),patch('runner.preflight') as probe:
                with self.assertRaisesRegex(ValueError,'twelve distinct'):
                    run(args)
                probe.assert_not_called()
                self.assertFalse(args.output.exists())

    def test_subset_selection_requires_known_distinct_ids_and_matching_grants(self):
        import runner
        plan=[{'backend':'evas','condition':str(i)} for i in range(12)]
        a={'selected_condition_ids':['1','8'],'max_simulation_launches':2,'max_compilation_launches':2}
        chosen=runner.select_conditions(plan,a,'evas')
        self.assertEqual([r['condition'] for r in chosen],['1','8'])
        for ids in ([],['1','1'],['unknown'],[True]):
            with self.assertRaises(ValueError):
                runner.select_conditions(plan,{**a,'selected_condition_ids':ids},'evas')
        with self.assertRaises(ValueError):
            runner.select_conditions(plan,{**a,'max_simulation_launches':12},'evas')

    def test_terminal_directory_budget_is_actual_and_excess_is_explicit(self):
        import runner
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp); (work/'raw').write_bytes(b'a'*11)
            result=runner.directory_budget(work,limit=10)
            self.assertEqual(result['actual_bytes'],11)
            self.assertEqual(result['status'],'condition_directory_limit_exceeded')
            self.assertFalse(result['runtime_hard_quota'])

    def test_two_selected_conditions_keep_twelve_records_without_launching_others(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import patch
        from runner import run
        from inputs import sha
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs=root/'inputs';inputs.mkdir()
            (inputs/'INPUT_MANIFEST.json').write_text('{}')
            (inputs/'core.json').write_text(json.dumps({'units':{'T_s':1e-6},'shared_contract':{'sample_gap_s':2e-10,'input_error_V':1e-5,'required_observation_error':{'time_s':1e-11,'voltage_V':5e-5}}}))
            plan=[]
            for i in range(12):
                name=f'fixture-{i}';work=inputs/name;work.mkdir()
                (work/'dut.va').write_text('fixture');(work/'request.json').write_text('{}')
                (work/'condition.json').write_text(json.dumps({'id':name,'observables':['out'],'stop_T':1,'observation_windows':[]}))
                plan.append({'backend':'evas','condition':name,'work':name,'deck':'request.json'})
            profile=root/'profile';profile.write_text('{"backend":"evas"}')
            allocation=root/'allocation';allocation.write_text(json.dumps({'backend':'evas',
                'input_manifest_sha256':sha(inputs/'INPUT_MANIFEST.json'),'tool_profile_sha256':sha(profile),
                'selected_condition_ids':['fixture-1','fixture-8'],'max_simulation_launches':2,'max_compilation_launches':2,
                'stage_timeout_s':90,'license_timeout_s':30,'memory_limit_bytes':4*1024**3,'file_limit_bytes':32*1024**2,'threads':1}))
            launched=[]
            def stage(argv,work,name,a):
                launched.append(work.name)
                return {'stage':name,'status':'completed','returncode':2,'timeout':False,'cleanup':{'complete':True}}
            args=SimpleNamespace(inputs=inputs,output=root/'output',backend='evas',tool_profile=profile,allocation=allocation)
            with patch('runner.verify',return_value=plan),patch('runner.verify_sources'),patch('runner.verify_tool'),patch('runner.preflight',return_value=({'kernel':'fixture'},None)),patch('runner.stage',side_effect=stage):
                run(args)
            records=json.loads((args.output/'EXECUTION.json').read_text())
            self.assertEqual(launched,['fixture-1','fixture-8'])
            self.assertEqual(len(records),12)
            self.assertEqual(sum(r.get('reason')=='not_selected_in_allocation' for r in records),10)
            for record in records:
                final=json.loads((args.output/('final-record-'+record['condition']+'.json')).read_text())
                self.assertEqual(final,record)
                manifest=json.loads((args.output/'FILE_MANIFEST.json').read_text())
                self.assertEqual(manifest['final-record-'+record['condition']+'.json']['sha256'],sha(args.output/('final-record-'+record['condition']+'.json')))
            self.assertEqual(len(json.loads((args.output/'DIRECTORY_BUDGETS.json').read_text())),2)
            from runner import directory_budget
            def successful_stage(argv,work,name,a):
                (work/'waveform.csv').write_text('time,out\n0,0\n1e-6,1\n')
                (work/'worker-result.json').write_text('{"status":"waveform_available"}')
                return {'stage':name,'status':'completed','returncode':0,'timeout':False,'cleanup':{'complete':True}}
            args.output=root/'overbudget-output'
            with patch('runner.verify',return_value=plan),patch('runner.verify_sources'),patch('runner.verify_tool'),patch('runner.preflight',return_value=({'kernel':'fixture'},None)),patch('runner.stage',side_effect=successful_stage),patch('runner.directory_budget',side_effect=lambda w:directory_budget(w,limit=1)):
                run(args)
            excess=json.loads((args.output/'EXECUTION.json').read_text())
            failures=[r for r in excess if r['status']=='condition_directory_limit_exceeded']
            self.assertEqual(len(failures),2)
            self.assertTrue(all(r['execution_status_before_budget']=='waveform_available' for r in failures))
            self.assertTrue(all(r['directory_budget']['actual_bytes']>1 for r in failures))
            for record in excess:
                self.assertEqual(json.loads((args.output/('final-record-'+record['condition']+'.json')).read_text()),record)
            for record in failures:
                snapshot=json.loads((args.output/'runs'/record['condition']/'RESULT.json').read_text())
                self.assertEqual(snapshot['status'],'waveform_available')
                self.assertNotIn('directory_budget',snapshot)
            args.output=root/'preflight-failed-output'
            with patch('runner.verify',return_value=plan),patch('runner.verify_sources'),patch('runner.preflight',side_effect=RuntimeError('fixture preflight failure')):
                with self.assertRaises(RuntimeError): run(args)
            self.assertEqual(json.loads((args.output/'DIRECTORY_BUDGETS.json').read_text()),{})
            final_rows=json.loads((args.output/'EXECUTION.json').read_text())
            self.assertEqual(len(final_rows),12)
            self.assertTrue(all(r['status']=='not_run' for r in final_rows))
            for record in final_rows:
                self.assertEqual(json.loads((args.output/('final-record-'+record['condition']+'.json')).read_text()),record)
            with self.assertRaises(FileExistsError):
                with patch('runner.verify',return_value=plan),patch('runner.verify_sources'):
                    run(args)

            args.output=root/'abort-selected-output'
            def failed_stage(argv,work,name,a):
                return {'stage':name,'status':'cleanup_incomplete','returncode':2,'timeout':False,'cleanup':{'complete':False}}
            with patch('runner.verify',return_value=plan),patch('runner.verify_sources'),patch('runner.verify_tool'),patch('runner.preflight',return_value=({'kernel':'fixture'},None)),patch('runner.stage',side_effect=failed_stage):
                run(args)
            abort=json.loads((args.output/'BATCH_ABORTED.json').read_text())
            self.assertEqual(abort['unrun'],['fixture-8'])
            self.assertEqual(len(abort['not_selected_in_allocation']),10)

    def test_gnucap_parser_errors_override_existing_waveform_and_zero_exit(self):
        done={'stage':'simulate','status':'completed','returncode':0,'timeout':False,'cleanup':{'complete':True}}
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);(work/'waveform.txt').write_text('raw retained fixture')
            for diagnostic in ('need )',"what's this?",'1: no match'):
                (work/'simulate.log').write_text('Vpaper_observer ... truncated\n    ^ ? '+diagnostic+'\n')
                state=result_state([done],work,'waveform.txt',backend='gnucap_modelgen')
                self.assertEqual(state['status'],'deck_parse_error')
                self.assertEqual(state['failure_stage'],'deck_parse')
                self.assertFalse(state['abort_batch'])
                self.assertEqual(state['rejected_waveform']['path'],'waveform.txt')
                self.assertEqual((work/'waveform.txt').read_text(),'raw retained fixture')
                self.assertIn(diagnostic,state['diagnostics'][0]['text'])
            (work/'simulate.log').write_text('param: already installed, replacing\n.options reltol=10.u\n')
            self.assertEqual(result_state([done],work,'waveform.txt',backend='gnucap_modelgen')['status'],'waveform_available')
            (work/'simulate.log').write_text('^ ? need )\n')
            self.assertEqual(result_state([done],work,'waveform.txt',backend='spectre')['status'],'waveform_available')
