"""Run the four frozen EVAS manifests and compare only exact native Spectre rows."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from evas.results import run


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--kernel', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    args.out.mkdir(parents=True, exist_ok=False)
    reference = json.loads((args.reference / 'reference-analysis.json').read_text())
    report = dict(kind='new EVAS execution with archived Spectre native-row pairing',
                  source_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=root,text=True).strip(),
                  kernel_sha256=digest(args.kernel), checker_sha256=digest(Path(__file__)),
                  reference_analysis_sha256=digest(args.reference/'reference-analysis.json'),
                  spectre_version='21.1.0.509.isr12', cases=[],
                  limits=['raw evidence local-only', 'two irregular t=0 rows missing remain I',
                          'Spectre effective reltol=1e-8 differs from requested 1e-7; original settings readback I retained',
                          'does not certify exact physical callback order or close original C1/#79/VCO F/I'])
    expected = {'static-irregular':lambda t:2*t,
                'continuous-periodic':lambda t:-math.expm1(-t),
                'implicit-irregular':lambda t:t,
                'timer-periodic':lambda t:math.floor(4*t)}
    names = [c['case'] for c in reference['cases']]
    if len(names)!=len(expected) or set(names)!=set(expected):
        raise ValueError('reference must contain the four frozen cases exactly once')
    for case in reference['cases']:
        name = case['case']
        fixtures = root/'evas/validation/strobe'/name
        contract = json.loads((fixtures/'case.json').read_text())
        out = args.out/name
        run(fixtures/'evas-manifest.json',kernel=args.kernel,out=out)
        bundle = json.loads((out/'manifest.json').read_text())
        assert bundle['status']=='complete'
        for item in bundle['files']:
            assert digest(out/item['path'])==item['sha256']
        response = json.loads((out/'result.json').read_text())
        yi = response['nodes'].index('y')
        ei = {t: row['voltages'] for t,row in zip(response['transient']['times'],response['solutions'])}
        forced = response['strobe_evidence']
        assert forced['times']==contract['forced_times']
        for t,row in zip(forced['times'],forced['voltages_V']):
            assert row==ei[t]
        if [r['time'] for r in case['requested']]!=contract['requested_times']:
            raise ValueError('reference omitted or changed a frozen requested time')
        rows=[]
        for requested in case['requested']:
            time=requested['time']; ev=ei[time]
            direct=[abs(ev[response['nodes'].index(node)]-native['voltages'][node])
                    for native in requested['matching_rows'] for node in contract['voltage_nodes']]
            analytic = expected[name](time)
            if requested['analytic_V']!=analytic:
                raise ValueError('reference analytic answer does not match independent equation')
            err=abs(ev[yi]-analytic)
            rows.append(dict(time=time,forced=time in contract['forced_times'],evas_y_V=ev[yi],
                             native_rows=requested['matching_rows'],direct_max_V=max(direct) if direct else None,
                             direct_status=('P' if max(direct)<=contract['acceptance']['direct_absolute_V'] else 'F') if direct else 'I',
                             evas_analytic_error_V=err,
                             evas_analytic_status='P' if err<=contract['acceptance']['analytic_absolute_V'] else 'F'))
        report['cases'].append(dict(case=name,inputs={p.name:digest(p) for p in sorted(fixtures.iterdir()) if p.is_file()},
                                  request_sha256=digest(out/'request.json'),response_sha256=digest(out/'result.json'),
                                  bundle_sha256=digest(out/'manifest.json'),frontend_identity=bundle.get('identity'),
                                  strobe_evidence=forced,rows=rows))
    (args.out/'pairing.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([{ 'case':c['case'], 'forced_points':len(c['strobe_evidence']['times']),
                       'direct_max_V':max(r['direct_max_V'] for r in c['rows'] if r['direct_max_V'] is not None),
                       'missing_times':[r['time'] for r in c['rows'] if r['direct_status']=='I'] } for c in report['cases']],indent=2))


if __name__=='__main__':
    main()
