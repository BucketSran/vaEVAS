"""Recompute new root-window results beside unchanged historical assessments.

Verifies frozen/executed bytes and native provenance before accepting a grade.
Raw outputs are read-only. Instrumented Spectre attempts keep separate identities.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
for area in ('evas/src','evas/validation/paper','experiments/backends/paper'):
    sys.path.insert(0,str(ROOT/area))
from evas import compile_sources,Instance
from inputs import sha,save
from observations import read_native
from precision_run import effective_settings
from precision_report import (qualification,spectre_fullprecision_settings,
    SPECTRE_CALIBRATED_BINARY_SHA256,SPECTRE_CALIBRATED_VERSION)
from precision_breadth_run import native_observation_evidence,runtime_control_evidence
from precision_binding_evidence import callback_trace,complete_boundary_search,axes
from precision_v2 import assess as old_shx
from precision_root_v3 import assess as new_shx
from precision_composition_root_v3 import reanalyze
from root_callback_evidence import qualify as ledger
import precision_breadth as breadth


def load(path):return json.loads(path.read_text())


def contained(base,rel):
    path=(base/rel).resolve()
    if Path(rel).is_absolute() or not path.is_relative_to(base.resolve()):
        raise ValueError('artifact path escapes owning directory: '+str(rel))
    return path


def verify_frozen(frozen,execution_source):
    """Execution bytes stay frozen; current analysis has a separate identity."""
    for filename,root in [('MANIFEST.json',frozen),('SOURCE_IDENTITY.json',execution_source)]:
        identity=load(frozen/filename)
        if not identity:raise ValueError('empty frozen identity: '+filename)
        for rel,digest in identity.items():
            if sha(contained(root,rel))!=digest:raise ValueError('frozen artifact drift: '+rel)


def fixed_executions(frozen,lane,backend):
    planned=[r for r in load(frozen/'PLAN.json') if r['backend']==backend]
    actual=load(lane/'EXECUTION.json')
    if not planned or len(actual)!=len(planned):raise ValueError('fixed execution denominator differs')
    if len({r['label'] for r in planned})!=len(planned):raise ValueError('duplicate planned label')
    for p,r in zip(planned,actual,strict=True):
        if any(r.get(k)!=v for k,v in p.items()):raise ValueError('execution differs from frozen plan')
        if Path(r['label']).name!=r['label'] or r['label'] in ('.','..'):
            raise ValueError('execution label is not a single directory name')
        contained(lane/'runs',r['label']);contained(frozen,r['work'])
        if r.get('status')=='waveform_available':
            expected='waveform.csv' if backend=='evas' else 'psf/tran.tran.tran'
            if r.get('waveform')!=expected:raise ValueError('waveform differs from backend artifact')
            contained(lane/'runs'/r['label'],r['waveform'])
    return actual


def verify_lane(lane):
    manifest=load(lane/'FILE_MANIFEST.json')
    actual={str(p.relative_to(lane)) for p in lane.rglob('*') if p.is_file() and p.name!='FILE_MANIFEST.json'}
    if not manifest or set(manifest)!=actual:raise ValueError('output manifest inventory differs')
    for rel,entry in manifest.items():
        p=contained(lane,rel)
        if p.stat().st_size!=entry['bytes'] or sha(p)!=entry['sha256']:
            raise ValueError('collected output drift: '+rel)


def producer(base,tool,previous_build,previous_manifest):
    """Kernel build/source reuse requires every actual EVAS source byte match."""
    identity=load(base/'SOURCE_PROVENANCE.json')
    if not identity['reuse_verified'] or tool.get('kernel_sha256')!=identity['kernel_sha256']:
        raise ValueError('unverified kernel reuse')
    if (sha(previous_build)!=identity['previous_build_record_sha256'] or
            sha(previous_manifest)!=identity['previous_source_manifest_sha256']):
        raise ValueError('previous build artifacts differ from reuse receipt')
    build=load(previous_build);manifest=load(previous_manifest)
    if (build['returncode']!=0 or build['stage']['status']!='completed' or
            build['source_revision']!=identity['previous_scientific_source_revision'] or
            build['source_manifest_sha256']!=sha(previous_manifest) or
            build['kernel_sha256']!=tool['kernel_sha256']):
        raise ValueError('previous build does not attest the reused kernel')
    inventory=set(subprocess.check_output(['git','ls-files','evas/src','evas/rust_core'],cwd=ROOT,text=True).splitlines())
    sources=identity['production_source_sha256']
    if not inventory or set(sources)!=inventory:raise ValueError('production source inventory differs')
    for rel,digest in sources.items():
        if manifest.get(rel)!=digest or sha(ROOT/rel)!=digest:
            raise ValueError('production EVAS source drift: '+rel)
    return {'status':'qualified','kernel_sha256':identity['kernel_sha256'],
            'reuse_proof_sha256':sha(base/'SOURCE_PROVENANCE.json'),
            'claim':'verified previous build and unchanged production source; new execution and checker identity'}


def spectre_producer(lane,tool):
    probe=tool.get('probe',{})
    if (tool.get('binary_sha256')!=SPECTRE_CALIBRATED_BINARY_SHA256 or
            tool.get('version','').split()!=['sub-version',SPECTRE_CALIBRATED_VERSION] or
            probe.get('returncode')!=0 or probe.get('timeout') is not False or
            probe.get('status')!='completed' or
            sha(contained(lane,probe['log']))!=probe['log_sha256']):
        raise ValueError('uncalibrated Spectre binary/version preflight')
    return {'status':'qualified','binary_sha256':tool['binary_sha256'],
            'version':SPECTRE_CALIBRATED_VERSION,'preflight_log_sha256':probe['log_sha256']}


def report(base,output,*,previous_build,previous_manifest):
    output.mkdir(parents=True,exist_ok=False);records=[]
    execution_source=base/'repo'
    if sha(base/'SOURCE_MANIFEST.json')!=load(base/'SOURCE_PROVENANCE.json')['source_manifest_sha256']:
        raise ValueError('execution source manifest differs from provenance')
    for rel,digest in load(base/'SOURCE_MANIFEST.json').items():
        if sha(contained(execution_source,rel))!=digest:raise ValueError('execution snapshot drift: '+rel)
    for name,backend,kind in [('original-evas','evas','original'),('original-spectre','spectre','original'),
                              ('trace-spectre','spectre','trace')]:
        frozen=base/'inputs'/kind;verify_frozen(frozen,execution_source)
        lane=base/'collected'/name/'outputs'/name;verify_lane(lane)
        tool=load(lane/'TOOL_IDENTITY.json');contracts=load(frozen/'ORIGINAL_CONTRACTS.json')
        engine=producer(base,tool,previous_build,previous_manifest) if backend=='evas' else spectre_producer(lane,tool)
        for execution in fixed_executions(frozen,lane,backend):
            cardid=execution['condition'];tier=execution['tier'];work=lane/'runs'/execution['label']
            record={'lane':name,'backend':backend,'condition':cardid,'target_tier':tier,
                    'callback_trace':kind=='trace','execution':execution['status'],'producer':engine}
            if execution['status']!='waveform_available':
                record['status']='execution_failed';records.append(record);continue
            original=frozen/execution['work']
            for filename in ('dut.va',execution['deck'],'condition.json','requested_settings.json',
                             'requested_times.json','observation_plan.json'):
                if sha(work/filename)!=sha(original/filename):raise ValueError('executed input drift: '+filename)
            card=load(work/'condition.json');contract=contracts['precision_v2' if cardid=='SH-X-RAMP' else 'breadth']
            if kind=='original' and (work/'dut.va').read_text()!=card['source']:
                raise ValueError('original model differs from canonical card source')
            rows=read_native(contained(work,execution['waveform']),backend)
            if backend=='evas':
                settings=effective_settings(work,backend)
                program=load(work/'program.json')
                compiled=json.loads(json.dumps(compile_sources({'dut.va':(work/'dut.va').read_text()},
                    [Instance('dut',card['top'],{n:n for n in card['ports']},card['parameters'])]).to_dict()))
                if compiled!=program:raise ValueError('compiled program differs from exact frozen model')
                response=load(work/'raw-response.json')
            else:
                settings=spectre_fullprecision_settings(work,tool,frozen_deck_sha256=sha(original/'tb.scs'))
            observed={**execution,'effective_settings':settings}
            q=qualification(work,backend,observed,rows,spectre_tool=tool if backend=='spectre' else None)
            native=native_observation_evidence(work,backend,q,rows,tool=tool,card=card,contract=contract)
            runtime=runtime_control_evidence(backend,settings)
            trusted=(engine['status']=='qualified' and q['status']=='qualified' and native['status']=='qualified' and runtime['status']=='qualified')
            record.update(settings=settings,qualification=q,native_observations=native,runtime_controls=runtime,
                          artifacts={f:sha(work/f) for f in ('dut.va',execution['deck'],execution['waveform'],
                             'requested_settings.json','requested_times.json')})
            if cardid=='SH-X-RAMP':
                old=old_shx(card,rows,contract)
                if backend=='evas':
                    proof=ledger(card,program,response,rows,producer_qualified=trusted)
                    new=new_shx(card,rows,contract,committed_callback_boxes=proof['committed_callback_boxes']) if proof['status']=='qualified' else new_shx(card,rows,contract)
                elif kind=='trace':
                    try:
                        proof=callback_trace(card,(work/'dut.va').read_text(),(work/'spectre.log').read_text(),rows)
                        evidence=output/(name+'--'+execution['label']+'--callbacks.json')
                        # This file binds all trace lines to the exact native rows.
                        proof['artifact_sha256']=sha(work/'spectre.log')
                        # event_evidence requires a contained artifact; preserve
                        # a byte-identical local analysis copy of the complete log.
                        artifact=evidence.with_suffix('.log');artifact.write_bytes((work/'spectre.log').read_bytes())
                        proof['artifact']=artifact.name;save(evidence,proof)
                        new=new_shx(card,rows,contract,event_evidence_path=evidence)
                        proof={'status':'qualified',**proof}
                    except ValueError as exc:
                        proof={'status':'unknown','reason':str(exc)};new=new_shx(card,rows,contract)
                else:
                    proof={'status':'unknown','reason':'original attempt has no read-only callback trace'}
                    new=new_shx(card,rows,contract)
                new,witnesses=complete_boundary_search(card,rows,new,contract)
                record.update(original_assessment=old,new_assessment=new,callback_evidence=proof,
                              boundary_witnesses=witnesses,axes=axes(new,q))
            else:
                if backend=='evas':
                    analyzed=reanalyze(card,rows,contract,backend=backend,program=program,response=response,producer_qualified=trusted)
                elif kind=='trace':
                    analyzed=reanalyze(card,rows,contract,backend=backend,executed_source=(work/'dut.va').read_text(),
                                       log=(work/'spectre.log').read_text(),producer_qualified=trusted)
                else:
                    old=breadth.assess(card,rows,contract)
                    analyzed={'original_assessment':old,'new_assessment':old,
                        'callback_evidence':{'status':'unknown','reason':'original attempt has no read-only callback trace'},
                        'strict_semantic_timing':'unresolved','serialized_resolution_timing':'evidence_insufficient'}
                record.update(analyzed)
            grade=record['new_assessment']['tiers'][tier]['status']
            record['status']=grade if trusted else 'evidence_insufficient'
            record['strict_semantic_timing']=record.get('strict_semantic_timing',record['new_assessment'].get('strict_semantic_timing','unresolved'))
            records.append(record)
    save(output/'REPORT.json',{'id':'root-window-v3','records':records,
        'claim':'new finite-resolution assessments beside unchanged originals; no strict no-early or universal alignment claim'})
    paths=set(load(base/'inputs/original/SOURCE_IDENTITY.json'))|{str(Path(__file__).relative_to(ROOT))}
    save(output/'ANALYSIS_IDENTITY.json',{'current_analysis':{rel:sha(ROOT/rel) for rel in sorted(paths)},
        'execution_source_identity_sha256':{kind:sha(base/'inputs'/kind/'SOURCE_IDENTITY.json') for kind in ('original','trace')},
        'analysis_changes_since_execution':{rel:{'execution':digest,'analysis':sha(ROOT/rel)}
            for rel,digest in load(base/'inputs/original/SOURCE_IDENTITY.json').items() if sha(ROOT/rel)!=digest},
        'claim':'execution snapshot verified separately; analysis revision never replaces frozen execution identity'})
    print(json.dumps([{k:r[k] for k in ('lane','condition','target_tier','status','strict_semantic_timing')} for r in records],indent=2))
    return records


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('base',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--previous-build',type=Path,required=True);p.add_argument('--previous-manifest',type=Path,required=True)
    a=p.parse_args();report(a.base.resolve(),a.output.resolve(),previous_build=a.previous_build.resolve(),previous_manifest=a.previous_manifest.resolve())
