import unittest
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'paper'))
from test_settings_readback import LOG, PSF
from settings_readback import ReadbackError, spectre
from primitives_audit import spectre_controls


class PrintedMetadataAudit(unittest.TestCase):
    def test_six_digit_metadata_preserves_strict_historical_readback(self):
        log=LOG.replace('200 ps','4.882812500000000e-10 s')
        psf=PSF.replace('"maxstep" 2e-10','"maxstep" 4.88281e-10')
        with self.assertRaises(ReadbackError): spectre(log,psf)
        audited=spectre_controls(log,psf)
        self.assertEqual(audited['effective']['maxstep_s']['value'],4.8828125e-10)
        self.assertEqual(audited['metadata_rounding'][0]['field'],'maxstep_s')

    def test_actual_disagreement_is_not_printed_rounding(self):
        log=LOG.replace('200 ps','4.882812500000000e-10 s')
        for value in ['4.88280e-10','4.88282e-10','4.8e-11']:
            with self.subTest(value=value),self.assertRaises(ReadbackError):
                spectre_controls(log,PSF.replace('"maxstep" 2e-10','"maxstep" '+value))

    def test_high_precision_stop_and_step_have_independent_rounding_checks(self):
        log = LOG.replace('6 us', '2.86102294921875 us').replace(
            '200 ps', '381.4697265625 ps')
        psf = PSF.replace('"stop" 6e-6', '"stop" 2.86102e-6').replace(
            '"maxstep" 2e-10', '"maxstep" 3.81470e-10')
        with self.assertRaises(ReadbackError):
            spectre(log, psf)
        audited = spectre_controls(log, psf)
        self.assertEqual(audited['effective']['stop_s']['value'], 2.86102294921875e-6)
        self.assertEqual({r['field'] for r in audited['metadata_rounding']},
                         {'stop_s', 'maxstep_s'})
        for stop in ('2.86101e-6', '2.86103e-6'):
            with self.subTest(stop=stop), self.assertRaises(ReadbackError):
                spectre_controls(log, psf.replace('2.86102e-6', stop))

    def test_rounding_does_not_hide_analysis_or_method_changes(self):
        log=LOG.replace('200 ps','4.882812500000000e-10 s')
        psf=PSF.replace('"maxstep" 2e-10','"maxstep" 4.88281e-10')
        for changed in [psf.replace('"tran"','"other"'),psf.replace('"traponly"','"gear2"'),
                        psf.replace('"stop" 6e-6','"stop" 7e-6')]:
            with self.subTest(changed=changed),self.assertRaises(ReadbackError):
                spectre_controls(log,changed)

    def test_small_printing_difference_is_retained_as_evidence(self):
        self.assertEqual(LOG.count('200 ps'),1)
        self.assertEqual(PSF.count('"maxstep" 2e-10'),1)
        log=LOG.replace('200 ps','4.882812500000000e-10 s').replace(
            ' reltol = 1e-6',' reltol = 1.00000000000001e-6')
        psf=PSF.replace('"maxstep" 2e-10','"maxstep" 4.88281e-10').replace(
            '"reltol" 1e-6','"reltol" 1.00000e-6')
        audited=spectre_controls(log,psf)
        self.assertEqual([r['field'] for r in audited['metadata_rounding']],
                         ['reltol','maxstep_s'])

    def test_float_rounding_cannot_hide_excess_at_decimal_boundary(self):
        psf=PSF.replace('"maxstep" 2e-10','"maxstep" 4.88281e-10')
        for value in ['4.88281500000000001e-10','4.88280499999999999e-10',
                      '4.882815000000000000000000000000000000001e-10']:
            with self.subTest(value=value),self.assertRaises(ReadbackError):
                spectre_controls(LOG.replace('200 ps',value+' s'),psf)


if __name__=='__main__': unittest.main()
