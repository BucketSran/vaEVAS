"""Benchmark-owned VA07 eight-case replay, with independent sampled evidence."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import types

SUPPORTED_ORACLES = {
    '46a5342f52b4add0df50ef6d4b28d6ed7761303bfa4f5d04dffc2fc53c73d8dd': 'cc386977 original canonical checker',
    '9e38eb5abcf0db2122355415b50904c9a4a8d01cf0e2b243861d83d9600171ea': '862d3fbb report-only classification fix',
}
ORACLE_PATH = Path(__file__).with_name('triangle_oscillator.py')
ORACLE_BYTES = ORACLE_PATH.read_bytes()
if hashlib.sha256(ORACLE_BYTES).hexdigest() not in SUPPORTED_ORACLES:
    raise ValueError('canonical oracle is not an explicitly calibrated full source file')
oracle = types.ModuleType('_va07_replay_oracle')
exec(compile(ORACLE_BYTES, str(ORACLE_PATH), 'exec'), oracle.__dict__)
SOLVER_OPTIONS = {'vabstol': 1e-8, 'reltol': 0}
LOADED_CHECKER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CASE_FIELDS = {'name','lo','hi','initial','direction','control','stop','maxstep','ttol','vtol','wave_atol','time_atol','reltol','vabstol','iabstol','method','netlist'}
CASES_SHA256 = 'df84f3123a91a8ef6e70818d5437db8e101c871aba8d5da85c7e8302653417e1'
CASE_NAMES = [f'{kind}-{level}' for kind in ['constant','descending','ramp','segments'] for level in ['tight','tighter']]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n')


def prepare_requests(case):
    """Predeclare both grids from the original condition, before reading a candidate."""
    if set(case)!=CASE_FIELDS:
        raise ValueError('unknown or missing case fields')
    if case['name'] not in CASE_NAMES:
        raise ValueError('unknown original VA07 case')
    times = sorted({0.,case['stop'],*[i*case['maxstep'] for i in range(int(case['stop']/case['maxstep'])+1)]})
    request = dict(models=['dut.va'], instances=[dict(name='dut',module='triangle',
        connections=dict(ctl='ctl',z='z',count='count',r='0'),parameters=dict(
            lower=case['lo'],upper=case['hi'],initial_voltage=case['initial'],
            direction=case['direction'],ttol=case['ttol'],vtol=case['vtol']))],
        transient=dict(sources={'ctl':copy.deepcopy(case['control'])},output_times=times,
            stop=case['stop'],max_step=case['maxstep']),tolerances=dict(SOLVER_OPTIONS))
    observation = copy.deepcopy(request)
    observation['transient']['output_times'] = sorted(set(times + [t+d for t in oracle.roots(case)
        for d in [-case['time_atol']/2,case['time_atol']/2] if 0<t+d<case['stop']]))
    mapping = dict(source_case=copy.deepcopy(case),evas_requested_settings=dict(SOLVER_OPTIONS),
        spectre_settings={k:case[k] for k in ['vabstol','reltol','iabstol','method']},
        unmapped_solver_settings={k:case[k] for k in ['iabstol','method']},
        basis='Existing oscillator compatibility mapping; no claim of solver-setting equivalence.',
        timing_authority='sampled_count_brackets',observation_basis='Analytic roots +/- time_atol/2; no kernel event authority.')
    return {'baseline':request,'observation':observation}, mapping


def rows_from_response(data, times):
    nodes = data['nodes']
    if any(type(t) not in (float,int) or not math.isfinite(t) for t in data['transient']['times']):
        raise ValueError('invalid response times')
    if (not isinstance(nodes,list) or any(not isinstance(n,str) for n in nodes)
        or len(set(nodes))!=len(nodes) or not {'z','count'}<=set(nodes)
        or data['transient']['times']!=times or len(data['solutions'])!=len(times)):
        raise ValueError('incomplete task signals or observation grid')
    rows=[]
    for t,solution in zip(times,data['solutions']):
        voltages=solution['voltages']
        if len(voltages)!=len(nodes) or any(type(v) not in (int,float) or not math.isfinite(v) for v in voltages):
            raise ValueError('invalid task voltage row')
        rows.append(dict(time=t,**dict(zip(nodes,voltages))))
    return rows


def assess_case(case, baseline, observation):
    """Apply original behavior thresholds, conservatively bounding sampled events."""
    requests,_=prepare_requests(case)
    try:
        rows={name:rows_from_response(data,requests[name]['transient']['output_times'])
              for name,data in [('baseline',baseline),('observation',observation)]}
    except (KeyError,TypeError,ValueError,OverflowError) as error:
        return dict(verdict='not_evaluated',reason=str(error))
    result=dict(verdict='pass',timing_authority='sampled_count_brackets',diagnostics={})
    for name,values in rows.items():
        try:
            measured=oracle.evaluate(values,case)
        except ValueError as error:
            measured=dict(passed=False,reason=str(error))
        result['diagnostics'][name]=measured
        # The original oracle reports metrics only after its count checks pass.
        if measured.get('max_voltage_error_v',math.inf)>case['wave_atol']:
            result['verdict']='fail'
    common={r['time']:r for r in rows['observation']}
    discrepancy=max(abs(r['z']-common[r['time']]['z']) for r in rows['baseline'])
    result['common_grid_max_voltage_difference_v']=discrepancy
    brackets=[[a['time'],b['time']] for a,b in zip(rows['observation'],rows['observation'][1:])
              if round(a['count'])!=round(b['count'])]
    expected=oracle.roots(case)
    result['observed_event_brackets_s']=brackets
    bounded=len(brackets)==len(expected) and all(max(abs(a-root),abs(b-root))<=case['time_atol']
        for (a,b),root in zip(brackets,expected))
    if result['verdict']!='fail' and (not bounded or discrepancy>case['wave_atol']):
        result.update(verdict='inconclusive',reason='Independent samples do not establish timing or grid consistency.')
    return result


def runtime_identity(kernel):
    import importlib.util
    spec=importlib.util.find_spec('evas')
    if spec is None or spec.origin is None or spec.submodule_search_locations is None or not Path(spec.origin).is_file():
        raise RuntimeError('EVAS Python package unavailable')
    root=Path(spec.origin).resolve().parent
    if any(root.rglob('*.pyc')) or any(root.rglob('*.pyo')):
        raise RuntimeError('EVAS bytecode caches are forbidden; provide source-only runtime')
    return dict(package_root=str(root),kernel_sha256=digest(kernel),python_sha256=digest(sys.executable),
        evas_python={str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*.py'))})


def execute_request(request, work, kernel, timeout_s):
    """Bound the external CLI process group and both log files."""
    import resource
    import signal
    identity=runtime_identity(kernel)
    cache=work/'.python-cache'
    cache.mkdir()
    environment=dict(os.environ,PYTHONPYCACHEPREFIX=str(cache),PYTHONDONTWRITEBYTECODE='1')
    bootstrap="import runpy,sys;sys.path.insert(0,sys.argv.pop(1));sys.argv[0]='evas';runpy.run_module('evas',run_name='__main__')"
    dump(work/'request.json',request)
    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024*1024,16*1024*1024))
    with (work/'raw.json').open('w') as stdout,(work/'stderr.log').open('w') as stderr:
        process=subprocess.Popen([sys.executable,'-B','-c',bootstrap,str(Path(identity['package_root']).parent),'transient',str(work/'request.json'),
            '--kernel',str(kernel),'--timeout',str(timeout_s)],stdout=stdout,stderr=stderr,
            start_new_session=True,preexec_fn=limits,env=environment)
        try:
            code=process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            process.wait()
            return dict(execution='timeout',returncode=None)
    if code!=0:
        return dict(execution='backend_error',returncode=code,stderr_sha256=digest(work/'stderr.log'))
    try:
        data=json.loads((work/'raw.json').read_text())
    except (ValueError,OSError) as error:
        return dict(execution='invalid_result',reason=str(error),returncode=code)
    return dict(execution='ok',returncode=0,raw_sha256=digest(work/'raw.json'),data=data)


def verify(candidate, output, cases_path, kernel, solver_options, timeout_s=15):
    """Produce a full eight-entry report; only complete grading produces reward."""
    cases=json.loads(cases_path.read_text())
    if digest(cases_path)!=CASES_SHA256 or [c['name'] for c in cases]!=CASE_NAMES:
        raise ValueError('replay requires the original eight-case file bytes')
    output.mkdir(parents=True,exist_ok=False)
    report=dict(candidate_sha256=digest(candidate),checker_sha256=digest(__file__),
        cases_sha256=digest(cases_path),solver_options=solver_options,status='unevaluable',reward=None,
        cases=[dict(name=c['name'],status='not_evaluated',passed=None,reason='not attempted') for c in cases])
    try:
        if solver_options!=SOLVER_OPTIONS:
            raise ValueError('only the explicitly declared fixed EVAS solver mapping is supported')
        if type(timeout_s) not in (int,float) or not math.isfinite(timeout_s) or not 0<timeout_s<=15:
            raise ValueError('execution timeout must be positive and at most 15 seconds')
        identity=runtime_identity(kernel)
        report['runtime']=identity
        source=candidate.read_bytes()
        if hashlib.sha256(source).hexdigest()!=report['candidate_sha256'] or digest(__file__)!=LOADED_CHECKER_SHA256:
            raise ValueError('loaded source or candidate identity differs')
        mapping_path=Path(__file__).with_name('mapping.json')
        if mapping_path.exists():
            declaration=json.loads(mapping_path.read_text())
            planned=[dict(name=c['name'],requests=prepare_requests(c)[0],mapping=prepare_requests(c)[1]) for c in cases]
            if declaration.get('solver_options')!=SOLVER_OPTIONS or declaration.get('cases')!=planned:
                raise ValueError('frozen mapping differs from prepared requests')
        for case,record in zip(cases,report['cases']):
            requests,mapping=prepare_requests(case)
            record.update(mapping=mapping,executions={})
            values={}
            try:
                for name,request in requests.items():
                    if runtime_identity(kernel)!=identity or candidate.read_bytes()!=source or ORACLE_PATH.read_bytes()!=ORACLE_BYTES or digest(__file__)!=LOADED_CHECKER_SHA256:
                        raise ValueError('runtime, candidate or oracle changed during replay')
                    work=output/case['name']/name
                    work.mkdir(parents=True)
                    (work/'dut.va').write_bytes(source)
                    execution=execute_request(request,work,kernel,timeout_s)
                    raw=execution.pop('data',None)
                    record['executions'][name]=execution
                    if execution['execution']!='ok':
                        record.update(reason=f'{name}: {execution["execution"]}')
                        break
                    values[name]=raw
                if runtime_identity(kernel)!=identity or candidate.read_bytes()!=source or ORACLE_PATH.read_bytes()!=ORACLE_BYTES or digest(__file__)!=LOADED_CHECKER_SHA256:
                    raise ValueError('runtime, candidate or oracle changed during replay')
                if len(values)!=2:
                    continue
                assessment=assess_case(case,**values)
                record.update(assessment)
                if assessment['verdict'] in ['pass','fail']:
                    record.update(status='graded',passed=assessment['verdict']=='pass',
                        waveform_sha256=record['executions']['observation']['raw_sha256'])
                    record.pop('reason',None)
                else:
                    record.update(reason=assessment.get('reason','independent evidence incomplete'))
            except (OSError,ValueError,TypeError,KeyError,RuntimeError) as error:
                record.update(reason=str(error))
        if all(r['status']=='graded' for r in report['cases']):
            report.update(status='completed',reward=int(all(r['passed'] for r in report['cases'])))
    except (OSError,ValueError,RuntimeError) as error:
        report.update(status='checker_error',reason=str(error))
        for record in report['cases']:
            record['reason']=str(error)
    dump(output/'report.json',report)
    if report['reward'] is not None:
        (output/'reward.txt').write_text(str(report['reward'])+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cases',type=Path,default=Path(__file__).with_name('cases.json'))
    parser.add_argument('--kernel',type=Path,default=Path(os.environ.get('EVAS_KERNEL','/opt/evas/evas-kernel')))
    args=parser.parse_args()
    options=json.loads(os.environ.get('CHIPS_SOLVER_OPTIONS','null'))
    report=verify(args.candidate.resolve(),args.output.resolve(),args.cases.resolve(),args.kernel.resolve(),options)
    print(json.dumps(dict(status=report['status'],reward=report['reward'])))
    return 0 if report['reward'] is not None else 2


if __name__=='__main__':
    raise SystemExit(main())
