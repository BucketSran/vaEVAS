#!/usr/bin/env python3
"""Network-disabled stock Pi request serialization fixture, not a model Trial."""
import argparse
import subprocess
import sys
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image')
parser.add_argument('--inside-container',action='store_true')
args=parser.parse_args()
if not args.inside_container:
    if not args.image:
        parser.error('--image is required')
    source=Path(__file__).resolve()
    result=subprocess.run(['docker','run','--rm','--network','none',
        '-v',f'{source}:/tmp/pi-budget-probe.py:ro','--entrypoint','python3',
        args.image,'/tmp/pi-budget-probe.py','--inside-container'],timeout=90)
    raise SystemExit(result.returncode)

import http.server,json,pathlib,subprocess,threading,os
root=pathlib.Path('/tmp/harbor-pi-agent');root.mkdir(exist_ok=True)
(root/'models.json').write_text(json.dumps({'providers':{'harbor-endpoint':{'baseUrl':'http://127.0.0.1:8765/v1','apiKey':'transport-fixture-key','api':'openai-completions','models':[{'id':'transport-fixture'}]}}}))
records=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  q=json.loads(self.rfile.read(int(self.headers['Content-Length'])));records.append({'model':q.get('model'),'max_tokens':q.get('max_tokens'),'max_completion_tokens':q.get('max_completion_tokens'),'messages':len(q.get('messages',[]))})
  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
  for c in [{'id':'fixture','object':'chat.completion.chunk','created':0,'model':'transport-fixture','choices':[{'index':0,'delta':{'role':'assistant','content':'transport fixture completed'},'finish_reason':None}]},{'id':'fixture','object':'chat.completion.chunk','created':0,'model':'transport-fixture','choices':[{'index':0,'delta':{},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}]:self.wfile.write(('data: '+json.dumps(c)+'\n\n').encode())
  self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
server=http.server.ThreadingHTTPServer(('127.0.0.1',8765),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();pathlib.Path('/logs/agent').mkdir(parents=True,exist_ok=True)
env=dict(os.environ,PI_CODING_AGENT_DIR=str(root),AGENTIC_MAX_OUTPUT_TOKENS='65536');run=subprocess.run(['/bin/bash','-lc','. ~/.nvm/nvm.sh; pi --print --mode json --provider harbor-endpoint --model transport-fixture --thinking medium --session-dir /tmp/fixture-session "Transport fixture only. Return fixture text."'],env=env,capture_output=True,text=True,timeout=60);server.shutdown()
receipt={'fixture_only':True,'vendor_requests':0,'pi_returncode':run.returncode,'captured_request_scalars':records,'extension_budget_records':[json.loads(x) for x in pathlib.Path('/logs/agent/output-budget.jsonl').read_text().splitlines()] if pathlib.Path('/logs/agent/output-budget.jsonl').exists() else [],'stderr':run.stderr[:1500]};print(json.dumps(receipt));assert run.returncode==0 and records and (records[0].get('max_tokens')==65536 or records[0].get('max_completion_tokens')==65536)
