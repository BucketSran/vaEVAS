"""Replay the separate EVAS recovery and actual Spectre follow-up batch."""
import argparse
import json
from pathlib import Path
import sys
import hashlib
import tarfile

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'evas/validation/paper'), str(ROOT/'experiments/backends/paper')]
from inputs import sha, save
from observations import read_native
from runner import effective_settings
from precision_v2 import load_contract, assess
from precision_reference import FirstOrder
from precision_v2_report import control_qualification
from precision_binding_evidence import callback_trace, complete_boundary_search, axes
from precision_boundary_probe import assess_boundaries


def load(path):
    return json.loads(path.read_text())


def verify_manifest(base):
    manifest = load(base/'FILE_MANIFEST.json')
    for rel, entry in manifest.items():
        p = (base/rel).resolve()
        if (not p.is_relative_to(base.resolve()) or sha(p) != entry['sha256']
                or p.stat().st_size != entry['bytes']):
            raise ValueError('artifact drift: '+rel)
    return sha(base/'FILE_MANIFEST.json')


def report(base, destination):
    destination.mkdir(parents=True, exist_ok=False)
    contract = load_contract()
    local = base/'final-local'; remote = base/'spectre/outputs'
    manifests = {name: verify_manifest(p) for name, p in [('local', local), ('spectre', remote)]}
    collection = load(base/'SPECTRE-COLLECTION.json')
    if sha(base/'spectre.tar.gz') != collection['archive_sha256']:
        raise ValueError('remote archive drift')
    if (manifests['spectre'] != collection['manifest_sha256'] or
            sha(base/'spectre/operator.json') != collection['operator_sha256']):
        raise ValueError('remote collection identity drift')
    operator = load(base/'spectre/operator.json')
    if not operator['cleanup_confirmed'] or operator['exit_code'] != 0:
        raise ValueError('remote execution did not finalize')
    for rel, digest in load(local/'SOURCE_IDENTITY.json').items():
        if sha(ROOT/rel) != digest:
            raise ValueError('candidate source differs from the executed source: '+rel)
    source_archive = load(base/'SOURCE-ARCHIVE.json')
    archive_path = ROOT/source_archive['path']
    if sha(archive_path) != source_archive['sha256']:
        raise ValueError('executed source archive drift')
    with tarfile.open(archive_path, 'r:gz') as archive:
        contents = {}
        for member in archive:
            if not member.isfile() or member.name in contents:
                raise ValueError('unexpected source archive member')
            contents[member.name] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    if contents != load(local/'SOURCE_IDENTITY.json'):
        raise ValueError('source archive differs from executed source manifest')
    tool = load(local/'TOOL_IDENTITY.json')
    if sha(Path(tool['kernel'])) != tool['kernel_sha256']:
        raise ValueError('candidate kernel drift')
    evidence = {}; results = []
    for backend, directory in [('evas', local), ('spectre', remote)]:
        identity = load(directory/'TOOL_IDENTITY.json')
        evidence[backend] = {k: identity[k] for k in ('kernel_sha256','binary_sha256','version','python','platform','rustc_version') if k in identity}
        for work in sorted((directory/'runs').iterdir()):
            card = load(work/'condition.json')
            if card != next(c for c in contract['cards'] if c['id'] == work.name):
                raise ValueError('frozen condition changed')
            for name, digest in load(work/'INPUT_IDENTITY.json').items():
                if sha(work/name) != digest: raise ValueError('input drift: '+name)
            # These are exact reruns of existing frozen recipes. Instrumented
            # Spectre sampling belongs to the earlier binding supplement.
            if backend == 'evas':
                old = (ROOT/'runs/precision-tiers-20261011/collected'/f"{card['family']}-evas"/
                       'outputs'/f"{card['family']}-evas"/'runs'/(work.name+'--'+load(work/'requested_settings.json')['id']))
                status = load(work/'worker-result.json')['status']
                record = {'effective_settings': effective_settings(work, backend)}
                waveform = work/'waveform.csv'
            else:
                profile = load(work/'requested_settings.json')['id']
                old = (ROOT/'runs/precision-binding-20261011/batch/collected'/f"{card['family']}-spectre"/
                       'outputs'/f"{card['family']}-spectre"/'runs'/(work.name+'--'+profile))
                record = load(work/'RESULT.json'); status = record['status']
                waveform = work/record['waveform']
            for name in load(work/'INPUT_IDENTITY.json'):
                if sha(work/name) != sha(old/name): raise ValueError('original recipe changed: '+name)
            if status != 'waveform_available': raise ValueError('incomplete run: '+str(work))
            rows = read_native(waveform, backend); timing = None
            if backend == 'spectre' and card['family'] == 'sample_hold':
                if identity['binary_sha256'] != '72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f':
                    raise ValueError('unreviewed callback tool')
                trace = callback_trace(card, (work/'dut.va').read_text(), (work/'spectre.log').read_text(), rows)
                folder = destination/'callback'; folder.mkdir()
                (folder/'spectre.log').write_bytes((work/'spectre.log').read_bytes())
                trace.update(artifact='spectre.log', artifact_sha256=sha(folder/'spectre.log'))
                timing = folder/'evidence.json'; save(timing, trace)
            assessment = assess(card, rows, contract, event_evidence_path=timing)
            assessment, witnesses = complete_boundary_search(card, rows, assessment, contract)
            qualification = control_qualification(work, backend, record, rows, contract, identity)
            results.append({'condition': card['id'], 'backend': backend,
                            'profile': load(work/'requested_settings.json')['id'],
                            'model_sha256': sha(work/'dut.va'), 'waveform_sha256': sha(waveform),
                            'input_identity_sha256': sha(work/'INPUT_IDENTITY.json'),
                            'assessment': assessment, 'settings': qualification,
                            'boundary_witnesses': witnesses, 'axes': axes(assessment, qualification)})
    cross = load(base/'cross-candidate/response.json')
    request = load(base/'cross-candidate/REQUEST.json')
    if request['kernel_sha256'] != tool['kernel_sha256']:
        raise ValueError('boundary query kernel differs')
    if request['original'] != load(local/'runs/SH-X-RAMP/request.json'):
        raise ValueError('boundary source/settings differ')
    strobe = cross['strobe_evidence']
    if strobe['times'] != request['times']:
        raise ValueError('boundary observations differ from requests')
    rows = [dict(zip(['time', *cross['nodes']], [t, *v], strict=True))
            for t, v in zip(strobe['times'], strobe['voltages_V'], strict=True)]
    boundary = assess_boundaries(load(local/'runs/SH-X-RAMP/condition.json'), rows)
    witnesses = load(base/'witnesses/SUMMARY.json')
    recoveries = []
    for witness in witnesses:
        name = witness['condition']
        before_path = base/'detailed-baseline'/(name+'-diagnostics.json')
        before = load(before_path)
        failures = [r for r in before['records'] if r['kind'] == 'accuracy_failure']
        if before['truncated'] or len(failures) != 1:
            raise ValueError('missing baseline failure witness')
        previous = json.loads(failures[0]['reason'])
        rejected_times = [r['start'] for r in before['records']
                          if r['kind'] == 'history_candidate' and r['outcome'] == 'rejected']
        if rejected_times != [witness['time_s']]:
            raise ValueError('recovery did not query the original failure time')
        after_path = base/'witnesses'/(name+'.json'); after = load(after_path)
        node = after['nodes'].index('y')
        if (after['transient']['times'] != [witness['time_s']] or
                after['solutions'][0]['voltages'][node] != witness['value_V'] or
                after['observation_evidence']['voltage_bounds_V'][0][node] != witness['enclosure_V']):
            raise ValueError('witness differs from actual output')
        original = load(local/'runs'/name/'request.json')
        value = witness['value_V']
        lo, hi = witness['enclosure_V']
        reference = FirstOrder(load(local/'runs'/name/'condition.json')).bounds(witness['time_s'])
        if (witness['error_bound_V'] != max(abs(value-lo), abs(value-hi)) or
                witness['internal_budget_V'] != original['vabstol']+original['reltol']*abs(value) or
                witness['independent_reference_V'] != list(reference) or
                witness['reference_error_upper_V'] != max(abs(value-reference[0]), abs(value-reference[1])) or
                not lo <= reference[0] <= reference[1] <= hi):
            raise ValueError('witness budget or independent reference differs')
        if witness['error_bound_V'] > witness['internal_budget_V']:
            raise ValueError('recovery witness exceeds original budget')
        recoveries.append({'before': previous, 'after': witness,
                           'before_sha256': sha(before_path), 'after_sha256': sha(after_path)})
    result = {'id': 'precision-evas-recovery-20261011', 'scope': 'local unmerged candidate; finite observations, original criteria unchanged',
              'artifact_availability': 'local-only bulk files; compact public facts are not a complete reproducible dataset',
              'analysis_sha256': sha(Path(__file__)), 'checker_sha256': sha(ROOT/'evas/validation/paper/precision_v2.py'),
              'source_identity': load(local/'SOURCE_IDENTITY.json'), 'source_archive': source_archive, 'manifests': manifests,
              'collection': collection, 'tools': evidence, 'results': results,
              'recovery_witnesses': recoveries,
              'boundary_probe': boundary,
              'boundary_artifacts': {str((base/'cross-candidate'/n).relative_to(ROOT)): sha(base/'cross-candidate'/n)
                                     for n in ('REQUEST.json', 'response.json')},
              'binding_registry': 'v1 retained for its historical source/tool identity; no new registry issued'}
    save(destination/'report.json', result)
    print(json.dumps([{'condition': r['condition'], 'backend': r['backend'], 'Q3': r['axes']['Q3'],
                       'error_upper_V': r['assessment']['error_upper_V']} for r in results], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('base', type=Path); parser.add_argument('destination', type=Path)
    args = parser.parse_args(); report(args.base.resolve(), args.destination.resolve())
