"""Independent finite-scan ADC oracle and bounded Spectre verifier, stdlib only.

Canonical source; task tests/verify.py is a byte-identical execution copy.
"""
import argparse
import bisect
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

M = 4096
T = 1e-6
T0 = 5*T
EDGE = 1e-9
STOP = T0 + M*T + T
V_ATOL = 2e-6
TIME_ATOL = .2e-9


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_psf(path):
    # Stream text so a large PSF does not coexist with a second split-lines copy.
    rows=[]; row=None; ended=False
    with Path(path).open() as stream:
        for line in stream:
            if line.strip()=='VALUE': break
        else: raise ValueError('missing PSF VALUE section')
        for line in stream:
            if line.strip()=='END':
                ended=True
                if any(tail.strip() for tail in stream): raise ValueError('trailing PSF data')
                break
            match=re.fullmatch(r'"([^\"]+)"\s+(\S+)',line.strip())
            if not match: raise ValueError('unsupported PSF value')
            key,value=sys.intern(match[1]),float(match[2])
            if key == 'time':
                if row is not None: rows.append(row)
                row={'time':value}
            elif row is None or key in row: raise ValueError('duplicate signal or missing time')
            else: row[key]=value
    if not ended: raise ValueError('incomplete PSF')
    if row is not None: rows.append(row)
    return rows


