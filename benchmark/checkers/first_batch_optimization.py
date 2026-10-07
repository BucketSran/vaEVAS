"""Trusted evidence primitives for simulation implementation optimization.

No speed/step threshold is chosen here. Functional grading and actual repeated
measurements must establish a candidate before a Harbor performance task exists.
"""
import hashlib
import importlib.util
import math
from pathlib import Path
import re


class OptimizationEvidenceError(ValueError):
    """Evidence is incomplete, ambiguous, or not trustworthy for performance."""


FORBIDDEN_LOG_OR_CONTROL_TASKS=frozenset({
    b'$display',b'$strobe',b'$write',b'$monitor',b'$debug',
    b'$fdisplay',b'$fstrobe',b'$fwrite',b'$fmonitor',
    b'$info',b'$warning',b'$error',b'$fatal',
    b'$finish',b'$stop',b'$exit',b'$abort',
})
UNITS={'s':1.,'ms':1e-3,'us':1e-6,'ns':1e-9}
NUMBER=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
TIME_PAIR=rf'\s*CPU\s*=\s*({NUMBER})\s*(s|ms|us|ns),\s*elapsed\s*=\s*({NUMBER})\s*(s|ms|us|ns)[.,]'


def validate_performance_source(source):
    """Reject active log/control tasks; comments and quoted text are inert.

    The shared submission boundary still owns includes, file I/O, and external
    reads. This additional restriction is part of a performance task's public
    contract because a candidate may otherwise forge native timing messages.
    """
    path=Path(__file__).with_name('adc_linearity.py')
    spec=importlib.util.spec_from_file_location('_optimization_tokens',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not isinstance(source,bytes):
        raise TypeError('source must be bytes')
    active={value for kind,value,_,_ in module.source_tokens(source)
            if kind=='identifier' and value in FORBIDDEN_LOG_OR_CONTROL_TASKS}
    if active:
        names=', '.join(task.decode() for task in sorted(active))
        raise OptimizationEvidenceError('performance submissions cannot print or control solver execution: '+names)
    return dict(version='optimization-native-io-v1',source_sha256=hashlib.sha256(source).hexdigest(),passed=True)


def one_match(pattern,text,label,required=True):
    matches=list(re.finditer(pattern,text,re.M))
    if not matches and not required:return None
    if len(matches)!=1:
        raise OptimizationEvidenceError(f'{label} must occur exactly once; observed {len(matches)}')
    return matches[0]


def time_pair(log,label):
    match=one_match(r'^'+re.escape(label)+TIME_PAIR,log,label)
    cpu,cu,elapsed,eu=match.groups()
    cpu=float(cpu)*UNITS[cu];elapsed=float(elapsed)*UNITS[eu]
    if not all(math.isfinite(v) and v>=0 for v in (cpu,elapsed)):
        raise OptimizationEvidenceError('invalid native analysis time')
    return dict(cpu_s=cpu,elapsed_s=elapsed)


def read_native_statistics(log):
    """Parse a native Spectre +log file after source and subprocess checks.

    Do not pass candidate stdout/stderr as if it were a native log. A caller
    must separately retain/check subprocess return code, stdout, stderr, complete
    waveform coverage and the performance source guard. Default logs omit
    rejected steps; missing is unknown, never zero.
    """
    if isinstance(log,bytes):
        log=log.decode('utf-8',errors='strict')
    if not isinstance(log,str):
        raise TypeError('log must be text or UTF-8 bytes')
    one_match(r'^Spectre \(R\) Circuit Simulator\s*$',log,'native simulator header')
    version=one_match(r'^Version ([^\r\n]+)\s*$',log,'native version').group(1).strip()
    footer=one_match(r'^spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?\.\s*$',log,'native completion footer')
    errors,warnings,notices=map(int,footer.groups())
    if errors:
        raise OptimizationEvidenceError('native solver reports errors')
    accepted=int(one_match(r'^Number of accepted tran steps\s*=\s*(\d+)\s*$',log,'accepted transient steps').group(1))
    if accepted<=0:
        raise OptimizationEvidenceError('no accepted transient work')
    rejected_match=one_match(r'^Number of rejected tran steps\s*=\s*(\d+)\s*$',log,'rejected transient steps',required=False)
    rejected=int(rejected_match.group(1)) if rejected_match else None
    intrinsic=time_pair(log,'Intrinsic tran analysis time:')
    total=time_pair(log,"Total time required for tran analysis `tran':")
    # A rounded total may equal intrinsic, but cannot precede it by more than
    # the display precision. Use a 1 us allowance for native printed rounding.
    if any(total[key]+1e-6<intrinsic[key] for key in ('cpu_s','elapsed_s')):
        raise OptimizationEvidenceError('total transient time precedes intrinsic time')
    return dict(version='optimization-native-stats-v1',native_log_sha256=hashlib.sha256(log.encode()).hexdigest(),
                spectre_version=version,accepted_steps=accepted,rejected_steps=rejected,
                intrinsic_tran=intrinsic,total_tran=total,native_errors=errors,
                native_warnings=warnings,native_notices=notices,
                aggregate_elapsed_used=False)


def validate_solver_evidence(source, returncode, native_log, stdout, stderr=None, *, stream_layout="separate"):
    """Validate actual process outcome, native log and explicitly captured streams.

    With stream_layout='merged', stdout is the captured stdout+stderr and stderr
    must be None. Separate mode requires both real streams. No missing stream is
    invented. Printed stream timings never replace native-file statistics.
    """
    guard=validate_performance_source(source)
    if type(returncode) is not int or returncode!=0:
        raise OptimizationEvidenceError('actual solver process did not exit successfully')
    streams={}
    fatal=re.compile(r'^(?:\s*(?:ERROR|FATAL)\s*\([A-Z][A-Z0-9_-]*-\d+\)|\s*Error found by spectre\b|\s*(?:Segmentation fault|Fatal error|Aborted)\b)',re.M|re.I)
    if stream_layout=='merged':
        if stderr is not None:raise OptimizationEvidenceError('merged layout has no separate stderr evidence')
        captured=(('stdout_stderr_merged',stdout),)
    elif stream_layout=='separate':
        if stderr is None:raise OptimizationEvidenceError('separate layout requires actual stderr capture')
        captured=(('stdout',stdout),('stderr',stderr))
    else:raise OptimizationEvidenceError('unknown captured stream layout')
    for name,stream in captured:
        if isinstance(stream,str):stream=stream.encode('utf-8')
        if not isinstance(stream,bytes):raise TypeError(name+' must be bytes or text')
        if fatal.search(stream.decode('utf-8',errors='replace')):
            raise OptimizationEvidenceError('native error/fatal diagnostic in captured '+name)
        streams[name+'_sha256']=hashlib.sha256(stream).hexdigest()
    statistics=read_native_statistics(native_log)
    statistics.update(source_identity=guard,process_returncode=returncode,stream_layout=stream_layout,stream_identities=streams)
    return statistics


class OptimizationAdmissionPending(OptimizationEvidenceError):
    """A prototype is not a scored optimization task without actual evidence."""


def validate_admitted_policy(policy):
    """Reject unfinished configurations; thresholds follow actual paired evidence."""
    if policy.get('admitted') is not True:
        raise OptimizationAdmissionPending('optimization task has not passed the actual evidence gate')
    evidence=policy.get('admission_evidence_sha256')
    if not isinstance(evidence,str) or not re.fullmatch('[0-9a-f]{64}',evidence):
        raise OptimizationEvidenceError('missing immutable admission evidence identity')
    if policy.get('pairs')!=5:
        raise OptimizationEvidenceError('scored optimization verification requires five alternating pairs')
    metric=policy.get('metric')
    if metric not in ('intrinsic_cpu_s','accepted_steps'):
        raise OptimizationEvidenceError('unsupported performance metric')
    limit=policy.get('max_median_ratio')
    if isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or not 0<limit<1:
        raise OptimizationEvidenceError('performance threshold must be an admitted ratio in (0,1)')
    winning=policy.get('min_winning_pairs')
    if type(winning) is not int or not 1<=winning<=5:
        raise OptimizationEvidenceError('invalid paired consistency requirement')
    return policy


def summarize_pairs(records,policy):
    """Only successful, equivalent, completed work enters a paired score."""
    import statistics
    validate_admitted_policy(policy)
    if len(records)!=10 or [r.get('role') for r in records]!=['baseline','candidate']*5:
        raise OptimizationEvidenceError('missing or non-alternating five-pair evidence')
    for record in records:
        if record.get('passed') is not True or record.get('status')!='completed':
            raise OptimizationEvidenceError('failed work cannot enter performance denominator')
    # Compare the same host, solver version and frozen netlist. The two source
    # roles may differ, but each role is byte-identical across its five trials.
    for key in ('host','netlist_sha256'):
        if any(not r.get(key) for r in records) or len({r[key] for r in records})!=1:
            raise OptimizationEvidenceError('paired '+key+' identity is missing or inconsistent')
    versions={r['statistics'].get('spectre_version') for r in records}
    if None in versions or len(versions)!=1:
        raise OptimizationEvidenceError('paired native solver version is missing or inconsistent')
    for offset in (0,1):
        sources={r.get('source_sha256') for r in records[offset::2]}
        if None in sources or len(sources)!=1:
            raise OptimizationEvidenceError('source changed within a paired role')
    def measure(record):
        stats=record['statistics']
        value=stats['intrinsic_tran']['cpu_s'] if policy['metric']=='intrinsic_cpu_s' else stats['accepted_steps']
        if not math.isfinite(value) or value<=0:raise OptimizationEvidenceError('nonpositive measured work')
        return value
    baseline=[measure(r) for r in records[::2]];candidate=[measure(r) for r in records[1::2]]
    ratios=[b/a for a,b in zip(baseline,candidate)]
    median_ratio=statistics.median(candidate)/statistics.median(baseline)
    winning=sum(ratio<1 for ratio in ratios)
    result=dict(metric=policy['metric'],baseline=dict(median=statistics.median(baseline),minimum=min(baseline),maximum=max(baseline)),
                candidate=dict(median=statistics.median(candidate),minimum=min(candidate),maximum=max(candidate)),
                pair_ratios=ratios,median_ratio=median_ratio,winning_pairs=winning,
                failures=0,pairs=5,admission_evidence_sha256=policy['admission_evidence_sha256'])
    result['passed']=median_ratio<=policy['max_median_ratio'] and winning>=policy['min_winning_pairs']
    return result


def run_one_source(source,case,evaluate,directory,*,binary='spectre',timeout_s=90):
    """One real sequential solve, retaining full source/netlist/log/PSF evidence.

    Not called by offline extraction. The caller owns the single active job slot.
    Spectre execution must be authorized through its normal task profile.
    """
    import json
    import os
    from pathlib import Path
    import subprocess
    import time
    from adc_linearity import read_psf
    from circuit_task import prepare_source,validate_rows
    guard=validate_performance_source(source)
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    output=directory/'output';output.mkdir()
    (directory/'original.va').write_bytes(source)
    executed,relocation=prepare_source(source,['dut.va'],[],output)
    (directory/'dut.va').write_bytes(executed)
    netlist=case['netlist'].encode();(directory/'tb.scs').write_bytes(netlist)
    argv=[binary,'-64','tb.scs','+log','spectre.log','-format','psfascii','-raw','psf','+lqtimeout','5','+mt=1']
    record=dict(status='pending',passed=False,source_sha256=guard['source_sha256'],
                executed_source_sha256=hashlib.sha256(executed).hexdigest(),
                netlist_sha256=hashlib.sha256(netlist).hexdigest(),output_translation=relocation,
                argv=argv,logical_cpus=os.cpu_count(),host=os.uname().nodename,
                load_before=list(os.getloadavg()),stream_layout='merged')
    started=time.monotonic()
    try:
        with (directory/'stdout.log').open('wb') as stream:
            run=subprocess.run(argv,cwd=directory,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout_s)
        record.update(process_elapsed_s=time.monotonic()-started,returncode=run.returncode,
                      load_after=list(os.getloadavg()))
        native=(directory/'spectre.log').read_text(errors='replace')
        merged=(directory/'stdout.log').read_bytes()
        stats=validate_solver_evidence(source,run.returncode,native,merged,None,stream_layout='merged')
        waveform=directory/'psf/tran.tran.tran';rows=read_psf(waveform);validate_rows(rows,case)
        verdict=evaluate(rows,case,directory)
        if not isinstance(verdict,dict) or type(verdict.get('passed')) is not bool:
            raise OptimizationEvidenceError('oracle did not return boolean passed')
        record.update(status='completed',passed=verdict['passed'],functional=verdict,statistics=stats,
                      waveform_sha256=hashlib.sha256(waveform.read_bytes()).hexdigest(),waveform_rows=len(rows))
    except subprocess.TimeoutExpired:
        record.update(status='simulation_timeout',process_elapsed_s=time.monotonic()-started)
    except (OSError,ValueError,KeyError,OptimizationEvidenceError) as exc:
        record.update(status='invalid_solver_evidence',error=f'{type(exc).__name__}: {exc}')
    (directory/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    return record


def run_paired_verification(candidate_source,baseline_source,case,evaluate,directory,policy,*,runner=run_one_source):
    """Preflight active-task guard, retain warmups, then five AB pairs in one job.

    candidate/baseline roles remain explicit. An invalid trusted baseline is a
    verifier/infrastructure failure; an invalid submission is a scored failure.
    No failed solve is dropped and no denominator is reduced.
    """
    import json
    from pathlib import Path
    validate_admitted_policy(policy)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    result=dict(kind='online_same_job_paired_verification',status='pending',reward=None,
                policy=policy,warmups=[],records=[])
    def finish(status,reward,reason=None):
        result.update(status=status,reward=reward)
        if reason is not None:result['reason']=reason
        (directory/'performance_report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        return result
    try:validate_performance_source(candidate_source)
    except OptimizationEvidenceError as exc:return finish('submission_contract_violation',0,str(exc))
    try:validate_performance_source(baseline_source)
    except OptimizationEvidenceError as exc:return finish('infrastructure_error',None,'invalid trusted baseline: '+str(exc))
    for phase in ('warmup',*[f'pair-{i:02d}' for i in range(1,6)]):
        for role,source in (('baseline',baseline_source),('candidate',candidate_source)):
            record=runner(source,case,evaluate,directory/f'{phase}-{role}')
            record.update(role=role,phase=phase)
            result['warmups' if phase=='warmup' else 'records'].append(record)
            if record.get('status')!='completed' or record.get('passed') is not True:
                if role=='baseline':return finish('infrastructure_error',None,'trusted baseline did not complete equivalent work')
                return finish('submission_failure',0,'candidate did not complete equivalent work')
    result['comparison']=summarize_pairs(result['records'],policy)
    return finish('completed',int(result['comparison']['passed']))



def canonical_case_sha256(case):
    import json
    return hashlib.sha256(json.dumps(case,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def classify_case_packet(cases,policy,selector=None):
    """Match trusted private packets to the declared complete task inventory.

    --case is never a scoring shortcut. A single-condition tests packet may be
    produced by trusted preparation, but its success does not mean task success.
    """
    if selector is not None:raise OptimizationEvidenceError('public case selectors cannot form scored task subsets')
    inventory=policy.get('case_inventory')
    if not isinstance(inventory,list) or not inventory:
        raise OptimizationEvidenceError('missing declared full task case inventory')
    names=[item.get('name') for item in inventory]
    if any(not isinstance(name,str) or not name for name in names) or len(set(names))!=len(names):
        raise OptimizationEvidenceError('invalid full task case names')
    for item in inventory:
        if type(item.get('performance')) is not bool or not re.fullmatch('[0-9a-f]{64}',str(item.get('case_sha256',''))):
            raise OptimizationEvidenceError('invalid declared case identity')
    if sum(item['performance'] for item in inventory)!=1:
        raise OptimizationEvidenceError('full task must declare exactly one performance condition')
    declared={item['name']:item for item in inventory}
    actual=[case.get('name') for case in cases]
    if not actual or len(set(actual))!=len(actual) or any(name not in declared for name in actual):
        raise OptimizationEvidenceError('missing, duplicate or undeclared condition packet')
    for case in cases:
        item=declared[case['name']]
        if canonical_case_sha256(case)!=item['case_sha256'] or bool(case.get('performance'))!=item['performance']:
            raise OptimizationEvidenceError('condition packet differs from its declared task case')
    if set(actual)==set(names):return 'full_task'
    if len(actual)==1 and policy.get('allow_private_condition_packets') is True:return 'condition_packet'
    raise OptimizationEvidenceError('scored packet must be the full task or one declared private condition')

def performance_main(evaluate):
    """Prospective task entry: guard before any solve, functional + repeated score.

    There are no admitted tasks/configurations yet. This entry is a prototype,
    not a claim that current probe jobs already use performance scoring.
    """
    import argparse
    import json
    import os
    from pathlib import Path
    from circuit_task import verify,write_report
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case')
    parser.add_argument('--tests',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    tests=args.tests.resolve();policy=json.loads((tests/'performance.json').read_text())
    source=args.candidate.read_bytes();baseline=(tests/'baseline.va').read_bytes()
    # Guard executes before circuit_task.verify's first simulation. Trusted
    # policy/baseline defects are infrastructure, never a candidate zero.
    def reject(status,reward,reason):
        args.output.mkdir(parents=True,exist_ok=False)
        write_report(args.output,dict(status=status,reward=reward,reason=reason,cases=[]))
        raise SystemExit(0 if reward is not None else 2)
    try:validate_admitted_policy(policy)
    except OptimizationEvidenceError as exc:reject('infrastructure_error',None,str(exc))
    try:validate_performance_source(baseline)
    except OptimizationEvidenceError as exc:reject('infrastructure_error',None,'invalid trusted baseline: '+str(exc))
    try:validate_performance_source(source)
    except OptimizationEvidenceError as exc:reject('submission_contract_violation',0,str(exc))
    selected=json.loads((tests/'cases.json').read_text())
    try:scope=classify_case_packet(selected,policy,args.case)
    except OptimizationEvidenceError as exc:reject('infrastructure_error',None,str(exc))
    def grade(rows,case,work):
        functional=evaluate(rows,case,work)
        if not functional.get('passed') or not case.get('performance'):return functional
        frozen=(Path(work)/'original/dut.va').read_bytes()
        if frozen!=source:
            return dict(passed=False,failures=['submission changed after source guard'],functional=functional)
        result=run_paired_verification(frozen,baseline,case,evaluate,Path(work)/'paired',policy,
                                      runner=lambda s,c,e,d:run_one_source(s,c,e,d,binary=os.environ.get('SPECTRE','spectre')))
        # An invalid trusted baseline remains infrastructure, never a fast score.
        if result['reward'] is None:
            return dict(passed=False,status='infrastructure_error',reason=result.get('reason'),functional=functional)
        return dict(passed=bool(result['reward']),functional=functional,
                    performance_status=result['status'],performance=result.get('comparison'),
                    failures=[] if result['reward'] else [result.get('reason','performance admission threshold not met')])
    result=verify(args.candidate,args.output.absolute(),tests,grade,None)
    result.update(verification_scope=scope,declared_full_task_cases=[item['name'] for item in policy['case_inventory']],
                  checked_cases=[case['name'] for case in selected],
                  full_task_success=(result['reward']==1) if scope=='full_task' else None)
    write_report(args.output,result)
    print(json.dumps(dict(status=result['status'],reward=result['reward'],verification_scope=scope,full_task_success=result['full_task_success'])))
    raise SystemExit(0 if result['reward'] is not None else 2)
