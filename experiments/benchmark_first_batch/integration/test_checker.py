"""Adversarial checker tests, not claims about simulated Verilog-A."""
import copy,json,math,re,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'benchmark/checkers'))
from first_batch_integration import evaluate

class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.case={'stop':4e-9,'signals':['result','valid'],'windows':[{'node':'result','start':1e-9,'end':3e-9,'value':.4,'atol':.002}],'samples':[{'node':'result','t':3.5e-9,'value':.4,'atol':.002}],'edges':[{'node':'valid','threshold':.5,'start':.1e-9,'times':[1e-9,3e-9],'atol':.02e-9}]}
        self.rows=[{'time':t*1e-9,'result':.4,'valid':v} for t,v in [(0,0),(.9,0),(1,0.5),(1.1,1),(2,1),(2.9,1),(3,.5),(3.1,0),(3.5,0),(4,0)]]
    def test_literal_correct_trace(self):self.assertTrue(evaluate(self.rows,self.case)['passed'])
    def test_wrong_local_result_rejected(self):
        rows=copy.deepcopy(self.rows);rows[4]['result']=.414
        self.assertFalse(evaluate(rows,self.case)['passed'])
    def test_extra_complete_pulse_rejected(self):
        rows=copy.deepcopy(self.rows)
        rows.extend([{'time':t*1e-9,'result':.4,'valid':v} for t,v in [(3.6,0),(3.65,1),(3.7,0)]]);rows.sort(key=lambda r:r['time'])
        self.assertFalse(evaluate(rows,self.case)['passed'])
    def test_missing_last_transition_rejected(self):
        rows=copy.deepcopy(self.rows)
        for row in rows:
            if row['time']>=3e-9:row['valid']=1
        self.assertFalse(evaluate(rows,self.case)['passed'])
    def test_late_edge_rejected(self):
        rows=copy.deepcopy(self.rows)
        for row in rows:
            if .9e-9<=row['time']<=1.1e-9:row['time']+=.06e-9
        self.assertFalse(evaluate(rows,self.case)['passed'])
    def test_nonfinite_rejected(self):
        rows=copy.deepcopy(self.rows);rows[4]['result']=float('nan')
        self.assertFalse(evaluate(rows,self.case)['passed'])
    def test_missing_signal_rejected(self):
        rows=copy.deepcopy(self.rows);del rows[4]['valid']
        self.assertFalse(evaluate(rows,self.case)['passed'])
    def test_truncated_waveform_rejected(self):self.assertFalse(evaluate(self.rows[:-1],self.case)['passed'])
    def test_sample_after_stable_window_rejected(self):
        rows=copy.deepcopy(self.rows);rows[-2]['result']=.5
        self.assertFalse(evaluate(rows,self.case)['passed'])
    def test_manifest_numerical_contract(self):
        paths=sorted((ROOT/'benchmark/tasks').glob('integrate-*/tests/cases.json'))
        self.assertEqual(len(paths),5)
        for path in paths:
            for case in json.loads(path.read_text()):
                self.assertGreater(case['stop'],0)
                for spec in case.get('windows',[]):
                    self.assertTrue(0<=spec['start']<spec['end']<=case['stop'],(path,spec))
                    self.assertIn(spec['node'],case['signals']);self.assertGreater(spec['atol'],0)
                for spec in case.get('samples',[]):
                    self.assertTrue(0<=spec['t']<=case['stop']);self.assertTrue(math.isfinite(spec['value']))
    def test_no_conflicting_stable_windows(self):
        for path in sorted((ROOT/'benchmark/tasks').glob('integrate-*/tests/cases.json')):
            for case in json.loads(path.read_text()):
                specs=case.get('windows',[])
                for i,a in enumerate(specs):
                    for b in specs[i+1:]:
                        if a['node']==b['node'] and max(a['start'],b['start'])<min(a['end'],b['end']):
                            self.assertLessEqual(abs(a['value']-b['value']),min(a['atol'],b['atol']),(path,a,b))
    def test_edge_ledgers_match_stable_flag_windows(self):
        for path in sorted((ROOT/'benchmark/tasks').glob('integrate-*/tests/cases.json')):
            for case in json.loads(path.read_text()):
                for edge in case.get('edges',[]):
                    for window in case.get('windows',[]):
                        if window['node']==edge['node']:
                            midpoint=(window['start']+window['end'])/2
                            level=sum(t<midpoint for t in edge['times'])%2
                            self.assertAlmostEqual(window['value'],level,msg=str((path,case['name'],window,edge)))
    def test_pll_literal_closed_form_and_phase_fault(self):
        case={'stop':4e-9,'signals':['frequency','wave'],'pll_protocol':{'hops':[(2,2)],'resets':[],'tau_ns':1}}
        # At the hop frequency is 1 and phase is 2 cycles. One ns later the
        # integral is 3+exp(-1) cycles, two ns later 5+exp(-2) cycles.
        rows=[{'time':t*1e-9,'frequency':f,'wave':w} for t,f,w in [(0,1,.5),(1,1,.5),(2,1,.5),(3,2-math.exp(-1),.5+.5*math.sin(2*math.pi*math.exp(-1))),(4,2-math.exp(-2),.5+.5*math.sin(2*math.pi*math.exp(-2)))]]
        self.assertTrue(evaluate(rows,case)['passed'])
        rows[3]['wave']+=.03
        self.assertFalse(evaluate(rows,case)['passed'])
    def test_pll_frequency_fault_is_separate_from_phase(self):
        case={'stop':2e-9,'signals':['frequency','wave'],'pll_protocol':{'hops':[],'resets':[],'tau_ns':5}}
        rows=[{'time':0,'frequency':1,'wave':.5},{'time':1e-9,'frequency':1.003,'wave':.5},{'time':2e-9,'frequency':1,'wave':.5}]
        result=evaluate(rows,case)
        self.assertFalse(result['passed']);self.assertEqual(result['failures'][0]['node'],'frequency')
    def test_every_public_and_hidden_pwl_has_monotone_times(self):
        for task in sorted((ROOT/'benchmark/tasks').glob('integrate-*')):
            for path in [task/'tests/cases.json',task/'environment/public/smoke_cases.json']:
                for case in json.loads(path.read_text()):
                    for waveform in re.findall(r'wave=\[([^]]+)\]',case['netlist']):
                        items=waveform.split();times=[float(v[:-1])*1e-9 for v in items[::2]]
                        self.assertTrue(all(a<b for a,b in zip(times,times[1:])),(path,case['name'],times))
                        self.assertLessEqual(times[-1],case['stop']+1e-18,(path,case['name']))
    def test_agc_does_not_reuse_actual_spectre_reserved_identifier(self):
        # VACOMP-1705 in the archived actual AGC calibration established this
        # reserved-name conflict. This is static protection, not compilation.
        paths=list((ROOT/'benchmark/tasks/integrate-agc-attack-release').rglob('*.va'))
        paths+=list((ROOT/'experiments/benchmark_first_batch/integration/mutants/integrate-agc-attack-release').rglob('*.va'))
        for path in paths:
            for declaration in re.findall(r'\breal\s+([^;]+);',path.read_text()):
                self.assertNotIn('current',re.findall(r'[A-Za-z_][A-Za-z0-9_]*',declaration),path)
if __name__=='__main__':unittest.main()
