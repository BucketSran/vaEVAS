"""Opt-in settings admission needs observed calibrated producer evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
from settings_readback import ReadbackError
from precision_report import spectre_fullprecision_settings, qualification

FIXTURE=ROOT/'experiments/backends/paper/fixtures/spectre-21.1.0.509-format-calibration.json'
class ProducerBinding(unittest.TestCase):
 def test_frozen_calibrated_producer_has_observed_not_requested_values(self):
  f=json.loads(FIXTURE.read_text())
  with tempfile.TemporaryDirectory() as tmp:
   w=Path(tmp);(w/'psf').mkdir();(w/'tb.scs').write_text(f['deck'])
   (w/'spectre.log').write_text(f['log']);(w/'psf/tran.tran.tran').write_text(f['psf_header'])
   req={'reltol':1e-5,'vabstol_V':1e-9,'iabstol_A':1e-13,'stop_s':2.1457672119140625e-6,'maxstep_s':2.9802322387695312e-8}
   (w/'requested_settings.json').write_text(json.dumps(req))
   tool={'version':'sub-version  21.1.0.509.isr12','binary_sha256':f['binary_sha256']}
   settings=spectre_fullprecision_settings(w,tool,frozen_deck_sha256=f['source_sha256']['sci_ascii_deck'])
   self.assertEqual(settings['actual']['maxstep'],2.980232238769531e-8)
   self.assertNotEqual(settings['actual']['maxstep'],req['maxstep_s'])
   record={'effective_settings':settings}
   q=qualification(w,'spectre',record,[],spectre_tool=tool)
   self.assertEqual(q['status'],'qualified')
   self.assertEqual(qualification(w,'spectre',record,[])['status'],'evidence_insufficient')
 def test_producer_rejects_wrong_binary_version_deck_and_case_claims(self):
  f=json.loads(FIXTURE.read_text())
  with tempfile.TemporaryDirectory() as tmp:
   w=Path(tmp);(w/'psf').mkdir();(w/'tb.scs').write_text(f['deck'])
   (w/'spectre.log').write_text(f['log']);(w/'psf/tran.tran.tran').write_text(f['psf_header'])
   (w/'requested_settings.json').write_text(json.dumps({'reltol':1e-5,'vabstol_V':1e-9,'iabstol_A':1e-13,'stop_s':2.1457672119140625e-6,'maxstep_s':2.9802322387695312e-8}))
   tool={'version':'sub-version  21.1.0.509.isr12','binary_sha256':f['binary_sha256']};digest=f['source_sha256']['sci_ascii_deck']
   for bad_tool in [{},{**tool,'binary_sha256':'0'*64},{**tool,'version':'sub-version 21.1.0.510'},{'verified':True}]:
    with self.subTest(tool=bad_tool),self.assertRaises(ReadbackError):spectre_fullprecision_settings(w,bad_tool,frozen_deck_sha256=digest)
   with self.assertRaises(ReadbackError):spectre_fullprecision_settings(w,tool,frozen_deck_sha256='0'*64)
   settings=spectre_fullprecision_settings(w,tool,frozen_deck_sha256=digest)
   settings['actual']['maxstep']=2.9802322387695312e-8
   self.assertEqual(qualification(w,'spectre',{'effective_settings':settings},[],spectre_tool=tool)['status'],'evidence_insufficient')
 def test_wrong_or_duplicate_producer_controls_are_not_admitted(self):
  import hashlib
  f=json.loads(FIXTURE.read_text())
  with tempfile.TemporaryDirectory() as tmp:
   w=Path(tmp);(w/'psf').mkdir();(w/'spectre.log').write_text(f['log']);(w/'psf/tran.tran.tran').write_text(f['psf_header'])
   tool={'version':'sub-version  21.1.0.509.isr12','binary_sha256':f['binary_sha256']}
   for old,new in [('digits=17','digits=6'),('digits=17','digits=17 digits=6'),('notation=sci','notation=eng'),('precision="%.17g"','precision="%.6g"'),('transres=1e-20','transres=1e-15'),('transres=1e-20','transres=1e-20 transres=1e-15'),('method=traponly','method=gear2only'),('errpreset=conservative','errpreset=moderate')]:
    deck=f['deck'].replace(old,new);(w/'tb.scs').write_text(deck)
    # Even a frozen modified deck cannot pretend to be the calibrated format.
    with self.subTest(new=new),self.assertRaises(ReadbackError):
     spectre_fullprecision_settings(w,tool,frozen_deck_sha256=hashlib.sha256(deck.encode()).hexdigest())
 def test_request_values_never_repair_or_change_observed_controls(self):
  f=json.loads(FIXTURE.read_text())
  with tempfile.TemporaryDirectory() as tmp:
   w=Path(tmp);(w/'psf').mkdir();(w/'tb.scs').write_text(f['deck']);(w/'spectre.log').write_text(f['log']);(w/'psf/tran.tran.tran').write_text(f['psf_header'])
   (w/'requested_settings.json').write_text(json.dumps({'reltol':1e-5,'vabstol_V':1e-9,'iabstol_A':1e-13,'stop_s':4e-6,'maxstep_s':1e-7}))
   tool={'version':'sub-version  21.1.0.509.isr12','binary_sha256':f['binary_sha256']}
   settings=spectre_fullprecision_settings(w,tool,frozen_deck_sha256=f['source_sha256']['sci_ascii_deck'])
   self.assertEqual(settings['actual']['stop'],2.145767211914062e-6)
   self.assertEqual(settings['actual']['maxstep'],2.980232238769531e-8)
   self.assertIn('maxstep',settings['mismatches'])
   self.assertIn('stop',settings['mismatches'])
   self.assertEqual(qualification(w,'spectre',{'effective_settings':settings},[],spectre_tool=tool)['status'],'evidence_insufficient')
