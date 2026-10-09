import copy,unittest
from check import dynamic_reference,check_dynamic

class Calibration(unittest.TestCase):
    def rows(self,event=False):
        return [dict(time=t,**dynamic_reference(t,event)) for t in [0,.125,.25,.5-1e-10,.5,.5+1e-10,.5+1e-8,.75,1]]
    def test_correct_answers_and_hand_anchors(self):
        self.assertEqual(dynamic_reference(0)['z'],1)
        self.assertEqual(dynamic_reference(1)['amp'],0)
        self.assertAlmostEqual(dynamic_reference(.5,True)['z'],2/3)
        self.assertAlmostEqual(dynamic_reference(1,True)['z'],.4)
        for event in [False,True]:self.assertTrue(check_dynamic(self.rows(event),event)['pass'])
    def test_wrong_initial_and_sign(self):
        for index,port,value in [(0,'z',.9),(2,'z',1.25)]:
            rows=self.rows();rows[index][port]=value;self.assertFalse(check_dynamic(rows)['pass'])
    def test_amplification_budget(self):
        rows=self.rows();rows[-1]['amp']=.002
        self.assertFalse(check_dynamic(rows)['pass'])
    def test_missing_event_and_bad_continuation(self):
        rows=self.rows(True)
        for r in rows:r['count']=0
        self.assertFalse(check_dynamic(rows,True)['pass'])
        rows=self.rows(True);rows[-1].update(dynamic_reference(1,False))
        self.assertFalse(check_dynamic(rows,True)['pass'])
    def test_wrong_event_time(self):
        self.assertFalse(check_dynamic(self.rows(True),True,[{'time':.500001}])['pass'])
    def test_missing_row_and_invalid_values(self):
        self.assertFalse(check_dynamic(self.rows()[1:])['pass'])
        for field,value in [('time',float('nan')),('z',float('inf'))]:
            rows=self.rows();rows[2][field]=value;self.assertFalse(check_dynamic(rows)['pass'])
    def test_reordered_duplicate_and_extra_events(self):
        rows=self.rows();rows.insert(2,copy.deepcopy(rows[1]));self.assertFalse(check_dynamic(rows)['pass'])
        rows=self.rows(True);rows[-1]['count']=2;self.assertFalse(check_dynamic(rows,True)['pass'])

if __name__=='__main__':unittest.main()

class VcoCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util,json
        from pathlib import Path
        p=Path(__file__).resolve().parent/'retained-vco'
        cls.card=json.loads((p/'condition.json').read_text())
        spec=importlib.util.spec_from_file_location('retained_paper_oracle',p/'oracle.py');cls.oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.oracle)
    def rows(self):
        times=set(i*2e-9 for i in range(4001))
        for t in self.card['event_contract'][0]['nominal_T']:
            times.update([t*1e-6-2e-11,t*1e-6+2e-11])
        return [dict(time=t,**self.oracle.values(self.card,t/1e-6,{},{})) for t in sorted(times)]
    def check(self,rows):
        from check import check_vco
        return check_vco(rows,self.card,self.oracle)
    def test_correct_maintained_reference(self):self.assertTrue(self.check(self.rows())['pass'])
    def test_wrong_frequency_and_sine(self):
        for name in ['freq','out']:
            rows=self.rows();rows[100][name]+=.02;self.assertFalse(self.check(rows)['pass'])
    def test_missing_wrap_and_initial(self):
        rows=self.rows()
        for r in rows:r['phase']=.1
        self.assertFalse(self.check(rows)['pass'])
        self.assertFalse(self.check(self.rows()[1:])['pass'])
    def test_ordinary_phase_error_visible_at_wrap(self):
        rows=self.rows();i=next(i for i,r in enumerate(rows) if abs(r['time']-self.card['event_contract'][0]['nominal_T'][0]*1e-6)<3e-11)
        rows[i]['phase']=1-rows[i]['phase']
        self.assertTrue(any(f.get('signal')=='phase_ordinary' and f['within_wrap_window'] for f in self.check(rows)['failures']))
