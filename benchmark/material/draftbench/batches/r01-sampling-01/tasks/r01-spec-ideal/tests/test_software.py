"""Pure software checks. These do not execute or calibrate Verilog-A."""
import copy
import csv
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TASK=Path(__file__).resolve().parents[1]
PUBLIC=TASK/'environment/starter/testbench'
sys.path.insert(0,str(PUBLIC))
sys.path.insert(0,str(TASK/'tests'))
sys.path.insert(0,str(TASK/'tests/calibration'))
from cases import public_cases, NS
from contract import crossings, diagnose, expected, observations, pwl, render, validate
from final_cases import final_cases
from verify import task_result
from mutants import candidates

class SoftwareTests(unittest.TestCase):
    def setUp(self):
        self.cases=public_cases()
        self.plan=observations(self.cases,NS,.01*NS)
    def at(self,case,instance,t):
        c=next(c for c in self.cases if c['name']==case)
        i=next(i for i in c['instances'] if i['name']==instance)
        return expected(i,t*NS)[0]
    def test_hand_startup(self):
        for t,r,value in [(0,0,.35),(1,0,.2),(0,1,.35),(1,1,.35)]:
            self.assertEqual(self.at('startup',f't{t}r{r}',0),value)
        self.assertEqual(self.at('startup','equality',0),.9)
        self.assertEqual(self.at('startup','equality_track',0),.9)
        self.assertEqual(self.at('startup','equality_reset',0),.2)
    def test_hand_track_and_close(self):
        self.assertAlmostEqual(self.at('windows','main',10),.7)
        self.assertAlmostEqual(self.at('windows','main',24),1.2)
        self.assertAlmostEqual(self.at('windows','main',28),1.2)
        self.assertAlmostEqual(self.at('windows','main',36),.32)
    def test_hand_reset(self):
        for instance,time,value in [('release_hold',16,1.),('release_hold',18,.55),
                                    ('release_hold',30,.55),('release_track',25,1.1),
                                    ('release_track',30,.2),('close_in_reset',30,.65)]:
            self.assertAlmostEqual(self.at('reset_history',instance,time),value)
    def test_hand_endpoint(self):
        i=final_cases()[-1]['instances'][0]
        self.assertAlmostEqual(expected(i,60*NS)[0],1.4906666666666666)
    def test_threshold_crossing_math(self):
        i=self.cases[-1]['instances'][0]
        self.assertAlmostEqual(crossings(i['track'],.6,-1)[0]/NS,24.066666666666666)
    def test_instance_order_independence(self):
        c=copy.deepcopy(self.cases[-1]); c['instances'].reverse()
        original=observations([self.cases[-1]],NS,.01*NS)
        reordered=observations([c],NS,.01*NS)
        self.assertEqual(sorted(original,key=str),sorted(reordered,key=str))
    def test_public_covered_by_final(self):
        final=final_cases()
        self.assertEqual(final[:len(self.cases)],self.cases)
        self.assertGreater(len(final),len(self.cases))
        validate(final)
        observations(final,NS,.01*NS)
    def test_all_mode_intervals_observed(self):
        modes={r['mode'] for r in self.plan}
        self.assertEqual(modes,{'reset','track','hold_sample','hold_initial_or_reset'})
        for c in self.cases:
            for i in c['instances']:
                rs=[r for r in self.plan if r['case']==c['name'] and r['instance']==i['name']]
                self.assertEqual(rs[0]['time'],0)
                self.assertEqual(rs[-1]['time'],c['stop'])
    def test_guard_cannot_erase_interval(self):
        with self.assertRaises(ValueError): observations(final_cases(),NS,1*NS)
    def test_invalid_stimulus_rejected(self):
        c=copy.deepcopy(self.cases)
        c[0]['instances'][0]['vin'][1][0]=0
        with self.assertRaises(ValueError): validate(c)
    def test_inclusive_threshold_comparator_is_detected(self):
        # An independent wrong >= comparator was previously masked when both
        # equal controls selected reset. Isolate each comparison explicitly.
        lookup={(c['name'],i['name']):i for c in self.cases for i in c['instances']}
        for target in ['equality_track','equality_reset']:
            rows=copy.deepcopy(self.plan)
            for row in rows:
                if row['case']=='startup' and row['instance']==target:
                    i=lookup[(row['case'],row['instance'])]
                    if row['rst']>=i['vth']: row['vout']=i['vinit']
                    elif row['track']>=i['vth']: row['vout']=row['vin']
            result=diagnose(self.plan,rows,1e-12,0)
            self.assertEqual(result['status'],'fail')
            self.assertTrue(any(x.get('field')=='vout' for x in result['issues']))

    def test_ideal_synthetic_trace(self):
        self.assertEqual(diagnose(self.plan,self.plan,0,0)['status'],'pass')
    def test_missing_and_duplicate(self):
        for rows,kind in [(self.plan[:-1],'missing'),(self.plan+[self.plan[0]],'duplicate')]:
            self.assertIn(kind,[x['kind'] for x in diagnose(self.plan,rows,0,0)['issues']])
    def test_nonfinite_and_bad_stimulus_time(self):
        for field,value in [('vout',float('nan')),('vout',float('inf')),('vin',999.),('track',999.),('rst',999.),('time',999.)]:
            rows=copy.deepcopy(self.plan); rows[0][field]=value
            self.assertEqual(diagnose(self.plan,rows,0,0)['status'],'fail')
    def test_wrong_hold_and_reset_trace(self):
        # These are synthetic observation errors, not executions of VA mutants.
        for mode in ['track','reset','hold_sample','hold_initial_or_reset']:
            rows=copy.deepcopy(self.plan)
            for row in rows:
                if row['mode']==mode: row['vout']+=.1
            self.assertEqual(diagnose(self.plan,rows,1e-12,0)['status'],'fail')
    def test_swapped_instances_trace(self):
        rows=copy.deepcopy(self.plan)
        for row in rows:
            if row['case']=='isolation' and row['instance']=='a': row['vout']=99.
        self.assertEqual(diagnose(self.plan,rows,0,0)['status'],'fail')
    def test_score_all_required(self):
        self.assertEqual(task_result(['a','b'],[dict(case='a',status='pass'),dict(case='b',status='pass')])['score'],1)
        for status in ['fail','error','timeout']:
            self.assertEqual(task_result(['a','b'],[dict(case='a',status=status)])['score'],0)
    def test_unexecuted_no_score(self):
        for records in [[],[dict(case='a',status='pass')],[dict(case='a',status='not_run')]]:
            self.assertIsNone(task_result(['a','b'],records)['score'])
    def test_score_rejects_fabricated_results(self):
        for required,rows in [([],[]),(['a'],[dict(case='x',status='pass')]),
                              (['a'],[dict(case='a',status='pass')]*2),
                              (['a'],[dict(case='a',status='maybe')])]:
            with self.assertRaises(ValueError): task_result(required,rows)
    def test_mutants_are_real_changed_candidates(self):
        gold=(TASK/'solution/circuit.va').read_text()
        variants=candidates()
        self.assertEqual(len(variants),11)
        self.assertEqual(len(set(variants.values())),11)
        self.assertTrue(all(s!=gold and 'endmodule' in s for s in variants.values()))
    def test_rendered_case_and_probes(self):
        with tempfile.TemporaryDirectory() as temp:
            c=self.cases[0]; render(c,self.plan,temp)
            deck=(Path(temp)/'tb.scs').read_text()
            expected_rows=[r for r in self.plan if r['case']==c['name']]
            self.assertIn('strobetimes=[',deck)
            self.assertNotIn('observe.va',deck)
            self.assertEqual(len(json.loads((Path(temp)/'nodes.json').read_text())),len(c['instances']))
            self.assertEqual(json.loads((Path(temp)/'expected.json').read_text()),expected_rows)
            self.assertIn('track_hold vth=',deck)
    def test_public_cli_plan_and_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            csvfile=Path(temp)/'trace.csv'
            fields=['case','instance','probe','time','vin','track','rst','vout']
            with csvfile.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(self.plan)
            proc=subprocess.run([sys.executable,'-B',str(PUBLIC/'check.py'),'check','--csv',str(csvfile),'--voltage-atol','0','--time-atol','0'],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            self.assertTrue(json.loads(proc.stdout)['diagnostic_only'])
    def test_final_prepare_does_not_execute_or_emit_reward(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'output'
            proc=subprocess.run([sys.executable,'-B',str(TASK/'tests/verify.py'),
                                 '--candidate',str(TASK/'solution/circuit.va'),'--output',str(output)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,2,proc.stderr)
            result=json.loads((output/'result.json').read_text())
            self.assertEqual(result['status'],'not_run')
            self.assertIsNone(result['score'])
            self.assertFalse((output/'reward.txt').exists())

if __name__=='__main__': unittest.main()
