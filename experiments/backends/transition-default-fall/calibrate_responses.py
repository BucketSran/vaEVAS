"""Read-only calibration on five frozen real requests/responses and altered copies."""
import argparse,copy,hashlib,json
from pathlib import Path
from check import SIGNALS
from response import observations
CASES=['native-three-arg--sparse','native-three-arg--dense','native-four-arg--sparse','timer-native-pair/native-zero-period--1e-12','timer-native-pair/native-positive-period--1e-12']
def calibrate(directory):
 result={}
 for case in CASES:
  folder=directory/case;request=json.loads((folder/'request.json').read_text());response=json.loads((folder/'stdout.json').read_text());times=request['transient']['output_times'];nodes=sorted(['0']+SIGNALS)
  rows=observations(response,times,nodes);rejected=[]
  mutations={'changed_time':lambda d:d['transient']['times'].__setitem__(1,d['transient']['times'][2]),'reordered_times':lambda d:d['transient']['times'].reverse(),'missing_node':lambda d:d['nodes'].pop(),'short_voltage_row':lambda d:d['solutions'][0]['voltages'].pop(),'missing_solution':lambda d:d['solutions'].pop(),'nonfinite_voltage':lambda d:d['solutions'][0]['voltages'].__setitem__(0,float('nan'))}
  for name,mutate in mutations.items():
   altered=copy.deepcopy(response);mutate(altered)
   try:observations(altered,times,nodes)
   except ValueError:rejected.append(name)
   else:raise AssertionError('altered response accepted: '+case+'/'+name)
  result[case]={'valid_rows':len(rows),'request_sha256':hashlib.sha256((folder/'request.json').read_bytes()).hexdigest(),'response_sha256':hashlib.sha256((folder/'stdout.json').read_bytes()).hexdigest(),'rejected_mutations':rejected}
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.write_text(json.dumps(calibrate(a.directory),indent=2)+'\n')
