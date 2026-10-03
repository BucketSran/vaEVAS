"""Checker calibration for explicit OR tables; no backend output fixtures."""
import math
import re
import unittest
from event_or_reference import UNIT, specifications, inspect, source


def fixture(c):
    # Hand-worked piecewise plateaus. Input interpolation is explicit arithmetic
    # here, independent of the checker helper used to audit physical observations.
    rows=[]
    for t in c['output_times']:
        row={'time':t}
        for name,points in c['inputs'].items():
            value=points[-1][1]
            for (a,u),(b,v) in zip(points,points[1:]):
                if t<=b:value=u+(v-u)*(t-a)/(b-a);break
            row[name]=value
        row.update(count=0,stamp=0,sample=.1 if c['family'].startswith('reset_') else 0)
        for e in c['events']:
            if t>=e['root_s']:row.update({n:e[n] for n in ['count','stamp','sample']})
        rows.append(row)
    return rows


class EventOrReference(unittest.TestCase):
    def test_numeric_literals_include_required_integer_part(self):
        # Observed Spectre VACOMP-1795: write 0.5 rather than .5.
        for c in specifications():
            with self.subTest(case=c["id"]):
                self.assertIsNone(re.search(r"(?<![A-Za-z0-9_])\.\d", source(c)))

    def test_explicit_tables_and_positive_controls(self):
        cases=specifications()
        self.assertEqual(len(cases),16)
        for c in cases:
            with self.subTest(case=c['id']):
                self.assertEqual(inspect(fixture(c),c)['status'],'observations_within_candidate_windows')
        by={c['id']:c for c in cases}
        self.assertEqual([e['root_s']/UNIT for e in by['distinct-fine']['events']],[.25,.75])
        self.assertEqual([e['count'] for e in by['same-fine']['events']],[1])
        self.assertEqual([e['root_s']/UNIT for e in by['nearby-fine']['events']],[.5,513/1024])
        self.assertEqual([e['sample'] for e in by['reset_active-fine']['events']],[.1,.725])

    def test_duplicate_missing_merged_and_extra_updates_are_rejected(self):
        by={c['id']:c for c in specifications()}
        for name,fault in [('same-fine','duplicate'),('distinct-fine','missing'),
                           ('nearby-fine','merge'),('duplicate-fine','extra')]:
            c=by[name];rows=fixture(c)
            for r in rows:
                if r['time']>.9*UNIT:r['count']+=1 if fault in ['duplicate','extra'] else -1
            self.assertEqual(inspect(rows,c)['status'],'observed_violation')

    def test_reset_priority_and_sampled_stamp_are_checked(self):
        for family,node,value in [('reset_same','sample',.75),('reset_active','sample',.1),('same','stamp',.6)]:
            c=next(c for c in specifications() if c['id']==family+'-fine');rows=fixture(c)
            for r in rows:
                if r['time']>.9*UNIT:r[node]=value
            self.assertEqual(inspect(rows,c)['status'],'observed_violation')

    def test_invalid_observations_cannot_pass(self):
        c=specifications()[0]
        for fault in ['missing','nonfinite','duplicate','tail','input']:
            rows=fixture(c)
            if fault=='missing':rows[10].pop('count')
            if fault=='nonfinite':rows[10]['count']=math.nan
            if fault=='duplicate':rows[10]['time']=rows[9]['time']
            if fault=='tail':rows.pop()
            if fault=='input':rows[10]['data']+=.1
            with self.subTest(fault=fault),self.assertRaises(ValueError):inspect(rows,c)


if __name__=='__main__':unittest.main()
