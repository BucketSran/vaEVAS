"""Owned POSIX process lifecycle, adapted from reviewed L3 bf06821a runner.

The leader is unreaped until TERM/KILL complete. Every exit cleans descendants.
Container lifecycle is separately checked by the paper runner.
"""
import json
import os
import signal
import subprocess
import time
from inputs import sha

def dump(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2)
        stream.write('\n')

def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

def exited_unreaped(process):
    return os.waitid(os.P_PID, process.pid,
        os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None

def stop_group(process):
    signals, errors = [], []
    # Keep the leader's PID allocated until every group signal has been sent.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
            signals.append(sig.name)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(repr(error))
        if sig == signal.SIGTERM:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    if exited_unreaped(process):
                        break
                except OSError as error:
                    errors.append(repr(error))
                    break
                time.sleep(0.01)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        errors.append('leader was not reaped within 5s after SIGKILL')
    except OSError as error:
        errors.append(repr(error))
    return dict(signals=signals, errors=errors, complete=not errors)

def execute(argv, work, log, seconds):
    for required in ('waitid', 'WNOWAIT', 'WEXITED', 'WNOHANG', 'P_PID'):
        if not hasattr(os, required):
            raise RuntimeError('owned process lifecycle requires os.' + required)
    start = time.monotonic()
    process = None
    cancelled = []
    def cancel(signum, frame):
        # Do not raise inside Popen before its owned process has been assigned.
        cancelled.append(signum)
    previous = {sig: signal.signal(sig, cancel)
        for sig in (signal.SIGINT, signal.SIGTERM)}
    record = dict(argv=argv, returncode=None, timeout=False, status='running')
    try:
        with (work / log).open('x') as stream:
            try:
                if not cancelled:
                    process = subprocess.Popen(argv, cwd=str(work), stdout=stream,
                        stderr=subprocess.STDOUT, start_new_session=True,
                        env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'))
                deadline = start + seconds
                while process is not None and not cancelled:
                    if exited_unreaped(process):
                        break
                    if time.monotonic() >= deadline:
                        record['timeout'] = True
                        break
                    time.sleep(0.01)
            except BaseException as error:
                record.update(status='execution_error', error=repr(error))
            finally:
                if process is not None:
                    record['cleanup'] = stop_group(process)
                    record['returncode'] = process.returncode
                else:
                    record['cleanup'] = dict(signals=[], errors=[], complete=True)
        if cancelled:
            record.update(status='cancelled', cancellation_signals=cancelled)
        elif not record['cleanup']['complete']:
            record['status'] = 'cleanup_incomplete'
        elif record['status'] == 'running':
            record['status'] = 'timeout' if record['timeout'] else 'completed'
        record.update(elapsed_seconds=time.monotonic()-start,
            completed_utc=utc(), log=log, log_sha256=sha(work/log))
        dump(work/(log+'.EXECUTION.json'), record)
        return record
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
