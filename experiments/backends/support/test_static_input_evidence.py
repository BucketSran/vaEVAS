"""Calibration controls for the fixed exact-input evidence gate."""
from copy import deepcopy
import math
import unittest

from static_input_evidence import qualify, qualify_spectre


def fixture():
    card = {'group_id': 'F03', 'inputs': {'u': [[0., .5], [1., .5]]},
            'events': [], 'counter_channels': {}}
    program = {'schema_version': 19, 'nodes': ['0', 'u', 'y'],
               'states': [], 'events': [], 'operators': [],
               'contributions': [{'positive': 2, 'negative': 0,
                                  'rhs': {'op': 'affine', 'constant': 0.,
                                          'terms': [{'node': 1, 'coefficient': 1.}]}}]}
    rows = [{'time': t, 'u': .5, 'y': .5} for t in (0., .5, 1.)]
    response = {'schema_version': 19, 'nodes': program['nodes'],
                'solutions': [{'voltages': [0., .5, .5]} for _ in rows],
                'transient': {'times': [r['time'] for r in rows]},
                'observation_evidence': {'nodes': program['nodes'], 'initial_settled': True,
                                         'sample_origins': ['stateless_working_point']*3,
                                         'voltage_bounds_V': [[[0., 0.], [.5, .5], [.5, .5]] for _ in rows]}}
    return card, program, response, {'inputs': deepcopy(card['inputs'])}, rows


class StaticInputCalibration(unittest.TestCase):
    def test_reviewed_spectre_native_path(self):
        card, _, _, _, rows = fixture()
        card.update(source='fixed source', outputs=['y'])
        self.assertEqual(qualify_spectre(card, card['source'], rows,
                                      producer_qualified=True)['status'], 'qualified')
        for mutation in ('unreviewed', 'source', 'group', 'event', 'phase',
                         'short', 'missing', 'nonfinite', 'reverse', 'next_bit', 'nonconstant'):
            with self.subTest(mutation=mutation):
                c, r = deepcopy(card), deepcopy(rows)
                source, approved = c['source'], True
                if mutation == 'unreviewed': approved = False
                elif mutation == 'source': source = 'different source'
                elif mutation == 'group': c['group_id'] = 'F13'
                elif mutation == 'event': c['events'] = [{}]
                elif mutation == 'phase': c['phase_obligations'] = {'dc': {}}
                elif mutation == 'short': r = r[:2]
                elif mutation == 'missing': del r[1]['y']
                elif mutation == 'nonfinite': r[1]['y'] = math.nan
                elif mutation == 'reverse': r.reverse()
                elif mutation == 'next_bit': r[1]['u'] = math.nextafter(.5, 1.)
                elif mutation == 'nonconstant': c['inputs']['u'][1][1] = .6
                self.assertEqual(qualify_spectre(c, source, r, producer_qualified=approved)['status'], 'unknown')

    def test_physical_constant_input(self):
        self.assertEqual(qualify(*fixture(), producer_qualified=True)['status'], 'qualified')
        self.assertEqual(qualify(*fixture())['status'], 'unknown')

    def test_list_operands_do_not_hide_internal_dependencies(self):
        card, program, response, request, rows = fixture()
        leaf = deepcopy(program['contributions'][0]['rhs'])
        program['contributions'][0]['rhs'] = {'op': 'add', 'args': [leaf]}
        self.assertEqual(qualify(card, program, response, request, rows,
                                 producer_qualified=True)['status'], 'qualified')
        leaf['terms'][0]['node'] = 2
        self.assertEqual(qualify(card, program, response, request, rows,
                                 producer_qualified=True)['status'], 'unknown')
        program['contributions'][0]['rhs']['args'] = [{'operands': [leaf]}]
        self.assertEqual(qualify(card, program, response, request, rows,
                                 producer_qualified=True)['status'], 'unknown')

    def test_incomplete_proof_stays_unknown(self):
        mutations = [
            'next_bit', 'input_bound', 'empty_bound', 'wave_time', 'wave_output',
            'unsettled', 'historical_sample', 'missing_sample', 'schema', 'internal_input',
            'driven_contribution', 'event', 'operator', 'state', 'request', 'nonconstant',
            'nonfinite', 'group', 'phase', 'ground', 'signed_time',
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                card, program, response, request, rows = fixture()
                if mutation == 'next_bit': rows[1]['u'] = math.nextafter(.5, 1.)
                elif mutation == 'input_bound': response['observation_evidence']['voltage_bounds_V'][1][1] = [.499, .501]
                elif mutation == 'empty_bound': response['observation_evidence']['voltage_bounds_V'][1][1] = []
                elif mutation == 'wave_time': rows[1]['time'] = .5001
                elif mutation == 'wave_output': rows[1]['y'] = .6
                elif mutation == 'unsettled': response['observation_evidence']['initial_settled'] = False
                elif mutation == 'historical_sample': response['observation_evidence']['sample_origins'][1] = 'interpolated'
                elif mutation == 'missing_sample': response['solutions'].pop()
                elif mutation == 'schema': response['schema_version'] = 18
                elif mutation == 'internal_input': program['contributions'][0]['rhs']['terms'][0]['node'] = 2
                elif mutation == 'driven_contribution': program['contributions'][0]['positive'] = 1
                elif mutation == 'event': program['events'] = [{}]
                elif mutation == 'operator': program['operators'] = [{}]
                elif mutation == 'state': program['states'] = [{}]
                elif mutation == 'request': request['inputs']['u'][0][1] = .6
                elif mutation == 'nonconstant': card['inputs']['u'][1][1] = .6
                elif mutation == 'nonfinite': rows[1]['u'] = math.nan
                elif mutation == 'group': card['group_id'] = 'F13'
                elif mutation == 'phase': card['phase_obligations'] = {'dc': {}}
                elif mutation == 'ground':
                    response['solutions'][1]['voltages'][0] = 1.
                    response['observation_evidence']['voltage_bounds_V'][1][0] = [1., 1.]
                elif mutation == 'signed_time': request['inputs']['u'][0][0] = -0.
                self.assertEqual(qualify(card, program, response, request, rows, producer_qualified=True)['status'], 'unknown')
