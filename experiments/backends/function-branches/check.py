"""Finite raw-observation checker, with no interpolation or DUT-derived oracle."""
import hashlib,json,math,re,sys,tempfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[3]
CONTRACTS=BASE/"evas/validation/cases/function_branches"

def read_psf(path):
 lines=[line.strip() for line in path.read_text().splitlines()]
 if not lines or lines[-1]!='END':raise ValueError('truncated PSF')
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
 times=contract['times'];nodes=contract['node_voltages_V'];tolerance=contract['absolute_tolerance_V']
 if not times or not nodes:raise ValueError('empty observation contract')
 if not math.isfinite(tolerance) or tolerance<=0:raise ValueError('invalid tolerance')
 if any(not math.isfinite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('invalid contract times')
 if any(len(values)!=len(times) or any(not math.isfinite(v) for v in values) for values in nodes.values()):raise ValueError('invalid contract voltages')
 selected=[];maximum=0.
 for index,t in enumerate(contract['times']):
  hits=[row for row in rows if row['time']==t]
  if len(hits)!=1:raise ValueError('missing or duplicate exact query '+str(t))
  row=hits[0];wanted={n:v[index] for n,v in contract['node_voltages_V'].items()}
  if not wanted.keys()<=row.keys():raise ValueError('required output missing')
  if any(not math.isfinite(row[n]) for n in wanted):raise ValueError('nonfinite observation')
  errors={n:abs(row[n]-v) for n,v in wanted.items()};maximum=max(maximum,*errors.values())
  selected.append({'time_s':t,'actual_V':{n:row[n] for n in wanted},'expected_V':wanted,'max_abs_error_V':max(errors.values())})
 return {'status':'PASS' if maximum<=contract['absolute_tolerance_V'] else 'FAIL','exact_query_count':len(selected),'max_abs_error_V':maximum,'observations':selected}

def assess_both(observations,contract):
 for i,row in enumerate(observations):
  if i>=len(contract['times']) or row['time_s']!=contract['times'][i]:raise ValueError('compact query grid mismatch')
  if row['expected_V']!={n:v[i] for n,v in contract['node_voltages_V'].items()}:raise ValueError('compact expected values differ from independent contract')
 if len(observations)!=len(contract['times']):raise ValueError('compact query count mismatch')
 spectre=assess([{'time':q['time_s'],**q['actual_V']} for q in observations],contract)
 evas=assess([{'time':q['time_s'],**q['EVAS_V']} for q in observations],contract)
 difference=max(abs(q['actual_V'][n]-q['EVAS_V'][n]) for q in observations for n in contract['node_voltages_V'])
 return {'status':'PASS' if spectre['status']==evas['status']=='PASS' and difference<=contract['absolute_tolerance_V'] else 'FAIL',
  'max_Spectre_expected_error_V':spectre['max_abs_error_V'],'max_EVAS_expected_error_V':evas['max_abs_error_V'],
  'max_EVAS_Spectre_difference_V':difference,'exact_query_count':len(observations)}

def check_compact(document):
 if set(document['cases'])!={'dc-table','continuous-pwl'}:raise ValueError('compact fixed case set mismatch')
 results={}
 for case,record in document['cases'].items():
  contract=json.loads((CONTRACTS/(case+'.expected.json')).read_text())
  for path,key in ((CONTRACTS/(case+'.expected.json'),'contract_sha256'),(CONTRACTS/(case+'.scs'),'deck_sha256'),(CONTRACTS/'dut.va','source_sha256')):
   if hashlib.sha256(path.read_bytes()).hexdigest()!=record[key]:raise ValueError('compact maintained input identity mismatch')
  result=assess_both(record['observations'],contract)
  for name in ('max_Spectre_expected_error_V','max_EVAS_expected_error_V','max_EVAS_Spectre_difference_V'):
   if result[name]!=record[name]:raise ValueError('compact declared maximum mismatch: '+case+'/'+name)
  results[case]=result
 return results

def calibrate():
 c={'times':[0,.25],'node_voltages_V':{'y':[0,1]},'absolute_tolerance_V':1e-8}
 good=[{'time':0,'y':0},{'time':.25,'y':1}];assert assess(good,c)['status']=='PASS'
 bad=[{'time':0,'y':0},{'time':.25,'y':1.001}];assert assess(bad,c)['status']=='FAIL'
 for rows in (good[:1],good+[good[-1]], [{'time':0,'z':0},{'time':.25,'z':1}]):
  try:assess(rows,c);raise AssertionError('bad coverage accepted')
  except ValueError:pass
 for contract in ({**c,'times':[]},{**c,'node_voltages_V':{}}):
  try:assess(good,contract);raise AssertionError('empty contract accepted')
  except ValueError:pass
 observations=[{'time_s':t,'actual_V':{'y':v},'EVAS_V':{'y':v},'expected_V':{'y':v}} for t,v in zip(c['times'],c['node_voltages_V']['y'])]
 assert assess_both(observations,c)['status']=='PASS'
 observations[-1]['EVAS_V']['y']+=.001;assert assess_both(observations,c)['status']=='FAIL'
 with tempfile.TemporaryDirectory() as directory:
  path=Path(directory)/'control.psf';valid='VALUE\n"time" 0\n"y" 0\n"time" 0.25\n"y" 1\nEND\n';path.write_text(valid);assert assess(read_psf(path),c)['status']=='PASS'
  for raw in (valid.replace('END\n',''),valid.replace('"y" 0','"y" nan'),valid.replace('"y" 0','"y" 0\n"y" 1'),valid.replace('"time" 0.25','"time" 0'),valid.replace('"time" 0.25','"time" -1'),valid.replace('"y" 0','bad row'),valid.replace('"time" 0.25','VALUE\n"time" 0.25')):
   path.write_text(raw)
   try:read_psf(path);raise AssertionError('malformed PSF accepted')
   except ValueError:pass
 return {'status':'PASS','controls':['exact observations accept','wrong voltage reject','missing query reject','duplicate exact query reject','missing output reject','raw PSF accept','truncated/nonfinite/duplicate-signal PSF reject','nonincreasing-time PSF reject','bad PSF row and second VALUE reject','empty times/nodes contract reject','compact both-backend accept and changed EVAS value reject']}

if __name__=='__main__':
 result={'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'calibration':calibrate(),'cases':{}}
 if len(sys.argv)==3 and sys.argv[1]=='--compact':
  result['analysis_kind']='compact arithmetic recheck; not raw execution verification'
  result['cases']=check_compact(json.loads(Path(sys.argv[2]).read_text()))
 elif len(sys.argv)==2:
  result['analysis_kind']='raw Spectre exact-observation check'
  for case in ('dc-table','continuous-pwl'):
   contract=json.loads((CONTRACTS/(case+'.expected.json')).read_text())
   path=Path(sys.argv[1])/case/'psf/tran.tran.tran'
   if not path.exists():result['cases'][case]={'status':'INCOMPLETE','reason':'actual raw waveform absent'};continue
   result['cases'][case]=assess(read_psf(path),contract)
 else:raise SystemExit('usage: check.py RAW_DIRECTORY | --compact comparison.json')
 print(json.dumps(result,indent=2))
 raise SystemExit(0 if result['cases'] and all(case['status']=='PASS' for case in result['cases'].values()) else 1)