def evaluate(rows, case, csv_path, trace_path=None):
    names={'time','vin','clk','done'}|{f'd{i}' for i in range(8)}
    if len(rows)<2 or any(not names.issubset(r) for r in rows):
        raise ValueError('missing waveform signals')
    if any(not math.isfinite(v) for r in rows for v in r.values()):
        raise ValueError('nonfinite waveform')
    ts=[r['time'] for r in rows]
    if any(a>=b for a,b in zip(ts,ts[1:])): raise ValueError('non-increasing waveform times')
    if abs(ts[0])>1e-15 or abs(ts[-1]-STOP)>1e-12: raise ValueError('incomplete transient interval')
    thresholds=case['thresholds']
    if len(thresholds)!=255 or sorted(thresholds)!=thresholds: raise ValueError('invalid ADC thresholds')
    failures=[]
    def fail(kind, **detail):
        if len(failures)<20: failures.append(dict(kind=kind,**detail))
    def value(t,node):
        i=max(0,min(bisect.bisect_right(ts,t)-1,len(rows)-2))
        a,b=rows[i],rows[i+1]
        return a[node]+(b[node]-a[node])*(t-ts[i])/(ts[i+1]-ts[i])
    def crossings(node,up,level=.5):
        found=[]
        for a,b in zip(rows,rows[1:]):
            if (a[node]<level<=b[node]) if up else (a[node]>level>=b[node]):
                found.append(a['time']+(b['time']-a['time'])*(level-a[node])/(b[node]-a[node]))
        return found
    def check_edges(node,up,expected,level=.5):
        actual=crossings(node,up,level)
        if len(actual)!=len(expected): fail('edge_count',node=node,up=up,expected=len(expected),actual=len(actual))
        elif any(abs(a-b)>TIME_ATOL for a,b in zip(actual,expected)):
            fail('edge_time',node=node,up=up)
    check_edges('clk',True,[T0+n*T+.25*T+.5*EDGE for n in range(M)])
    check_edges('clk',False,[T0+n*T+.50*T+.5*EDGE for n in range(M)])
    check_edges('done',True,[T0+(M-1)*T+.75*T+.5*EDGE])
    check_edges('done',False,[])
    # The 10% and 90% crossings distinguish 1 ns finite edges from sharp edges
    # with the same 50% crossing. The 0.2 ns envelope permits solver interpolation.
    for level in [.1,.9]:
        check_edges('clk',True,[T0+n*T+.25*T+level*EDGE for n in range(M)],level)
        check_edges('clk',False,[T0+n*T+.5*T+(1-level)*EDGE for n in range(M)],level)
        check_edges('done',True,[T0+(M-1)*T+.75*T+level*EDGE],level)

    for node,expected in [('vin',.5/M),('clk',0),('done',0)]:
        if abs(rows[0][node]-expected)>V_ATOL: fail('initial',node=node)
    # Check every saved input/logic point, including holding after completion.
    for row in rows:
        t=row['time']; n=min(M-1,max(0,math.floor((t-T0)/T+1e-9)))
        expected=(n+.5)/M
        offset=t-(T0+n*T)
        if n>0 and -1e-15<=offset<=EDGE+1e-15:
            if not (expected-1/M-V_ATOL<=row['vin']<=expected+V_ATOL): fail('input_transition')
        elif abs(row['vin']-expected)>V_ATOL: fail('input_hold',time=t)
        for node in ['clk','done']:
            if not (-V_ATOL<=row[node]<=1+V_ATOL): fail('logic_range',node=node)
    # Each input increment has its own relative 10%/90% crossing. Use a
    # running maximum only to ignore solver jitter within the voltage tolerance.
    input_values=[]; held=-math.inf
    for row in rows:
        if row['vin']<held-V_ATOL: fail('input_not_monotonic')
        held=max(held,row['vin']); input_values.append(held)
    for n in range(1,M):
        for level in [.1,.9]:
            threshold=(n-.5+level)/M
            i=bisect.bisect_right(input_values,threshold)-1
            if i<0 or i>=len(rows)-1 or input_values[i+1]==input_values[i]:
                fail('input_edge_missing',index=n)
            else:
                crossing=ts[i]+(ts[i+1]-ts[i])*(threshold-input_values[i])/(input_values[i+1]-input_values[i])
                if abs(crossing-(T0+n*T+level*EDGE))>TIME_ATOL:
                    fail('input_edge_time',index=n,level=level)
    for n in range(M):
        for phase in [.01,.25,.75]:
            if abs(value(T0+(n+phase)*T,'vin')-(n+.5)/M)>V_ATOL: fail('scan_point',index=n)
    for n in range(M):
        for phase,expected in [(.1,0),(.3,1),(.6,0),(.9,0)]:
            if abs(value(T0+(n+phase)*T,'clk')-expected)>V_ATOL:
                fail('clock_level',index=n,phase=phase)
    if abs(value(STOP,'clk'))>V_ATOL or abs(value(STOP,'done')-1)>V_ATOL:
        fail('final_hold')
    if failures: return dict(passed=False,status='candidate_failure',failures=failures)
    # The raw bus and the known quantizer are independent of candidate CSV.
    histogram=[0]*256
    for n in range(M):
        t=T0+(n+.75)*T; code=0
        for bit in range(8):
            voltage=value(t,f'd{bit}')
            if min(abs(voltage),abs(voltage-1))>V_ATOL: fail('unsettled_bus',index=n,bit=bit)
            if voltage>=.5: code |= 1<<bit
        expected=bisect.bisect_right(thresholds,(n+.5)/M)
        if code!=expected: fail('adc_truth',index=n,expected=expected,actual=code)
        histogram[code]+=1
    if failures: return dict(passed=False,status='environment_error',failures=failures)
    try:
        with Path(csv_path).open(newline='') as f:
            reader=csv.reader(f)
            if next(reader)!=['code','hits','dnl','inl']: raise ValueError('wrong CSV header')
            records=list(reader)
        if len(records)!=254: raise ValueError('expected 254 CSV records')
        internal=sum(histogram[1:255]); cumulative=0.
        for k,record in enumerate(records,1):
            if len(record)!=4 or record[0]!=str(k) or record[1]!=str(histogram[k]):
                raise ValueError(f'code/hits mismatch at code {k}')
            dnl=254*histogram[k]/internal-1; cumulative+=dnl
            for actual,expected in zip(map(float,record[2:]),[dnl,cumulative]):
                if not math.isfinite(actual) or abs(actual-expected)>1e-6:
                    raise ValueError(f'DNL/INL mismatch at code {k}')
        if trace_path is not None:
            with Path(trace_path).open(newline='') as f:
                trace=list(csv.reader(f))
            if len(trace)!=M+1 or trace[0] != ['index','time','code']:
                raise ValueError('expected 4096 sample records')
            for n,record in enumerate(trace[1:]):
                if len(record)!=3 or record[0]!=str(n): raise ValueError('sample index mismatch')
                sampled_time=float(record[1]); sampled_code=int(record[2])
                if not math.isfinite(sampled_time) or abs(sampled_time-(T0+(n+.75)*T))>1e-12:
                    raise ValueError('sample time mismatch')
                if sampled_code != bisect.bisect_right(thresholds,(n+.5)/M):
                    raise ValueError('sample code mismatch')
    except (OSError,ValueError,StopIteration) as exc:
        return dict(passed=False,status='candidate_failure',failures=[dict(kind='result',reason=str(exc))])
    return dict(passed=True,status='graded',samples=M,internal_samples=internal,endpoint_hits=[histogram[0],histogram[255]])


def adc_source(thresholds,delay):
    comparisons='\n'.join(f'            if (V(vin) >= {threshold:.17g}) code = code + 1;' for threshold in thresholds)
    drives='\n'.join(f'        V(dout[{i}]) <+ transition((code >> {i}) & 1, {delay:.17g}, 1n, 1n);' for i in range(8))
    return f'''`include "disciplines.vams"
module fixture_adc(vin,clk,dout);
input vin,clk;
output [7:0] dout;
electrical vin,clk;
electrical [7:0] dout;
integer code;
analog begin
    @(initial_step) code=0;
    @(cross(V(clk)-0.5,+1)) begin
        code=0;
{comparisons}
    end
{drives}
end
endmodule
'''


