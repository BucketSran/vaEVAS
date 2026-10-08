import unittest
from settings_contract import qualify_settings


def hand_readback():
    # Independent table transcribed from frozen deck and original log/PSF.
    return {'global_user':{'reltol':{'value':1e-5},'vabstol_V':{'value':1e-7},'iabstol_A':{'value':1e-12}},
            'effective':{'reltol':{'value':1e-6},'vabstol_V':{'value':1e-7},'iabstol_A':{'value':1e-12},
                         'stop_s':{'value':1.},'maxstep_s':{'value':.025},'method':{'value':'traponly'}},
            'psf_effective':{'reltol':{'value':1e-6},'vabstol_V':{'value':1e-7},'iabstol_A':{'value':1e-12},
                             'stop_s':{'value':1.},'maxstep_s':{'value':.025},'method':{'value':'traponly'}},
            'psf_relative_metadata':{'tolerance.relative':{'value':1e-5}}}


class SettingsCalibration(unittest.TestCase):
    def test_frozen_request_and_declared_conservative_effective_pass(self):
        self.assertEqual(qualify_settings(hand_readback())['status'],'P')

    def test_wrong_requested_control_rejects(self):
        requested=dict(reltol=1e-4,vabstol_V=1e-7,iabstol_A=1e-12,stop_s=1.,maxstep_s=.025,
                       method='traponly',errpreset='conservative')
        with self.assertRaisesRegex(ValueError,'requested settings differ'):
            qualify_settings(hand_readback(),requested)

    def test_wrong_global_request_and_consistent_wrong_effective_reject(self):
        for key,value in (('stop_s',2.),('maxstep_s',.05),('method','gear2only'),
                          ('reltol',1e-5),('vabstol_V',1e-6),('iabstol_A',1e-11)):
            readback=hand_readback()
            for scope in ('effective','psf_effective'): readback[scope][key]['value']=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'frozen setting mismatch'):
                qualify_settings(readback)
        readback=hand_readback();readback['global_user']['reltol']['value']=1e-4
        with self.assertRaisesRegex(ValueError,'frozen setting mismatch'): qualify_settings(readback)

    def test_missing_nonfinite_or_boolean_control_rejects(self):
        for value in (float('nan'),float('inf'),True):
            readback=hand_readback();readback['effective']['stop_s']['value']=value
            with self.assertRaises(ValueError): qualify_settings(readback)
        readback=hand_readback();del readback['effective']['method']
        with self.assertRaisesRegex(ValueError,'missing frozen setting'): qualify_settings(readback)

    def test_shared_reader_internal_consistency_is_not_frozen_qualification(self):
        import importlib.util
        from pathlib import Path
        path=Path(__file__).resolve().parents[3]/'experiments/backends/paper/settings_readback.py'
        spec=importlib.util.spec_from_file_location('settings_readback',path)
        reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
        log="""Global user options:
    reltol = 1e-5
    vabstol = 1e-7
    iabstol = 1e-12

Transient Analysis `tran':
Important parameter values:
    stop = 1 s
    maxstep = 50 ms
    reltol = 1e-6
    abstol(V) = 100 nV
    abstol(I) = 1 pA
    method = traponly

"""
        psf="""HEADER
"analysis name" "tran"
"analysis type" "tran"
"stop" 1
"maxstep" .05
"reltol" 1e-6
"abstol(V)" 1e-7
"abstol(I)" 1e-12
"method" "traponly"
"tolerance.relative" 1e-5
TYPE
"""
        readback=reader.spectre(log,psf)
        self.assertEqual(readback['effective']['maxstep_s']['value'],.05)
        with self.assertRaisesRegex(ValueError,'frozen setting mismatch'):
            qualify_settings(readback)
