"""Root-window fault calibration from exact rational PWL interpolation."""
import copy
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from precision_v2 import assess as old_assess, load_contract, rows_digest
from precision_root_v3 import assess
from root_windows import reference_roots
from test_precision_v2 import sample_rows


CONTRACT=load_contract()
CARD=next(c for c in CONTRACT['cards'] if c['id']=='SH-X-RAMP')


def pwl(points,time):
    time=F(time)
    for (a,u),(b,v) in zip(points,points[1:]):
        a,u,b,v=map(F,(a,u,b,v))
        if time<=b:
            return u+(v-u)*(time-a)/(b-a)
    return F(points[-1][1])


def literal_roots():
    # Independent linear interpolation at clk=.5, using represented endpoints.
    return [F(a)+(F(.5)-F(u))*(F(b)-F(a))/(F(v)-F(u))
            for (a,u),(b,v) in zip(CARD['inputs']['clk'],CARD['inputs']['clk'][1:])
            if u<.5<=v]


def enclosed(value):
    t=float(value)
    return [math.nextafter(t,-math.inf) if F(t)>value else t,
            math.nextafter(t,math.inf) if F(t)<value else t]


def trace(shift=F(50,10**12), *, exact=False):
    roots=literal_roots()
    boxes=[enclosed(r if exact else r+shift) for r in roots]
    moments=[box[1] for box in boxes]
    times={r['time'] for r in sample_rows(CARD)}
    for box in boxes:
        # Preserve the old boundary-side detector's five-row neighborhood.
        # Two adjacent callback observations suffice; redundant sub-ULP rows
        # would conceal the requested one-picosecond side observations.
        times={t for t in times if not box[0]-32*math.ulp(CARD['stop_s'])<=t<=box[1]+32*math.ulp(CARD['stop_s'])}
        times.update([math.nextafter(box[0],-math.inf),box[1]])
    rows=[]
    for t in sorted(times):
        n=sum(moment<=t for moment in moments)
        rows.append(dict(time=t,u=float(pwl(CARD['inputs']['u'],t)),
                         clk=float(pwl(CARD['inputs']['clk'],t)),count=float(n),
                         y=CARD['initial_V'] if n==0 else float(pwl(CARD['inputs']['u'],moments[n-1]))))
    return rows,boxes


def evaluate(rows,boxes=None, *, card=CARD,contract=CONTRACT):
    if boxes is None:return assess(card,rows,contract)
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp);raw=base/'synthetic.txt'
        raw.write_text('Independent synthetic calibration, not backend evidence.\n')
        proof={'method':'independent_callback_trace','waveform_rows_sha256':rows_digest(rows),
               'artifact':raw.name,'artifact_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
               'events':[{'index':i,'time_bounds_s':[str(F(v)) for v in box]}
                         for i,box in enumerate(boxes,1)]}
        path=base/'proof.json';path.write_text(json.dumps(proof))
        return assess(card,rows,contract,event_evidence_path=path)