def netlist():
    return '''simulator lang=spectre
ahdl_include "dut.va"
ahdl_include "adc.va"
tester (vin clk d7 d6 d5 d4 d3 d2 d1 d0 done) adc_linearity_tester
adc (vin clk d7 d6 d5 d4 d3 d2 d1 d0) fixture_adc
options reltol=1e-6 vabstol=1e-9 iabstol=1e-12
tran tran stop=4.102m maxstep=20n errpreset=conservative
save vin clk done d0 d1 d2 d3 d4 d5 d6 d7
'''


def source_tokens(source):
    """Tokenize active VA bytes, preserving literal spans and excluding comments."""
    tokens=[]; i=0; identifier=re.compile(rb'[A-Za-z_$][A-Za-z0-9_$]*')
    while i<len(source):
        if source[i:i+1] in b' \t\r\n\f': i+=1; continue
        if source[i:i+2]==b'//':
            end=source.find(b'\n',i+2); i=len(source) if end<0 else end+1; continue
        if source[i:i+2]==b'/*':
            end=source.find(b'*/',i+2)
            if end<0: raise ValueError('unterminated comment')
            i=end+2; continue
        start=i
        if source[i]==34:
            i+=1
            while i<len(source) and source[i]!=34:
                if source[i] in [10,13]: raise ValueError('newline in string literal')
                if source[i]==92: i+=1
                i+=1
            if i>=len(source): raise ValueError('unterminated string')
            i+=1; kind='string'
        else:
            match=identifier.match(source,i)
            if match: i+=len(match[0]); kind='identifier'
            else: i+=1; kind='symbol'
        tokens.append((kind,source[start:i],start,i))
    return tokens


def source_contract(source):
    """Validate active calls and return only the two allowed fopen path spans.

    Arbitrary macros are unsupported: expansion could introduce file/system I/O.
    Standard includes are the only accepted preprocessing directives.
    """
    tokens=source_tokens(source); edits=[]; i=0
    allowed={b'"/work/output/linearity.csv"',b'"/work/output/samples.csv"'}
    while i<len(tokens):
        kind,value,start,end=tokens[i]
        if value==b'`':
            if i+2>=len(tokens) or tokens[i+1][1]!=b'include' or tokens[i+2][1] not in [b'"disciplines.vams"',b'"constants.vams"']:
                raise ValueError('only standard includes are supported; macros are prohibited')
            i+=3; continue
        if kind=='identifier' and value==b'$fopen':
            call=tokens[i+1:i+6]
            if len(call)!=5 or [t[1] for t in call][::2]!=[b'(',b',',b')'] or call[1][1] not in allowed or call[3][1]!=b'"w"':
                raise ValueError('only literal write-mode opens of the two result files are permitted')
            edits.append((call[1][2],call[1][3],call[1][1])); i+=6; continue
        if kind=='identifier' and (value in [b'$system',b'$fscanf',b'$fgets',b'$fread',b'$getenv',b'$popen'] or value.startswith(b'$readmem')):
            raise ValueError('external reads and system calls are prohibited')
        i+=1
    return edits


def relocate_output_paths(source,result_directory):
    """Replace approved path literal bytes; prove the inverse restores all bytes."""
    was_text=isinstance(source,str)
    original=source.encode('utf-8') if was_text else source
    spans=source_contract(original)
    destinations={f'/work/output/{name}':str(Path(result_directory).resolve()/name)
                  for name in ['linearity.csv','samples.csv']}
    pieces=[]; cursor=0; edits=[]
    for start,end,literal in spans:
        old_path=literal[1:-1].decode('ascii')
        replacement=json.dumps(destinations[old_path],ensure_ascii=False).encode('utf-8')
        pieces.extend([original[cursor:start],replacement])
        edits.append(dict(start=start,end=end,original_literal=literal.decode('ascii'),executed_literal=replacement.decode('utf-8')))
        cursor=end
    pieces.append(original[cursor:])
    executed=b''.join(pieces)
    # Independently undo the actual execution bytes at the recorded edited spans.
    restored=[]; original_cursor=executed_cursor=0
    for edit in edits:
        untouched=edit['start']-original_cursor
        restored.append(executed[executed_cursor:executed_cursor+untouched]); executed_cursor+=untouched
        replacement=edit['executed_literal'].encode('utf-8')
        if executed[executed_cursor:executed_cursor+len(replacement)]!=replacement: raise ValueError('relocation span mismatch')
        restored.append(edit['original_literal'].encode('ascii')); executed_cursor+=len(replacement); original_cursor=edit['end']
    restored.append(executed[executed_cursor:])
    if b''.join(restored)!=original: raise ValueError('relocation changed bytes outside allowed literals')
    receipt=dict(version='adc-output-paths-v2',mapping=destinations,edits=edits,inverse_verified=True)
    return (executed.decode('utf-8') if was_text else executed),receipt


