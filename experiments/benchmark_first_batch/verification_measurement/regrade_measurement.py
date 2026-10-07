"""Regrade sealed Spectre observations; never run archived code or a simulator.

Only trusted canonical parser/runtime/checker are imported. Archived files are
read as bytes, their receipts are verified, and frozen cases must equal the
current cases before any evidence can be reused.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import tarfile
import sys
import tempfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def require_same_case(current, frozen):
    require(canonical(current) == canonical(frozen), 'current/frozen case values differ; refuse reuse')


def load_module(path, name):
    # Keep the canonical checkout read-only even without a caller-supplied -B.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SealedArchive:
    def __init__(self, path, receipt):
        self.path = path
        self.tar = tarfile.open(path, 'r:gz')
        self.members = {}
        total = 0
        for member in self.tar.getmembers():
            name = PurePosixPath(member.name)
            require(member.isfile() and not name.is_absolute() and '..' not in name.parts,
                    'unsafe nonregular archive member')
            require(member.name not in self.members, 'duplicate archive member')
            require(member.size <= 268435456, 'oversize archive member')
            total += member.size
            require(total <= 536870912, 'oversize archive inventory')
            self.members[member.name] = member
        require(path.stat().st_size == receipt['package']['bytes'], 'archive receipt byte count')
        require(digest(path.read_bytes()) == receipt['package']['sha256'], 'archive receipt SHA256')
        require(set(self.members) == set(receipt['members']), 'archive receipt inventory differs')
        self.verified = {}
        for name, member in self.members.items():
            hasher = hashlib.sha256()
            with self.tar.extractfile(member) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    hasher.update(chunk)
            record = {'sha256': hasher.hexdigest(), 'bytes': member.size}
            require(record == receipt['members'][name], 'archive member receipt mismatch: ' + name)
            self.verified[name] = record
        self.receipt = receipt

    def read(self, name):
        require(name in self.members, 'missing required archived member: ' + name)
        return self.tar.extractfile(self.members[name]).read()

    def json(self, name):
        return json.loads(self.read(name))

    def close(self):
        self.tar.close()


def inventory(archive, prefix):
    return {name[len(prefix):]: record for name, record in archive.verified.items()
            if name.startswith(prefix)}


def verify_seal(archive, wrapper):
    result = wrapper['result']
    completion = archive.json('completion.json')
    require(completion == archive.receipt['completion'], 'completion differs from archive receipt')
    require(completion['result'] == result == archive.json('run/result.json'), 'results.json differs from sealed result')
    for name, receipt in completion['artifacts'].items():
        require(archive.verified.get(name) == receipt, 'completion artifact mismatch: ' + name)
    for name, receipt in result['artifacts'].items():
        require(archive.verified.get('run/' + name) == receipt, 'result artifact mismatch: ' + name)
    identity = archive.json('run/identity.json')
    request = archive.json('request.json')
    require(request == archive.receipt['request'], 'request differs from archive receipt')
    require(request['job_id'] == wrapper['job_id'] and request['identity'] == identity, 'job identity differs')
    require(identity['backend'] == 'benchmark_spectre' and identity['purpose'] == 'final', 'not final Spectre evidence')
    package = archive.json('task-package/manifest.json')
    package_files = inventory(archive, 'task-package/')
    require(package_files == identity['package']['files'], 'package inventory differs from identity')
    require(digest(canonical(package_files)) == identity['package']['sha256'] == result['task_package_sha256'], 'package bundle identity')
    require(package == identity['package']['manifest'] == archive.json('run/work/manifest.json'), 'package manifest differs')
    require({k:v for k,v in package_files.items() if k != 'manifest.json'} == package['files'], 'manifest declared files differ')
    for name, receipt in package['files'].items():
        require(archive.verified.get('run/work/' + name) == receipt, 'working package differs: ' + name)
    candidate = archive.json('candidate/manifest.json')
    candidate_files = inventory(archive, 'candidate/')
    require(candidate_files == identity['candidate'], 'candidate bundle inventory differs')
    require({k[len('files/'):]:v for k,v in candidate_files.items() if k.startswith('files/')} == candidate['files'], 'candidate manifest files differ')
    core = {k:candidate[k] for k in ('task_id','task_version','files')}
    require(digest(canonical(core)) == candidate['candidate_sha256'] == result['candidate_sha256'], 'candidate bundle identity')
    require(all(candidate[k] == identity['candidate_manifest'][k] for k in core), 'candidate identity manifest differs')
    require(candidate['candidate_sha256'] == identity['candidate_manifest']['candidate_sha256'], 'candidate identity bundle differs')
    for key in ('task_id','task_version','criteria_sha256','condition_id'):
        require(package[key] == result[key], 'result/package identity field: ' + key)
    require(wrapper['condition_id'] == package['condition_id'], 'wrapper condition differs')
    return result, package, candidate


def regrade_one(directory, wrapper, root, modules, scratch):
    archive_path = directory / 'remote' / wrapper['job_id'] / 'archive/job.tar.gz'
    receipt_path = archive_path.with_name('receipt.json')
    require(archive_path.is_file() and receipt_path.is_file(), 'completed job lacks sealed archive')
    archive = SealedArchive(archive_path, json.loads(receipt_path.read_text()))
    try:
        result, package, candidate = verify_seal(archive, wrapper)
        require(result['execution'] == 'ok' and result['benchmark_status'] == 'completed', 'job is not a completed numerical execution')
        require(result['score'] in (0,1), 'missing binary original score')
        report = archive.json('run/work/verifier/report.json')
        require(report['status'] == 'completed' and len(report['cases']) == 1, 'not one completed frozen condition')
        old = report['cases'][0]
        require(old['status'] == 'graded' and old['name'] == wrapper['condition_id'], 'not a graded matching condition')
        require(report['reward'] == result['score'] == int(old['passed']), 'original score/report inconsistency')
        frozen_bytes = archive.read('run/work/tests/cases.json')
        require(digest(frozen_bytes) == report['cases_sha256'], 'report cases SHA256 differs')
        frozen = json.loads(frozen_bytes)
        require(len(frozen) == 1 and frozen[0]['name'] == old['name'], 'frozen case selection')
        case = frozen[0]
        task = root / 'benchmark/tasks' / package['task_id']
        current_cases = json.loads((task / 'tests/cases.json').read_text())
        matches = [c for c in current_cases if c['name'] == case['name']]
        require(len(matches) == 1, 'current case missing or duplicated; refuse reuse')
        require_same_case(matches[0],case)
        require(archive.read('task-package/tests/cases.json') == frozen_bytes, 'execution/frozen cases differ')
        require(archive.read('run/work/tests/contract.json') == (task / 'tests/contract.json').read_bytes(), 'current/frozen submission contract differs')
        bindings = {'contract_sha256':'contract.json','checker_sha256':'verify.py',
                    'runtime_sha256':'circuit_task.py','parser_sha256':'adc_linearity.py'}
        for key, name in bindings.items():
            require(report[key] == digest(archive.read('run/work/tests/' + name)), 'report source identity: ' + name)
        main_file = package['candidate_file']
        require(report['candidate_sha256'] == candidate['files'][main_file]['sha256'], 'report candidate file identity')
        for name, identities in old['candidate_files'].items():
            original = archive.read('run/work/candidate/' + name)
            executed = archive.read('run/work/verifier/' + old['name'] + '/' + name)
            require(digest(original) == candidate['files'][name]['sha256'] == identities['original_sha256'], 'original candidate identity')
            require(digest(executed) == identities['executed_sha256'], 'executed candidate identity')
            require(identities['output_translation']['inverse_verified'] and not identities['output_translation']['edits'] and original == executed,
                    'unexpected candidate translation in no-I/O measurement task')
        work_prefix = 'run/work/verifier/' + old['name'] + '/'
        require(digest(archive.read(work_prefix + 'tb.scs')) == old['netlist_sha256'] == digest(case['netlist'].encode()), 'executed netlist differs')
        for name, text in case.get('support',{}).items():
            require(archive.read(work_prefix + name) == text.encode(), 'executed support differs: ' + name)
        raw = archive.read(work_prefix + 'psf/tran.tran.tran')
        require(digest(raw) == old['waveform_sha256'], 'report raw waveform identity differs')
        raw_path = scratch / 'raw.psf'
        raw_path.write_bytes(raw)
        parser, runtime, checker = modules
        rows = parser.read_psf(raw_path)
        runtime.validate_rows(rows,case)
        require(len(rows) == old['waveform_rows'], 'raw waveform completeness row count differs')
        new = checker.evaluate(rows,case,None)
        require(type(new['passed']) is bool, 'checker returned nonboolean verdict')
        deltas = {}
        for key in ('expected_metrics','observed_metrics'):
            require(set(old.get(key,{})) == set(new.get(key,{})), 'metric fields differ: ' + key)
            deltas[key] = {name:new[key][name]-old[key][name] for name in new.get(key,{})}
        return {'task_id':package['task_id'],'variant':directory.name,'condition_id':case['name'],
                'job_id':wrapper['job_id'],'original_score':result['score'],'regraded_score':int(new['passed']),
                'original_failures':old.get('failures',[]),'regraded_failures':new.get('failures',[]),
                'metric_deltas':deltas,'old_metrics':{k:old[k] for k in deltas},'new_metrics':{k:new[k] for k in deltas},
                'archive_sha256':archive.receipt['package']['sha256'],'results_sha256':digest((directory/'results.json').read_bytes()),
                'report_sha256':digest(archive.read('run/work/verifier/report.json')),'waveform_sha256':digest(raw),
                'frozen_case_sha256':digest(frozen_bytes),'case_value_sha256':digest(canonical(case)),
                'candidate_bundle_sha256':candidate['candidate_sha256'],'candidate_file_sha256':report['candidate_sha256'],
                'old_measurement_checker_sha256':digest(archive.read('run/work/tests/first_batch_measurement.py')),
                'old_criteria_sha256':result['criteria_sha256'],'waveform_rows':len(rows),
                'verified_archive_members':len(archive.members)}
    finally:
        archive.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--canonical-root',type=Path,required=True)
    parser.add_argument('--input',type=Path,action='append',required=True,help='One measure-* directory with variant subdirectories')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=args.canonical_root.resolve();output=args.output.resolve()
    require(not output.exists(),'output must be a new file')
    paths=[root/'benchmark/checkers'/name for name in ('adc_linearity.py','circuit_task.py','first_batch_measurement.py')]
    modules=[load_module(path,'measurement_regrade_'+path.stem) for path in paths]
    records=[];pending=[]
    with tempfile.TemporaryDirectory(prefix='measurement-waveform-regrade-') as temporary:
        scratch=Path(temporary)
        for input_dir in args.input:
            require(input_dir.is_dir() and input_dir.name.startswith('measure-'),'input must be one measurement task directory')
            for directory in sorted(p for p in input_dir.iterdir() if p.is_dir()):
                results=directory/'results.json'
                if not results.exists():
                    pending.append({'task_id':input_dir.name,'variant':directory.name,'reason':'no results.json yet'});continue
                wrappers=json.loads(results.read_text())
                require(isinstance(wrappers,list) and wrappers,'results must be a nonempty array')
                for wrapper in wrappers:
                    records.append(regrade_one(directory,wrapper,root,modules,scratch))
    require(records,'no completed archived conditions')
    keys=[(r['task_id'],r['variant'],r['condition_id']) for r in records]
    require(len(set(keys))==len(keys),'duplicate task/variant/condition evidence')
    identity={path.name:digest(path.read_bytes()) for path in paths}
    report={'schema_version':1,'mode':'sealed_saved_waveform_regrade_no_simulation',
            'python_version':sys.version.split()[0],'python_implementation':sys.implementation.name,
            'canonical_identity':identity,
            'tool_sha256':digest(Path(__file__).read_bytes()),'records':records,'pending':pending,
            'conditions':len(records),'scores_unchanged':all(r['original_score']==r['regraded_score'] for r in records),
            'maximum_absolute_metric_delta':max(abs(d) for r in records for group in r['metric_deltas'].values() for d in group.values()),
            'invalid_zero_adc_and_empty_pll_ref':'row_tests_only_no_actual_VA_induction_claim'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('conditions','scores_unchanged','maximum_absolute_metric_delta','pending')}))


if __name__=='__main__':
    main()
