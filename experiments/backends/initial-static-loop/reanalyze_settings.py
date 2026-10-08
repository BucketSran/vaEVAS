"""Offline qualification repair; reuses fixed requests/responses, executes no kernel."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from analyze import ROOT, ARCHIVE, REQUIRED_MEMBERS, SOURCE, READBACK, sha, save, git
from settings_contract import qualify_settings

ORIGINAL='a6a1b0c754242e632c01732aac1993b98b5ce927'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection',type=Path,required=True)
    parser.add_argument('--prior-analysis',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    if git('diff','HEAD','--','evas/src','evas/rust_core/src','evas/rust_core/crates'):
        raise ValueError('uncommitted production changes prevent fixed-source reuse')
    from experiments.backends.evidence.archive import verify_archive_members
    from evas import Instance, compile_sources
    from evas.identity import inspect_identity
    members=verify_archive_members(args.collection,ARCHIVE,REQUIRED_MEMBERS)
    base=args.collection/'spectre-output';raw=base/'runs/initial-loop'
    manifest_map=json.loads((base/'FILE_MANIFEST.json').read_text())
    if not isinstance(manifest_map,dict) or not manifest_map: raise ValueError('empty output manifest')
    for name,identity in manifest_map.items():
        if members.get('spectre-output/'+name)!=identity: raise ValueError('manifest identity mismatch')
    fixture=ROOT/'evas/validation/cases/initial_static_loop'
    if sha(raw/'dut.va')!=SOURCE or sha(fixture/'dut.va')!=SOURCE: raise ValueError('source mismatch')
    for actual,expected in (('manifest.json','manifest.json'),('tb.scs','table.scs')):
        if (raw/actual).read_bytes()!=(fixture/expected).read_bytes(): raise ValueError('frozen input mismatch')
    original=git('show',ORIGINAL+':experiments/backends/initial-static-loop/evidence.json')
    evidence=json.loads(original)
    reused={}
    for name,identity in evidence['analysis_files'].items():
        path=args.prior_analysis/name
        if sha(path)!=identity['sha256'] or path.stat().st_size!=identity['bytes']:
            raise ValueError('prior analysis identity mismatch: '+name)
        reused[name]=identity
    reader_path=ROOT/'experiments/backends/paper/settings_readback.py'
    if reader_path.read_bytes()!=git('show',READBACK+':experiments/backends/paper/settings_readback.py'):
        raise ValueError('readback reader identity differs')
    spec=importlib.util.spec_from_file_location('shared_readback',reader_path)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    settings=reader.spectre((raw/'spectre.log').read_text(),(raw/'psf/tran.tran.tran').read_text())
    qualification=qualify_settings(settings)
    manifest=json.loads((fixture/'manifest.json').read_text())
    program=compile_sources({'dut.va':(fixture/'dut.va').read_text()},[Instance(**instance) for instance in manifest['instances']])
    public_program=json.loads(json.dumps(program.to_dict(),allow_nan=False))
    for label in ('canonical','sparse','dense','all-native-supplemental'):
        request=json.loads((args.prior_analysis/(label+'-request.json')).read_text())
        if public_program!=request['program']: raise ValueError('accepted program changed: '+label)
    closure={str(path.relative_to(ROOT)):sha(path) for path in sorted((ROOT/'evas/src/evas').glob('*.py'))}
    closure.update({str(path.relative_to(ROOT)):sha(path) for path in sorted((ROOT/'evas/rust_core').rglob('*.rs')) if 'target' not in path.parts})
    identity,error=inspect_identity(ROOT/'evas/rust_core/target/debug/evas-kernel')
    if error: raise error
    args.output.mkdir(parents=True,exist_ok=True)
    save(args.output/'settings-readback-pr109.json',settings)
    save(args.output/'settings-qualification.json',qualification)
    evidence['settings_reanalysis_status']=qualification['status']
    evidence['settings_reanalysis']=settings
    evidence['settings_qualification']=qualification
    evidence['offline_reanalysis']=dict(original_evidence_revision=ORIGINAL,
        original_evidence_sha256=__import__('hashlib').sha256(original).hexdigest(),
        reused_analysis_files=reused,prior_analysis='runs/initial-event-static-loop/actual-native-analysis-v4',
        new_simulator_calls=0,source_revision=git('rev-parse','HEAD').decode().strip(),
        production_changes='Resource diagnostic propagation and main PR114 diagnostic changes; accepted Program exactly equal for all four original requests.',
        program_equal_for_all_four_requests=True,current_kernel_identity=identity,
        current_kernel_sha256=sha(ROOT/'evas/rust_core/target/debug/evas-kernel'),current_production_source_closure=closure,
        public_program_sha256=__import__('hashlib').sha256(json.dumps(public_program,sort_keys=True,allow_nan=False).encode()).hexdigest(),
        preserved_numerical_execution_revision=evidence['tested_revision'],
        preserved_original_result=evidence['preserved_original_result'],
        settings_checker_identity={name:sha(Path(__file__).with_name(name)) for name in
            ('reanalyze_settings.py','settings_contract.py','test_settings_contract.py','analyze.py')},
        offline_files={path.name:dict(sha256=sha(path),bytes=path.stat().st_size) for path in sorted(args.output.glob('*.json'))})
    evidence['offline_reanalysis']['calibration_receipt']=dict(path='calibration.json',sha256=sha(Path(__file__).with_name('calibration.json')),tests=20)
    save(args.evidence,evidence)
    print(json.dumps(dict(status=qualification['status'],new_simulator_calls=0,reused_requests=4,program_equal=True)))


if __name__=='__main__':
    try: main()
    except ValueError as error:
        print(json.dumps(dict(status='ERROR',reason=str(error))),file=sys.stderr)
        raise SystemExit(2)
