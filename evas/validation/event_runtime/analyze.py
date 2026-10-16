"""Check one native simulator display line against frozen independent integers."""
from pathlib import Path
import argparse,json,math,re
D=Path(__file__).resolve().parent

def check(case,text):
    contract=json.loads((D/'CONTRACT.json').read_text())[case]
    lines=re.findall(r'IR23_RESULT[^\r\n]*',text)
    if len(lines)!=1:raise ValueError(f'expected exactly one result record, got {len(lines)}')
    pairs=re.findall(r'([A-Za-z][A-Za-z0-9]*)=([^\s]+)',lines[0])
    if len({k for k,v in pairs})!=len(pairs):raise ValueError('duplicate result fields')
    fields={k:float(v) for k,v in pairs}
    if fields.keys()!=({'te'}|contract['expected'].keys()):raise ValueError('missing or extra result fields')
    if not all(math.isfinite(v) for v in fields.values()):raise ValueError('nonfinite result')
    if abs(fields['te']-contract['event_time'])>contract['event_time_tolerance_s']:raise ValueError('callback time outside frozen tolerance')
    for key,value in contract['expected'].items():
        if fields[key]!=value:raise ValueError(f'{key}: {fields[key]} != exact integer {value}')
    return {'case':case,'status':'PASS','actual':fields,'expected_integers':contract['expected'],'scope':'finite runtime observer record only; not original CDS or waveform qualification'}

def self_test():
    contracts=json.loads((D/'CONTRACT.json').read_text())
    for case,c in contracts.items():
        good='IR23_RESULT te=0.5 '+' '.join(f'{k}={v}' for k,v in c['expected'].items())
        check(case,good)
        bads=[good+'\n'+good,good.replace('te=0.5','te=0.6'),good.replace('te=0.5','te=nan'),good+' extra=1',good.replace('acc='+str(c['expected']['acc']),'acc='+str(c['expected']['acc']+1)),good.replace(' i=',' omitted=')]
        for bad in bads:
            try:check(case,bad)
            except ValueError:pass
            else:raise AssertionError((case,bad))
    print('3 accept controls and18 reject controls PASS')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=['sequential','nested','quotient']);p.add_argument('--reference-log',type=Path);p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test:self_test()
    else:
        if not a.case or not a.reference_log:p.error('require --case and --reference-log')
        print(json.dumps(check(a.case,a.reference_log.read_text()),indent=2))
