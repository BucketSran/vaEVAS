"""Freeze declared sample_hold causal probes; never transform submissions."""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'benchmark/tasks/v2-integrate-349-multichannel-readout'
OUT=Path(__file__).resolve().parent
VERSION='sample-hold-causal-v2'


def main():
    path=TASK/'tests/cases.json'
    healthy=[c for c in json.loads(path.read_text()) if 'architecture_gain' not in c]
    baseline=(TASK/'environment/public/baseline.va').read_text()
    probes=[]
    for gain in (0.75,0.6):
        for original in healthy[:1]:
            case=copy.deepcopy(original)
            case['name']=f'architecture-gain-{gain}-{original["name"]}'
            case['architecture_gain']=gain
            case['architecture_version']=VERSION
            case['support']['baseline.va']=baseline.replace('held = V(IN, VSS);',f'held = {gain} * V(IN, VSS);')
            for check in case['checks']:
                if 'out' in check:check['out']*=gain
            for window in case.get('hold_windows',[]):
                if window['signal']=='out':window['value']*=gain
            probes.append(case)
    path.write_text(json.dumps(healthy+probes,indent=2)+'\n')
    contract=TASK/'tests/contract.json'
    data=json.loads(contract.read_text());data['architecture_version']=VERSION
    contract.write_text(json.dumps(data,indent=2)+'\n')
    manifest_path=OUT/'manifest.json';manifest=json.loads(manifest_path.read_text())
    requests=manifest['calibration_requests']
    for variant,reason in [('architecture-rewrite','online four-frame state machine without sample_hold'),
                           ('architecture-bypass','four active baseline instances sunk; independent frame state drives outputs')]:
        directory=OUT/'candidates'/TASK.name/variant
        row=dict(task=str(TASK.relative_to(ROOT)),variant=variant,candidate_directory=str(directory.relative_to(ROOT)),expected='fail',semantic_behavior=reason,certification='pending-live-execution')
        requests[:]=[r for r in requests if not(r['task']==row['task'] and r['variant']==variant)]
        requests.append(row)
    manifest['architecture_349']={'version':VERSION,'healthy_conditions':len(healthy),'diagnostic_conditions':len(probes),'gains':[0.75,0.6],'calibration':'pending-live-execution','cases_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':main()
