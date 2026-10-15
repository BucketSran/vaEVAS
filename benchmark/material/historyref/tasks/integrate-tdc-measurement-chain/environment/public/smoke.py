#!/usr/bin/env python3
"""Local public self-test only. Requires licensed Spectre; no hidden material."""
import argparse,json,os,re,shutil,subprocess,tempfile
from pathlib import Path
from waveform_check import evaluate

def read_psf(path):
    lines=path.read_text().splitlines();rows=[];row=None
    for line in lines[lines.index('VALUE')+1:]:
        if line.strip()=='END':break
        m=re.fullmatch(r'"([^"]+)"\s+(\S+)',line.strip())
        if not m:raise ValueError('unsupported PSF value')
        if m[1]=='time':
            if row is not None:rows.append(row)
            row={'time':float(m[2])}
        else:row[m[1]]=float(m[2])
    if row is not None:rows.append(row)
    return rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',type=Path,required=True);args=parser.parse_args()
    here=Path(__file__).resolve().parent;files=json.loads((here/'SUBMISSION.json').read_text())['candidate_files']
    binary=os.environ.get('SPECTRE','spectre')
    if not shutil.which(binary):raise SystemExit('Spectre unavailable: public self-test not run')
    for case in json.loads((here/'smoke_cases.json').read_text()):
        with tempfile.TemporaryDirectory(prefix='integration-smoke-') as temp:
            work=Path(temp)
            for relative in files:
                source=args.candidate.parent/relative;dest=work/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
            (work/'tb.scs').write_text(case['netlist'])
            for relative,text in case.get('support',{}).items():
                dest=work/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
            result=subprocess.run([binary,'-64','tb.scs','+log','spectre.log','-format','psfascii','-raw','psf','+mt=1'],cwd=work,capture_output=True,text=True,timeout=90)
            if result.returncode:raise SystemExit(result.stdout+'\n'+result.stderr)
            report=evaluate(read_psf(work/'psf/tran.tran.tran'),case,work);print(json.dumps(report,indent=2))
            if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
