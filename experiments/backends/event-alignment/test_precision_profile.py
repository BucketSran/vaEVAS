"""Calibration of the frozen reference workflow's public evidence boundary."""
import copy
import tempfile
import unittest
from pathlib import Path
import precision_profile as precision


class PrecisionProfileTests(unittest.TestCase):
    def fixture(self):
        case = {'id':'control', 'stop':1., 'times':[0., 1.], 'inputs':{},
                'voltage_nodes':['y','n'], 'criteria':{'expected_final_counts':{'n':1}},
                'module':'probe','ports':['y','n','r'],'ground_port':'r',
                'settings':{'strobeoutput':'all','save_all_named_outputs':True}}
        ladder = {'version':1,'id':'calibration','method':'traponly','acceptance_pair':['tight','tighter'],'levels':[
            {'id':name,'reltol':tol,'vabstol':tol/100,'iabstol':tol/10000,'maxstep':.1}
            for name,tol in [('base',1e-8),('tight',1e-9),('tighter',1e-10)]]}
        contract = {'stop':1.,'required_times':[0.,1.], 'budgets_v':{'y':1e-6,'n':0.},'phase_nodes':['n']}
        frozen = precision.freeze(case,b'module probe; endmodule\n',ladder,contract,{'declaration':'zero DC initialization'})
        records = []
        for level in frozen['ladder']['levels']:
            records.append({'profile_id':level['id'],'frozen_sha256':precision.digest(frozen),
                            'settings_status':'P','execution_status':'success','spectre_version':'21.1',
                            'rows':[{'time':0.,'voltages':{'y':0.,'n':0.}},
                                    {'time':1.,'voltages':{'y':1.,'n':1.}}]})
        return frozen,records

    def test_finite_stability_retains_every_level_and_does_not_claim_proof(self):
        frozen, records = self.fixture()
        result = precision.analyze(frozen,records)
        self.assertEqual(result['classification'],'finite_reference_stability')
        self.assertEqual(len(result['profiles']),3)
        self.assertEqual(result['formal_qualification'],'I')

    def test_event_count_missing_is_gap_not_instability(self):
        frozen, records = self.fixture()
        del records[1]['rows'][1]['voltages']['n']
        self.assertEqual(precision.analyze(frozen,records)['classification'],'incomplete')

    def test_real_event_count_change_is_unstable_even_with_voltage_agreement(self):
        frozen, records = self.fixture()
        records[1]['rows'][1]['voltages']['n'] = 2.
        self.assertEqual(precision.analyze(frozen,records)['classification'],'event_count_unstable')

    def test_missing_observation_and_missing_profile_cannot_be_selected_away(self):
        frozen, records = self.fixture()
        records[1]['rows'].pop()
        self.assertEqual(precision.analyze(frozen,records)['classification'],'incomplete')
        with self.assertRaises(ValueError):
            precision.analyze(frozen,records[1:])

    def test_budget_source_and_requested_setting_changes_have_new_identity(self):
        frozen, records = self.fixture()
        for change in ['model_sha256','contract','ladder']:
            modified=copy.deepcopy(frozen)
            if change=='model_sha256': modified[change]='0'*64
            elif change=='contract': modified[change]['budgets_v']['y']=2e-6
            else: modified[change]['levels'][0]['reltol']=2e-8
            with self.assertRaises(ValueError):
                precision.analyze(modified,records)

    def test_wrong_effective_setting_cannot_be_stable(self):
        frozen, records = self.fixture()
        records[1]['settings_status']='I'
        self.assertEqual(precision.analyze(frozen,records)['classification'],'incomplete')

    def test_predeclared_tail_acceptance_retains_baseline_failure(self):
        frozen, records = self.fixture()
        records[0]['rows'][1]['voltages']['y']=1.00001
        result=precision.analyze(frozen,records)
        self.assertEqual(result['classification'],'finite_reference_stability')
        self.assertEqual(result['pairs'][0]['comparison']['finite_pair_status'],'F')

    def test_actual_readback_and_byte_identity_are_required(self):
        frozen, _ = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            level=frozen['ladder']['levels'][0]
            (root/'dut.va').write_bytes(b'module probe; endmodule\n')
            (root/'tb.scs').write_text(precision.deck(frozen['case'],level))
            log = "21.1\nGlobal user options:\n reltol = 1e-8\n vabstol = 1e-10\n iabstol = 1e-12\n\nTransient Analysis `tran': time = (0 s -> 1 s)\nImportant parameter values:\n reltol = 1e-8\n abstol(V) = 1e-10\n abstol(I) = 1e-12\n maxstep = 0.1 s\n stop = 1 s\n method = traponly\n\n"
            psf = 'HEADER\n"analysis name" "tran"\n"analysis type" "tran"\n"reltol" 1e-8\n"abstol(V)" 1e-10\n"abstol(I)" 1e-12\n"maxstep" 0.1\n"stop" 1\n"method" "traponly"\n"tolerance.relative" 1e-8\nTYPE\nVALUE\n"time" 0\n"y" 0\n"n" 0\n"time" 1\n"y" 1\n"n" 1\nEND\n'
            (root/'spectre.log').write_text(log)
            (root/'tran.psf').write_text(psf)
            def attest():
                return precision.attest(frozen,'base',root,root/'tran.psf',root/'spectre.log','21.1','success')
            self.assertEqual(attest()['settings_status'],'P')
            (root/'spectre.log').write_text(log.replace('reltol = 1e-8','reltol = 2e-8'))
            (root/'tran.psf').write_text(psf.replace('"y" 1\n','"y" 1.00001\n'))
            record=attest()
            self.assertEqual(record['settings_status'],'I')
            self.assertEqual(len(record['rows']),2)
            frozen, records=self.fixture()
            records[1].update(rows=record['rows'],settings_status=record['settings_status'])
            result=precision.analyze(frozen,records)
            self.assertEqual(result['acceptance_pair']['comparison']['finite_pair_status'],'F')
            self.assertEqual(result['finite_reference_stability_status'],'I')
            (root/'dut.va').write_text('different model')
            with self.assertRaises(ValueError): attest()

    def test_counter_coverage_does_not_depend_on_phase_annotation(self):
        frozen, records = self.fixture()
        frozen['contract']['phase_nodes']=[]
        for record in records: record['frozen_sha256']=precision.digest(frozen)
        self.assertEqual(precision.analyze(frozen,records)['event_count_status'],'finite_stable')

    def test_invalid_native_observation_is_not_hidden_by_fixed_grid_filter(self):
        frozen, records = self.fixture()
        records[1]['rows'].append({'time':2.,'voltages':{'y':1.,'n':1.}})
        self.assertEqual(precision.analyze(frozen,records)['classification'],'incomplete')

    def test_target_failure_is_not_hidden_by_baseline_or_tail_selection(self):
        frozen, records = self.fixture()
        records[1]['rows'][1]['voltages']['y']=1.00001
        self.assertEqual(precision.analyze(frozen,records)['classification'],'not_converged')

    def test_malformed_acceptance_pair_is_rejected_before_preparation(self):
        frozen, records = self.fixture()
        for pair in [None,[],['tight'],['tight','tight'],['tighter','tight'],['tight','unknown']]:
            modified=copy.deepcopy(frozen)
            modified['ladder']['acceptance_pair']=pair
            for record in records: record['frozen_sha256']=precision.digest(modified)
            with self.assertRaises(ValueError): precision.analyze(modified,records)
        modified=copy.deepcopy(frozen)
        del modified['ladder']['acceptance_pair']
        with self.assertRaises(ValueError): precision.analyze(modified,records)

    def test_missing_confirmation_cannot_be_selected_away(self):
        frozen, records = self.fixture()
        records[2]['rows'].pop()
        self.assertEqual(precision.analyze(frozen,records)['classification'],'incomplete')

    def test_empty_or_whitespace_backend_version_cannot_attest_or_qualify(self):
        frozen, records = self.fixture()
        for version in ['', '   ', '\t']:
            for record in records: record['spectre_version']=version
            result=precision.analyze(frozen,records)
            self.assertEqual(result['classification'],'incomplete')
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    precision.attest(frozen,'base',Path(directory),Path(directory)/'psf',Path(directory)/'log',version,'success')


if __name__ == '__main__':
    unittest.main()
