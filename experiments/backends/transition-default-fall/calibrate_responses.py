"""Read-only calibration on five frozen real requests/responses and altered copies."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
from check import BASE,SIGNALS
sys.path.insert(0,str(BASE.parents[2]/'evas/src'))
from evas import Instance,compile_sources
from evas.errors import KernelError
from response import observations
CASES=['native-three-arg--sparse','native-three-arg--dense','native-four-arg--sparse','timer-native-pair/native-zero-period--1e-12','timer-native-pair/native-positive-period--1e-12']
def calibrate(directory):
 result={}
 for case in CASES:
  folder=directory/case;request=json.loads((folder/'request.json').read_text());response=json.loads((folder/'stdout.json').read_text());times=request['transient']['output_times'];nodes=sorted(['0']+SIGNALS)
  name=folder.name.removeprefix('native-');source=(BASE/name/'dut.va') if not name.startswith(('zero-period','positive-period')) else BASE/'timer-controls'/name/'dut.va'
  instances=[Instance(i,'transition_default',{'r':'0'}|{n:i+'_'+n for n in ['simple','reverse','extend','mirror','qs','qr','qe','qm']},{'edge':tr,'delay':d}) for i,tr,d in [('a',.5,0),('b',1,.125)]]
  program=compile_sources({str(source):source.read_text()},instances)
  rows=observations(response,times,program);rejected=[]
  mutations={'changed_time':lambda d:d['transient']['times'].__setitem__(1,d['transient']['times'][2]),'reordered_times':lambda d:d['transient']['times'].reverse(),'missing_node':lambda d:d['nodes'].pop(),'short_voltage_row':lambda d:d['solutions'][0]['voltages'].pop(),'missing_solution':lambda d:d['solutions'].pop(),'nonfinite_voltage':lambda d:d['solutions'][0]['voltages'].__setitem__(0,float('nan'))}
  for name,mutate in mutations.items():
   altered=copy.deepcopy(response);mutate(altered)
   try:observations(altered,times,program)
   except KernelError:rejected.append(name)
   else:raise AssertionError('altered response accepted: '+case+'/'+name)
  result[case]={'valid_rows':len(rows),'request_sha256':hashlib.sha256((folder/'request.json').read_bytes()).hexdigest(),'response_sha256':hashlib.sha256((folder/'stdout.json').read_bytes()).hexdigest(),'rejected_mutations':rejected}
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.write_text(json.dumps(calibrate(a.directory),indent=2)+'\n')
