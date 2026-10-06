"""Finite raw-observation checker, with no interpolation or DUT-derived oracle."""
import hashlib,json,math,re,sys,tempfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[3]
CONTRACTS=BASE/"evas/validation/cases/function_branches"

def read_psf(path):
 lines=[line.strip() for line in path.read_text().splitlines()]
 if lines[-1]!='END':raise ValueError('truncated PSF')
 rows=[];row=None
 for line in lines[lines.index('VALUE')+1:-1]:
  m=re.fullmatch(r'"([^"]+)"\s+(\S+)',line)
  if not m:raise ValueError('unexpected PSF value')
  name,value=m[1],float(m[2])
  if not math.isfinite(value):raise ValueError('nonfinite PSF')
  if name=='time':
   if row is not None:rows.append(row)
   row={'time':value}
  elif row is None or name in row:raise ValueError('missing time or duplicate signal')
  else:row[name]=value
 if row is not None:rows.append(row)
 if any(b['time']<=a['time'] for a,b in zip(rows,rows[1:])):raise ValueError('nonincreasing time')
 return rows

def assess(rows,contract):
 selected=[];maximum=0.
 for index,t in enumerate(contract['times']):
  hits=[row for row in rows if row['time']==t]
  if len(hits)!=1:raise ValueError('missing or duplicate exact query '+str(t))
  row=hits[0];wanted={n:v[index] for n,v in contract['node_voltages_V'].items()}
  if not wanted.keys()<=row.keys():raise ValueError('required output missing')
  errors={n:abs(row[n]-v) for n,v in wanted.items()};maximum=max(maximum,*errors.values())
  selected.append({'time_s':t,'actual_V':{n:row[n] for n in wanted},'expected_V':wanted,'max_abs_error_V':max(errors.values())})
 return {'status':'PASS' if maximum<=contract['absolute_tolerance_V'] else 'FAIL','exact_query_count':len(selected),'max_abs_error_V':maximum,'observations':selected}

def calibrate():
 c={'times':[0,.25],'node_voltages_V':{'y':[0,1]},'absolute_tolerance_V':1e-8}
 good=[{'time':0,'y':0},{'time':.25,'y':1}];assert assess(good,c)['status']=='PASS'
 bad=[{'time':0,'y':0},{'time':.25,'y':1.001}];assert assess(bad,c)['status']=='FAIL'
 for rows in (good[:1],good+[good[-1]], [{'time':0,'z':0},{'time':.25,'z':1}]):
  try:assess(rows,c);raise AssertionError('bad coverage accepted')
  except ValueError:pass
 with tempfile.TemporaryDirectory() as directory:
  path=Path(directory)/'control.psf';valid='VALUE\n"time" 0\n"y" 0\n"time" 0.25\n"y" 1\nEND\n';path.write_text(valid);assert assess(read_psf(path),c)['status']=='PASS'
  for raw in (valid.replace('END\n',''),valid.replace('"y" 0','"y" nan'),valid.replace('"y" 0','"y" 0\n"y" 1')):
   path.write_text(raw)
   try:read_psf(path);raise AssertionError('malformed PSF accepted')
   except ValueError:pass
 return {'status':'PASS','controls':['exact observations accept','wrong voltage reject','missing query reject','duplicate exact query reject','missing output reject','raw PSF accept','truncated/nonfinite/duplicate-signal PSF reject']}

if __name__=='__main__':
 result={'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'calibration':calibrate(),'cases':{}}
 for case in ('dc-table','continuous-pwl'):
  contract=json.loads((CONTRACTS/(case+'.expected.json')).read_text())
  path=Path(sys.argv[1])/case/'psf/tran.tran.tran'
  if not path.exists():result['cases'][case]={'status':'INCOMPLETE','reason':'actual raw waveform absent'};continue
  result['cases'][case]=assess(read_psf(path),contract)
 print(json.dumps(result,indent=2))
 raise SystemExit(0 if all(case["status"]=="PASS" for case in result["cases"].values()) else 1)
