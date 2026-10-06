"""Harbor verifier delegates ADC jobs to the existing circuit harness transport."""
import asyncio
import hashlib
import json
import math
from pathlib import Path

from harbor.models.verifier.result import VerifierResult
from harbor.verifier.base import BaseVerifier
from .harness_adapter import TASK,aggregate,load_harness,prepare


class ADCHarnessVerifier(BaseVerifier):
    def __init__(self,*args,config_path=None,**kwargs):
        super().__init__(*args,**kwargs)
        if config_path is None: raise ValueError('explicit private ADC harness config_path required')
        path=Path(config_path).resolve()
        if path.stat().st_mode & 0o077: raise ValueError('harness config must be private')
        for protected in [self.task.paths.task_dir.resolve(),self.trial_paths.trial_dir.resolve()]:
            if path.is_relative_to(protected): raise ValueError('verifier config must stay outside candidate task/trial')
        config=json.loads(path.read_text())
        if set(config)!={'harness_checkout','remote'}: raise ValueError('invalid ADC harness config')
        self.config=config

    async def verify(self):
        if self.task.paths.task_dir.name!=TASK.name: raise ValueError('ADC verifier requires the ADC task')
        output=self.trial_paths.verifier_dir.resolve();output.mkdir(parents=True,exist_ok=True)
        candidate=output/'candidate.va'
        await self.environment.download_file('/work/dut.va',candidate)
        prepared=output/'prepared'
        record=await asyncio.to_thread(prepare,self.config['harness_checkout'],candidate,prepared)
        _,_,remote=load_harness(self.config['harness_checkout'])
        transport=remote.RemoteBenchmarkSpectre(self.config['remote'],output/'transport')
        prefix='adc-'+hashlib.sha256(str(self.trial_paths.trial_dir.resolve()).encode()).hexdigest()[:16]
        results=[]
        try:
            for case in record['cases']:
                job_id=prefix+'-'+case['condition_id']
                state=await asyncio.to_thread(transport.submit,prepared/'frozen',Path(case['package']),job_id)
                while True:
                    if state.get('state')=='finished':
                        archive=state.get('archive')
                        archive_state=archive.get('state') if isinstance(archive,dict) else None
                        if archive_state=='verified': break
                        if archive_state not in ['pending','running']:
                            raise RuntimeError('harness archive unavailable; preserve job and inspect evidence')
                    if state.get('state') not in ['queued','running','unknown','finished']:
                        raise RuntimeError('harness job is not recoverable; keep its existing ID')
                    await asyncio.sleep(1)
                    state=await asyncio.to_thread(transport.query,job_id)
                result=await asyncio.to_thread(transport.retrieve,job_id)
                results.append(result)
                if result.get('execution')!='ok': break
        finally: transport.interrupt_wait()
        report=aggregate(results)
        if len(results)!=len(record['cases']): report.update(status='infrastructure_error',reward=None)
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        score=report['reward']
        if score is None or not math.isfinite(score): raise RuntimeError('ADC harness execution incomplete; no task score')
        (output/'reward.txt').write_text(str(score)+'\n')
        return VerifierResult(rewards={'reward':score})
