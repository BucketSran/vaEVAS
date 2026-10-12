"""Audit sealed finite primitive evidence without rescoring or running a solver.

Unlike event cards, these cards compare the actual exported (t, u, y) values.
They do not require an accepted-step origin or certify a continuous trajectory.
Unknown runtime controls remain unknown even when the finite observations pass.
"""
from decimal import Decimal
from fractions import Fraction
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'experiments/backends/paper'))
from settings_readback import ReadbackError, spectre, assignments
from observations import read_native
from precision_readback_audit import verify_lane, sha


def spectre_controls(log, psf):
    """Keep the strict reader, with a separate audit of printed PSF rounding.

    No log or PSF text is modified. The numerical checker and old settings
    verdicts are unchanged. Reject actual disagreements and ambiguous headers.
    """
    try:
        return {**spectre(log, psf), 'metadata_rounding': []}
    except ReadbackError as exc:
        if str(exc) not in ('log/PSF disagreement: maxstep_s',
                            'log/PSF disagreement: stop_s'):
            raise
    lines=list(enumerate(log.splitlines(),1))
    starts=[i for i,(_,s) in enumerate(lines) if s.strip()=='Important parameter values:']
    if len(starts)!=1: raise ReadbackError('ambiguous parameter block')
    start=starts[0]+1
    end=next((i for i in range(start,len(lines)) if not lines[i][1].strip()),len(lines))
    mapping={'reltol':'reltol','abstol(V)':'vabstol_V','abstol(I)':'iabstol_A',
             'maxstep':'maxstep_s','stop':'stop_s','method':'method'}
    effective=assignments(lines[start:end],mapping,'transient:tran')
    header=psf.split('TYPE\n',1)[0]
    # The failed strict reader has already checked analysis/global/header
    # identities and duplicates before reaching the comparison loop.
    psf_effective=assignments(list(enumerate(header.splitlines(),1))[1:],mapping,
                              'psf_transient:tran',quoted=True)
    rounded=[]
    for key, fact in effective.items():
        other=psf_effective[key]
        if key=='method':
            if fact['value']!=other['value']: raise ReadbackError('method disagreement')
            continue
        token=other['raw'].split()[-1]
        value=Decimal(token)
        half_quantum=Decimal(1).scaleb(value.as_tuple().exponent)/2
        # Parse the original log token, not its binary64 representative: a
        # float round trip can erase a tiny excess at the printing boundary.
        raw_value=fact['raw'].split('=',1)[1].strip()
        match=re.fullmatch(r'([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)\s*([A-Za-z]*)',raw_value)
        units={'':0,'s':0,'V':0,'A':0,'ms':-3,'us':-6,'ns':-9,'ps':-12,
               'nV':-9,'pV':-12,'fV':-15,'pA':-12,'fA':-15,'aA':-18}
        if not match or match[2] not in units: raise ReadbackError('invalid raw control')
        actual=Fraction(Decimal(match[1]))*Fraction(10)**units[match[2]]
        if abs(actual-Fraction(value))>Fraction(half_quantum):
            raise ReadbackError('log outside printed PSF rounding interval: '+key)
        if actual != Fraction(value):
            rounded.append({'field':key,'log':fact,'psf':other,
                            'printed_half_quantum':str(half_quantum)})
    return {'effective':effective,'psf_effective':psf_effective,
            'metadata_rounding':rounded,
            'limit':'high precision transient log; PSF rounded metadata is only a crosscheck'}


def audit(lane, analysis, inputs):
    verify_lane(lane)
    indexed={(r['backend'],r['label']):r for r in analysis}
    records=[]
    for result in json.loads((lane/'EXECUTION.json').read_text()):
        work=lane/'runs'/result['label']
        if not work.resolve().is_relative_to((lane/'runs').resolve()):
            raise ValueError('unsafe execution label')
        saved=json.loads((work/'RESULT.json').read_text())
        if result!=saved: raise ValueError('execution/result disagreement')
        frozen=inputs/result['work']
        if not frozen.resolve().is_relative_to(inputs.resolve()):
            raise ValueError('unsafe frozen input path')
        filenames=['dut.va','condition.json','requested_settings.json',
                   'requested_times.json',result['deck']]
        if any(sha(work/f)!=sha(frozen/f) for f in filenames):
            raise ValueError('execution/frozen input disagreement')
        grade=indexed[(result['backend'],result['label'])]
        if grade['result_sha256']!=sha(work/'RESULT.json') or grade['execution']!=result['status']:
            raise ValueError('analysis/execution disagreement')
        record={**grade,'input_hashes':{f:sha(work/f) for f in filenames},
                'requested_controls':json.loads((work/'requested_settings.json').read_text()),
                'reason':saved.get('reason'), 'finite_evidence':'no waveform',
                'effective_controls':saved.get('settings_readback')}
        record['execution_artifacts']={f:sha(work/f) for f in ('compile.json','simulate.json','simulate.log')
                                       if (work/f).is_file()}
        if (work/'worker-result.json').is_file():
            worker=json.loads((work/'worker-result.json').read_text())
            record['reason']=worker.get('reason',record['reason'])
            record['execution_artifacts']['worker-result.json']=sha(work/'worker-result.json')
        if result['status']=='waveform_available':
            if not (work/result['waveform']).resolve().is_relative_to(work.resolve()):
                raise ValueError('unsafe waveform path')
            rows=read_native(work/result['waveform'],result['backend'])
            record['native_export']={'path':result['waveform'],'sha256':sha(work/result['waveform']),
                                    'rows':len(rows),'start_s':rows[0]['time'],'end_s':rows[-1]['time'],
                                    'max_gap_s':max(b['time']-a['time'] for a,b in zip(rows,rows[1:])),
                                    'reader_interpolation':False,
                                    'claim':'actual exported observations, not accepted-step certification'}
            backend=result['backend']
            if backend=='spectre':
                record['effective_controls']=spectre_controls((work/'spectre.log').read_text(),
                                                              (work/result['waveform']).read_text())
                if 'digits=17' not in (work/result['deck']).read_text():
                    raise ValueError('missing precision export setting')
            elif backend=='evas':
                record['control_limit']='iabstol/integration method are not EVAS voltage-domain controls'
            else:
                deck=(work/result['deck']).read_text()
                if 'numdgt=17' not in deck: raise ValueError('missing precision export setting')
                record['control_limit']='stop/maxstep supplied by verified invocation; no independent runtime echo'
                if backend=='gnucap_modelgen':
                    log=(work/'simulate.log').read_text()
                    record['option_echo_lines']=[line for line in log.splitlines()
                                                  if line.startswith('.options') and any(
                                                      k in line for k in ('numdgt=','method=','dtmin='))]
            # Finite observations need source, plan, export and actual tolerance
            # facts. They do not promote unknown solver internals into facts.
            record['finite_evidence']='audited'
        record.pop('full_qualification',None)
        record.pop('settings',None)
        records.append(record)
    return records


