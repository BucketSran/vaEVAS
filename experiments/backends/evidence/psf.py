"""Lossless row/token adapter for real-valued ASCII PSF. No interpolation."""
import argparse, hashlib, json, math, re
from pathlib import Path
LINE=re.compile(r'"([^"\n]+)"\s+(\S+)')
def normalize(path,case):
    data=path.read_bytes();lines=data.decode().splitlines();clean=[line.strip() for line in lines]
    if clean.count('VALUE')!=1 or not clean or clean[-1]!='END':raise ValueError('missing VALUE or truncated PSF')
    begin=clean.index('VALUE')+1;raw=[];row=None;tokens=[];line_numbers=[]
    for i,line in enumerate(clean[begin:-1],begin+1):
        match=LINE.fullmatch(line)
        if not match:raise ValueError(f'unexpected PSF VALUE row at line {i}')
        name,token=match.groups()
        try:value=float(token)
        except ValueError:raise ValueError(f'invalid numeric token at line {i}')
        if not math.isfinite(value):raise ValueError(f'nonfinite token at line {i}')
        if name=='time':
            if row is not None:raw.append(row)
            row={'time':token};line_numbers.append(i)
        elif row is None or name in row:raise ValueError(f'duplicate signal/missing time at line {i}')
        else:row[name]=token
    if row is not None:raw.append(row)
    if not raw:raise ValueError('empty waveform')
    rows=[]
    for row in raw:
        missing=set(case['voltage_nodes'])-set(row)
        if missing:raise ValueError('missing explicit voltage nodes: '+','.join(sorted(missing)))
        token={'time':row['time'],'voltages':{n:row[n] for n in case['voltage_nodes']}}
        tokens.append(token);rows.append({'time':float(token['time']),'voltages':{n:float(v) for n,v in token['voltages'].items()}})
    return dict(rows=rows,decimal_tokens=tokens,raw_signal_tokens=raw,psf_value_line_numbers=line_numbers,origin='spectre_psfascii_unqualified_decimal_export',psf_sha256=hashlib.sha256(data).hexdigest(),limits='Native saved rows preserved including duplicate time records; tokens do not certify hidden callback order or exact physical endpoints.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('psf',type=Path);p.add_argument('case_json',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    case=json.loads(a.case_json.read_text());result=normalize(a.psf,case);result['case_sha256']=hashlib.sha256(a.case_json.read_bytes()).hexdigest();result['normalizer_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'rows':len(result['rows']),'output':str(a.output),'psf_sha256':result['psf_sha256']}))
