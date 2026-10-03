"""Harbor adapters for tool-disabled host CLI generation and remote Spectre.

Only instruction.md is passed to the model. Provider credentials never enter the
task environment or the remote simulator. No source repair or regeneration occurs.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from harbor.agents.base import BaseAgent
from harbor.verifier.base import BaseVerifier
from harbor.models.verifier.result import VerifierResult
from .remote import grade


def extract_source(text):
    stripped=text.strip()
    fenced=re.fullmatch(r'```(?:verilog|veriloga|verilog-a|vams)?\s*\n(.*?)\n```',stripped,re.S|re.I)
    return (fenced[1] if fenced else stripped)+'\n'


def generate(instruction, model, logs):
    logs=Path(logs).resolve();logs.mkdir(parents=True,exist_ok=True)
    (logs/'prompt.md').write_text(instruction)
    kind='glm' if model.startswith('glm-') else 'codex'
    metadata=dict(model_requested=model,channel=kind,effort='xhigh',protocol='one-shot-no-tools-no-feedback',
                  instruction_sha256=hashlib.sha256(instruction.encode()).hexdigest(),started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='va-screen-') as temp:
        work=Path(temp);env=os.environ.copy()
        if kind=='codex':
            executable=shutil.which('codex')
            original_home=Path(env.get('CODEX_HOME',str(Path.home()/'.codex')))
            private_home=work/'codex-home';private_home.mkdir(mode=0o700)
            # Copy only authentication, never user/project prompts, tools, or skills.
            shutil.copyfile(original_home/'auth.json',private_home/'auth.json')
            (private_home/'auth.json').chmod(0o600);env['CODEX_HOME']=str(private_home)
            argv=[executable,'exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check',
                  '--sandbox','read-only','-C',str(work),'-m',model,'-c','model_reasoning_effort="xhigh"',
                  '-c','web_search="disabled"','-c','project_doc_max_bytes=0','--enable','skip_host_skill_discovery']
            for feature in ['shell_tool','unified_exec','apps','plugins','browser_use','browser_use_external',
                            'browser_use_full_cdp_access','multi_agent','code_mode_host','code_mode','computer_use',
                            'image_generation','in_app_browser','view_image','hooks','skill_search','shell_snapshot','sleep_tool']:
                argv+=['--disable',feature]
            argv+=['--json','--output-last-message',str(logs/'response.txt'),'-']
        else:
            executable=shutil.which('claude')
            argv=[executable,'--print','--model',model,'--effort','xhigh','--tools','',
                  '--safe-mode','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
                  '--setting-sources','user','--disable-slash-commands','--no-session-persistence','--output-format','json']
        metadata['cli_version']=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=20).stdout.strip()
        # Args contain no credentials. The temporary auth location is not retained.
        metadata['argv']=[a.replace(str(work),'<isolated-workdir>') for a in argv]
        with (logs/'stdout.jsonl').open('w') as out,(logs/'stderr.log').open('w') as err:
            run=subprocess.run(argv,input=instruction,text=True,stdout=out,stderr=err,cwd=work,env=env,timeout=850)
        metadata.update(returncode=run.returncode,elapsed_s=time.monotonic()-start)
        if run.returncode!=0:
            (logs/'generation.json').write_text(json.dumps(metadata,indent=2)+'\n')
            raise RuntimeError(f'{kind} generation failed; inspect isolated agent logs')
        raw=(logs/'stdout.jsonl').read_text()
        if kind=='glm':
            data=json.loads(raw)
            if data.get('is_error'):raise RuntimeError('GLM CLI returned an error')
            response=data['result'];(logs/'response.txt').write_text(response)
            metadata.update(usage=data.get('usage'),model_usage=data.get('modelUsage'),num_turns=data.get('num_turns'))
            if data.get('num_turns',1)!=1:raise RuntimeError('GLM one-shot protocol violated')
        else:
            events=[json.loads(line) for line in raw.splitlines() if line.startswith('{')]
            for event in events:
                if event.get('type')=='turn.completed':metadata['usage']=event.get('usage')
            forbidden=[e for e in events if e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search','file_change']]
            metadata['tool_events']=len(forbidden)
            if forbidden:raise RuntimeError('Codex one-shot protocol violated: tool use observed')
            response=(logs/'response.txt').read_text()
        candidate=extract_source(response);(logs/'dut.va').write_text(candidate)
        metadata['candidate_sha256']=hashlib.sha256(candidate.encode()).hexdigest()
        (logs/'generation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


class OneShotAgent(BaseAgent):
    @staticmethod
    def name():return 'va-one-shot-cli'

    def version(self):return '1'

    async def setup(self,environment):
        await environment.exec('mkdir -p /work')

    async def run(self,instruction,environment,context):
        metadata=await asyncio.to_thread(generate,instruction,self.model_name,self.logs_dir)
        context.metadata=metadata
        usage=metadata.get('usage') or {}
        context.n_input_tokens=usage.get('input_tokens')
        context.n_output_tokens=usage.get('output_tokens')
        await environment.upload_file(self.logs_dir/'dut.va','/work/dut.va')


class RemoteSpectreVerifier(BaseVerifier):
    async def verify(self):
        output=self.trial_paths.verifier_dir.resolve();output.mkdir(parents=True,exist_ok=True)
        candidate=output/'dut.va'
        await self.environment.download_file('/work/dut.va',candidate)
        report=await asyncio.to_thread(grade,self.task.paths.task_dir,candidate,output)
        if report['reward'] is None:raise RuntimeError('Spectre/checker infrastructure error; no model score assigned')
        return VerifierResult(rewards={'reward':report['reward']})
