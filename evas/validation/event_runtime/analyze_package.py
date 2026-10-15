"""Recheck compact native extracts; never interpolate or run a simulator."""
from pathlib import Path
from fractions import Fraction as F
import argparse,hashlib,json,re
from analyze import check, self_test as record_self_test
D=Path(__file__).resolve().parent
TIMES=[F(i,4) for i in range(5)]
BUDGET=F('1e-7')

def exact_record(case,text):
    result=check(case,text)
    record=re.findall(r'IR23_RESULT[^\r\n]*',text)[0]
    tokens=dict(re.findall(r'([A-Za-z][A-Za-z0-9]*)=([^\s]+)',record))
    contract=json.loads((D/'CONTRACT.json').read_text())[case]
    for key,value in contract['expected'].items():
        if F(tokens[key])!=value:raise ValueError('decimal token differs from exact integer: '+key)
    if abs(F(tokens['te'])-F(str(contract['event_time'])))>F(str(contract['event_time_tolerance_s'])):
        raise ValueError('exact decimal event time exceeds tolerance')
    return result

def voltage(reference,dut):
    if [F(r['time']) for r in reference]!=TIMES or [F(r['time']) for r in dut]!=TIMES:
        raise ValueError('require all five exact native times in order, no duplicates or interpolation')
    errors={'spectre_vs_one':max(abs(F(r['u'])-1) for r in reference),
            'evas_vs_one':max(abs(F(r['u'])-1) for r in dut),
            'paired':max(abs(F(a['u'])-F(b['u'])) for a,b in zip(reference,dut))}
    if max(errors.values())>BUDGET:raise ValueError('source voltage exceeds100nV budget')
    return {k:float(v) for k,v in errors.items()}

def self_test():
    record_self_test()
    exact_record('sequential','IR23_RESULT te=0.5 n=3 i=3 acc=10 a0=1 a1=3 a2=6 a3=0')
    try:exact_record('sequential','IR23_RESULT te=0.5 n=3 i=3 acc=10.0000000000000001 a0=1 a1=3 a2=6 a3=0')
    except ValueError:pass
    else:raise AssertionError('rounded decimal integer error accepted')
    print('exact decimal integer:1accept/1reject PASS')
    good=[{'time':str(t),'u':'1'} for t in TIMES]
    assert voltage(good,good)==dict(spectre_vs_one=0.,evas_vs_one=0.,paired=0.)
    wrong=[dict(r) for r in good];wrong[2]['u']='1.000001'
    duplicate=[dict(r) for r in good];duplicate[2]['time']=duplicate[1]['time']
    nonfinite=[dict(r) for r in good];nonfinite[2]['u']='nan'
    for bad in [good[1:],good[:-1],wrong,duplicate,nonfinite]:
        try:voltage(bad,good)
        except (ValueError,ZeroDivisionError):pass
        else:raise AssertionError('invalid native rows accepted')
    print('source grid/voltage:1accept/5reject PASS')

def main():
    receipt=json.loads((D/'receipt.json').read_text())
    for name,expected in receipt['retained_files_sha256'].items():
        if hashlib.sha256((D/name).read_bytes()).hexdigest()!=expected:raise ValueError('retained file changed: '+name)
    results={}
    for case in ('sequential','nested','quotient'):
        base=D/case
        reference=exact_record(case,(base/'spectre-display.txt').read_text())
        dut=exact_record(case,(base/'evas-display.txt').read_text())
        if reference['actual']!=dut['actual']:raise ValueError('native/DUT integer or time mismatch')
        obs=json.loads((base/'observations.json').read_text());error=voltage(obs['spectre_native_decimal_rows'],obs['evas_saved_rows'])
        fields=json.loads((base/'effective-settings.json').read_text())['fields']
        if F(fields['reltol'])!=F('1e-9') or F(fields['abstol(V)'])!=BUDGET or F(fields['maxstep'])!=F(1,4) or F(fields['stop'])!=1:raise ValueError('required effective PSF setting mismatch')
        if fields['version']!='21.1.0.509.isr12':raise ValueError('reference version mismatch')
        results[case]={'status':'PASS','native_te_s':reference['actual']['te'],'exact_integer_fields':reference['expected_integers'],'max_voltage_error_V':error,'native_rows':5}
    print(json.dumps({'cases':results,'scope':'finite development comparisons only; not F integrated rerun, original CDS recovery or new Q'},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:self_test()
    else:main()
