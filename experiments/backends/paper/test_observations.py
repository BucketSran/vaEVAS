import unittest
from observations import normalize_observation

CARD = {'id':'fixture','observables':['in','count'], 'stop_T':0.0004,
        'observation_windows':[{'center_T':0.0002,'start_T':0.00018,'end_T':0.00022,'max_gap_s':2e-11}]}
CONTRACT = {'sample_gap_s':2e-10,'required_observation_error':{'time_s':1e-11,'voltage_V':5e-5},'input_error_V':1e-5}

class ObservationContracts(unittest.TestCase):
    def test_dense_interpolated_counter_cannot_become_native_evidence(self):
        rows=[{'time':t,'in':0.4,'count':1} for t in (0,1.8e-10,2e-10,2.2e-10,4e-10)]
        q={'time_error_s':0,'voltage_error_V':0,'input_error_V':0,'qualified':True,
           'source_validated':True,'input_bounds_qualified':True,'evidence':['fixture exact export'],
           'interpolation_error_bound_V':0}
        result=normalize_observation(CARD,'evas',rows,['interpolated']*5,q,contract=CONTRACT)
        self.assertFalse(result['qualification']['native_counters'])
        self.assertEqual(result['rows'],rows)
        self.assertEqual(result['metadata']['exact_boundary_rows'],[2])

    def test_missing_uncertainty_never_inferred_from_native_grid(self):
        rows=[{'time':t,'in':0.4,'count':1} for t in (0,1.8e-10,2e-10,2.2e-10,4e-10)]
        result=normalize_observation(CARD,'spectre',rows,['accepted']*5,contract=CONTRACT)
        self.assertFalse(result['qualification']['qualified'])
        self.assertIsNone(result['qualification']['time_error_s'])

    def test_invalid_input_rows_are_preserved_and_flagged(self):
        rows=[{'time':0,'in':float('nan'),'count':0},{'time':0,'in':0,'count':0}]
        result=normalize_observation(CARD,'evas',rows,['accepted']*2,contract=CONTRACT)
        self.assertEqual(result['status'],'observation_invalid')
        self.assertEqual(len(result['rows']),2)

    def test_native_format_reader_preserves_raw_boundary_values(self):
        from observations import read_native
        from pathlib import Path
        import tempfile
        fixtures={
            'spectre':'HEADER\nVALUE\n"time" 0\n"phase" 1\n"time" 1e-6\n"phase" 0\nEND\n',
            'evas':'time,phase\n0,1\n1e-6,0\n',
            'openvaf_r_ngspice':'time v(phase)\n0 1\n1e-6 0\n',
            'gnucap_modelgen':'#Time v(phase)\n0 1\n1u 0\n'}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wave'
            for backend,text in fixtures.items():
                path.write_text(text)
                rows=read_native(path,backend)
                self.assertEqual(rows,[{'time':0,'phase':1},{'time':1e-6,'phase':0}])

    def test_empty_local_window_not_hidden_by_contained_point_filter(self):
        rows=[{'time':0,'in':0,'count':0},{'time':4e-10,'in':0,'count':0}]
        result=normalize_observation(CARD,'evas',rows,['accepted']*2,contract=CONTRACT)
        self.assertAlmostEqual(result['metadata']['local_windows'][0]['max_gap_s'],4e-11,delta=1e-25)
        self.assertFalse(result['qualification']['local_gap_qualified'])

    def test_qualified_native_export_requires_unchanged_role_certificates(self):
        import hashlib
        from pathlib import Path
        import tempfile
        rows=[{'time':t,'in':0.4,'count':1} for t in (0,1.8e-10,2e-10,2.2e-10,4e-10)]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'export-proof.txt'
            path.write_text('Synthetic exact fixture certificate; not backend evidence.\n')
            certificate={'method':'exact fixture construction','artifact_path':str(path),
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            q={'time_error_s':0,'voltage_error_V':0,'input_error_V':0,'qualified':True,
               'source_validated':True,'input_bounds_qualified':True,
               'qualification_evidence':{r:certificate for r in ('source','time','voltage','inputs','native_counters')}}
            result=normalize_observation(CARD,'evas',rows,['accepted']*5,q,contract=CONTRACT)
            self.assertTrue(result['qualification']['qualified'])
            path.write_text('Changed proof')
            result=normalize_observation(CARD,'evas',rows,['accepted']*5,q,contract=CONTRACT)
            self.assertFalse(result['qualification']['qualified'])
