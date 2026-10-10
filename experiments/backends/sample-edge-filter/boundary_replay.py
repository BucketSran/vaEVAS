"""Keep exact held-state alignment separate from the engineering window check."""
import argparse
import json
from pathlib import Path


def inspect(spectre, evas):
    differences = []
    compared = 0
    for case in ('SEF-TIMER', 'SEF-RESET', 'SEF-INTERRUPT', 'SEF-ISOLATION'):
        for setting in ('base', 'tight', 'fine'):
            sp = json.loads((spectre / case / setting / 'rows.json').read_text())
            ev = json.loads((evas / case / ('native-' + setting) / 'rows.json').read_text())
            if [r['time'] for r in sp] != [r['time'] for r in ev]:
                raise ValueError('Different grids: ' + case + '/' + setting)
            for index, (reference, candidate) in enumerate(zip(sp, ev, strict=True)):
                compared += 1
                for instance in ('a', 'b') if case == 'SEF-ISOLATION' else ('a',):
                    if reference[instance+'n'] != candidate[instance+'n']:
                        differences.append(dict(case=case, setting=setting, row=index,
                                                instance=instance, time=reference['time'],
                                                spectre={p:reference[instance+p] for p in 'hn'},
                                                evas={p:candidate[instance+p] for p in 'hn'}))
    return dict(status='FAIL' if differences else 'PASS', compared_rows=compared,
                counter_difference_records=len(differences), differences=differences,
                claim='Exact same-time held-state phase only; engineering waveform acceptance is separate')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('spectre', type=Path)
    parser.add_argument('evas', type=Path)
    args = parser.parse_args()
    result = inspect(args.spectre, args.evas)
    print(json.dumps(result, indent=2))
    raise SystemExit(result['status'] != 'PASS')
