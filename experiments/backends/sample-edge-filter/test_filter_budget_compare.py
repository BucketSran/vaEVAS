import copy
from decimal import Decimal, localcontext
import json
import math
from pathlib import Path
import tempfile
import unittest

from filter_budget_compare import (ROOT, SOURCE, OBSERVATION_TIME,
                                  OBSERVATION_SOURCE, assess, freeze,
                                  check_observation_control)

CONTRACT = ROOT/'evas/validation/paper/precision-v1.json'


class FilterBudgetChecker(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(CONTRACT.read_text())
        self.data['signal_scale_V'] = 2.
        self.budget = self.data['budgets']['absolute_V']+2*self.data['budgets']['relative']
        root = math.sqrt(2)
        times = sorted({i/32 for i in range(97)} | {
            t+s*2e-12 for t in (root,root+.125,root+.625) for s in (-1,1)})
        self.rows=[]
        # An independently evaluated high-precision closed form calibrates the
        # binary64 checker; mutations below test its rejection obligations.
        with localcontext() as c:
            c.prec=80
            q=Decimal(2).sqrt(); tau=Decimal('0.25'); duration=Decimal('0.5')
            for t in times:
                h=max(Decimal(0),Decimal.from_float(t)-q-Decimal('0.125'))
                a=min(h,duration)
                y=(a-tau*(1-(-a/tau).exp()))/duration
                if h>duration:y=1+(y-1)*(-(h-duration)/tau).exp()
                self.rows.append(dict(time=t,u=t,e=float(q*a/duration),y=float(q*y)))

    def test_exact_response_passes_and_output_or_input_corruption_fails(self):
        self.assertEqual(assess(self.rows,self.data,self.budget)['status'],'pass')
        for node in ('u','e','y'):
            rows=copy.deepcopy(self.rows);rows[-1][node]+=self.budget*10
            self.assertEqual(assess(rows,self.data,self.budget)['status'],'numerical_error')

    def test_missing_boundary_nonfinite_and_missing_data_are_not_passes(self):
        root=math.sqrt(2)+.625
        controls=[[],self.rows[:-1],self.rows[::-1],
                  [r for r in self.rows if abs(r['time']-root)>1e-10]]
        bad=copy.deepcopy(self.rows);bad[-1]['y']=math.nan;controls.append(bad)
        for rows in controls:
            self.assertEqual(assess(rows,self.data,self.budget)['status'],'evidence_insufficient')

    def test_old_export_without_right_edge_end_is_insufficient(self):
        root=math.sqrt(2)+.625
        rows=[r for r in self.rows if not 0<r['time']-root<1e-10]
        self.assertEqual(assess(rows,self.data,self.budget)['reason'],'boundary coverage')

    def test_freeze_preserves_all_original_budgets_and_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'inputs';freeze(dest,CONTRACT)
            stored=json.loads((dest/'CONTRACT.json').read_text())
            self.assertEqual(stored['budgets'],self.data['budgets'])
            self.assertEqual(stored['profiles'],self.data['profiles'])
            self.assertEqual(stored['profile_selection'],self.data['profile_selection'])
            self.assertEqual({p.name for p in dest.iterdir() if p.is_dir()},
                             {p['id'] for p in self.data['profiles']})
            self.assertEqual(len(json.loads((dest/'MANIFEST.json').read_text())),17)
            for profile in stored['profiles']:
                work=dest/profile['id']
                self.assertEqual((work/'dut.va').read_text(),SOURCE)
                self.assertNotIn('transres=',(work/'tb.scs').read_text())
                self.assertTrue((work/'observation.va').is_file())

    def test_observation_control_requires_unmodified_source_and_actual_callback(self):
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)/'input';ref=Path(temp)/'ref'
            for path in (work,ref):
                path.mkdir();(path/'observation.va').write_text(OBSERVATION_SOURCE)
            good=f'FILTER_OBSERVATION {OBSERVATION_TIME:.17g}\n'
            (ref/'spectre.log').write_text(good)
            self.assertEqual(check_observation_control(work,ref)['actual_s'],OBSERVATION_TIME)
            for text in ('',good+good,'FILTER_OBSERVATION nan\n',
                         f'FILTER_OBSERVATION {OBSERVATION_TIME+1e-6:.17g}\n'):
                (ref/'spectre.log').write_text(text)
                with self.assertRaises(ValueError):check_observation_control(work,ref)
            (ref/'spectre.log').write_text(good)
            (ref/'observation.va').write_text(OBSERVATION_SOURCE+'// changed\n')
            with self.assertRaises(ValueError):check_observation_control(work,ref)


if __name__=='__main__':unittest.main()
