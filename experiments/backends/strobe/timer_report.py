"""Verify collected timer-strobe runs and regenerate a compact comparison receipt."""
import argparse
from bisect import bisect_left, bisect_right
from collections import Counter
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'experiments/backends/support'),str(ROOT/'evas/validation/strobe')]
import precision_run as run
from precision_report import qualification
from timer_composition import assess as composition_assess
load=run.load
sha=run.sha


def verify_timer_diagnostic(base):
    """Prove the additional controls differ only in the explicit timer TT."""
    original=base/'composition-inputs/runs'
    diagnostic=base/'timer-diagnostic-inputs'
    plan=load(diagnostic/'PLAN.json')
    expected={(backend,'both-TT'+label) for backend in ('evas','spectre') for label in ('10ps','1ps')}
    if len(plan)!=4 or {(r['backend'],r['profile']) for r in plan}!=expected:
        raise ValueError('changed timer diagnostic denominator')
    for row in plan:
        old=original/row['backend']/'STROBE-TIMER-IDT--both';new=diagnostic/row['work']
        for name in ('dut.va','condition.json','requested_times.json'):
            if sha(old/name)!=sha(new/name):raise ValueError('timer diagnostic model/grid drift: '+name)
        tt=1e-11 if row['profile']=='both-TT10ps' else 1e-12
        settings={**load(old/'requested_settings.json'),'id':row['profile'],'timer_tolerance_s':tt}
        if load(new/'requested_settings.json')!=settings:raise ValueError('timer diagnostic solver drift')
        if row['backend']=='evas':
            request=load(old/'request.json');request['instances'][0]['parameters']['TT']=tt
            if load(new/'request.json')!=request:raise ValueError('timer diagnostic request drift')
        else:
            deck=(old/'tb.scs').read_text();needle=' TT=1e-10 '
            if deck.count(needle)!=1 or (new/'tb.scs').read_text()!=deck.replace(needle,' TT='+format(tt,'.17g')+' '):
                raise ValueError('timer diagnostic deck drift')


def time_coverage(requested, rows, backend, stop):
    """Coverage only: never replace a native timestamp or interpolate a value.

    Spectre export uses the original precision card's 16-ULP(stop) allowance.
    EVAS receipts must match requested binary64 times exactly. Disjoint request
    windows cannot reuse one native observation to cover two requested points.
    """
    times=[r['time'] for r in rows]
    allowance=0. if backend=='evas' else 16*math.ulp(stop)
    seen=set();missing=[];maximum=0.;ambiguous=False
    for t in requested:
        insertion=bisect_left(times,t)
        neighbors=times[max(0,insertion-1):insertion+1]
        if neighbors:maximum=max(maximum,min(abs(actual-t) for actual in neighbors))
        indices=set(range(bisect_left(times,t-allowance),bisect_right(times,t+allowance)))
        if not indices:missing.append(t);continue
        if indices & seen:ambiguous=True
        seen.update(indices)
    return dict(status='covered' if not missing and not ambiguous else 'evidence_insufficient',
                missing_requested_times_s=missing,reused_native_record=ambiguous,
                exact_float_mismatches=len(set(requested)-set(times)),allowance_s=allowance,
                maximum_nearest_distance_s=maximum if times else None,
                claim='native time coverage; all values are assessed at their unmodified actual times, not proof of hidden callback timestamps')


