import unittest
from settings_readback import ReadbackError, spectre, ngspice

LOG='''Global user options:
 reltol = 1e-5
 vabstol = 1e-7
 iabstol = 1e-12

Transient Analysis `tran': time = (0 s -> 6 us)
Important parameter values:
 reltol = 1e-6
 abstol(V) = 100 nV
 abstol(I) = 1 pA
 maxstep = 200 ps
 stop = 6 us
 method = traponly

'''
PSF='''HEADER
"analysis name" "tran"
"analysis type" "tran"
"reltol" 1e-6
"abstol(V)" 1e-7
"abstol(I)" 1e-12
"maxstep" 2e-10
"stop" 6e-6
"method" "traponly"
"tolerance.relative" 1e-5
TYPE
'''
SNAP='''* Current simulation options *
Integration Method = TRAPEZOIDAL
reltol (current) = {}
vntol (voltage) = 1e-7
abstol (current) = 1e-12
'''
NG=SNAP.format('0.001')+'Doing analysis at TEMP = 27\n'+SNAP.format('1e-5')
DECK='''.control
option
tran 2e-10 6e-6 0 2e-10
wrdata waveform.txt v(out)
option
quit
.endc
'''
class Calibration(unittest.TestCase):
 def test_spectre_scoped_positive(self):
  r=spectre(LOG,PSF)
  self.assertEqual(r['effective']['reltol']['value'],1e-6)
  self.assertEqual(r['global_user']['reltol']['value'],1e-5)
  self.assertEqual(r['psf_relative_metadata']['tolerance.relative']['value'],1e-5)
 def test_spectre_ambiguity(self):
  with self.assertRaises(ReadbackError): spectre(LOG.replace(' reltol = 1e-6',' reltol = 1e-6\n reltol = 2e-6'),PSF)
 def test_spectre_missing(self):
  with self.assertRaises(ReadbackError): spectre(LOG.replace(' maxstep = 200 ps\n',''),PSF)
 def test_spectre_malformed(self):
  for token in ['NaN','-1e-6','1e-6junk','inf']:
   with self.subTest(token=token),self.assertRaises(ReadbackError): spectre(LOG.replace(' reltol = 1e-6',' reltol = '+token),PSF)
 def test_spectre_multianalysis(self):
  with self.assertRaises(ReadbackError): spectre(LOG+"Transient Analysis `tran2': time = (0 s -> 6 us)\n",PSF)
 def test_psf_mismatch(self):
  for mutated in [PSF.replace('"tran"','"other"'),PSF.replace('"reltol" 1e-6','"reltol" 1e-5'),PSF.replace('"reltol" 1e-6','')]:
   with self.subTest(mutated=mutated),self.assertRaises(ReadbackError): spectre(LOG,mutated)
 def test_ng_scope_positive(self):
  r=ngspice(NG,DECK)
  self.assertEqual(r['effective']['reltol']['value'],1e-5)
  self.assertEqual(r['initial_snapshot']['reltol']['value'],0.001)
  self.assertEqual(r['invocation_controls']['maxstep_s']['value'],2e-10)
 def test_ng_ambiguity(self):
  with self.assertRaises(ReadbackError): ngspice(NG+SNAP.format('2e-5'),DECK)
 def test_ng_missing(self):
  with self.assertRaises(ReadbackError): ngspice(NG.replace('vntol (voltage) = 1e-7\n',''),DECK)
 def test_ng_malformed(self):
  with self.assertRaises(ReadbackError): ngspice(NG.replace('reltol (current) = 1e-5','reltol (current) = NaN'),DECK)
 def test_ng_multianalysis(self):
  with self.assertRaises(ReadbackError): ngspice(NG,DECK.replace('wrdata','tran 2e-10 6e-6 0 2e-10\nwrdata'))
 def test_ng_intervening_mutator(self):
  with self.assertRaises(ReadbackError): ngspice(NG,DECK.replace('wrdata','option reltol=1e-3\nwrdata'))
 def test_dimension_wrong(self):
  from settings_readback import numeric
  for token,dimension in [('1e-6V','dimensionless'),('1e-7A','voltage'),('1e-12V','current'),('200nV','time')]:
   with self.subTest(token=token),self.assertRaises(ReadbackError): numeric(token,dimension)
  with self.assertRaises(ReadbackError): spectre(LOG.replace('reltol = 1e-6','reltol = 1e-6V'),PSF)
  with self.assertRaises(ReadbackError): ngspice(NG.replace('reltol (current) = 1e-5','reltol (current) = 1e-5V'),DECK)
 def test_global_after_analysis(self):
  global_part,analysis_part=LOG.split("Transient Analysis",1)
  with self.assertRaises(ReadbackError): spectre('Transient Analysis'+analysis_part+global_part,PSF)
 def test_ng_mutable_commands(self):
  for command in ['alter R1 20','reset','source other.cir','let reltol=1e-3','set reltol=1e-3','run','echo unknown']:
   with self.subTest(command=command),self.assertRaises(ReadbackError): ngspice(NG,DECK.replace('option\ntran',command+'\noption\ntran'))
 def test_ng_command_suffix_mutation(self):
  for command in ['wrdata waveform.txt v(out); reset','pre_osdi dut.osdi; reset','set numdgt=17; reset']:
   deck=DECK.replace('wrdata waveform.txt v(out)',command) if command.startswith('wrdata') else DECK.replace('option\ntran',command+'\noption\ntran')
   with self.subTest(command=command),self.assertRaises(ReadbackError): ngspice(NG,deck)
 def test_ng_source_stepping_is_failure_diagnostic(self):
  result=ngspice('Note: Starting source stepping\nWarning: source stepping failed\n'+NG,DECK)
  self.assertEqual(result['effective']['reltol']['value'],1e-5)
 def test_ng_logged_mutator_rejected(self):
  with self.assertRaises(ReadbackError): ngspice(NG+'ngspice 2 -> reset\n',DECK)
 def test_ng_analysis_outside_snapshots(self):
  with self.assertRaises(ReadbackError): ngspice(NG.replace('Doing analysis at TEMP = 27\n','')+'Doing analysis at TEMP = 27\n',DECK)
 def test_ng_setting_change_after_snapshot(self):
  with self.assertRaises(ReadbackError): ngspice(NG,DECK.replace('quit','set reltol=1e-3\nquit'))
 def test_psf_malformed_method_quotes(self):
  with self.assertRaises(ReadbackError): spectre(LOG,PSF.replace('"method" "traponly"','"method" "traponly'))
 def test_psf_duplicate(self):
  with self.assertRaises(ReadbackError): spectre(LOG,PSF.replace('"reltol" 1e-6','"reltol" 1e-6\n"reltol" 1e-6'))
 def test_runner_preserves_scopes_mismatch_unknown(self):
  import json
  import tempfile
  from pathlib import Path
  from runner import effective_settings
  with tempfile.TemporaryDirectory() as tmp:
   work=Path(tmp); (work/'psf').mkdir()
   request={'reltol':1e-5,'vabstol_V':1e-7,'iabstol_A':1e-12,'stop_s':6e-6,'maxstep_s':2e-10,'spice_maxstep_s':2e-10}
   (work/'requested_settings.json').write_text(json.dumps(request))
   (work/'spectre.log').write_text(LOG); (work/'psf/tran.tran.tran').write_text(PSF)
   r=effective_settings(work,'spectre')
   self.assertEqual(r['status'],'I'); self.assertEqual(r['mismatches'],['reltol'])
   self.assertEqual(r['actual']['reltol'],1e-6)
   self.assertEqual(r['scoped_readback']['global_user']['reltol']['value'],1e-5)
   (work/'simulate.log').write_text(NG); (work/'tb.cir').write_text(DECK)
   r=effective_settings(work,'openvaf_r_ngspice')
   self.assertEqual(r['status'],'I'); self.assertEqual(r['actual']['reltol'],1e-5)
   self.assertTrue(r['actual']['maxstep'].startswith('unknown'))
   self.assertTrue(r['actual']['stop'].startswith('unknown'))
 def test_gnucap_parse_error_blocks_settings(self):
  import json
  import tempfile
  from pathlib import Path
  from runner import effective_settings
  with tempfile.TemporaryDirectory() as tmp:
   work=Path(tmp)
   (work/'requested_settings.json').write_text(json.dumps({'reltol':1e-5,'vabstol_V':1e-7,'iabstol_A':1e-12,'stop_s':6e-6,'maxstep_s':2e-10,'spice_maxstep_s':2e-10}))
   (work/'simulate.log').write_text("^ ? need )\n.options reltol=10.u vntol=100.n abstol=1.p\n")
   with self.assertRaises(ValueError): effective_settings(work,'gnucap_modelgen')
if __name__=='__main__': unittest.main()
