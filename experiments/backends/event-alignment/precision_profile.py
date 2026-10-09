"""Freeze, attest, and compare a predeclared Spectre precision ladder. Never dispatch."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

from compare import compare, finite
from normalize_psf import normalize
from prepare_spectre import deck, ident

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('precision_settings_readback', HERE.parent/'paper/settings_readback.py')
_readback = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_readback)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(case, model, ladder, contract, initialization):
    if ladder.get('method') != 'traponly':
        raise ValueError('maintained deck builder admits only declared traponly method')
    if ladder['version'] != 1 or len(ladder['levels']) < 3:
        raise ValueError('version 1 requires at least three predeclared levels')
    ids = [ident(p['id']) for p in ladder['levels']]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate profile id')
    if not initialization or not isinstance(initialization,dict):
        raise ValueError('explicit initial-condition declaration required')
    if contract['stop'] != case['stop'] or contract['required_times'] != case['times']:
        raise ValueError('case/observation contract mismatch')
    if set(contract['budgets_v']) != set(case['voltage_nodes']):
        raise ValueError('all declared observations need frozen budgets')
    # Validate the contract through the maintained checker, without executing.
    compare(contract, {}, {})
    decks = {p['id']:deck(case,p) for p in ladder['levels']}
    return copy.deepcopy(dict(schema_version=1, case=case, ladder=ladder,
                             contract=contract, initialization=initialization,
                             model_sha256=hashlib.sha256(model).hexdigest(),
                             tooling_sha256={name:file_hash(path) for name,path in
                                 dict(profile=Path(__file__),deck=HERE/'prepare_spectre.py',
                                      normalizer=HERE/'normalize_psf.py',comparator=HERE/'compare.py',
                                      readback=HERE.parent/'paper/settings_readback.py').items()},
                             deck_sha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in decks.items()},
                             identity_components={k:digest(v) for k,v in
                                dict(inputs=case['inputs'], initialization=initialization,
                                     observations=case['times'], budgets=contract).items()},
                             event_count_nodes=list(case.get('criteria',{}).get('expected_final_counts',{})),
                             limits='Solver tolerances are controls, not output-error bounds. Finite stability is not a continuous-time proof.'))


def analyze(frozen, records):
    expected = [p['id'] for p in frozen['ladder']['levels']]
    if len(records) != len(expected) or [r['profile_id'] for r in records] != expected:
        raise ValueError('every frozen profile must appear once, in declared order')
    if any(r['frozen_sha256'] != digest(frozen) for r in records):
        raise ValueError('stale source/input/initial/observation/budget identity')
    gaps = []
    versions = {r.get('spectre_version') for r in records}
    if len(versions) != 1 or None in versions:
        gaps.append('missing or differing simulator version')
    for r in records:
        if r['settings_status'] != 'P' or r['execution_status'] != 'success':
            gaps.append(r['profile_id']+': execution/settings not qualified')
    contract = frozen['contract']
    required = set(contract['required_times'])
    native_audits = [compare(contract,r,r) for r in records]
    for profile,audit in zip(expected,native_audits):
        gaps.extend(profile+': '+gap for gap in audit['coverage_gaps'])
    # Native rows are retained in attestations. The fixed-grid comparison never
    # chooses a nearest row, interpolates, or selects a duplicate phase.
    traces = [dict(rows=[row for row in r.get('rows',[]) if row['time'] in required]) for r in records]
    pairs = [dict(left=expected[i],right=expected[i+1],comparison=compare(contract,traces[i],traces[i+1]))
             for i in range(len(traces)-1)]
    counts = {n:[] for n in frozen['event_count_nodes']}
    unstable = False
    for n, samples in counts.items():
        for trace in traces:
            samples.append({r['time']:r['voltages'][n] for r in trace['rows']
                            if n in r['voltages'] and finite(r['voltages'][n])})
        for left,right in zip(samples,samples[1:]):
            unstable |= any(left[t] != right[t] for t in left.keys() & right.keys())
    statuses = [p['comparison']['finite_pair_status'] for p in pairs]
    classification = ('event_count_unstable' if unstable else
                      'not_converged' if 'F' in statuses else
                      'incomplete' if gaps or 'I' in statuses else 'finite_stable')
    return dict(classification=classification,formal_qualification='I',
                event_count_status='unstable' if unstable else 'unknown' if not counts else
                    'incomplete' if any(set(sample)!=required for samples in counts.values() for sample in samples)
                    or any(p['comparison']['duplicate_times'][engine] for p in pairs for engine in ['evas','spectre'])
                    else 'finite_stable',
                analysis_sha256=file_hash(Path(__file__)),native_observation_audits=native_audits,
                frozen_sha256=digest(frozen),profiles=records,pairs=pairs,
                event_count_samples=counts,identity_gaps=gaps,
                limits=frozen['limits'])


def attest(frozen, profile_id, folder, psf_path, log_path, spectre_version, execution_status):
    profile = next(p for p in frozen['ladder']['levels'] if p['id']==profile_id)
    if file_hash(folder/'dut.va') != frozen['model_sha256'] or file_hash(folder/'tb.scs') != frozen['deck_sha256'][profile_id]:
        raise ValueError('executed model/deck differs from frozen inputs')
    result = dict(profile_id=profile_id,frozen_sha256=digest(frozen),
                  execution_status=execution_status,spectre_version=spectre_version,
                  requested_settings=profile,settings_status='I',rows=[],identities={},gaps=[])
    for name,path in [('model',folder/'dut.va'),('deck',folder/'tb.scs'),('psf',psf_path),('log',log_path)]:
        if path.exists():
            result['identities'][name] = dict(path=str(path.resolve()),sha256=file_hash(path))
    try:
        log = log_path.read_text()
        if spectre_version not in log:
            raise ValueError('provided simulator version absent from execution log')
        readback = _readback.spectre(log,psf_path.read_text())
        result['readback'] = readback
        requested = dict(reltol=profile['reltol'],vabstol_V=profile['vabstol'],
                         iabstol_A=profile['iabstol'],maxstep_s=profile['maxstep'],
                         stop_s=frozen['case']['stop'],method='traponly')
        for scope in ['effective','global_user','psf_effective']:
            for key,fact in readback[scope].items():
                target = requested[key]
                if not (target==fact['value'] if isinstance(target,str) else
                        math.isclose(target,fact['value'],rel_tol=1e-12,abs_tol=0.)):
                    raise ValueError('requested/effective mismatch: '+scope+'/'+key)
        result['settings_status'] = 'P'
        observations = normalize(psf_path,frozen['case'])
        result.update(observations)
    except (OSError,ValueError) as error:
        result['gaps'].append(str(error))
    return result


def write_new(path,value):
    encoded=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with path.open('x') as file:
        file.write(encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    p = commands.add_parser('freeze')
    for name in ['case_dir','ladder','contract','initialization','output']:
        p.add_argument(name,type=Path)
    p = commands.add_parser('attest')
    p.add_argument('frozen',type=Path);p.add_argument('profile_id')
    for name in ['folder','psf','log','output']:
        p.add_argument(name,type=Path)
    p.add_argument('--spectre-version',required=True)
    p.add_argument('--execution-status',choices=['success','runtime_failure','timeout','infrastructure_failure'],required=True)
    p = commands.add_parser('analyze')
    p.add_argument('frozen',type=Path);p.add_argument('output',type=Path);p.add_argument('records',nargs='+',type=Path)
    args = parser.parse_args()
    load = lambda path:json.loads(path.read_text())
    if args.command=='freeze':
        case=load(args.case_dir/'case.json');model=(args.case_dir/'dut.va').read_bytes()
        frozen=freeze(case,model,load(args.ladder),load(args.contract),load(args.initialization))
        args.output.mkdir(parents=True,exist_ok=False)
        write_new(args.output/'FROZEN.json',frozen)
        for profile in frozen['ladder']['levels']:
            target=args.output/profile['id'];target.mkdir()
            (target/'dut.va').write_bytes(model)
            (target/'tb.scs').write_text(deck(case,profile))
            write_new(target/'PROFILE.json',profile)
    elif args.command=='attest':
        write_new(args.output,attest(load(args.frozen),args.profile_id,args.folder,args.psf,args.log,args.spectre_version,args.execution_status))
    else:
        write_new(args.output,analyze(load(args.frozen),[load(p) for p in args.records]))


if __name__=='__main__':
    main()
