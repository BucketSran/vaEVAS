import unittest

from check import NODES, assess, pair, parse_psf


def ideal():
    # Hand table independent of the checker expected() implementation.
    times=[0,.125,.25,.375,.5,.625,.75,.875,1]
    columns=dict(u=times, q1=[1]*4+[2]*5, q2=[3]*4+[4]*5, qc=[1]*4+[1.5]*5,
                 y1=[1,1.125,1.25,1.375,2.5,2.625,2.75,2.875,3],
                 z1=[1,1.375,1.75,2.125,3.5,3.875,4.25,4.625,5],
                 h1=[1.25,1.625,2,2.375,3.75,4.125,4.5,4.875,5.25],
                 y2=[3,3.25,3.5,3.75,5,5.25,5.5,5.75,6],
                 z2=[3,3.75,4.5,5.25,7,7.75,8.5,9.25,10],
                 h2=[3.25,3.625,4,4.375,5.75,6.125,6.5,6.875,7.25],
                 yc=[1,1.125,1.25,1.375,2,2.125,2.25,2.375,2.5])
    return [dict(time=str(t),voltages={n:str(columns[n][i]) for n in NODES}) for i,t in enumerate(times)]


class Calibration(unittest.TestCase):
    def test_independent_linear_integrals_and_timer_stages_pass(self):
        result = assess(ideal())
        self.assertEqual(result['formula_and_stage_status'],'P')
        self.assertEqual(result['strict_observation_status'],'P')
        self.assertEqual(pair(ideal(),ideal())['same_stage_values_compared'],99)

    def test_wrong_gain_history_offset_and_event_capture_fail(self):
        for node in ('y2','z1','h1','yc'):
            rows=ideal(); rows[5]['voltages'][node]=str(float(rows[5]['voltages'][node])+.01)
            with self.subTest(node=node):
                self.assertEqual(assess(rows)['formula_and_stage_status'],'F')
                self.assertEqual(pair(rows,ideal())['voltage_status'],'F')

    def test_observers_must_change_in_one_shared_stage(self):
        rows=ideal(); rows[4]['voltages']['q2']='3'
        self.assertFalse(assess(rows)['shared_observer_stage'])
        self.assertEqual(assess(rows)['formula_and_stage_status'],'F')

    def test_delayed_event_and_multiple_changes_are_not_hidden_by_oracle(self):
        rows=ideal(); rows[5]['voltages']=dict(u='.625',q1='1',q2='3',qc='1',y1='1.625',z1='2.875',h1='3.125',y2='4.25',z2='6.75',h2='5.125',yc='1.625')
        self.assertEqual(assess(rows)['formula_and_stage_status'],'F')

    def test_missing_initial_stop_and_anchor_remain_inconclusive(self):
        for rows in (ideal()[1:],ideal()[:-1],ideal()[:2]+ideal()[3:]):
            self.assertEqual(assess(rows)['strict_observation_status'],'I')

    def test_decimal_stop_overshoot_is_not_an_exact_stop(self):
        rows=ideal(); rows[-1]['time']='1.0000000000000002'
        result=assess(rows)
        self.assertEqual(result['formula_and_stage_status'],'P')
        self.assertEqual(result['exact_stop_status'],'I')
        self.assertEqual(result['exact_required_point_count'],8)

    def test_same_time_pre_and_post_stage_difference_is_visible(self):
        rows=ideal(); rows[4]['voltages']=dict(u='.5',q1='1',q2='3',qc='1',y1='1.5',z1='2.5',h1='2.75',y2='4',z2='6',h2='4.75',yc='1.5')
        self.assertEqual(assess(rows)['formula_and_stage_status'],'P')
        result=pair(rows,ideal())
        self.assertEqual(result['phase_status'],'I')
        self.assertEqual(len(result['phase_differences']),1)
        self.assertEqual(result['same_stage_values_compared'],88)

    def test_empty_pair_cannot_pass_without_values(self):
        with self.assertRaisesRegex(ValueError,"empty waveform"):
            assess([])
        for native,candidate in (([],[]),([],ideal()),(ideal(),[])):
            with self.subTest(native=len(native),candidate=len(candidate)):
                with self.assertRaisesRegex(ValueError,"empty native/candidate waveform"):
                    pair(native,candidate)

    def test_unqualified_pair_stage_does_not_pass_or_crash(self):
        rows=ideal(); rows[4]['voltages']['q2']='3'
        self.assertEqual(pair(rows,rows)['voltage_status'],'F')

    def test_malformed_missing_nonfinite_or_out_of_order_psf_rejects(self):
        block='\n'.join('"'+n+'" 0' for n in NODES)
        positive='HEADER\nVALUE\n"time" 0\n'+block+'\nEND'
        self.assertEqual(len(parse_psf(positive)),1)
        for text in (positive[:-3],positive.replace('"y1" 0','"y1" nan'),
                     positive.replace('"q1" 0\n',''),positive.replace('END','"time" -1\n'+block+'\nEND')):
            with self.subTest(text=text), self.assertRaises(ValueError): parse_psf(text)
