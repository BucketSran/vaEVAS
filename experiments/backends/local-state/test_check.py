import unittest

from check import NODES, TIMES, assess, expected, pair, parse_psf


def ideal():
    return [dict(time=str(float(t)), voltages={n: str(float(v)) for n,v in expected(t,int(t>=.5)).items()}) for t in TIMES]


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
        rows=ideal(); rows[5]['voltages']={n:str(float(v)) for n,v in expected(TIMES[5],0).items()}
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
        rows=ideal(); rows[4]['voltages']={n:str(float(v)) for n,v in expected(TIMES[4],0).items()}
        self.assertEqual(assess(rows)['formula_and_stage_status'],'P')
        result=pair(rows,ideal())
        self.assertEqual(result['phase_status'],'I')
        self.assertEqual(len(result['phase_differences']),1)
        self.assertEqual(result['same_stage_values_compared'],88)

    def test_malformed_missing_nonfinite_or_out_of_order_psf_rejects(self):
        block='\n'.join('"'+n+'" 0' for n in NODES)
        positive='HEADER\nVALUE\n"time" 0\n'+block+'\nEND'
        self.assertEqual(len(parse_psf(positive)),1)
        for text in (positive[:-3],positive.replace('"y1" 0','"y1" nan'),
                     positive.replace('"q1" 0\n',''),positive.replace('END','"time" -1\n'+block+'\nEND')):
            with self.subTest(text=text), self.assertRaises(ValueError): parse_psf(text)
