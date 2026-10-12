"""Negative controls for uncertain budgets and engineering qualification."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
from test_precision import CARDS, BUDGETS, sample_rows
from precision_checker import assess
from precision_report import qualification, report, sha, BACKENDS


def put(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))


def finalized_abort_batch(base):
    """Synthetic finalized lanes model an abort before the first case."""
    frozen=base/'inputs'
    cards=[{'id':f+'-case','family':f} for f in ('sample_hold','first_order')]
    put(frozen/'cards.json',{'cards':cards,'profiles':[{'id':'base'}],'budgets':BUDGETS})
    deps=('evas/validation/paper/precision_checker.py','experiments/backends/paper/inputs.py','experiments/backends/paper/observations.py','experiments/backends/paper/settings_readback.py',
          'experiments/archive/dvs2-starter-pilot/analyze.py','experiments/archive/dvs2-starter-pilot/suite.py')
    put(frozen/'SOURCE_IDENTITY.json',{p:sha(ROOT/p) for p in deps})
    put(frozen/'MANIFEST.json',{p.name:sha(p) for p in frozen.iterdir()})
    put(base/'SOURCE_PROVENANCE.json',{'fixture':True})
    for card in cards:
        for backend in BACKENDS:
            lane=card['family']+'-'+backend;col=base/'collected'/lane;out=col/'outputs'/lane
            put(out/'TOOL_IDENTITY.json',{'fixture':True})
            put(out/'EXECUTION.json',[{'condition':card['id'],'family':card['family'],'profile':'base',
                 'backend':backend,'label':card['id']+'--base','status':'not_run','reason':'synthetic abort'}])
            put(out/'FILE_MANIFEST.json',{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.iterdir()})
            (col/'raw.tar.gz').write_bytes(b'synthetic archive fixture')
            put(col/'COLLECTION.json',{'archive_sha256':sha(col/'raw.tar.gz')})
            put(col/'operator-receipts'/(lane+'.json'),{'status':'complete','cleanup_confirmed':True,'child_exit_code':0,'exit_code':0})
            if backend=='evas':put(col/'build/BUILD.json',{k:'fixture' for k in ('source_revision','source_manifest_sha256','kernel_sha256','cargo_lock_sha256','toolchain','returncode')})


class ReportingChecks(unittest.TestCase):
    def test_initial_budget_overlap_is_not_confirmed_error(self):
        c=CARDS['SH-T-RAMP'];rows=sample_rows(c)
        budget=BUDGETS['absolute_V']+BUDGETS['relative']*c['scale_V']
        for r in rows:
            if r['count']==0:r['y']+=budget-1e-16
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'evidence_insufficient')

    def test_hold_budget_overlap_is_not_confirmed_error(self):
        c=CARDS['SH-T-LONG'];rows=sample_rows(c)
        budget=BUDGETS['absolute_V']+BUDGETS['relative']*c['scale_V']
        group=[r for r in rows if r['count']==2]
        group[0]['y']-=.5*(budget-1e-16);group[-1]['y']+=.5*(budget-1e-16)
        self.assertEqual(assess(c,rows,BUDGETS)['status'],'evidence_insufficient')

    def test_missing_method_and_ground_never_qualify(self):
        record={'effective_settings':{'actual':{'reltol':1e-5,'vabstol':1e-9,'iabstol':1e-13},'requested':{},'mismatches':[]}}
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);(work/'simulate.log').write_text('.options reltol= 10.u\n')
            q=qualification(work,'gnucap_modelgen',record,[{'time':0.,'bench_ref':0.}])
            self.assertEqual(q['status'],'evidence_insufficient')
            (work/'simulate.log').write_text('.options method=trap\n')
            for row in ({'time':0.},{'time':0.,'bench_ref':float('nan')},{'time':0.,'bench_ref':1.}):
                self.assertEqual(qualification(work,'gnucap_modelgen',record,[row])['status'],'evidence_insufficient')
            self.assertEqual(qualification(work,'gnucap_modelgen',record,[{'bench_ref':0.}])['status'],'qualified')

    def test_aborted_batch_keeps_unrun_denominator_without_case_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);finalized_abort_batch(base);frozen=base/'inputs'
            result=report(base)
            self.assertIn('experiments/backends/paper/settings_readback.py',result['analysis_dependencies'])
            self.assertEqual(len(result['results']),8)
            self.assertTrue(all(r['status']=='not_run' for r in result['results']))
            self.assertTrue(all(v['passed']==0 and v['total']==1 for f in result['summary'].values() for v in f.values()))
            # The frozen runner already pins the settings reader; drift must abort
            # default reanalysis rather than silently change old qualification.
            source=json.loads((frozen/'SOURCE_IDENTITY.json').read_text())
            source['experiments/backends/paper/settings_readback.py']='0'*64
            put(frozen/'SOURCE_IDENTITY.json',source)
            put(frozen/'MANIFEST.json',{p.name:sha(p) for p in frozen.iterdir() if p.name!='MANIFEST.json'})
            with self.assertRaisesRegex(ValueError,'analysis dependency drift: .*settings_readback'):
                report(base)


    def test_report_rebinds_opted_in_spectre_to_actual_lane_tool_identity(self):
        from precision_report import spectre_fullprecision_settings
        fixture=json.loads((ROOT/'experiments/backends/paper/fixtures/spectre-21.1.0.509-format-calibration.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);finalized_abort_batch(base)
            out=base/'collected/sample_hold-spectre/outputs/sample_hold-spectre'
            record=json.loads((out/'EXECUTION.json').read_text())[0]
            work=out/'runs'/record['label'];(work/'psf').mkdir(parents=True)
            (work/'tb.scs').write_text(fixture['deck']);(work/'dut.va').write_text('// synthetic report fixture')
            (work/'spectre.log').write_text(fixture['log']);(work/'psf/tran.tran.tran').write_text(fixture['psf_header'])
            put(work/'requested_settings.json',{'reltol':1e-5,'vabstol_V':1e-9,'iabstol_A':1e-13,
                'stop_s':2.1457672119140625e-6,'maxstep_s':2.9802322387695312e-8})
            tool={'version':'sub-version  21.1.0.509.isr12','binary_sha256':fixture['binary_sha256']}
            put(out/'TOOL_IDENTITY.json',tool)
            settings=spectre_fullprecision_settings(work,tool,frozen_deck_sha256=fixture['source_sha256']['sci_ascii_deck'])
            card=CARDS['SH-T-RAMP'];put(work/'condition.json',card);put(work/'RESULT.json',{})
            # Independent piecewise rows exercise the real native reader/checker;
            # this fixture tests settings admission, not physical simulation.
            wave='VALUE\n'+''.join(''.join('"'+key+'" '+repr(value)+'\n' for key,value in row.items()) for row in sample_rows(card))+'END\n'
            (work/'wave.txt').write_text(wave)
            record.update(status='waveform_available',deck='tb.scs',waveform='wave.txt',effective_settings=settings)
            put(out/'EXECUTION.json',[record])
            def seal():
                put(out/'FILE_MANIFEST.json',{str(p.relative_to(out)):{'sha256':sha(p),'bytes':p.stat().st_size}
                    for p in out.rglob('*') if p.is_file() and p.name!='FILE_MANIFEST.json'})
            seal();result=report(base)
            row=next(r for r in result['results'] if r['lane']=='sample_hold-spectre')
            self.assertEqual(row['qualification']['status'],'qualified')
            # A receipt marker does not substitute for actual external preflight.
            put(out/'TOOL_IDENTITY.json',{**tool,'binary_sha256':'0'*64});seal()
            row=next(r for r in report(base)['results'] if r['lane']=='sample_hold-spectre')
            self.assertEqual(row['qualification']['status'],'evidence_insufficient')

    def test_unexplained_preset_mismatch_not_excused(self):
        record={'effective_settings':{'actual':{'reltol':1e-6,'vabstol':1e-9,'iabstol':1e-13,'method':'traponly'},
            'requested':{'reltol':1e-5},'mismatches':['reltol']}}
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);(work/'tb.scs').write_text('tran tran errpreset=conservative\n')
            self.assertEqual(qualification(work,'spectre',record,[])['status'],'evidence_insufficient')
            record['effective_settings']['scoped_readback']={'psf_effective':{'reltol':{'value':1e-6}}}
            self.assertEqual(qualification(work,'spectre',record,[])['status'],'qualified')

if __name__=='__main__':unittest.main()
