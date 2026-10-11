"""Synthetic adapter fault calibration, not backend execution evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from precision_breadth_open_evidence import (PINS, INPUTS, qualify_open_backend, sha,
                                             waveform_complete, control_block)


class OpenEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.work = self.root / 'work'; self.work.mkdir()
        self.backend = 'openvaf_r_ngspice'; self.build()

    def save(self, name, value):
        (self.work / name).write_text(json.dumps(value))

    def build(self, backend=None, cap=1e-8):
        if backend: self.backend = backend
        pin = PINS[self.backend]
        for name in INPUTS: (self.work / name).write_text('{}')
        self.request = dict(stop_s=1e-6, maxstep_s=cap, reltol=1e-5, vabstol_V=1e-9, iabstol_A=1e-13)
        self.save('requested_settings.json', self.request)
        if self.backend == 'openvaf_r_ngspice':
            deck = f'''Paper fixture
Vu u 0 PWL(0 0 1e-6 1)
N0 u y model0
.model model0 probe
.options reltol=1e-5 vntol=1e-9 abstol=1e-13 method=trap trtol=7 chgtol=1e-14 itl4=10
.control
pre_osdi dut.osdi
set filetype=ascii
set wr_singlescale
set wr_vecnames
set numdgt=17
option
tran {cap} 1e-6 0 {cap}
wrdata waveform.txt v(u) v(y)
option
quit
.endc
.end
'''
            snapshot = '''* Current simulation options *
reltol (current) = 1e-05
vntol (voltage) = 1e-09
abstol (current) = 1e-13
Integration Method = TRAPEZOIDAL
trtol = 7.000000
chgtol (charge) = 1e-14
itl4 (transient iterations) = 10
'''
            log = snapshot + 'Doing analysis at TEMP = 27\nNo. of Data Rows : 2\n' + snapshot + 'ngspice-46 done\n'
            waveform = 'time v(u) v(y)\n0 0 0\n1e-6 1 1\n'
        else:
            deck = f'''load mgsim
load ./dut.so
verilog
\\probe dut(u,y);
spice
Vu u 0 PWL(0 0 1e-6 1)
.options numdgt=17 method=trap dtmin=1e-16 trtol=7 dtratio=1e9 short=1e-9 reltol=1e-5 vntol=1e-9 abstol=1e-13
.options
.print tran v(u) v(y) v(bench_ref)
.tran {cap} 1e-6 0 {cap} trace alltime > waveform.txt
.end
'''
            log = '.options reltol= 10.u vntol= 1.n abstol= 100.f method=trap dtmin= 100.E-18 trtol= 7. dtratio= 1.G\n'
            waveform = '#Time v(u) v(y) v(bench_ref)\n0 0 0 0\n1e-6 1 1 0\n'
        (self.work / pin['deck']).write_text(deck); (self.work / pin['compiled']).write_text('synthetic compiled fixture')
        (self.work / 'simulate.log').write_text(log); (self.work / 'waveform.txt').write_text(waveform)
        self.save('RESULT.json', {'status':'waveform_available','backend':self.backend,'label':self.work.name,'deck':pin['deck'],
                                  'waveform':'waveform.txt','waveform_sha256':sha(self.work/'waveform.txt'),
                                  'compiled_artifacts':{pin['compiled']:sha(self.work/pin['compiled'])}})
        argv = ['podman','run','--rm','--read-only','--pull=never','--network=none',pin['image'],pin['exe']]
        if self.backend == 'openvaf_r_ngspice': argv += ['-b']
        argv += [pin['deck']]
        self.execution = dict(argv=argv,status='completed',returncode=0,timeout=False,log_sha256=sha(self.work/'simulate.log'),container_cleanup={'complete':True})
        self.tool = {'images':{pin['image_key']:{'config_id':pin['image']}},'environment_sha256':'1'*64}
        for name in ['astra.txt','glm.txt','mechanism.txt']: (self.root/name).write_text('SYNTHETIC TEST ONLY ' + name)
        self.proof = {'schema':'open-backend-proof-v1','backend':self.backend,'image_id':pin['image'],'binary_hashes':pin['binaries'],
            'attachments':{n:sha(self.root/n) for n in ['astra.txt','glm.txt','mechanism.txt']},
            'reviews':{r:{'path':r+'.txt','sha256':sha(self.root/(r+'.txt'))} for r in ['astra','glm']},
            'environment_sha256':self.tool['environment_sha256'],
            'argv_sha256':[hashlib.sha256(json.dumps(argv,separators=(',',':')).encode()).hexdigest()],
            'claims':{'runtime':pin['mapping'],'native':'ngspice-noninterpolated-wrdata-v1' if self.backend=='openvaf_r_ngspice' else 'gnucap-converged-alltime-v1',
                      'startup':'closed','export':'closed','diagnostic_contract':'closed'}}
        self.refresh()

    def refresh(self):
        pin=PINS[self.backend]
        self.execution['log_sha256']=sha(self.work/'simulate.log')
        self.save('simulate-final.json',self.execution)
        self.save('INPUT_IDENTITY.json',{'source_sha256':sha(self.work/'dut.va'),'deck_sha256':sha(self.work/pin['deck']),
                                        'requested_settings_sha256':sha(self.work/'requested_settings.json')})
        self.frozen={n:sha(self.work/n) for n in (*INPUTS,pin['deck'])}
        self.raw={n:sha(self.work/n) for n in ['simulate-final.json','simulate.log','waveform.txt',pin['compiled'],'INPUT_IDENTITY.json','RESULT.json']}
        if 'run_scopes' not in self.proof:
            self.proof['run_scopes']=[{'argv_sha256':self.proof['argv_sha256'][0], 'frozen_manifest':dict(self.frozen),
                                       'compiled_sha256':self.raw[pin['compiled']]}]
        self.proofpath=self.root/'proof.json';self.proofpath.write_text(json.dumps(self.proof));self.approved=sha(self.proofpath)

    def run_adapter(self, **kwargs):
        args=dict(proof_path=self.proofpath,evidence_root=self.root,approved_proof_sha256=self.approved);args.update(kwargs)
        return qualify_open_backend(self.work,self.backend,self.tool,self.frozen,self.raw,**args)

    def mutate(self,name,old,new):
        p=self.work/name;p.write_text(p.read_text().replace(old,new))
        if name == 'waveform.txt':
            result=json.loads((self.work/'RESULT.json').read_text());result['waveform_sha256']=sha(p);self.save('RESULT.json',result)
        self.refresh()

    def test_ng_complete_reviewed_fixture(self):
        result=self.run_adapter();self.assertEqual(result['issues'],[])
        for axis in ['identity','config','runtime','native']: self.assertEqual(result[axis]['status'],'qualified')
        self.assertEqual(result['integrator']['status'],'unknown')

    def test_gn_complete_reviewed_fixture(self):
        self.build('gnucap_modelgen');self.assertEqual(self.run_adapter()['native']['status'],'qualified')

    def test_gn_quantized_cap_not_exact(self):
        self.build('gnucap_modelgen',cap=4.8828125e-10);r=self.run_adapter()
        self.assertEqual(r['runtime']['status'],'unknown');self.assertEqual(r['runtime']['mapped_effective']['maxstep_s'],4.882813e-10)
        self.assertEqual(r['native']['status'],'qualified')

    def test_gn_effective_dtmin_uses_dtratio(self):
        self.build('gnucap_modelgen');self.mutate('simulate.log','dtratio= 1.G','dtratio= 1.')
        r=self.run_adapter();self.assertEqual(r['runtime']['mapped_effective']['dtmin_s'],1e-8)
        self.assertEqual(r['config']['status'],'unknown');self.assertEqual(r['native']['status'],'unknown')

    def test_ng_extra_readback_override(self):
        self.mutate('simulate.log','trtol = 7.000000','trtol = 8.000000')
        self.assertEqual(self.run_adapter()['config']['status'],'unknown')

    def test_result_waveform_binding(self):
        result=json.loads((self.work/'RESULT.json').read_text());result['waveform_sha256']='0'*64
        self.save('RESULT.json',result);self.refresh();self.assertTrue(self.run_adapter()['issues'])

    def test_result_compiled_binding(self):
        result=json.loads((self.work/'RESULT.json').read_text());result['compiled_artifacts']={}
        self.save('RESULT.json',result);self.refresh();self.assertTrue(self.run_adapter()['issues'])

    def test_second_osdi_load_rejected(self):
        self.mutate('tb.cir','pre_osdi dut.osdi','pre_osdi dut.osdi\npre_osdi /work/other.osdi')
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_include_after_control_rejected(self):
        self.mutate('tb.cir','.endc\n.end','.endc\n.include /work/extra.cir\n.end')
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_gn_tran_continuation_rejected(self):
        self.build('gnucap_modelgen');self.mutate('tb.gc','trace alltime > waveform.txt','trace alltime > waveform.txt\n+ trace rejected')
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_missing_environment_both_sides(self):
        del self.tool['environment_sha256'];del self.proof['environment_sha256'];self.refresh()
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_new_dut_cannot_reuse_approved_scope(self):
        approved=self.approved
        (self.work/'dut.va').write_text('different but independently frozen source')
        (self.work/'dut.osdi').write_text('different compiled DUT')
        result=json.loads((self.work/'RESULT.json').read_text())
        result['compiled_artifacts']['dut.osdi']=sha(self.work/'dut.osdi');self.save('RESULT.json',result);self.refresh()
        self.assertEqual(self.approved,approved)
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')
        self.assertIn('outside reviewed per-run scope',' '.join(self.run_adapter()['issues']))

    def test_missing_run_scope(self):
        del self.proof['run_scopes']
        # Deliberately do not call refresh, which supplies a synthetic test scope.
        self.proofpath.write_text(json.dumps(self.proof));self.approved=sha(self.proofpath)
        self.assertEqual(self.run_adapter()['runtime']['status'],'unknown')

    def test_gn_numeric_pwl_continuation_allowed(self):
        self.build('gnucap_modelgen')
        self.mutate('tb.gc','PWL(0 0 1e-6 1)','PWL(0 0\n+ 1e-6 1)')
        # Approval updated for the legitimate new frozen source representation.
        self.proof['run_scopes'][0]['frozen_manifest']=dict(self.frozen);self.refresh()
        self.assertEqual(self.run_adapter()['native']['status'],'qualified')

    def test_gn_continuation_cannot_inject_command_in_pwl(self):
        self.build('gnucap_modelgen');self.mutate('tb.gc','PWL(0 0 1e-6 1)','PWL(0 0\n+ trace rejected)')
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_gn_continuation_after_closed_source_rejected(self):
        self.build('gnucap_modelgen');self.mutate('tb.gc','PWL(0 0 1e-6 1)','PWL(0 0 1e-6 1)\n+ trace rejected')
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_ng_unknown_device_line_rejected(self):
        self.mutate('tb.cir','N0 u y model0','Xexternal u y foreign\nN0 u y model0')
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_malformed_environment_both_sides(self):
        self.tool['environment_sha256']='not-a-sha';self.proof['environment_sha256']='not-a-sha';self.refresh()
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def assert_malformed_unknown(self, result):
        for axis in ('identity','config','runtime','native','integrator','diagnostics','observations'):
            self.assertEqual(result[axis]['status'],'unknown')
        self.assertTrue(result['issues'])

    def test_result_json_list_fail_closed(self):
        self.save('RESULT.json',[]);self.raw['RESULT.json']=sha(self.work/'RESULT.json')
        self.assert_malformed_unknown(self.run_adapter())

    def test_execution_json_list_fail_closed(self):
        self.save('simulate-final.json',[]);self.raw['simulate-final.json']=sha(self.work/'simulate-final.json')
        self.assert_malformed_unknown(self.run_adapter())

    def test_proof_json_list_fail_closed(self):
        self.proofpath.write_text('[]');self.approved=sha(self.proofpath)
        self.assert_malformed_unknown(self.run_adapter())

    def test_reviews_same_path_rejected(self):
        self.proof['reviews']['glm']=dict(self.proof['reviews']['astra']);self.refresh()
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_reviews_same_digest_rejected(self):
        # Two different paths with identical content still are one report.
        (self.root/'glm.txt').write_text((self.root/'astra.txt').read_text())
        digest=sha(self.root/'glm.txt');self.proof['attachments']['glm.txt']=digest
        self.proof['reviews']['glm']['sha256']=digest;self.refresh()
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')

    def test_other_root_json_types_fail_closed(self):
        for name in ('RESULT.json','simulate-final.json','INPUT_IDENTITY.json','requested_settings.json'):
            original=(self.work/name).read_text()
            for value in (None, 'unexpected', False):
                with self.subTest(name=name,value=value):
                    self.save(name,value)
                    if name in self.raw:self.raw[name]=sha(self.work/name)
                    if name in self.frozen:self.frozen[name]=sha(self.work/name)
                    self.assert_malformed_unknown(self.run_adapter())
            (self.work/name).write_text(original)
            if name in self.raw:self.raw[name]=sha(self.work/name)
            if name in self.frozen:self.frozen[name]=sha(self.work/name)

    def test_nested_cleanup_schema_fail_closed(self):
        self.execution['container_cleanup']=[];self.refresh()
        self.assert_malformed_unknown(self.run_adapter())

    def test_nested_tool_schema_fail_closed(self):
        self.tool['images']=[];self.assert_malformed_unknown(self.run_adapter())

    def test_proof_claims_schema_fail_closed(self):
        self.proof['claims']=[];self.refresh();self.assert_malformed_unknown(self.run_adapter())

    def test_proof_argv_digest_schema_fail_closed(self):
        original=list(self.proof['argv_sha256'])
        for value in (original[0], {original[0]: True}, None, 123, [], ['bad'], [None], ['A'*64]):
            with self.subTest(value=value):
                self.proof['argv_sha256']=value;self.refresh()
                self.assert_malformed_unknown(self.run_adapter())
        self.proof['argv_sha256']=original;self.refresh()
        self.assertEqual(self.run_adapter()['native']['status'],'qualified')

    def test_default_axes_present(self):
        result=self.run_adapter(approved_proof_sha256=None)
        for axis in ('identity','config','runtime','native','integrator','diagnostics','observations'):
            self.assertIn(axis,result)

    def test_invalid_proof_json_fail_closed(self):
        self.proofpath.write_text('{invalid-json');self.approved=sha(self.proofpath)
        self.assert_malformed_unknown(self.run_adapter())

    def test_no_approval(self): self.assertEqual(self.run_adapter(approved_proof_sha256=None)['runtime']['status'],'unknown')
    def test_wrong_approved_digest(self): self.assertTrue(self.run_adapter(approved_proof_sha256='0'*64)['issues'])
    def test_one_review_missing(self):
        del self.proof['reviews']['glm'];self.refresh();self.assertTrue(self.run_adapter()['issues'])
    def test_review_attachment_changed(self):
        (self.root/'astra.txt').write_text('changed');self.assertTrue(self.run_adapter()['issues'])
    def test_wrong_binary(self):
        self.proof['binary_hashes']={};self.refresh();self.assertTrue(self.run_adapter()['issues'])
    def test_wrong_tool_image(self):
        self.tool['images']['ngspice']['config_id']='wrong';self.assertEqual(self.run_adapter()['identity']['status'],'unknown')
    def test_raw_waveform_changed(self):
        (self.work/'waveform.txt').write_text('changed');self.assertTrue(self.run_adapter()['issues'])
    def test_source_changed(self):
        (self.work/'dut.va').write_text('changed');self.assertTrue(self.run_adapter()['issues'])
    def test_missing_manifest_digest(self):
        del self.raw['dut.osdi'];self.assertTrue(self.run_adapter()['issues'])
    def test_exit_zero_transient_failure(self):
        self.mutate('simulate.log','ngspice-46 done','Error: Transient op failed, timestep too small\nngspice-46 done')
        self.assertEqual(self.run_adapter()['native']['status'],'unknown')
    def test_no_startup_proof(self):
        del self.proof['claims']['startup'];self.refresh();r=self.run_adapter()
        self.assertEqual(r['runtime']['status'],'qualified');self.assertEqual(r['native']['status'],'unknown')
    def test_full_argv_not_approved(self):
        self.execution['argv'].insert(2,'--env=SPICE_LIB_DIR=/evil');self.refresh();self.assertTrue(self.run_adapter()['issues'])
    def test_cleanup_incomplete(self):
        self.execution['container_cleanup']['complete']=False;self.refresh();self.assertTrue(self.run_adapter()['issues'])
    def test_compile_failed_cannot_qualify(self):
        self.save('RESULT.json',{'status':'compile_failed'});self.refresh();self.assertTrue(self.run_adapter()['issues'])
    def test_ng_linearize(self):
        self.mutate('tb.cir','wrdata waveform','linearize\nwrdata waveform');self.assertTrue(self.run_adapter()['issues'])
    def test_ng_interp(self):
        self.mutate('tb.cir','set numdgt=17','set numdgt=17\nset interp');self.assertTrue(self.run_adapter()['issues'])
    def test_ng_zero_tmax(self):
        self.mutate('tb.cir','tran 1e-08 1e-6 0 1e-08','tran 1e-08 1e-6 0 0');self.assertTrue(self.run_adapter()['issues'])
    def test_gn_rejected_trace(self):
        self.build('gnucap_modelgen');self.mutate('tb.gc','trace alltime','trace rejected');self.assertTrue(self.run_adapter()['issues'])
    def test_gn_initial_failed(self):
        self.build('gnucap_modelgen');self.mutate('simulate.log','.options','did not converge\n.options');self.assertTrue(self.run_adapter()['issues'])
    def test_gn_quitconvfail(self):
        self.build('gnucap_modelgen');self.mutate('simulate.log','.options','convergence failure, giving up\n.options');self.assertTrue(self.run_adapter()['issues'])
    def test_gn_unknown_option(self):
        self.build('gnucap_modelgen');self.mutate('tb.gc','short=1e-9','short=1e-9 quitconvfail');self.assertTrue(self.run_adapter()['issues'])
    def test_unknown_warning(self):
        self.mutate('simulate.log','ngspice-46 done','Warning: unexplained\nngspice-46 done');self.assertEqual(self.run_adapter()['native']['status'],'unknown')
    def test_plot_count_mismatch(self):
        self.mutate('simulate.log','Data Rows : 2','Data Rows : 3');self.assertEqual(self.run_adapter()['native']['status'],'unknown')
    def test_early_stop(self):
        self.mutate('waveform.txt','1e-6 1 1','9e-7 1 1');self.assertEqual(self.run_adapter()['native']['status'],'unknown')
    def test_extra_tail_row(self):
        self.mutate('waveform.txt','1e-6 1 1','1e-6 1 1\n1.0000001e-6 1 1');self.assertEqual(self.run_adapter()['native']['status'],'unknown')
    def test_unrecognized_row_not_filtered(self):
        self.mutate('waveform.txt','1e-6 1 1','garbage');self.assertEqual(self.run_adapter()['native']['status'],'unknown')


if __name__ == '__main__': unittest.main()