class RootWindowCalibration(unittest.TestCase):
    def assert_all(self,result,status):
        self.assertEqual([v['status'] for v in result['tiers'].values()],[status]*3,result)

    def test_eight_independently_derived_roots_and_valid_rows(self):
        roots=literal_roots();self.assertEqual(len(roots),8)
        self.assertEqual([r.exact for r in reference_roots(CARD)],roots)
        rows,boxes=trace();result=evaluate(rows,boxes)
        self.assert_all(result,'pass');self.assertEqual(result['schema_version'],3)
        self.assertEqual(result['reference_version'],'root-window-v3')
        self.assertEqual(len(result['event_records']),8)
        self.assertEqual([r['qualified_callback_s'] for r in result['event_records']],boxes)
        self.assertTrue(all(r['strict_semantic_timing']=='pass' for r in result['event_records']))

    def test_exact_root_box_preserved_and_strict_boundary_unresolved(self):
        rows,boxes=trace(exact=True);result=evaluate(rows,boxes)
        self.assert_all(result,'pass')
        self.assertEqual(result['strict_semantic_timing'],'unresolved')
        self.assertEqual(result['serialized_resolution_timing'],'pass')
        self.assertEqual([r['callback_bounds_s'] for r in result['event_records']],boxes)
        self.assertTrue(any(r['strict_semantic_timing']=='unresolved' for r in result['event_records']))
        self.assertTrue(all(r['serialized_resolution_timing']=='pass' for r in result['event_records']))
        self.assertTrue(all(r['serialization_allowance_s']==
                            CONTRACT['budgets']['time_serialization_ulps']*math.ulp(CARD['stop_s'])
                            for r in result['event_records']))
        self.assertTrue(all(v['status']!='pass' for v in old_assess(CARD,rows,CONTRACT)['tiers'].values()))

    def test_committed_callback_protocol_keeps_complete_boxes_and_method(self):
        rows,boxes=trace(exact=True)
        supplied={k:box for k,box in enumerate(boxes,1)}
        before=copy.deepcopy(supplied)
        result=assess(CARD,rows,CONTRACT,committed_callback_boxes=supplied)
        self.assert_all(result,'pass');self.assertEqual(supplied,before)
        self.assertEqual([r['callback_bounds_s'] for r in result['event_records']],boxes)
        self.assertTrue(all(not r['independent_event_evidence_used'] for r in result['event_records']))
        self.assertTrue(all(r['callback_evidence_method']=='externally_qualified_committed_callback'
                            for r in result['event_records']))
        invalid=[{1:boxes[0]}, {**supplied,9:[0.,0.]}, {**supplied,True:boxes[0]},
                 {**supplied,1:[1.,0.]}, {**supplied,1:[float('nan'),1.]},
                 {**supplied,1:[-1.,0.]}, {**supplied,1:[0.,CARD['stop_s']+1.]},
                 {**supplied,1:['0','1']}, {**supplied,1:[0.]}, {**supplied,1:[0.,10**400]}]
        # bool aliases integer keys, so construct that malformed inventory explicitly.
        invalid[2]={True:boxes[0],**{k:v for k,v in supplied.items() if k!=1}}
        for proof in invalid:
            with self.subTest(proof=proof),self.assertRaises(ValueError):
                assess(CARD,rows,CONTRACT,committed_callback_boxes=proof)
        conflict=copy.deepcopy(supplied);conflict[1]=[0.,0.]
        result=assess(CARD,rows,CONTRACT,committed_callback_boxes=conflict)
        self.assertTrue(all(v['status']!='pass' for v in result['tiers'].values()))
        self.assertTrue(any('conflicts with native' in s for s in result['observation_issues']))

    def test_counts_reject_missing_duplicate_reversed_and_noninteger(self):
        for fault in ('missing','duplicate','reverse','fractional','initial','final'):
            rows,boxes=trace()
            if fault=='missing':
                for row in rows:
                    if row['count']>=3:row['count']-=1
            elif fault=='duplicate':
                for row in rows:
                    if row['count']>=3:row['count']+=1
            elif fault=='reverse':rows[next(i for i,r in enumerate(rows) if r['count']==3)+1]['count']=2.
            elif fault=='fractional':rows[5]['count']+=.01
            elif fault=='initial':rows[0]['count']=1.
            else:rows[-1]['count']=7.
            with self.subTest(fault=fault):self.assert_all(evaluate(rows,boxes),'behavior_error')

    def test_wrong_sample_and_every_holding_stage_drift(self):
        rows,boxes=trace();next(r for r in rows if r['count']==2)['y']+=.01
        self.assert_all(evaluate(rows,boxes),'numerical_error')
        for stage in range(9):
            rows,boxes=trace();group=[r for r in rows if r['count']==stage]
            group[0]['y']-=.7*1.01e-6;group[-1]['y']+=.7*1.01e-6
            with self.subTest(stage=stage):
                self.assertEqual(evaluate(rows,boxes)['tiers']['Q2']['status'],'numerical_error')

    def test_early_and_late_callbacks_are_rejected(self):
        for shift in (F(-1,10**12),F(400,10**12)):
            rows,boxes=trace(shift)
            with self.subTest(shift=shift):self.assert_all(evaluate(rows,boxes),'behavior_error')

    def test_full_native_bracket_remains_unqualified_without_proof(self):
        rows,_=trace(exact=True)
        result=evaluate(rows)
        self.assert_all(result,'evidence_insufficient')
        self.assertTrue(any(r['serialized_resolution_timing']=='evidence_insufficient'
                            for r in result['event_records']))

    def test_wide_bracket_and_missing_boundaries_are_not_passes(self):
        rows,_=trace()
        # Full 200ps native counter gaps still intersect the allowed window.
        rows=[r for r in rows if all(not t-50e-12<r['time']<t+150e-12 for t in CARD['events_s'])]
        result=evaluate(rows)
        self.assertTrue(all(v['status']!='pass' for v in result['tiers'].values()))
        self.assertGreater(result['max_callback_bracket_s'],100e-12)
        rows,boxes=trace();t=CARD['events_s'][0]+CARD['event_late_s']
        rows=[r for r in rows if abs(r['time']-t)>3e-12]
        result=evaluate(rows,boxes)
        self.assert_all(result,'evidence_insufficient')
        self.assertTrue(any('missing boundary' in s for s in result['observation_issues']))

    def test_inputs_and_voltage_tiers_keep_original_budgets(self):
        rows,boxes=trace();original=evaluate(rows,boxes)
        self.assertEqual([v['voltage_budget_V'] for v in original['tiers'].values()],
                         [v['voltage_budget_V'] for v in old_assess(CARD,rows,CONTRACT)['tiers'].values()])
        for row in rows:row['y']+=2e-6
        self.assertEqual([v['status'] for v in evaluate(rows,boxes)['tiers'].values()],
                         ['pass','numerical_error','numerical_error'])
        for channel in ('u','clk'):
            rows,boxes=trace();rows[5][channel]+=.001
            with self.subTest(channel=channel):self.assert_all(evaluate(rows,boxes),'input_mismatch')

    def test_model_source_and_budget_substitution_refused(self):
        rows,boxes=trace()
        for key in ('source','inputs','events_s'):
            card=copy.deepcopy(CARD)
            if key=='source':card[key]+='\n// substituted source'
            elif key=='inputs':card[key]['clk'][1][1]=.001
            else:card[key][0]+=1e-12
            with self.subTest(key=key),self.assertRaises(ValueError):evaluate(rows,boxes,card=card)
        for section in ('budgets','observation','tiers'):
            contract=copy.deepcopy(CONTRACT)
            if section=='budgets':contract[section]['time_serialization_ulps']*=2
            elif section=='observation':contract[section]['reference_fraction']*=2
            else:contract[section][0]['factor']*=2
            with self.subTest(section=section),self.assertRaises(ValueError):evaluate(rows,boxes,contract=contract)

    def test_missing_nonfinite_and_unordered_observations_stay_insufficient(self):
        for fault in ('short','missing_output','nonfinite','unordered'):
            rows,_=trace()
            if fault=='short':rows=rows[:2]
            elif fault=='missing_output':del rows[4]['y']
            elif fault=='nonfinite':rows[4]['clk']=float('inf')
            else:rows[4]['time']=rows[3]['time']
            with self.subTest(fault=fault):
                result=evaluate(rows);self.assert_all(result,'evidence_insufficient')
                self.assertEqual(result['strict_semantic_timing'],'unresolved')


if __name__=='__main__':unittest.main()
