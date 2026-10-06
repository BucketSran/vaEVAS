"""Execute only an explicitly allocated, frozen paper backend lane, without retries.

This is experiment tooling, not circuit orchestration. A profile/allocation file
records already granted resources; it does not itself grant execution permission.
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

from inputs import ROOT, BACKENDS, identity, save, sha, verify
from observations import read_native, normalize_observation
from process import execute
from settings_readback import spectre as spectre_readback, ngspice as ngspice_readback


def load(path):
    return json.loads(path.read_text())


def allocation_check(a, backend, inputs_sha, profile_sha):
    if a.get('backend')!=backend or a.get('input_manifest_sha256')!=inputs_sha or a.get('tool_profile_sha256')!=profile_sha:
        raise ValueError('allocation identity mismatch')
    caps={'max_simulation_launches':12,'max_compilation_launches':12,'stage_timeout_s':90,
          'license_timeout_s':30,'memory_limit_bytes':4*1024**3,'file_limit_bytes':32*1024**2,'threads':1}
    if any(type(a.get(k)) is not int or a[k]<=0 or a[k]>cap for k,cap in caps.items()):
        raise ValueError('missing or excessive allocation bound')
    if backend in ('openvaf_r_ngspice','gnucap_modelgen') and a['memory_limit_bytes']!=4*1024**3:
        raise ValueError('pinned container factory requires fixed 4GiB allocation')


def select_conditions(plan, allocation, backend):
    fixed=[r for r in plan if r['backend']==backend]
    if len(fixed)!=12 or len({r['condition'] for r in fixed})!=12:
        raise ValueError('paper plan requires twelve distinct conditions')
    ids=allocation.get('selected_condition_ids')
    known={r['condition'] for r in fixed}
    if (not isinstance(ids,list) or not ids or any(type(c) is not str for c in ids)
        or len(ids)!=len(set(ids)) or not set(ids)<=known):
        raise ValueError('allocation requires known distinct selected_condition_ids')
    if any(allocation[k]!=len(ids) for k in ('max_simulation_launches','max_compilation_launches')):
        raise ValueError('selected conditions differ from allocated launch counts')
    return [r for r in fixed if r['condition'] in ids]


def directory_budget(work, *, limit=256*1024**2):
    actual=sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
    return {'actual_bytes':actual,'limit_bytes':limit,
            'status':'within_limit' if actual<=limit else 'condition_directory_limit_exceeded',
            'measurement':'terminal directory files; not an active disk quota','runtime_hard_quota':False}


def stage_failure(stage):
    if not stage.get('cleanup',{}).get('complete'):
        return {'status':'cleanup_incomplete','failure_stage':stage['stage'],'abort_batch':True}
    status=stage.get('status')
    if status in ('cancelled','execution_error','cleanup_incomplete'):
        return {'status':status,'failure_stage':stage['stage'],'abort_batch':True}
    if stage.get('timeout'):
        return {'status':'compile_timeout' if stage['stage']=='compile' else 'runtime_timeout',
                'failure_stage':stage['stage'],'abort_batch':False}
    if status!='completed' or stage.get('returncode')!=0:
        return {'status':'compile_failed' if stage['stage']=='compile' else 'execution_failed',
                'failure_stage':stage['stage'],'abort_batch':False}
    return None


def result_state(stages, work, waveform, compiled=None, worker_result=None, *, backend=None):
    for stage in stages:
        failure=stage_failure(stage)
        if failure:
            return failure
    if compiled and not (work/compiled).is_file():
        return {'status':'missing_compile_artifact','failure_stage':'compile','abort_batch':False}
    if worker_result and worker_result.get('status')!='waveform_available':
        return {**worker_result,'abort_batch':False}
    if backend=='gnucap_modelgen' and (work/'simulate.log').is_file():
        # Gnucap can report deck parse failures, continue simulation and exit 0.
        # A raw file from that altered topology is retained, never accepted.
        diagnostics=[{'line_number':i,'text':line} for i,line in enumerate(
            (work/'simulate.log').read_text(errors='replace').splitlines(),1)
            if re.match(r"^\s*\^\s*\?\s*",line)]
        if diagnostics:
            rejected={'path':waveform,'sha256':sha(work/waveform)} if (work/waveform).is_file() else None
            return {'status':'deck_parse_error','failure_stage':'deck_parse','abort_batch':False,
                    'diagnostics':diagnostics,'diagnostic_log_sha256':sha(work/'simulate.log'),
                    'rejected_waveform':rejected}
    if not (work/waveform).is_file():
        return {'status':'missing_waveform','failure_stage':'export','abort_batch':False}
    return {'status':'waveform_available','waveform':waveform,'waveform_sha256':sha(work/waveform),'abort_batch':False}


def module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def verify_sources(inputs):
    for relative,digest in load(inputs/'ADAPTER_IDENTITY.json').items():
        path=ROOT/relative
        if not path.resolve().is_relative_to(ROOT.resolve()) or not path.is_file() or sha(path)!=digest:
            raise ValueError('execution source differs from freeze: '+relative)
    checker = load(inputs/'CHECKER_IDENTITY.json')
    if not checker:
        raise ValueError('checker integration was not frozen')
    for relative,digest in checker.items():
        path=ROOT/relative
        if not path.resolve().is_relative_to(ROOT.resolve()) or not path.is_file() or sha(path)!=digest:
            raise ValueError('checker differs from freeze: '+relative)
    for relative,digest in load(inputs/'RUNTIME_IDENTITY.json').items():
        path=ROOT/relative
        if not path.resolve().is_relative_to(ROOT.resolve()) or not path.is_file() or sha(path)!=digest:
            raise ValueError('EVAS runtime differs from freeze: '+relative)


def limits(argv, a):
    if sys.platform!='linux' or not hasattr(os,'sched_getaffinity'):
        raise ValueError('actual execution profile requires Linux taskset/prlimit; fixtures are portable')
    return ['taskset','-c',str(min(os.sched_getaffinity(0))),'prlimit',
            '--as='+str(a['memory_limit_bytes']),'--fsize='+str(a['file_limit_bytes']),'--',*argv]


def stage(argv, work, name, a, seconds=None):
    record=execute(limits(argv,a),work,name+'.log',min(seconds,a['stage_timeout_s']) if seconds else a['stage_timeout_s'])
    record['stage']=name
    record['resource_caps']={k:a[k] for k in ('memory_limit_bytes','file_limit_bytes','threads')}
    save(work/(name+'.json'),record)
    return record


def container_stage(env, image, executable, arguments, work, name, a, seconds=None):
    argv, owned=env.container(image,executable,arguments,work)
    # Pin actual OCI process limits; a host podman-client limit alone does not
    # constrain container children. Do not call the historical env.execute.
    at=argv.index('run')+1
    argv[at:at]=['--ulimit=fsize='+str(a['file_limit_bytes'])+':'+str(a['file_limit_bytes'])]
    record=None
    cleanup=[]
    try:
        record=stage(argv,work,name,a,seconds)
    finally:
        # Every return path, including successful leader exit, destroys our named
        # container and confirms absence before a following case can launch.
        remove=stage(env.podman()+['rm','-f',owned],work,name+'-container-remove',a,15)
        absent=stage(env.podman()+['container','exists',owned],work,name+'-container-absent',a,5)
        cleanup=[remove,absent]
        complete=(remove.get('status')=='completed' and not remove.get('timeout') and remove.get('cleanup',{}).get('complete') and absent.get('status')=='completed' and absent.get('returncode')==1
                  and absent.get('cleanup',{}).get('complete'))
        if record is not None:
            record['container_cleanup']={'name':owned,'complete':bool(complete),'commands':cleanup}
            record['cleanup']['complete']=record['cleanup']['complete'] and bool(complete)
            if not complete:
                record['status']='cleanup_incomplete'
            save(work/(name+'-final.json'),record)
        elif not complete:
            raise RuntimeError('container cleanup failed after launch exception')
    return record


def preflight(backend, profile, output, a):
    if profile.get('backend')!=backend:
        raise ValueError('tool profile backend mismatch')
    tool={'profile_identity':identity(profile),'unknowns':[]}
    if backend=='evas':
        kernel=Path(profile['kernel']).resolve()
        if sha(kernel)!=profile['kernel_sha256']:
            raise ValueError('explicit kernel hash drift')
        record=stage([str(kernel),'--version','--json'],output,'version',a,5)
        if stage_failure(record):
            raise RuntimeError('kernel preflight failed')
        reported=json.loads((output/'version.log').read_text())
        sys.path.insert(0,str(ROOT/'evas/src'))
        from evas.ir import SCHEMA_VERSION
        if reported.get('name')!='evas-kernel' or reported.get('ir_schema_version')!=SCHEMA_VERSION:
            raise ValueError('kernel identity/IR mismatch')
        tool.update(kernel=str(kernel),kernel_sha256=sha(kernel),reported=reported,probe=record,
                    interpreter={'path':sys.executable,'version':sys.version})
        if reported.get('build_revision') is None:
            tool['unknowns'].append('kernel build revision not reported; source identity alone does not prove binary provenance')
        return tool,None
    if backend=='spectre':
        binary=profile['binary']; setups=profile['setup_scripts']
        if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',p) for p in [binary,*setups]):
            raise ValueError('unsafe tool path')
        if sha(Path(binary))!=profile['binary_sha256'] or {p:sha(Path(p)) for p in setups}!=profile['setup_sha256']:
            raise ValueError('Spectre binary/setup drift')
        setup=''.join('source '+p+'\n' for p in setups)
        (output/'version.csh').write_text(setup+binary+' -W\nexit $status\n')
        record=stage(['/bin/csh','-f','version.csh'],output,'version',a,30)
        if stage_failure(record):
            raise RuntimeError('Spectre preflight failed')
        tool.update(binary=binary,binary_sha256=sha(Path(binary)),setup_sha256=profile['setup_sha256'],
                    version=(output/'version.log').read_text().strip(),probe=record,setup=setup)
        if not tool['version']:
            raise ValueError('empty Spectre version')
        return tool,None
    directory=Path(profile['environment']).resolve()
    path=directory/'environment.py'
    if sha(path)!=profile['environment_sha256'] or sha(directory/'INPUT_MANIFEST.json')!=profile['environment_manifest_sha256']:
        raise ValueError('pinned environment source/manifest drift')
    # Inspect package hashes before importing its code. Never trust a nearby
    # environment solely because its path was used by an earlier run.
    package_manifest=load(directory/'INPUT_MANIFEST.json')
    if 'IMAGE_IDENTITIES.json' not in package_manifest:
        raise ValueError('image identity file not bound by pinned manifest')
    for relative,digest in package_manifest.items():
        file=(directory/'package'/relative).resolve()
        if not file.is_relative_to((directory/'package').resolve()) or sha(file)!=digest:
            raise ValueError('pinned package drift')
    env=module(path,'paper_environment')
    images=load(directory/'package/IMAGE_IDENTITIES.json')
    names=('openvaf_runtime','ngspice') if backend=='openvaf_r_ngspice' else ('gnucap',)
    for name in names:
        if images[name]['config_id']!=profile['images'][name]['config_id']:
            raise ValueError('pinned image drift')
        record=stage(env.podman()+['image','inspect',images[name]['config_id']],output,'image-'+name,a,30)
        if stage_failure(record):
            raise RuntimeError('image preflight failed')
        actual=json.loads((output/('image-'+name+'.log')).read_text())[0]
        if actual['Id'].removeprefix('sha256:')!=images[name]['config_id'].removeprefix('sha256:') or actual['Architecture']!='amd64':
            raise ValueError('actual image identity mismatch')
    tool.update(images={n:images[n] for n in names},environment_sha256=sha(path),
                environment_manifest_sha256=sha(directory/'INPUT_MANIFEST.json'))
    probes=[('openvaf_runtime','/compiler/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r'),
            ('ngspice','/opt/ngspice/bin/ngspice')] if backend=='openvaf_r_ngspice' else [
            ('gnucap','/opt/gnucap/bin/gnucap-mg-vams')]
    versions={}
    for name,exe in probes:
        record=container_stage(env,images[name]['config_id'],exe,['--version'],output,'version-'+name,a,30)
        if stage_failure(record):
            raise RuntimeError('container component version failed')
        versions[name]={'probe':record,'self_report':(output/('version-'+name+'.log')).read_text().strip() or 'unknown'}
    tool['versions']=versions
    tool['compiler_flags']=['dut.va','-o','dut.osdi'] if backend=='openvaf_r_ngspice' else ['-I','/opt/gnucap/include/gnucap','--cc','-std=c++14','-fPIC','-shared']
    if backend=='openvaf_r_ngspice':
        compiler=env.PACKAGE/'backend-semantics-v1/tools/reloaded/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r'
        if sha(compiler)!=profile['compiler_sha256']:
            raise ValueError('OpenVAF-R compiler hash drift')
        tool['compiler_sha256']=sha(compiler)
    return tool,env


def verify_tool(tool, profile, env):
    """Check mutable executable/setup bytes again before each condition."""
    backend=profile['backend']
    if backend=='evas':
        if sha(Path(tool['kernel']))!=tool['kernel_sha256']:
            raise ValueError('kernel changed after preflight')
    elif backend=='spectre':
        if sha(Path(tool['binary']))!=tool['binary_sha256'] or {p:sha(Path(p)) for p in profile['setup_scripts']}!=tool['setup_sha256']:
            raise ValueError('Spectre tool/setup changed after preflight')
    else:
        if sha(Path(profile['environment'])/'environment.py')!=tool['environment_sha256']:
            raise ValueError('container environment changed after preflight')
        manifest=Path(profile['environment'])/'INPUT_MANIFEST.json'
        if sha(manifest)!=tool['environment_manifest_sha256']:
            raise ValueError('pinned container manifest changed after preflight')
        for relative,digest in load(manifest).items():
            if sha(env.PACKAGE/relative)!=digest:
                raise ValueError('pinned container package changed after preflight')
        if backend=='openvaf_r_ngspice':
            compiler=env.PACKAGE/'backend-semantics-v1/tools/reloaded/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r'
            if sha(compiler)!=tool['compiler_sha256']:
                raise ValueError('compiler changed after preflight')


def worker(work, kernel):
    """Normal compiler/top hierarchy, current transient API, no source rewriting."""
    sys.path.insert(0,str(ROOT/'evas/src'))
    from evas import CompileError, KernelError, Instance, compile_sources, transient
    request=load(work/'request.json')
    result={'status':'execution_failed','reason':'worker did not complete'}
    try:
        instances=[Instance(i['name'],i['module'],i['ports'],i['parameters']) for i in request['instances']]
        program=compile_sources({'dut.va':(work/'dut.va').read_text()},instances)
        save(work/'program.json',program.to_dict())
        times=load(work/request['requested_times'])
        response=transient(program,request['inputs'],times,stop=request['stop'],max_step=request['max_step'],
                           kernel=kernel,vabstol=request['vabstol'],reltol=request['reltol'],timeout=None)
        save(work/'raw-response.json',response)
        # Owned outer stage kills the complete worker/kernel group at its limit.
        with (work/'waveform.csv').open('x') as f:
            writer=csv.writer(f)
            writer.writerow(['time',*response['nodes']])
            writer.writerows([t,*r['voltages']] for t,r in zip(times,response['solutions'],strict=True))
        save(work/'effective.json',{'request_echo':{'reltol':request['reltol'],'vabstol':request['vabstol'],
            'stop':request['stop'],'maxstep':request['max_step']},
            'observed_response':{'engine':response['engine'],'accepted_steps':response['transient'].get('accepted_steps')},
            'unsupported_controls':['iabstol','integration_method'],
            'sample_origin':'unknown; output query is not automatically an accepted step',
            'settings_readback':'unknown; current response does not report applied tolerances/maxstep/stop'})
        result={'status':'waveform_available','waveform':'waveform.csv'}
    except CompileError as exc:
        result={'status':'compile_failed','failure_stage':'compile','reason':str(exc)}
    except KernelError as exc:
        result={'status':'execution_failed','failure_stage':'kernel','reason':str(exc),'detail':exc.detail}
    except Exception as exc:
        result={'status':'execution_failed','failure_stage':'worker','exception_type':type(exc).__name__,'reason':str(exc)}
    save(work/'worker-result.json',result)


def effective_settings(work, backend):
    request=load(work/'requested_settings.json')
    expected={'reltol':request['reltol'],'vabstol':request['vabstol_V'],
              'iabstol':request['iabstol_A'],'stop':request['stop_s'],
              'maxstep':request['maxstep_s'] if backend in ('evas','spectre') else request['spice_maxstep_s']}
    if backend=='evas':
        record=load(work/'effective.json')
        return {'status':'I','actual':{k:'unknown' for k in expected},'requested':expected,
                'request_echo':record.get('request_echo',{k:record[k] for k in ('reltol','vabstol','stop','maxstep') if k in record}),
                'observed_response':record.get('observed_response',{k:record[k] for k in ('engine','accepted_steps') if k in record}),
                'claim':'current EVAS response does not establish effective settings; request echo is not readback'}
    elif backend in ('spectre','openvaf_r_ngspice'):
        if backend=='spectre':
            scoped=spectre_readback((work/'spectre.log').read_text(),
                                   (work/'psf/tran.tran.tran').read_text())
        else:
            scoped=ngspice_readback((work/'simulate.log').read_text(),(work/'tb.cir').read_text())
        keymap={'reltol':'reltol','vabstol':'vabstol_V','iabstol':'iabstol_A',
                'stop':'stop_s','maxstep':'maxstep_s'}
        actual={k:scoped['effective'][v]['value'] if v in scoped['effective'] else
                'unknown; deck invocation is not runtime setting readback' for k,v in keymap.items()}
        actual['method']=scoped['effective']['method']['value']
        names=tuple(k for k in expected if isinstance(actual[k],(int,float)))
        mismatches=[k for k in names if not math.isclose(actual[k],expected[k],rel_tol=1e-12,abs_tol=0)]
        return {'actual':actual,'requested':expected,'mismatches':mismatches,'scoped_readback':scoped,
                'status':'I' if mismatches or backend=='openvaf_r_ngspice' else 'readback_matches',
                'claim':'scoped controls do not establish mathematical or native provenance qualification; actual/requested differences remain'}
    else:
        # Preserve logged actual settings without the historical audit's fixed
        # numdgt=16 assert. Paper uses17digits, so this has its own settings parser.
        log=(work/'simulate.log').read_text()
        if re.search(r'^\s*\^\s*\?\s*',log,re.M):
            raise ValueError('Gnucap deck parse error; settings are not qualified')
        actual={}
        for name,target in [('reltol','reltol'),('vntol','vabstol'),('abstol','iabstol')]:
            pattern=r'\b'+name+r'=\s*(\S+)'
            matches=re.findall(pattern,log,re.M)
            if not matches:
                raise ValueError('missing effective setting: '+name)
            token=matches[-1]
            # Reuse the parser's calibrated SPICE numeric suffix conversion.
            from observations import READER_DIR
            old=sys.modules.get('suite')
            try:
                sys.modules['suite']=module(READER_DIR/'suite.py','paper_setting_suite')
                reader=module(READER_DIR/'analyze.py','paper_setting_number')
                actual[target]=reader.number(token)
            finally:
                if old is None: sys.modules.pop('suite',None)
                else: sys.modules['suite']=old
        names=('reltol','vabstol','iabstol')
        actual['stop']='unknown; waveform extent is not setting readback'
        actual['maxstep']='unknown; requested deck is not setting readback'
    mismatches=[k for k in names if not math.isclose(actual[k],expected[k],rel_tol=1e-12,abs_tol=0)]
    return {'actual':actual,'requested':expected,'mismatches':mismatches,
            'status':'I' if mismatches or backend in ('gnucap_modelgen','openvaf_r_ngspice') else 'readback_matches',
            'claim':'setting equality does not establish equivalent backend error control'}


def run(args):
    inputs=args.inputs.resolve(); output=args.output.resolve()
    plan=verify(inputs)
    verify_sources(inputs)
    profile=load(args.tool_profile); a=load(args.allocation)
    allocation_check(a,args.backend,sha(inputs/'INPUT_MANIFEST.json'),sha(args.tool_profile))
    if output.is_relative_to(inputs):
        raise ValueError('output must be outside frozen inputs')
    fixed=[r for r in plan if r['backend']==args.backend]
    selected=select_conditions(plan,a,args.backend)
    selected_ids={r['condition'] for r in selected}
    output.mkdir(parents=True,exist_ok=False)
    save(output/'STARTED.json',{'backend':args.backend,'allocation':a,'input_manifest_sha256':sha(inputs/'INPUT_MANIFEST.json'),
         'tool_profile_sha256':sha(args.tool_profile),'runner_sha256':sha(Path(__file__)),
         'fixed_conditions':[r['condition'] for r in fixed],'selected_condition_ids':[r['condition'] for r in selected],'speed_comparison':False})
    try:
        tool,env=preflight(args.backend,profile,output,a)
    except Exception as exc:
        save(output/'PREFLIGHT_FAILED.json',{'reason':str(exc),'status':'preflight_failed','cases_launched':0})
        final=[{**r,'status':'not_run','reason':'preflight failed: '+str(exc) if r['condition'] in selected_ids else 'not_selected_in_allocation'} for r in fixed]
        save(output/'DIRECTORY_BUDGETS.json',{})
        save(output/'EXECUTION.json',final)
        for record in final:
            save(output/('final-record-'+record['condition']+'.json'),record)
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
                                          for p in sorted(output.rglob('*')) if p.is_file()})
        raise
    save(output/'TOOL_IDENTITY.json',tool)
    data=load(inputs/'core.json'); results=[]
    active=None; work=None; stages=[]; launched=False; abort=None; failure_stage='batch_setup'
    try:
        for row in selected:
            active=row; work=None; stages=[]; launched=False
            failure_stage='source_identity'
            verify_sources(inputs)
            failure_stage='tool_identity'
            verify_tool(tool,profile,env)
            failure_stage='input_identity'
            if sha(inputs/'INPUT_MANIFEST.json')!=a['input_manifest_sha256']:
                raise ValueError('input manifest changed after allocation')
            verify(inputs)
            failure_stage='prepare'
            # Every allocation creates a new output. The coordinator may select
            # previously unlaunched conditions under the same frozen identity.
            # This runner never resumes or retries an existing result.
            work=output/'runs'/row['condition']
            shutil.copytree(inputs/row['work'],work)
            save(work/'STARTED.json',{'condition':row['condition'],'tool_identity_sha256':sha(output/'TOOL_IDENTITY.json'),
                 'source_sha256':sha(work/'dut.va'),'deck_sha256':sha(work/row['deck'])})
            stages=[]; compiled=None; worker_result=None
            if args.backend=='evas':
                waveform='waveform.csv'
                failure_stage='simulate'; launched=True
                stages.append(stage([sys.executable,'-B',str(Path(__file__).resolve()),'worker',str(work),tool['kernel']],work,'simulate',a))
                worker_result=load(work/'worker-result.json') if (work/'worker-result.json').is_file() else {'status':'execution_failed','failure_stage':'worker','reason':'missing worker result'}
            elif args.backend=='spectre':
                waveform='psf/tran.tran.tran'
                command=tool['setup']+tool['binary']+' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout '+str(a['license_timeout_s'])+' +mt=1\nexit $status\n'
                (work/'run.csh').write_text(command)
                failure_stage='simulate'; launched=True
                stages.append(stage(['/bin/csh','-f','run.csh'],work,'simulate',a))
            else:
                waveform='waveform.txt'
                if args.backend=='openvaf_r_ngspice':
                    compiled='dut.osdi'
                    failure_stage='compile'; launched=True
                    stages.append(container_stage(env,tool['images']['openvaf_runtime']['config_id'],
                        '/compiler/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r',['dut.va','-o',compiled],work,'compile',a))
                    image=tool['images']['ngspice']['config_id']; executable='/opt/ngspice/bin/ngspice'; arguments=['-b','tb.cir']
                else:
                    compiled='dut.so'; image=tool['images']['gnucap']['config_id']
                    compile_command='/opt/gnucap/bin/gnucap-mg-vams -I /opt/gnucap/include/gnucap -o dut.cc --cc dut.va && /usr/bin/c++ -std=c++14 -I /opt/gnucap/include/gnucap -fPIC -shared dut.cc -o dut.so'
                    failure_stage='compile'; launched=True
                    stages.append(container_stage(env,image,'/bin/sh',['-c',compile_command],work,'compile',a))
                    executable='/opt/gnucap/bin/gnucap'; arguments=['tb.gc']
                if not stage_failure(stages[-1]) and (work/compiled).is_file():
                    failure_stage='simulate'; launched=True
                    stages.append(container_stage(env,image,executable,arguments,work,'simulate',a))
            failure_stage='result_collection'
            result={**row,**result_state(stages,work,waveform,compiled,worker_result,backend=args.backend),'stages':stages,
                    'compiled_artifacts':{n:sha(work/n) for n in ('dut.osdi','dut.so','dut.cc') if (work/n).is_file()}}
            failure_stage='observation'
            if result['status']=='waveform_available':
                try:
                    rows=read_native(work/waveform,args.backend)
                    if args.backend=='gnucap_modelgen' and any(not math.isfinite(r.get('bench_ref',math.nan)) or abs(r['bench_ref'])>1e-7 for r in rows):
                        raise ValueError('unqualified Gnucap ground alias')
                    card=load(work/'condition.json')
                    observation=normalize_observation(card,args.backend,rows,['unknown']*len(rows),contract=data['shared_contract'],T=data['units']['T_s'])
                    save(work/'observation.json',observation)
                    result['observation']={'path':str((work/'observation.json').relative_to(output)),
                        'sha256':sha(work/'observation.json'),'status':observation['status'],
                        'qualification':'I; actual origins and independent error certificates pending'}
                    result['source_deck_acceptance']='tool accepted execution; LRM/source qualification still requires independent evidence'
                except (ValueError,KeyError,TypeError,IndexError,OSError) as exc:
                    result.update(status='observation_invalid',observation_error=str(exc))
                try:
                    result['effective_settings']=effective_settings(work,args.backend)
                except (ValueError,KeyError,TypeError,OSError) as exc:
                    result['effective_settings']={'status':'I','reason':str(exc)}
            failure_stage='result_receipt'
            save(work/'RESULT.json',result)
            results.append(result)
            save(output/('record-'+row['condition']+'.json'),result)
            if result['abort_batch']:
                abort={'condition':row['condition'],'reason':result['status'],
                       'failure_stage':result.get('failure_stage',failure_stage)}
                break
    except BaseException as exc:
        abort={'condition':active['condition'] if active else None,'reason':str(exc),
               'failure_stage':failure_stage,'exception_type':type(exc).__name__}
        if active and not any(r['condition']==active['condition'] for r in results):
            failed={**active,'status':'execution_error' if launched else 'not_run',
                    'failure_stage':failure_stage,'reason':str(exc),'abort_batch':True,'stages':stages}
            results.append(failed)
            save(output/('record-'+active['condition']+'.json'),failed)
        raise
    finally:
        recorded={r['condition'] for r in results}
        results.extend({**r,'status':'not_run','reason':'batch aborted before this condition'}
                       for r in fixed if r['condition'] not in recorded and r['condition'] in selected_ids)
        results.extend({**r,'status':'not_run','reason':'not_selected_in_allocation'}
                       for r in fixed if r['condition'] not in selected_ids)
        budgets={}
        for record in results:
            directory=output/'runs'/record['condition']
            if directory.is_dir():
                budget=directory_budget(directory)
                budgets[record['condition']]=budget
                record['directory_budget']=budget
                if budget['status']!='within_limit':
                    record['execution_status_before_budget']=record['status']
                    record.update(status='condition_directory_limit_exceeded',failure_stage='terminal_directory_budget')
        save(output/'DIRECTORY_BUDGETS.json',budgets)
        if abort:
            abort['unrun']=[r['condition'] for r in results if r['status']=='not_run' and r['condition'] in selected_ids]
            abort['not_selected_in_allocation']=[r['condition'] for r in results if r['condition'] not in selected_ids]
            save(output/'BATCH_ABORTED.json',abort)
        save(output/'EXECUTION.json',results)
        for record in results:
            save(output/('final-record-'+record['condition']+'.json'),record)
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
                                          for p in sorted(output.rglob('*')) if p.is_file()})



if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':
        worker(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('inputs',type=Path); parser.add_argument('output',type=Path)
        parser.add_argument('--backend',choices=BACKENDS,required=True)
        parser.add_argument('--tool-profile',type=Path,required=True)
        parser.add_argument('--allocation',type=Path,required=True)
        run(parser.parse_args())
