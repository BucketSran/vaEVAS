"""Calibration uses a hand table, independently of checker formulas."""
import unittest
from check import assess, pair


def ideal():
    times=['0','0.125','0.25','0.375','0.5','0.625','0.75','0.875','1']
    columns={
        'y1':[1,1,81,81,1,1,1,1,1], 'q01':[0,0,40,40,0,0,0,0,0],
        'q11':[1,1,41,41,1,1,1,1,1], 'qlast1':[1,1,41,41,1,1,1,1,1],
        'y2':[33,33,213,213,33,33,33,33,33], 'q02':[10,10,70,70,10,10,10,10,10],
        'q12':[11,11,71,71,11,11,11,11,11], 'qlast2':[12,12,72,72,12,12,12,12,12],
    }
    return [dict(time=t,voltages=dict(u=t,**{n:str(v[i]) for n,v in columns.items()})) for i,t in enumerate(times)]


class Calibration(unittest.TestCase):
    def test_hand_stages_and_both_instances_pass(self):
        result=assess(ideal())
        self.assertEqual(result['formula_and_stage_status'],'P')
        self.assertEqual(result['strict_observation_status'],'P')
        self.assertEqual(pair(ideal(),ideal())['same_stage_values_compared'],81)
        self.assertEqual([len(v) for v in result['event_brackets'].values()],[2,2])

    def test_wrong_sum_and_each_observer_fail(self):
        for node in ('y1','q01','q11','qlast1','y2','q02','q12','qlast2','u'):
            rows=ideal(); rows[3]['voltages'][node]=str(float(rows[3]['voltages'][node])+0.01)
            with self.subTest(node=node):
                self.assertEqual(assess(rows)['formula_and_stage_status'],'F')
                self.assertEqual(pair(rows,ideal())['voltage_status'],'F')

    def test_mixed_element_stage_fails(self):
        rows=ideal(); rows[2]['voltages']['q11']='1'
        self.assertEqual(assess(rows)['formula_and_stage_status'],'F')

    def test_instance_parameter_aliasing_fails(self):
        rows=ideal(); rows[0]['voltages'].update(q02='0',q12='1',qlast2='2',y2='3')
        self.assertEqual(assess(rows)['formula_and_stage_status'],'F')

    def test_missing_pollution_or_repeated_restore_fails(self):
        for index,source in ((3,0),(6,2)):
            rows=ideal()
            for node in rows[index]['voltages']:
                if node!='u': rows[index]['voltages'][node]=rows[source]['voltages'][node]
            self.assertEqual(assess(rows)['formula_and_stage_status'],'F')

    def test_missing_initial_stop_or_anchor_is_inconclusive(self):
        for rows in (ideal()[1:],ideal()[:-1],ideal()[:1]+ideal()[2:]):
            self.assertEqual(assess(rows)['strict_observation_status'],'I')

    def test_decimal_stop_overshoot_does_not_supply_exact_stop(self):
        rows=ideal(); rows[-1]['time']='1.0000000000000002'; rows[-1]['voltages']['u']='1'
        result=assess(rows)
        self.assertEqual(result['formula_and_stage_status'],'P')
        self.assertEqual(result['exact_stop_status'],'I')
        self.assertEqual(result['exact_required_point_count'],8)

    def test_boundary_phase_difference_is_visible_per_instance(self):
        rows=ideal()
        for node in ('y1','q01','q11','qlast1'):
            rows[2]['voltages'][node]=rows[1]['voltages'][node]
        self.assertEqual(assess(rows)['formula_and_stage_status'],'P')
        result=pair(rows,ideal())
        self.assertEqual(result['phase_status'],'I')
        self.assertEqual(result['voltage_status'],'P')
        self.assertEqual(len(result['phase_differences']),1)
        self.assertEqual(result['same_stage_values_compared'],77)

    def test_empty_waveform_is_input_error(self):
        with self.assertRaisesRegex(ValueError,'empty'): assess([])
        for a,b in (([],[]),([],ideal()),(ideal(),[])):
            with self.assertRaisesRegex(ValueError,'empty'): pair(a,b)

    def test_missing_node_nonfinite_and_decreasing_time_are_input_errors(self):
        missing=ideal(); del missing[0]['voltages']['q01']
        nonfinite=ideal(); nonfinite[0]['voltages']['u']='nan'
        decreasing=ideal(); decreasing[1]['time']='-1'
        for rows in (missing,nonfinite,decreasing):
            with self.assertRaises(ValueError): assess(rows)

    def test_missing_candidate_time_fails_pair(self):
        self.assertEqual(pair(ideal(),ideal()[:-1])['voltage_status'],'F')

    def test_phase_difference_outside_window_is_failure(self):
        rows=ideal()
        for node in ('y1','q01','q11','qlast1'): rows[3]['voltages'][node]=rows[0]['voltages'][node]
        self.assertEqual(pair(rows,ideal())['voltage_status'],'F')
