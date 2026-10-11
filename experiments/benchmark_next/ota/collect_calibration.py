"""Collect actual author calibration without copying private operator/log paths."""
import argparse,hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent

def collect(revision,replacement_revision=None):
    plan=json.loads((HERE/'calibration-plan.json').read_text());records=[]
    for variant in plan:
        campaign=replacement_revision if replacement_revision and variant['task'].endswith('v3-ota-data-model') and variant['variant']=='clear-recovery' else revision
        prepared=ROOT/'runs'/('ota-calibration-'+campaign)/Path(variant['task']).name/variant['variant']/'prepared'
        results=prepared/'results.json'
        if not results.exists():continue
        for result in json.loads(results.read_text()):
            archive=prepared/'remote'/result['job_id']/'archive/job.tar.gz'
            with tarfile.open(archive) as tf:
                name=next(n for n in tf.getnames() if n.endswith('/verifier/report.json'))
                raw=tf.extractfile(name).read();report=json.loads(raw)
            record=dict(campaign=campaign,task=Path(variant['task']).name,variant=variant['variant'],expected_pass=variant['expected_pass'],condition=result['condition_id'],job_id=result['job_id'],execution=result['result'].get('execution'),score=result['result'].get('score'),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),report_sha256=hashlib.sha256(raw).hexdigest())
            for key in ['runtime_sha256','parser_sha256','cases_sha256','contract_sha256','candidate_sha256','checker_sha256']:
                record[key]=report.get(key)
            record['cases']=[{key:case[key] for key in ['name','status','passed','metrics','netlist_sha256','candidate_files','support_sha256','returncode','waveform_sha256','waveform_rows','max_error_V','input_error_V','enable_error_V','windows','reports','stimulus_failure_count','first_stimulus_failure_s','dut_error_V','stimulus_error_V'] if key in case} for case in report['cases']]
            records.append(record)
    execution_manifest=HERE/'calibration-material-manifest.json'
    if not execution_manifest.exists():execution_manifest=HERE/'material-manifest.json'
    summary=dict(schema_version=1,revision=revision,calibration_plan_sha256=hashlib.sha256((HERE/'calibration-plan.json').read_bytes()).hexdigest(),planned_variants=len(plan),planned_conditions=len(plan)*3,actual_conditions=len(records),scored_conditions=sum(r['execution']=='ok' for r in records),execution_material_manifest_sha256=hashlib.sha256(execution_manifest.read_bytes()).hexdigest(),delivery_material_manifest_sha256=hashlib.sha256((HERE/'material-manifest.json').read_bytes()).hexdigest(),analysis_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),records=records)
    summary['superseded_records']=[]
    if replacement_revision:
        original=collect(revision)
        summary['superseded_records']=[r for r in original['records'] if r['task']=='v3-ota-data-model' and r['variant']=='clear-recovery']
        summary['replacement_revision']=replacement_revision
        summary['replacement_execution_manifest_sha256']=hashlib.sha256((HERE/'replacement-material-manifest.json').read_bytes()).hexdigest()
    summary['actual_author_conditions']=len(records)+len(summary['superseded_records'])
    summary['scored_author_conditions']=sum(r['execution']=='ok' for r in records+summary['superseded_records'])
    summary['complete']=summary['actual_conditions']==summary['planned_conditions'] and summary['scored_conditions']==summary['planned_conditions']
    groups=[]
    for variant in plan:
        observed=[r for r in records if r['task']==Path(variant['task']).name and r['variant']==variant['variant']]
        full=len(observed)==3 and all(r['execution']=='ok' for r in observed)
        # A wrong behavior may be dormant in one DUT condition (e.g. stale valid
        # when every slow-DUT round times out). Keep all scores in the denominator.
        accepted=full and (all(r['score']==1 for r in observed) if variant['expected_pass'] else any(r['score']==0 for r in observed))
        groups.append(dict(task=Path(variant['task']).name,variant=variant['variant'],expected_pass=variant['expected_pass'],complete=full,expectation_met=accepted,conditions=[dict(condition=r['condition'],score=r['score']) for r in observed]))
    summary['variant_acceptance']=groups
    summary['expectations_match']=summary['complete'] and all(g['expectation_met'] for g in groups)
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--revision',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--replacement-revision');a=p.parse_args();a.output.write_text(json.dumps(collect(a.revision,a.replacement_revision),indent=2)+'\n')
