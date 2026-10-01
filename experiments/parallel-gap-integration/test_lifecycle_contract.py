"""Calibrate independent finite-observation diagnostics, not simulator behavior."""
from copy import deepcopy
import math
import re
import unittest

import lifecycle_contract as m


def fixture(family, *, post_reset=True, delayed=False):
    c=next(c for c in m.specifications() if c['family']==family and c['profile']=='base')
    event=.25 if family in ['warm-restart','release-sample'] else .5
    release=.5 if family=='release-sample' else .75
    if 'cross' in family:
        lo,hi=m.crossing_window(.2,.8,m.UNIT,c['ttol'],c['etol'])
        event=float((lo+hi)/2/m.Q(m.UNIT)) if delayed else float(lo/m.Q(m.UNIT))
    sample=(.2+(.8-.2)*event if family=='cross-condition' else
            .5 if family=='warm-restart' else
            1+event if family.startswith('inactive') or (family.startswith('active') and not post_reset) else 1)
    rows=[]
    for i in range(33):
        x=i/32; flag=0; stamp=-1.; held=0 if family in ['cross-condition','warm-restart'] else 1.
        if family!='cold-nonstationary' and x>=event:
            flag=(2 if delayed else 3) if family=='cross-condition' else 1
            stamp=event; held=sample
            if (family.startswith('active') or family in ['reset-only','release-sample']) and x>=release:
                flag=2; stamp=release
        if family=='cold-nonstationary': z,y=3+x,2+x+math.exp(-x)
        elif family=='cross-condition': z,y=0.,held
        elif family=='warm-restart': z,y=1.,1. if x<event else 2-4/(4+x-event)
        else:
            reset=family.startswith('active') or family in ['reset-only','release-sample']
            z=float(m.integral_after_event(x,event,sample,reset=reset,release=release))
            y=m.filter_after_event(x,event,sample,reset=reset,release=release)
        rows.append(dict(time=x*m.UNIT,u=0. if family=='warm-restart' else .2+(.8-.2)*x,
                         clock=x,y=y,z=z,held=held,stamp=stamp,flag=flag))
    return rows,c


class LifecycleCheckerCalibration(unittest.TestCase):
    def test_settings_display_rounding_is_separate_from_waveform_accuracy(self):
        rows,c=fixture('inactive-timer')
        log='\n'.join(f'{k} = {v}' for k,v in dict(vabstol='1e-10',
            iabstol='1e-14',reltol='1e-8',stop='953.674 ns',
            step='119.209 ns',maxstep='119.209 ns',method='traponly').items())
        actual,audit=m.audit_displayed_settings(log,c,rows)
        self.assertNotEqual(actual['maxstep'],c['maxstep'])
        self.assertTrue(audit['waveform_matches_requested'])
        for wrong in [log.replace('119.209','120.209'),
                      log.replace('traponly','gear2only'),
                      log.replace('953.674','954.674'),
                      log.replace('1e-10','NaN')]:
            with self.assertRaises(ValueError): m.audit_displayed_settings(wrong,c,rows)
        rows[-1]['time']-=1e-12
        with self.assertRaisesRegex(ValueError,'waveform stop mismatch'):
            m.audit_displayed_settings(log,c,rows)

    def test_generated_models_use_portable_real_literals(self):
        for c in m.specifications():
            with self.subTest(case=c['id']):
                self.assertIsNone(re.search(r'(?<![A-Za-z0-9_])\.\d', m.source(c)))

    def test_closed_forms_for_all_families(self):
        for f in m.FAMILIES:
            with self.subTest(family=f):
                rows,c=fixture(f)
                self.assertIn(m.inspect(rows,c)['status'],['finite_consistent','classified_trigger_observation'])

    def test_reset_alternatives_are_classified_without_a_normative_pass_claim(self):
        for post,label in [(True,'post_reset_sample'),(False,'pre_reset_sample')]:
            rows,c=fixture('active-forward',post_reset=post)
            answer=m.inspect(rows,c)
            self.assertEqual(answer['status'],'finite_consistent')
            self.assertEqual(answer['reset_sample_class'],label)

    def test_release_sample_is_bound_to_release_stage(self):
        rows,c=fixture('release-sample')
        for r in rows:
            if r['flag']==2: r['held']=1.0000013
        # Stage 1 legitimately retains its initial q. The later sample exceeds
        # the unchanged IC allowance, rather than changing outside its event.
        with self.assertRaisesRegex(ValueError,'held/reset-release state differs from IC'):
            m.inspect(rows,c)
        rows[10]['held']+=.01
        with self.assertRaisesRegex(ValueError,'outside its event'):
            m.inspect(rows,c)

    def test_root_and_later_trigger_conditions_are_distinct_observations(self):
        for delayed,flag in [(False,3),(True,2)]:
            rows,c=fixture('cross-condition',delayed=delayed)
            answer=m.inspect(rows,c)
            self.assertEqual(answer['strict_condition_flag'],flag)
            self.assertEqual(answer['status'],'classified_trigger_observation')

    def test_individually_allowed_but_inconsistent_sample_times_are_rejected(self):
        rows,c=fixture('cross-condition')
        for r in rows:
            if r['flag']:
                r['held']+=.001; r['y']=r['held']
        with self.assertRaisesRegex(ValueError,'cannot share one allowed event time'):
            m.inspect(rows,c)

    def test_wrong_history_and_repeated_cold_initialization_are_detected(self):
        rows,c=fixture('reset-only')
        wrong=deepcopy(rows)
        for r in wrong:
            if r['time']>.55*m.UNIT: r['y']+=.01
        self.assertEqual(m.inspect(wrong,c)['status'],'finite_inconsistent')
        wrong=deepcopy(rows); wrong[-1]['z']+=.001
        self.assertEqual(m.inspect(wrong,c)['status'],'finite_inconsistent')

    def test_missing_nonfinite_input_and_changed_held_state_are_rejected(self):
        rows,c=fixture('inactive-timer')
        for mutation in ['missing','nonfinite','input','held']:
            with self.subTest(mutation=mutation):
                bad=deepcopy(rows)
                if mutation=='missing': del bad[0]['clock']
                elif mutation=='nonfinite': bad[1]['z']=math.nan
                elif mutation=='input': bad[2]['u']+=.01
                else: bad[-2]['held']+=.01
                with self.assertRaises(ValueError): m.inspect(bad,c)


if __name__=='__main__':
    unittest.main()
