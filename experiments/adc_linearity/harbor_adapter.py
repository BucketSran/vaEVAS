"""Harbor verifier delegates ADC jobs to the existing circuit harness transport."""
import asyncio
import hashlib
import json
import math
import traceback
from pathlib import Path

from harbor.models.verifier.result import VerifierResult
from harbor.verifier.base import BaseVerifier
from .harness_adapter import TASK,aggregate,load_harness,prepare,private_workspace,validate_private_location,visible_mount_roots,publish_result


class ADCHarnessVerifier(BaseVerifier):
    def __init__(self,*args,config_path=None,**kwargs):
        super().__init__(*args,**kwargs)
        if config_path is None: raise ValueError('explicit private ADC harness config_path required')
        self.visible=visible_mount_roots(self.environment,self.task.paths.task_dir,self.trial_paths.trial_dir)
        path=validate_private_location(config_path,self.visible,directory=False)
        config=json.loads(path.read_text())
        if set(config)!={'harness_checkout','remote','private_root'}: raise ValueError('invalid ADC harness config')
        validate_private_location(config['private_root'],self.visible)
        self.config=config

    async def verify(self):
        if self.task.paths.task_dir.name!=TASK.name: raise ValueError('ADC verifier requires the ADC task')
        output=self.trial_paths.verifier_dir.absolute()
        prefix='adc-'+hashlib.sha256(str(self.trial_paths.trial_dir.resolve()).encode()).hexdigest()[:16]
        self.visible=visible_mount_roots(self.environment,self.task.paths.task_dir,self.trial_paths.trial_dir)
        private=private_workspace(self.config['private_root'],self.visible,prefix)
        try:
            report=await self._evaluate(private,prefix)
        except Exception:
            (private/'failure.txt').write_text(traceback.format_exc())
            publish_result(output,{'status':'infrastructure_error','reward':None})
            raise RuntimeError('ADC harness execution failed; private operator evidence retained') from None
        publish_result(output,report)
        score=report['reward']
        if score is None or not math.isfinite(score): raise RuntimeError('ADC harness execution incomplete; no task score')
        return VerifierResult(rewards={'reward':score})

    async def _evaluate(self,private,prefix):
        candidate=private/'candidate.va'
        await self.environment.download_file('/work/dut.va',candidate)
        prepared=private/'prepared'
        record=await asyncio.to_thread(prepare,self.config['harness_checkout'],candidate,prepared)
        _,_,remote=load_harness(self.config['harness_checkout'])
        transport=remote.RemoteBenchmarkSpectre(self.config['remote'],private/'transport')
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
        (private/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
