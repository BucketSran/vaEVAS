"""Reject plausible semantic mutants before freezing the model experiment."""
from pathlib import Path
import argparse
import json
from .remote import grade

ROOT=Path(__file__).resolve().parents[2]
MUTATIONS={
    'va01-and2':('&&','||','AND changed to OR'),
    'va02-sar-handshake':('if(d[step])n[step]=1;else p[step]=1;','if(d[step])p[step]=1;else n[step]=1;','CDAC polarity reversed'),
    'va03-zoom-timing':('SAR_num*SAR_interval','(SAR_num-1)*SAR_interval','SAR envelope shortened by one bit'),
    'va04-gain-calibration':('gainctrlcode = gainctrlcode-stepcode;','gainctrlcode = gainctrlcode+stepcode;','gain correction sign reversed'),
    'va05-dynamic-vco':('idt(integ_dir*(center_freq + vco_gain*V(vin)), 0)','idt(integ_dir*center_freq, 0)','control voltage ignored by phase integrator'),
    'va06-loaded-opamp':('I(vref, vout) <+ V(cout, vref)/rout;\n      I(vout, vref) <+ V(vout, vref)/rout;','V(vout, vref) <+ V(cout, vref);','output resistance omitted'),
}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--task',choices=list(MUTATIONS));args=parser.parse_args()
    output=ROOT/'runs/va-screen/mutations';summary=[]
    if args.task and (output/'summary.json').exists():
        summary=[r for r in json.loads((output/'summary.json').read_text()) if r['task']!=args.task]
    for name,(old,new,description) in MUTATIONS.items():
        if args.task and name!=args.task:continue
        task=ROOT/'benchmark/tasks'/name;text=(task/'solution/dut.va').read_text()
        assert old in text,(name,'mutation target absent')
        candidate=output/name/'dut.va';candidate.parent.mkdir(parents=True,exist_ok=True)
        candidate.write_text(text.replace(old,new,1))
        report=grade(task,candidate,candidate.parent/'verifier')
        semantic_rejection=report['reward']==0 and all(c['status']=='graded' for c in report['cases'])
        summary.append(dict(task=name,mutation=description,compiled_and_rejected=semantic_rejection,report=str(candidate.parent/'verifier/report.json')))
        print(name,description,semantic_rejection,flush=True)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not all(r['compiled_and_rejected'] for r in summary):raise SystemExit('mutation calibration failed')


if __name__=='__main__':main()