def receipt(lanes, analyses, inputs, build):
    from primitives_run import verify
    verify(inputs)
    plan=json.loads((inputs/'PLAN.json').read_text())
    expected={(r['backend'],r['label']) for r in plan}
    if len(expected)!=len(plan): raise ValueError('duplicate frozen positions')
    grades=[]
    identities=[]
    for path in analyses:
        data=json.loads(path.read_text())
        for name,digest in data['analysis_source_identity'].items():
            if sha(ROOT/name)!=digest: raise ValueError('analysis source no longer retrievable: '+name)
        grades.extend(data['records'])
        identities.append({'file':path.name,'sha256':sha(path),
                           'analysis_source_identity':data['analysis_source_identity']})
    if len(grades)!=len(expected) or {(r['backend'],r['label']) for r in grades}!=expected:
        raise ValueError('analysis does not cover frozen denominator exactly')
    records=[]; sources=[]
    for lane in lanes:
        result=audit(lane,grades,inputs)
        records.extend(result)
        tool=json.loads((lane/'TOOL_IDENTITY.json').read_text())
        sources.append({'lane':lane.name,'manifest_sha256':sha(lane/'FILE_MANIFEST.json'),
                        'tool_identity_sha256':sha(lane/'TOOL_IDENTITY.json'),
                        'tool_binary_sha256':tool.get('binary_sha256',tool.get('kernel_sha256')),
                        'version':tool.get('version',tool.get('reported',{}).get('version')),
                        'images':tool.get('images'),'environment_sha256':tool.get('environment_sha256'),
                        'availability':'local-only'})
    if len(records)!=len(expected) or {(r['backend'],r['label']) for r in records}!=expected:
        raise ValueError('audited lanes do not cover frozen denominator exactly')
    source=json.loads((inputs/'SOURCE_IDENTITY.json').read_text())
    build_record=json.loads(build.read_text())
    if build_record['returncode']!=0 or build_record['source_revision']!=source['checkpoint']:
        raise ValueError('build/checkpoint disagreement')
    evas_source=next(s for s in sources if s['lane'].endswith('-evas'))
    if evas_source['tool_binary_sha256']!=build_record['kernel_sha256']:
        raise ValueError('execution/build kernel disagreement')
    # Keep runtime unknowns and scoped settings, but omit duplicated long raw
    # lines from this compact receipt. Their hashes remain in sealed evidence.
    for record in records:
        controls=record.get('effective_controls')
        if record['backend']=='spectre' and controls:
            record['effective_controls']={k:v['value'] for k,v in controls['effective'].items()}
            record['metadata_rounding']=controls.get('metadata_rounding',[])
        elif controls:
            record['effective_controls']=controls.get('actual')
    counts={b:dict(Counter(r.get('assessment',{}).get('status',r['execution'])
                          for r in records if r['backend']==b)) for b in sorted({r['backend'] for r in records})}
    return {'schema':'finite-primitives-audit-v1','operation':'new evidence audit; original scientific verdicts unchanged',
            'checkpoint':source['checkpoint'],'positions':len(expected),'counts':counts,
            'contract':json.loads((inputs/'CONTRACT.json').read_text()),
            'inputs_manifest_sha256':sha(inputs/'MANIFEST.json'),
            'source_identity_sha256':sha(inputs/'SOURCE_IDENTITY.json'),
            'kernel_build':{'record_sha256':sha(build),'kernel_sha256':build_record['kernel_sha256'],
                            'compiler_identity':build_record['compiler_identity'],
                            'cargo_lock_sha256':build_record['cargo_lock_sha256']},
            'analyses':identities,'auditor_sha256':sha(Path(__file__)),'sources':sources,'records':records,
            'claim':'audited finite exported observations only; no event-origin or continuous-trajectory guarantee',
            'history':'prior criteria, scores and rejected fixture attempts retained separately'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane',type=Path,action='append',required=True)
    parser.add_argument('--analysis',type=Path,action='append',required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=receipt(args.lane,args.analysis,args.inputs,args.build)
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False)
        stream.write('\n')
    print(json.dumps(result['counts']))
