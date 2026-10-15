"""Verify real harness archives and produce curated, identity-bound calibration."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import math
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.benchmark_first_batch.batch import summarize
sys.path.insert(0,str(ROOT/"benchmark/material/historyref/legacy-authoring/checkers"))
from adc_linearity import read_psf


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def compact(prepared):
    summary=summarize(prepared)
    for c in summary['conditions']:
        archive=Path(c.pop('archive'))
        c['archive_sha256']=sha(archive)
        with tarfile.open(archive) as stream:
            report=json.load(stream.extractfile('run/work/verifier/report.json'))
        c['spectre_version']=report.get('spectre_version')
        c['checker_sha256']=report.get('checker_files',{}).get('v2_next_filter.py')
        c['runtime_sha256']=report.get('runtime_sha256')
        c['parser_sha256']=report.get('parser_sha256')
        c['simulator_returncodes']=[case.get('returncode') for case in report['cases']]
        if summary['task_id']=='v3-filter-sweep-measurement':
            plan=json.loads((Path(prepared)/'preparation.json').read_text())
            selected=next(x for x in plan['cases'] if x['condition_id']==c['condition_id'])
            case=json.loads((Path(selected['package'])/'tests/cases.json').read_text())[0]
            with tempfile.TemporaryDirectory(prefix='filter-seal-',dir=ROOT/'runs') as temporary:
                with tarfile.open(archive) as stream:
                    raw=stream.extractfile('run/work/verifier/'+case['name']+'/psf/tran.tran.tran').read()
                path=Path(temporary)/'waveform.psf';path.write_bytes(raw)
                if sha(path)!=report['cases'][0]['waveform_sha256']:raise ValueError('waveform identity mismatch')
                rows=read_psf(path)
            diagnostics=[];p=case['parameters']
            for check in report['cases'][0]['checks']:
                if 'measured_gain' not in check:continue
                idx=check['tone'];end=idx*p['slot']+p['settle']+p['window'];finish=(idx+1)*p['slot']
                held=[r for r in rows if end+2*case['step']<=r['time']<=finish-case['step']]
                diagnostics.append({'tone':idx,'gain_max_error':max(abs(r['gain']-check['measured_gain']) for r in held),'wrapped_phase_max_error':max(abs(math.atan2(math.sin(r['phase']-check['measured_phase']),math.cos(r['phase']-check['measured_phase']))) for r in held)})
            c['measurement_numerical_diagnostics']=diagnostics
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runs',type=Path,required=True);parser.add_argument('--solve-artifacts',type=Path,required=True);parser.add_argument('--baseline-health',type=Path,required=True);args=parser.parse_args()
    plan=json.loads(Path(__file__).with_name('run-plan.json').read_text());records=[]
    for e in plan:
        task=Path(e['task']).name;p=args.runs/task/e['variant']
        s=compact(p)
        expected=e['expected']
        compiled=all(c['simulator_returncodes'] and all(code==0 for code in c['simulator_returncodes']) for c in s['conditions'])
        accepted=compiled and s['all_conditions_graded'] and (s['reference_passed'] if expected=='pass' else s['has_graded_failure'])
        records.append(dict(task_id=task,variant=e['variant'],expected=expected,calibration_matched=accepted,**{k:v for k,v in s.items() if k!='task_id'}))
    # Keep the earlier complete executions and errors as historical attempts.
    history=[]
    for revision in ['r1','r2','r3','r4']:
        folder=ROOT/'runs'/('filter-next-'+revision)
        for p in sorted(folder.glob('v3-filter-*/*/preparation.json')):
            d=p.parent;prepared=json.loads(p.read_text());item=dict(revision=revision,task_id=prepared['task_id'],variant=d.name,criteria_sha256=prepared['criteria_sha256'],candidate_sha256=prepared['candidate']['candidate_sha256'],simulator_executed=False)
            if (d/'results.json').exists():
                results=json.loads((d/'results.json').read_text());item['results']=[dict(condition_id=r['condition_id'],job_id=r['job_id'],execution=r['result']['execution'],score=r['result'].get('score')) for r in results]
                item['simulator_executed']=any(r['result']['execution']!='dependency_unavailable' for r in results)
                item['archive_identities']=[sha(a) for a in d.glob('remote/*/archive/job.tar.gz')]
            else:item['status']='prepared_only_not_run'
            if revision=='r1':item['disposition']='old deployment rejected v3 before simulation; deployment profile corrected'
            elif revision=='r2' and prepared['task_id'] in ['v3-filter-programmable-lp','v3-filter-envelope']:item['disposition']='author compile error VACOMP-2340: reserved initial parameter renamed initval'
            elif revision=='r3':item['disposition']='prepared only; final sweep window qualification added before any launch'
            elif revision=='r4':item['disposition']='reference smoke; final matrix additionally checks report held until window end'
            history.append(item)
    baseline_health=compact(args.baseline_health)
    baseline_health['asset_sha256']=sha(ROOT/'benchmark/material/draftbench/batches/v3-01/tasks/v3-filter-programmable-lp/public/fixed_lp.va')
    entrypoints=json.loads((args.runs/'test-entry-help.json').read_text())
    task_ids={Path(e['task']).name for e in plan}
    if {e['task_id'] for e in entrypoints}!=task_ids or len(entrypoints)!=len(task_ids):
        raise ValueError('original test entrypoint coverage mismatch')
    for e in entrypoints:
        tests=ROOT/'benchmark/material/draftbench/batches/v3-01/tasks'/e['task_id']/'tests'
        if not e['original_test_sh_executed'] or e['returncode']!=0 or not e['import_completed']:
            raise ValueError('original test entrypoint did not import successfully')
        if e['test_sh_sha256']!=sha(tests/'test.sh') or e['verify_sha256']!=sha(tests/'verify.py'):
            raise ValueError('original test entrypoint identity mismatch')
    report=dict(baseline_health=baseline_health,spec_issue=149,model_experiments_run=False,backend='Spectre',task_count=5,variant_count=len(records),condition_positions=sum(r['expected_conditions'] for r in records),all_author_expectations_matched=all(r['calibration_matched'] for r in records),records=records,historical_attempts=history,original_solve_receipts=json.loads((args.solve_artifacts/'receipt.json').read_text()),material_identities={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'benchmark/material/historyref/legacy-authoring/checkers/v2_next_filter.py',Path(__file__).with_name('build.py'),Path(__file__).with_name('run-plan.json'),Path(__file__).with_name('manifest.json'),Path(__file__).with_name('source-identities.json')]})
    recovery=args.runs/'sweep-reference-recovery.log'
    if recovery.exists():
        state=json.loads((args.runs/'v3-filter-sweep-measurement/reference/sweep-2-job.json').read_text())
        report['transport_recovery']={'condition_id':state['condition_id'],'job_id':state['job_id'],'initial_failure':'SSH status query exceeded 30 seconds','same_job_id_recovered':any(c['job_id']==state['job_id'] and c['execution']=='ok' for r in records for c in r['conditions']),'recovery_log_sha256':sha(recovery)}
    report['completion_conditions_met']=report['all_author_expectations_matched'] and baseline_health['reference_passed']
    report['original_test_entrypoint_receipts']=entrypoints
    report['outcome_counts']={
        'positive_variants':sum(r['expected']=='pass' for r in records),
        'positive_conditions_passed':sum(c['score']==1 for r in records if r['expected']=='pass' for c in r['conditions']),
        'negative_variants_rejected':sum(r['expected']!='pass' and r['calibration_matched'] for r in records),
        'negative_conditions_failed':sum(c['score']==0 for r in records if r['expected']!='pass' for c in r['conditions']),
        'negative_conditions_passed':sum(c['score']==1 for r in records if r['expected']!='pass' for c in r['conditions']),
    }
    Path(__file__).with_name('calibration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['task_count','variant_count','condition_positions','all_author_expectations_matched','completion_conditions_met']}))
    if not report['completion_conditions_met']:raise SystemExit(1)
if __name__=='__main__':main()
