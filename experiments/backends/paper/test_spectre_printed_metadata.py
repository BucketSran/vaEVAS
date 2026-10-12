"""Public readback calibration at the scoped log/PSF boundary."""
import unittest
import json
from pathlib import Path
from settings_readback import spectre, ReadbackError
from test_settings_readback import LOG, PSF

class PrintedMetadata(unittest.TestCase):
 def test_strict_mode_does_not_accept_rounded_header(self):
  log=LOG.replace('200 ps','2.980232238769531e-08 s').replace('6 us','2.145767211914062e-06 s')
  psf=PSF.replace('2e-10','2.98023e-08').replace('6e-6','2.14577e-06')
  with self.assertRaises(ReadbackError):spectre(log,psf)
 def test_rounding_alone_is_not_calibration(self):
  with self.assertRaises(ReadbackError):spectre(LOG,PSF,format_evidence={'verified':True})

 def test_actual_sci_producer_uses_log_values_and_printed_intervals(self):
  evidence=(Path(__file__).parent/'fixtures/spectre-21.1.0.509-format-calibration.json').read_bytes()
  fixture=json.loads(evidence)
  result=spectre(fixture['log'],fixture['psf_header'],format_evidence=evidence)
  self.assertEqual(result['effective']['maxstep_s']['value'],2.980232238769531e-8)
  self.assertNotEqual(result['effective']['maxstep_s']['value'],2.98023e-8)
  self.assertNotIn('psf_effective',result)
  self.assertEqual(result['psf_printed_intervals']['maxstep_s']['lower_s_or_native'],'2.980225E-8')
 def test_opt_in_rejects_scope_format_identity_and_value_corruption(self):
  evidence=(Path(__file__).parent/'fixtures/spectre-21.1.0.509-format-calibration.json').read_bytes()
  f=json.loads(evidence);log=f['log'];psf=f['psf_header']
  mutations=[(log,psf.replace('"maxstep" 2.98023e-08','"maxstep" 2.98024e-08')),
   (log.replace('2.980232238769531e-08 s','2.980250000000000e-08 s'),psf),
   (log.replace('2.980232238769531e-08 s','2.980232238769531e-08 V'),psf),
   (log.replace('2.980232238769531e-08 s','2.98023e-08 s'),psf),
   (log.replace('21.1.0.509.isr12','21.1.0.510'),psf),
   (log,psf.replace('21.1.0.509.isr12','21.1.0.510')),
   (log,psf.replace('"method" "traponly"','"method" "gear2only"')),
   (log.replace('maxstep =','maxstep = NaN\n    maxstep ='),psf),
   (log.replace('stop = 2.145767211914062e-06 s','stop = inf'),psf),
   (log+"Transient Analysis `other': time = (0 s -> 3 us)\n",psf),
   (log,psf.replace('"maxstep" 2.98023e-08','"maxstep" 2.98023e-08\n"maxstep" 2.98023e-08')),
   (log,psf.replace('"analysis name" "tran"','"analysis name" "other"')),
   (log,psf.replace('"analysis type" "tran"','"analysis type" "ac"')),
   (log,psf.replace('"simulator" "spectre"','"simulator" "other"')),
   (log,psf.replace('"PSFversion" "1.00"','"PSFversion" "1.1"')),
   (log,psf.replace('"tolerance.relative" 1.00000e-05','"tolerance.relative" 1.00000e-03')),
   (log,psf.replace('"maxstep" 2.98023e-08','"maxstep" 2.98023e-08 s')),
   (log,psf.replace('"maxstep" 2.98023e-08','"maxstep" 2.98e-08'))]
  for bad_log,bad_psf in mutations:
   with self.subTest(log=bad_log,psf=bad_psf),self.assertRaises(ReadbackError):
    spectre(bad_log,bad_psf,format_evidence=evidence)
 def test_changed_calibration_is_not_an_admission_flag(self):
  evidence=(Path(__file__).parent/'fixtures/spectre-21.1.0.509-format-calibration.json').read_bytes()
  f=json.loads(evidence)
  with self.assertRaises(ReadbackError):spectre(f['log'],f['psf_header'],format_evidence=evidence+b' ')
 def test_decimal_power_of_ten_lower_bin_is_narrower(self):
  from settings_readback import printed_interval
  interval=printed_interval(' maxstep = 1.000000000000000e-06 s','"maxstep" 1.00000e-06','maxstep_s')
  self.assertEqual(interval['lower_s_or_native'],'9.999995E-7')
  with self.assertRaises(ReadbackError):
   printed_interval(' maxstep = 9.999980000000000e-07 s','"maxstep" 1.00000e-06','maxstep_s')
