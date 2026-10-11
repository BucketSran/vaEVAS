"""Measure interpolation error of exported observations against raw source runs."""
import csv,json
from pathlib import Path
from generate_source import experiments,interp
ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'benchmark/tasks/v2-data-sampling-identification';report={}
for group,exps in experiments().items():
    for exp in exps:
        path=TASK/('tests/truth' if group=='heldout' else 'environment/public/data')/(exp['name']+'.csv')
        csvrows=[list(map(float,r)) for r in list(csv.reader(path.open()))[1:]]
        raw=[list(map(float,l.split())) for l in (ROOT/'runs/v2-data-source'/exp['name']/'waveform.txt').read_text().splitlines()[1:]]
        errors=[(r[0],abs(r[4]-interp(csvrows,r[0],3))) for r in raw]
        scored=[e for t,e in errors if any(a<=t<=b for a,b in exp['tracks']+exp['holds'])]
        report[exp['name']]={'group':group,'rows':len(csvrows),'full_interpolation_max_V':max(e for t,e in errors),'scored_interpolation_max_V':max(scored),'initial_abs_error_V':abs(raw[0][4]-exp['initial'])}
(Path(__file__).parent/'export-errors.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'public_rows':sum(r['rows'] for r in report.values() if r['group']!='heldout'),'full_max_V':max(r['full_interpolation_max_V'] for r in report.values()),'scored_max_V':max(r['scored_interpolation_max_V'] for r in report.values()),'initial_max_V':max(r['initial_abs_error_V'] for r in report.values())},indent=2))