def report(base):
    source=load(base/'SOURCE_MANIFEST.json')
    for rel,digest in source.items():
        if sha(base/'repo'/rel)!=digest:raise ValueError('executed source snapshot drift: '+rel)
    deps=['evas/validation/strobe/timer_composition.py','evas/validation/sample_edge_filter/contract.py',
          'evas/validation/paper/precision_checker.py','evas/validation/paper/precision-v1.json',
          'experiments/backends/support/precision_report.py','experiments/backends/paper/observations.py',
          'experiments/backends/paper/inputs.py','experiments/archive/dvs2-starter-pilot/analyze.py',
          'experiments/archive/dvs2-starter-pilot/suite.py']
    for rel in deps:
        if sha(ROOT/rel)!=source[rel]:raise ValueError('analysis dependency drift: '+rel)
    diagnostic=(base/'timer-diagnostic-inputs').is_dir()
    if diagnostic:verify_timer_diagnostic(base)
    for folder in ('inputs','composition-inputs',*(['timer-diagnostic-inputs'] if diagnostic else [])):
        for rel,digest in load(base/folder/'MANIFEST.json').items():
            if sha(base/folder/rel)!=digest:raise ValueError('input drift: '+rel)
    result=dict(schema_version=1,purpose='fixed timer forced solves and bounded history consumers',
                source=load(base/'SOURCE_PROVENANCE.json'),source_manifest_sha256=sha(base/'SOURCE_MANIFEST.json'),
                implementation_files={p:source[p] for p in ('evas/rust_core/src/exact_time.rs','evas/rust_core/src/schedule.rs')},
                input_preservation=load(base/'PRESERVED_INPUTS.json'),analysis_sha256=sha(Path(__file__)),
                analysis_dependencies={p:source[p] for p in deps},limits=run.LIMITS,
                availability=dict(compact='repository-contained',raw='local-only',local_root=str(base),
                                  source_snapshot='repo/',source_bundle_sha256=sha(base/'bundle.tar.gz')),
                lanes={},results=[],pairing=[])
    pairs={}
    lanes=['sample_hold-evas','sample_hold-spectre','composition-evas','composition-spectre','first_order-evas']
    if diagnostic:lanes+=['timer-diagnostic-spectre','timer-diagnostic-evas']
    for lane in lanes:
        col=base/'collected'/lane;out=col/'outputs'/lane
        for rel,entry in load(out/'FILE_MANIFEST.json').items():
            p=(out/rel).resolve()
            if not p.is_relative_to(out.resolve()) or sha(p)!=entry['sha256'] or p.stat().st_size!=entry['bytes']:
                raise ValueError('raw artifact drift: '+rel)
        collection=load(col/'COLLECTION.json')
        if sha(col/'raw.tar.gz')!=collection['archive_sha256']:raise ValueError('archive drift: '+lane)
        operator=load(col/'operator-receipts'/(lane+'.json'))
        if operator.get('cleanup_confirmed') is not True:raise ValueError('unconfirmed cleanup: '+lane)
        backend=lane.split('-')[-1]
        is_composition=lane.startswith(('composition','timer-diagnostic'))
        frozen=base/('timer-diagnostic-inputs' if lane.startswith('timer-diagnostic') else
                     'composition-inputs' if is_composition else 'inputs')
        expected=[r for r in load(frozen/'PLAN.json') if r['backend']==backend and
                  (is_composition or r['family']==lane.split('-')[0])]
        records=load(out/'EXECUTION.json')
        if [r['label'] for r in records]!=[r['label'] for r in expected]:raise ValueError('changed denominator: '+lane)
        tool=load(out/'TOOL_IDENTITY.json')
        result['lanes'][lane]=dict(configurations=len(records),collection=collection,tool=tool,
                                  file_manifest_sha256=sha(out/'FILE_MANIFEST.json'),operator_sha256=sha(col/'operator-receipts'/(lane+'.json')))
        if backend=='evas':
            build=load(col/'build/BUILD.json')
            if build['source_manifest_sha256']!=sha(base/'SOURCE_MANIFEST.json') or build['kernel_sha256']!=tool['kernel_sha256']:
                raise ValueError('build/source/kernel mismatch: '+lane)
            result['lanes'][lane]['build']=build
        for record in records:
            work=out/'runs'/record['label'];request=frozen/'runs'/backend/record['label']
            for name in ('dut.va','condition.json','requested_times.json','requested_settings.json',
                         'request.json' if backend=='evas' else 'tb.scs'):
                if sha(work/name)!=sha(request/name):raise ValueError('run inputs differ: '+str(work/name))
            r=dict(lane=lane,condition=record['condition'],profile=record['profile'],execution=record['status'],
                   original_result_sha256=sha(work/'RESULT.json'),source_sha256=sha(work/'dut.va'),
                   requested_times_sha256=sha(work/'requested_times.json'),verdict='execution_failed')
            if 'verdict' in record:r['original_runner_verdict']=record['verdict']
            if record['status']=='waveform_available':
                rows=run.read_native(work/record['waveform'],backend);case=load(work/'condition.json')
                a=composition_assess(case,rows) if is_composition else run.assess(case,rows,load(frozen/'cards.json')['budgets'])
                q=qualification(work,backend,record,rows)
                requested=load(work/'requested_times.json');native={row['time']:row for row in rows}
                coverage=time_coverage(requested,rows,backend,load(work/'requested_settings.json')['stop_s'])
                r.update(assessment={k:v for k,v in a.items() if k not in ('event_records','event_brackets','worst')},
                         event_records=len(a.get('event_records',a.get('event_brackets',[]))),
                         qualification=q,time_coverage=coverage,
                         waveform_sha256=sha(work/record['waveform']),forced_points=len(requested),
                         verdict='pass' if a['status']=='pass' and q['status']=='qualified' and
                         (backend!='evas' or coverage['status']=='covered') else 'fail')
                pairs.setdefault((lane.rsplit('-',1)[0],record['label']),{})[backend]=(requested,native)
            else:r['reason']=record.get('reason',record.get('worker_result'))
            result['results'].append(r)
        result['lanes'][lane]['verdicts']=dict(Counter(r['verdict'] for r in result['results'] if r['lane']==lane))
    for (family,label),backends in pairs.items():
        if set(backends)!={'evas','spectre'}:continue
        et,ev=backends['evas'];st,sp=backends['spectre']
        if et!=st:raise ValueError('paired requested times differ: '+label)
        common=[t for t in et if t in ev and t in sp]
        signals=sorted(set(ev[common[0]]) & set(sp[common[0]])-{'time'}) if common else []
        errors={s:max(abs(ev[t][s]-sp[t][s]) for t in common) for s in signals}
        counters=[s for s in signals if s=='count' or s in ('an','bn')]
        phase_differences=sum(any(abs(ev[t][s]-sp[t][s])>1e-6 for s in counters) for t in common)
        result['pairing'].append(dict(family=family,label=label,requested_points=len(et),common_points=len(common),
                                     maximum_difference_V=errors,points_with_different_counter=phase_differences,
                                     claim='diagnostic only; every boundary remains in each independent engineering assessment'))
    result['total_configurations']=len(result['results'])
    result['original_configurations']=80
    result['additional_timer_diagnostic_configurations']=4 if diagnostic else 0
    if diagnostic:
        result['timer_diagnostic_note']='Additional both-profile controls tighten only the timer TT parameter to 10 ps and 1 ps. Original 100 ps runs and their nominal integral 100 uV failures remain. Source, stimulus, query times, numerical budgets, stop, solver tolerances and maxstep are unchanged; this is a separate causal diagnostic, not replacement data.'
        result['timer_diagnostic_manifest_sha256']=sha(base/'timer-diagnostic-inputs/MANIFEST.json')
    result['reanalysis_note']='The original composition runner added exact timestamp membership for Spectre beyond the frozen engineering criteria. Preserve its verdict. Report exact/16-ULP requested-time coverage separately, including misses; engineering assessments use all actual native timestamps and do not grant exact forced-point identity to Spectre. Mathematical checkers, budgets, models and native rows are unchanged. EVAS still requires exact forced times and accepted provenance.'
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('base',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    run.save(a.output,report(a.base.resolve()))
