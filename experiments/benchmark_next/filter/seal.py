"""Verify real harness archives and produce curated, identity-bound calibration."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.benchmark_first_batch.batch import summarize


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
        c['simulator_returncodes']=[case.get('returncode') for case in report['cases']]
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runs',type=Path,required=True);parser.add_argument('--solve-artifacts',type=Path,required=True);args=parser.parse_args()
    plan=json.loads(Path(__file__).with_name('run-plan.json').read_text());records=[]
    for e in plan:
        task=Path(e['task']).name;p=args.runs/task/e['variant']
        s=compact(p)
        expected=e['expected'];accepted=s['all_conditions_graded'] and (s['reference_passed'] if expected=='pass' else s['has_graded_failure'])
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
    report=dict(spec_issue=149,model_experiments_run=False,backend='Spectre',task_count=5,variant_count=len(records),condition_positions=sum(r['expected_conditions'] for r in records),all_author_expectations_matched=all(r['calibration_matched'] for r in records),records=records,historical_attempts=history,original_solve_receipts=json.loads((args.solve_artifacts/'receipt.json').read_text()),material_identities={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'benchmark/checkers/v2_next_filter.py',Path(__file__).with_name('build.py'),Path(__file__).with_name('run-plan.json'),Path(__file__).with_name('manifest.json'),Path(__file__).with_name('source-identities.json')]})
    Path(__file__).with_name('calibration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['task_count','variant_count','condition_positions','all_author_expectations_matched']}))
    if not report['all_author_expectations_matched']:raise SystemExit(1)
if __name__=='__main__':main()
