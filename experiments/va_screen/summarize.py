"""Summarize designated first-attempt Harbor jobs, retaining channel failures."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    run=args.run.resolve();records=[];infra=[]
    amendment_path=run/'channel-amendment.json'
    amendment=json.loads(amendment_path.read_text()) if amendment_path.exists() else None
    # Only the historical amended run used replacement job names.
    designated={label:amendment[f'scored_{label}_jobs'] if amendment else [label]
                for label in ['glm','codex']}
    for label,jobs in designated.items():
        for job in jobs:
            for trial in sorted((run/job).glob('va*')):
                generation=trial/'agent/generation.json';verification=trial/'verifier/report.json'
                if not generation.exists() or not verification.exists():
                    r=trial/'result.json'
                    infra.append(dict(channel=label,trial=str(trial.relative_to(run)),exception=json.loads(r.read_text()).get('exception_info') if r.exists() else 'unfinished'))
                    continue
                g=json.loads(generation.read_text());v=json.loads(verification.read_text())
                if v['reward'] is None:
                    infra.append(dict(channel=label,trial=str(trial.relative_to(run)),exception='verifier infrastructure error'))
                    continue
                task=trial.name.split('__')[0]
                candidate=trial/'agent/dut.va';prompt=trial/'agent/prompt.md'
                assert hashlib.sha256(candidate.read_bytes()).hexdigest()==g['candidate_sha256']==v['candidate_sha256'],trial
                assert hashlib.sha256(prompt.read_bytes()).hexdigest()==g['instruction_sha256'],trial
                harbor_result=json.loads((trial/'result.json').read_text())
                assert harbor_result['verifier_result']['rewards']['reward']==v['reward'],trial
                if label=='codex':
                    events=[json.loads(line) for line in (trial/'agent/stdout.jsonl').read_text().splitlines() if line.startswith('{')]
                    assert {e['item']['type'] for e in events if 'item' in e}<={'agent_message','reasoning','error'},trial
                    assert sum(e['type']=='turn.completed' for e in events)==1,trial
                else:
                    assert g['num_turns']==1,trial
                    assert not any(x.get('webSearchRequests',0) for x in g['model_usage'].values()),trial
                records.append(dict(task=task,channel=label,model=g['model_requested'],cli_version=g['cli_version'],
                    reward=v['reward'],status=v['status'],conditions=len(v['cases']),passed_conditions=sum(bool(c.get('passed')) for c in v['cases']),
                    elapsed_generation_s=g['elapsed_s'],usage=g.get('usage'),model_usage=g.get('model_usage'),
                    num_turns=g.get('num_turns'),tool_events=g.get('tool_events'),
                    instruction_sha256=g['instruction_sha256'],candidate_sha256=g['candidate_sha256'],
                    cases_sha256=v['cases_sha256'],checker_sha256=v['checker_sha256'],spectre_version=v.get('spectre_version'),
                    cases=[{k:c[k] for k in ['name','status','passed','bad_samples','bad_edge_checks','failures','waveform_sha256'] if k in c} for c in v['cases']],
                    trial=str(trial.relative_to(run)),remote_root=v['remote_root']))
    if amendment and 'codex' not in designated['codex']:
        # The original old-CLI job produced request rejections, not submissions.
        for trial in (run/'codex').glob('va*'):
            result=trial/'result.json'
            if result.exists():
                r=json.loads(result.read_text());infra.append(dict(channel='codex-old-cli',trial=str(trial.relative_to(run)),exception=r.get('exception_info')))
    assert len({(r['task'],r['channel']) for r in records})==len(records),'multiple submissions for one logical trial'
    for task in {r['task'] for r in records}:
        assert len({r['instruction_sha256'] for r in records if r['task']==task})==1,'models received different prompts'
    manifest=json.loads((run/'input-manifest.json').read_text());root=Path(__file__).resolve().parents[2]
    unchanged=all(hashlib.sha256((root/name).read_bytes()).hexdigest()==value for name,value in manifest.items())
    diagnostics=[]
    for directory in sorted((run/'diagnostics').glob('*')):
        patch=directory/'patch.json';report=directory/'verifier/report.json'
        if patch.exists() and report.exists():
            d=json.loads(report.read_text())
            diagnostics.append(dict(name=directory.name,patch=json.loads(patch.read_text()),
                counts_as_model_success=False,reward=d['reward'],candidate_sha256=d['candidate_sha256'],
                cases_sha256=d['cases_sha256'],checker_sha256=d['checker_sha256'],
                conditions=len(d['cases']),passed_conditions=sum(bool(c.get('passed')) for c in d['cases']),
                remote_root=d['remote_root']))
    result=dict(run_root=str(run),protocol=json.loads((run/'protocol.json').read_text()),frozen_inputs_unchanged=unchanged,
                analysis_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                channel_amendment=amendment,
                submission_identity_and_no_tool_audit=True,
                expected_submissions=12,graded_submissions=len(records),records=records,infrastructure_events=infra,
                human_authored_diagnostics=diagnostics)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Frozen inputs unchanged:',unchanged)
    for r in sorted(records,key=lambda x:(x['task'],x['channel'])):print(r['task'],r['channel'],r['reward'],f"{r['passed_conditions']}/{r['conditions']}")
    print('Graded',len(records),'/ 12; infrastructure events',len(infra))


if __name__=='__main__':main()
