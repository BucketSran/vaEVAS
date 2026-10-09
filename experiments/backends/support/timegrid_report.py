"""Verify the Gnucap time-resolution follow-up without replacing base receipts."""
import argparse
import collections
import copy
import json
from pathlib import Path
import sys

from summarize import ROOT, BACKENDS, load, sha, ref, verify, compact

sys.path.insert(0, str(ROOT/'evas/validation/support'))
from checker import assess


def summarize(base):
    original_path = ROOT/'experiments/backends/support/20261009.json'
    original = load(original_path)
    cards = {c['id']: c for c in load(ROOT/'evas/validation/support/cases-v2.json')['cards']}
    selected = {(r['backend'], r['condition']): copy.deepcopy(r) for r in original['support']}
    followups, receipts, identities = {}, {}, {}
    expected = {'gnucap-timegrid': set(cards)-{'LANG-array-events', 'LANG-vector'},
                'gnucap-step-scan': {'LP-nd', 'LP-np', 'DDT-pwl'}}
    backend = 'gnucap_modelgen'
    prior_image = load(base/original['tool_identities'][backend]['core']['path'])['images']['gnucap']['config_id']
    for name, ids in expected.items():
        directory = base/name
        lane = directory/'collected'/backend/'outputs'/backend
        results = verify(lane)
        assert {r['condition'] for r in results} == ids and len(results) == len(ids)
        manifest = load(directory/'inputs/INPUT_MANIFEST.json')
        for relative, digest in manifest.items():
            assert sha(directory/'inputs'/relative) == digest
        actual_cards = {c['id']: c for c in load(directory/'inputs/cards.json')['cards']}
        identities[name] = ref(lane/'TOOL_IDENTITY.json', base)
        assert load(lane/'TOOL_IDENTITY.json')['images']['gnucap']['config_id'] == prior_image
        control = directory/'collected'/backend/'operator-receipts'/f'{backend}.json'
        assert load(control)['cleanup_confirmed'] and load(control)['exit_code'] == 0
        receipts[name] = ref(control, base)
        followups[name] = []
        for result in results:
            cid = result['condition']
            card = copy.deepcopy(cards[cid])
            if name == 'gnucap-step-scan':
                card['maxstep_x'] /= 16
            assert actual_cards[cid] == card
            work = lane/'runs'/cid
            assert (work/'dut.va').read_text() == cards[cid]['source']
            for filename in ('tb.gc', 'requested_times.json', 'requested_settings.json'):
                assert (work/filename).read_bytes() == (directory/'inputs'/backend/cid/filename).read_bytes()
            settings = load(work/'requested_settings.json')
            assert settings['gnucap_dtmin_s'] == card['unit_s']/2**24
            assert settings['maxstep_s'] == card['maxstep_x']*card['unit_s']
            # Replay every actual sample through the unchanged physical checker.
            assert result['status'] == 'waveform_available'
            assert assess(cards[cid], load(work/'rows.json')) == result['assessment']
            entry = compact(result, lane, base)
            entry['solver_settings'] = settings
            entry['input_manifest'] = ref(directory/'inputs/INPUT_MANIFEST.json', base)
            entry['source_generation'] = 'unchanged v2 model; new Gnucap dtmin' + (' and maxstep/16' if name.endswith('scan') else '')
            followups[name].append(entry)
            if name == 'gnucap-timegrid':
                selected[backend, cid] = entry
    primary = list(selected.values())
    assert len(primary) == 60
    counts = {b: dict(collections.Counter(r.get('assessment', {}).get('status', r['status'])
                                        for r in primary if r['backend'] == b)) for b in BACKENDS}
    # Preserve base records by reference; expose which 13 slots use new settings.
    return {'schema_version': 1, 'claim': 'Finite sampled behavior at declared settings; no formal core qualification or full-language claim',
            'original_receipt': {'path': str(original_path.relative_to(ROOT)), 'sha256': sha(original_path)},
            'source_revision': original['source_revision'], 'counts': counts,
            'selected_slots': [{'backend': r['backend'], 'condition': r['condition'], 'receipt': r['receipt'],
                                'status': r.get('assessment', {}).get('status', r['status'])} for r in primary],
            'followups': followups, 'operator_receipts': receipts, 'tool_identities': identities,
            'primary_conditions': 27, 'primary_slots': 108, 'core_results': 'original 48 reused, including I/X; not regraded',
            'new_configurations': sum(len(v) for v in followups.values()),
            'total_configurations_including_original': original['new_backend_configurations']+sum(len(v) for v in followups.values()),
            'time_quantization_source': ref(base/'gnucap-timegrid/time-rounding-source.txt', base),
            'checked_in_analysis': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT/'evas/validation/support/checker.py', ROOT/'experiments/backends/support/probes.py']},
            'raw_availability': 'local-only; raw paths relative to runs/'+base.name,
            'correction': 'Original endpoint failures were caused by Gnucap dtmin time quantization, not a short decimal print format. The native output already has 17 digits. Old verdicts are retained.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    summary = summarize(args.run.resolve())
    with args.output.open('x') as stream:
        json.dump(summary, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps(summary['counts'], indent=2))
