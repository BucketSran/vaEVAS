"""Reanalyze fixed initial-loop raw; only local EVAS execution, no remote calls."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

from check import NODES, assess, pair, rational
from settings_contract import qualify_settings

ROOT = Path(__file__).resolve().parents[3]
BEHAVIOR = 'dc177010d47fede4d276606e8e15d85ed2da0c13'
READBACK = '5e795852d18548a5389ffe2332fdb5708d4f8796'
ARCHIVE = '7b6aba27a2f7854513aa1e01f2d238d42306d6db65fba12e13a643b1c7e8daa8'
SOURCE = 'ff6f07aa84f74b68028019216c2e72685004c5f310350e9a97b7e809ccaf8a69'
# Protocol entrances are fixed here, never inferred from the untrusted manifest.
REQUIRED_MEMBERS = (
    'spectre-output/FILE_MANIFEST.json', 'spectre-output/TOOL_IDENTITY.json',
    *('spectre-output/runs/initial-loop/'+name for name in (
        'dut.va', 'manifest.json', 'tb.scs', 'RESULT.json',
        'simulate.json', 'spectre.log', 'psf/tran.tran.tran')),
)
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def execute(program, manifest, times, stop, sources, out, label):
    from evas import transient
    options = dict(manifest['EVAS'], stop=stop)
    request = dict(program=program.to_dict(), driven=list(sources), samples=[],
                   tolerances=dict(absolute=options['vabstol'],relative=options['reltol']),
                   transient=dict(pwl=list(sources.values()),output_times=times,stop=stop,max_step=options['max_step']))
    response = transient(program,sources,times,kernel=ROOT/'evas/rust_core/target/debug/evas-kernel',**options)
    save(out/(label+'-request.json'),request)
    save(out/(label+'-response.json'),response)
    rows = [dict(time=repr(time),voltages={n:repr(row['voltages'][response['nodes'].index(n)]) for n in NODES})
            for time,row in zip(times,response['solutions'])]
    return response, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection',type=Path,required=True,help='collected/spectre directory')
    parser.add_argument('--readback',type=Path,required=True,help='exact PR109 settings_readback.py')
    parser.add_argument('--output',type=Path,required=True,help='ignored local full analysis directory')
    parser.add_argument('--evidence',type=Path,required=True,help='compact curated JSON')
    parser.add_argument('--candidate-revision',default=BEHAVIOR,help='fixed tested production revision; no uncommitted production changes')
    args = parser.parse_args()
    from evas import Instance, compile_sources
    from evas.identity import inspect_identity
    from evas.ir import SCHEMA_VERSION
    assert not git('diff',args.candidate_revision,'--','evas/src','evas/rust_core/src','evas/rust_core/crates'), 'candidate production differs'
    shared = git('show',READBACK+':experiments/backends/paper/settings_readback.py')
    assert args.readback.read_bytes() == shared, 'wrong shared readback revision'
    spec = importlib.util.spec_from_file_location('shared_readback',args.readback)
    readback = importlib.util.module_from_spec(spec); spec.loader.exec_module(readback)
    collected=args.collection; base=collected/'spectre-output'; raw=base/'runs/initial-loop'
    from experiments.backends.evidence.archive import verify_archive_members
    from experiments.backends.evidence.psf import normalize
    from experiments.backends.evidence import archive as archive_helper, psf as psf_helper
    archive_members=verify_archive_members(collected,ARCHIVE,REQUIRED_MEMBERS)
    file_manifest=json.loads((base/'FILE_MANIFEST.json').read_text())
    if not isinstance(file_manifest,dict) or not file_manifest: raise ValueError('empty/invalid file manifest')
    for name, identity in file_manifest.items():
        if archive_members.get('spectre-output/'+name)!=identity: raise ValueError('file manifest identity mismatch: '+name)
    fixture=ROOT/'evas/validation/cases/initial_static_loop'
    assert sha(raw/'dut.va')==sha(fixture/'dut.va')==SOURCE
    assert (raw/'manifest.json').read_bytes()==(fixture/'manifest.json').read_bytes()
    assert (raw/'tb.scs').read_bytes()==(fixture/'table.scs').read_bytes()
    manifest=json.loads((fixture/'manifest.json').read_text())
    assert manifest['comparison']['voltage_absolute']==1e-7 and manifest['comparison']['voltage_relative']==1e-5
    original_result=json.loads((raw/'RESULT.json').read_text())
    psf=raw/'psf/tran.tran.tran'; log=raw/'spectre.log'
    settings=readback.spectre(log.read_text(),psf.read_text())
    settings_qualification=qualify_settings(settings)
    normalized=normalize(psf,{'voltage_nodes':list(NODES)})
    native=normalized['decimal_tokens']
    assert all(rational(b['time']) >= rational(a['time']) for a,b in zip(native,native[1:])), 'native time order decreases'
    args.output.mkdir(parents=True,exist_ok=True)
    save(args.output/'native-tokens.json',native)
    save(args.output/'settings-readback-pr109.json',settings)
    program=compile_sources({'dut.va':(fixture/'dut.va').read_text()},[Instance(**x) for x in manifest['instances']])
    canonical, canonical_rows=execute(program,manifest,manifest['times'],1,manifest['input'],args.output,'canonical')
    sparse, _=execute(program,manifest,[0,.375,1],1,manifest['input'],args.output,'sparse')
    within=sorted(set(manifest['times']+[float(row['time']) for row in native if float(row['time'])<=1]))
    dense, dense_rows=execute(program,manifest,within,1,manifest['input'],args.output,'dense')
    common=[]
    for time, row in zip(canonical['transient']['times'],canonical['solutions']):
        index=dense['transient']['times'].index(time)
        common.append(row==dense['solutions'][index])
    sparse_equal=all(sparse['solutions'][i]==canonical['solutions'][manifest['times'].index(time)] for i,time in enumerate([0,.375,1]))
    grid=dict(common_canonical_voltages_bitwise_equal=all(common), sparse_common_voltages_bitwise_equal=sparse_equal,
              common_canonical_states_equal=all(canonical['transient']['states'][i]==dense['transient']['states'][within.index(time)] for i,time in enumerate(manifest['times'])),
              event_records_equal=canonical['transient']['events']==dense['transient']['events']==sparse['transient']['events'],
              output_counts=[len(sparse['solutions']),len(canonical['solutions']),len(dense['solutions'])],
              accepted_steps=[r['transient']['accepted_steps'] for r in (sparse,canonical,dense)],
              discarded_trials=[r['transient']['discarded_trials'] for r in (sparse,canonical,dense)])
    times=sorted(set(float(row['time']) for row in native))
    stop=max(1.,times[-1])
    sources=manifest['input']
    if stop>1:
        sources={name:[*points,[stop,points[-1][1]]] for name,points in sources.items()}
    _, candidate_rows=execute(program,manifest,times,stop,sources,args.output,'all-native-supplemental')
    native_check=assess(native); candidate_check=assess(candidate_rows); canonical_check=assess(canonical_rows)
    native_pair=pair(native,candidate_rows)
    original_native=[row for row in native if rational(row['time'])<=1]
    original_pair=pair(original_native,dense_rows)
    tool=json.loads((base/'TOOL_IDENTITY.json').read_text())
    receipt=json.loads((raw/'simulate.json').read_text())
    match=re.search(r'Number of accepted tran steps\s*=\s*(\d+)',log.read_text())
    native_provenance=dict(parsed_saved_rows=len(native),accepted_steps=int(match[1]) if match else None,
                           count_matches_steps_plus_initial=bool(match and len(native)==int(match[1])+1),
                           evidence='Executed psfascii command, save 9 nodes, strobeoutput=all, skipdc=no, native q observer values and accepted-step count.',
                           qualification_limit='Count/deck/format do not certify arbitrary hidden callback stages, exact endpoint or exact-real time serialization.')
    if len(canonical['transient']['events'])!=4: raise ValueError('expected four EVAS event records')
    if canonical['transient']['states'][0]!=[0,1,10,11,12]: raise ValueError('EVAS initial element values mismatch')
    paths=[psf,log,raw/'RESULT.json',raw/'tb.scs',raw/'dut.va',raw/'manifest.json',raw/'simulate.json',base/'TOOL_IDENTITY.json',base/'FILE_MANIFEST.json']
    local_raw={str(p.relative_to(collected)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in paths}
    closure={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'evas/src/evas').glob('*.py'))}
    closure.update({str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'evas/rust_core').rglob('*.rs')) if 'target' not in p.parts})
    closure.update({name:sha(ROOT/name) for name in ('evas/pyproject.toml','evas/rust_core/Cargo.toml','evas/rust_core/Cargo.lock')})
    identity, identity_error=inspect_identity(ROOT/'evas/rust_core/target/debug/evas-kernel')
    if identity_error:
        raise identity_error
    evidence=dict(schema=1,scope='One actual Spectre configuration, two instances in one frozen DUT; not two configurations or complete #65/SAR closure.',
                  first_timeout=dict(archive_sha256='839b3b229878592fc8c85e0bfb597a1fd3a3ed19c171026d86042ec68c1ddbb0',status='compile timeout, no waveform; not numerical F'),
                  execution_condition='Warm-cache input retained from first lane; both N2 and N3 actually compiled again. Speedup cause unknown.',
                  feature_revision=BEHAVIOR,tested_revision=args.candidate_revision,IR=SCHEMA_VERSION,archive_sha256=ARCHIVE,verified_manifest_files=len(file_manifest),
                  archive_authentication=dict(verified_regular_members=len(archive_members),
                                              required_members=list(REQUIRED_MEMBERS), members=archive_members,
                                              helper_sha256=sha(Path(archive_helper.__file__)),
                                              helper_revision=git("log","-1","--format=%H","--","experiments/backends/evidence/archive.py").decode().strip(),
                                              psf_adapter_sha256=sha(Path(psf_helper.__file__))),
                  source_sha256=SOURCE,solver_controls=manifest['EVAS'],frozen_voltage_budget=dict(absolute=1e-7,relative=1e-5),
                  readback_revision=READBACK,readback_sha256=hashlib.sha256(shared).hexdigest(),settings_reanalysis_status=settings_qualification['status'],settings_reanalysis=settings,settings_qualification=settings_qualification,
                  preserved_original_result=original_result,raw_availability='local-only',
                  collection_workspace_relative='current/runs/issue-closure-20261008/initial-loop-reference-v2/collected/spectre',
                  raw_identities=local_raw,spectre=dict(version=tool['version'],binary_sha256=tool['binary_sha256'],
                                                     setup_sha256=list(tool['setup_sha256'].values()),receipt=receipt),
                  EVAS=dict(package=identity['package'],compatibility=identity['compatibility'],kernel_reported=identity['kernel']['reported'],
                            kernel_sha256=sha(ROOT/'evas/rust_core/target/debug/evas-kernel'),production_source_closure=closure),
                  native_provenance=native_provenance,native_independent=native_check,
                  EVAS_canonical_independent=canonical_check,EVAS_native_time_independent=candidate_check,
                  original_stop_native_pair=dict(request_stop=1,native_rows=len(original_native),pair=original_pair,
                                                 excluded_terminal_rows=len(native)-len(original_native),
                                                 exact_stop_status=native_check['exact_stop_status']),
                  all_native_pair=native_pair,all_native_pair_request='supplemental stop+1ULP, not original canonical request',canonical_grid_invariance=grid,
                  supplemental_terminal_extension=dict(canonical_stop=1,supplemental_stop=stop,input='Original PWL unchanged through t=1; hold last value over the extra one-ULP terminal interval.',
                                                        purpose='Query every exported native timestamp; not evidence of exact canonical-stop serialization.'),
                  analysis_files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(args.output.glob('*.json'))},
                  checker_identity={p.name:sha(p) for p in [Path(__file__),Path(__file__).with_name('check.py'),Path(__file__).with_name('test_check.py'),Path(__file__).with_name('settings_contract.py'),Path(__file__).with_name('test_settings_contract.py')]},
                  calibration_receipt=dict(path="calibration.json",sha256=sha(Path(__file__).with_name("calibration.json"))),
                  overall_strict_qualification='I',
                  qualification_gaps=['Exact native anchor coverage is recorded under native_independent; missing anchors remain I, no interpolation/extrapolation performed.',
                                      'Terminal raw token is 1.0000000000000002; supplemental request differs explicitly from canonical stop.',
                                      'Native event brackets are timing observations, not strict callback/serialization certificates.',
                                      'Raw/tool receipts are local-only; compact evidence is not full public reproducibility.'])
    save(args.evidence,evidence)
    print(json.dumps(dict(original_stop_native_pair=original_pair,supplemental_native_rows=len(native),native_formula=native_check['formula_and_stage_status'],
                          pair=native_pair,strict='I',grid=grid),indent=2))


if __name__=='__main__':
    try:
        main()
    except ValueError as error:
        print(json.dumps(dict(status='ERROR',reason=str(error))),file=sys.stderr)
        raise SystemExit(2)
