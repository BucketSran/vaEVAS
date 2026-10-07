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