def verify(candidate,output,case_name=None):
    output.mkdir(parents=True,exist_ok=True)
    cases_path=Path(__file__).with_name('cases.json')
    cases=json.loads(cases_path.read_text())
    if case_name is not None:
        cases=[case for case in cases if case['name']==case_name]
        if not cases: raise ValueError('unknown case selector')
    report=dict(candidate_sha256=sha(candidate),checker_sha256=sha(__file__),cases_sha256=sha(cases_path),cases=[])
    binary=os.environ.get('SPECTRE','spectre')
    source=candidate.read_bytes()
    try:
        source_contract(source)
        contract_error=None
    except ValueError as exc: contract_error=str(exc)
    if contract_error:
        report.update(status='submission_contract_violation',reward=0,reason=contract_error)
    elif not shutil.which(binary):
        report.update(status='infrastructure_error',reward=None,reason='Spectre unavailable')
    else:
        version=subprocess.run([binary,'-W'],capture_output=True,text=True,timeout=30)
        report['spectre_version']=version.stdout+version.stderr
        report['spectre_version_returncode']=version.returncode
        if version.returncode!=0 or not report['spectre_version'].strip():
            report.update(status='infrastructure_error',reward=None,reason='Spectre version probe failed')
            (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            (output/'reward.txt').unlink(missing_ok=True)
            return report
        for case in cases:
            work=output/case['name']; work.mkdir(exist_ok=False)
            shutil.copyfile(candidate,work/'candidate-original.va')
            results=work/'output';results.mkdir(mode=0o700)
            executed_source,path_translation=relocate_output_paths(source,results)
            (work/'dut.va').write_bytes(executed_source)
            (work/'adc.va').write_text(adc_source(case['thresholds'],case['delay']))
            (work/'tb.scs').write_text(netlist())
            argv=[binary,'-64','tb.scs','+log','spectre.log','-format','psfascii','-raw','psf','+lqtimeout','5','+mt=1']
            record=dict(name=case['name'],argv=argv,adc_sha256=sha(work/'adc.va'),netlist_sha256=sha(work/'tb.scs'),
                        original_source_sha256=sha(work/'candidate-original.va'),executed_source_sha256=sha(work/'dut.va'),
                        output_translation=path_translation)
            start=time.monotonic()
            try:
                with (work/'stdout.log').open('w') as stream:
                    run=subprocess.run(argv,cwd=work,stdout=stream,stderr=subprocess.STDOUT,timeout=90)
                log=(work/'stdout.log').read_text(errors='replace')
                record.update(returncode=run.returncode,elapsed_s=time.monotonic()-start,log_tail=log[-5000:])
                if re.search(r'license.*(?:not available|failed|unable)',log,re.I):
                    record.update(status='infrastructure_error',passed=False)
                elif run.returncode: record.update(status='simulation_failure',passed=False)
                else:
                    for name in ['linearity.csv','samples.csv']:
                        if (results/name).exists(): shutil.copyfile(results/name,work/name)
                    wave=work/'psf/tran.tran.tran'
                    verdict=evaluate(read_psf(wave),case,work/'linearity.csv',work/'samples.csv')
                    if verdict['status']=='candidate_failure':
                        verdict.update(status='graded',grading_status='candidate_failure')
                    record.update(verdict)
                    record['waveform_sha256']=sha(wave)
            except subprocess.TimeoutExpired: record.update(status='simulation_timeout',passed=False)
            except Exception as exc: record.update(status='checker_error',passed=False,reason=str(exc))
            report['cases'].append(record)
        infrastructure=any(c['status'] in ['checker_error','environment_error','infrastructure_error','simulation_failure','simulation_timeout'] for c in report['cases'])
        report.update(status='infrastructure_error' if infrastructure else 'completed',reward=None if infrastructure else int(all(c['passed'] for c in report['cases'])))
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'reward.txt').unlink(missing_ok=True)
    if report['reward'] is not None: (output/'reward.txt').write_text(str(report['reward'])+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=['ideal-fast','alternating-slow','missing-code','endpoint-shift'])
    args=parser.parse_args();report=verify(args.candidate.resolve(),args.output.resolve(),args.case)
    print(json.dumps(dict(status=report['status'],reward=report['reward'])))
    raise SystemExit(2 if report['reward'] is None else 0)
