"""Diagnostic capture preserves independently specified results and failures."""
GUARDS = ["PERFORMANCE", "EVENT-ORDER", "COMPOSE"]

import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from evas import KernelError
from evas.diagnostics import Session, capture, canonical, digest
from evas.mcp import Server
from evas.mcp import MAX_MESSAGE
from evas.runtime import _invoke
from test_affine import KERNEL, model


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def fixture(self, body=None, declarations='integer n;', source_points=None):
        body = body or '@(initial_step)n=0; @(timer(0.25,0.25,1e-12))n=n+1; V(y,r)<+n+idt(V(u,r),0);'
        (self.root/'model.va').write_text(model(body, declarations))
        manifest = dict(models=['model.va'], instances=[dict(name='dut', module='m', connections=dict(u='u', y='y', r='0'))],
                        transient=dict(sources=dict(u=source_points or [[0,0],[1,1]]),
                                       output_times=[0,0.25,0.5,0.75,1], stop=1, max_step=0.4))
        path = self.root/'manifest.json'
        path.write_text(json.dumps(manifest))
        return path

    def session(self, manifest):
        artifact = capture(manifest, KERNEL)
        path = self.root/'session.json'
        path.write_bytes(canonical(artifact))
        return artifact, Session(path)

    def test_timer_integral_answer_and_byte_equivalence(self):
        artifact, session = self.session(self.fixture())
        payload = artifact['payload']
        ordinary = _invoke(payload['request'], KERNEL)
        self.assertEqual(ordinary, payload['response'])
        values = [row['voltages'][ordinary['nodes'].index('y')] for row in ordinary['solutions']]
        self.assertEqual(values, [n+0.5*t*t for n,t in enumerate([0,0.25,0.5,0.75,1])])
        self.assertEqual([row['time'] for row in ordinary['transient']['events']], [0.25,0.5,0.75,1])
        committed = [r for r in payload['diagnostics']['records'] if r['kind']=='event_batch']
        self.assertEqual([r['start'] for r in committed], [0.25,0.5,0.75,1])
        before = copy.deepcopy(payload)
        with patch('evas.diagnostics._invoke', side_effect=AssertionError('query executed kernel')):
            for section in ['status','nodes','operators','trace','samples','firings','metrics']:
                session.query(section)
        self.assertEqual(before, payload)

    def test_failure_retains_commit_prefix_and_original_error(self):
        artifact, session = self.session(self.fixture('@(initial_step)n=2147483646; @(timer(0.25,0.25,1e-12))n=n+1; V(y,r)<+n;', 'integer n;'))
        payload = artifact['payload']
        self.assertEqual(payload['status'], 'failed')
        with self.assertRaises(KernelError) as error:
            _invoke(payload['request'], KERNEL)
        self.assertEqual(error.exception.detail, payload['error'])
        committed = [r for r in payload['diagnostics']['records'] if r['outcome']=='committed' and r['kind']=='event_batch']
        self.assertEqual([r['start'] for r in committed], [0.25])
        self.assertTrue(any(r['outcome']=='rejected' for r in payload['diagnostics']['records']))
        self.assertEqual(session.query('samples')['status'], 'unknown')
        server = Server(session)
        server.phase = 'ready'
        result = server.dispatch(dict(jsonrpc='2.0', id=1, method='tools/call',
            params=dict(name='evas_status', arguments={})))
        self.assertEqual(result['result']['structuredContent']['status'], 'failed')
        result = server.dispatch(dict(jsonrpc='2.0', id=2, method='tools/call',
            params=dict(name='evas_trace', arguments={})))
        self.assertFalse(result['result']['isError'])
        self.assertTrue(result['result']['structuredContent']['items'])

    def test_small_budget_is_explicit_and_does_not_change_answers(self):
        with patch.dict('os.environ', {'EVAS_DIAGNOSTICS_RECORDS':'1', 'EVAS_DIAGNOSTICS_BYTES':'256'}):
            artifact, session = self.session(self.fixture())
        report = artifact['payload']['diagnostics']
        self.assertEqual(len(report['records']), 1)
        self.assertTrue(report['truncated'])
        self.assertGreater(report['dropped_records'], 0)
        self.assertLessEqual(report['record_bytes'], 256)
        self.assertTrue(session.query('status')['trace_truncated'])
        self.assertEqual(_invoke(artifact['payload']['request'], KERNEL), artifact['payload']['response'])

    def test_stale_source_manifest_ir_kernel_and_session_are_rejected(self):
        artifact, session = self.session(self.fixture())
        for item in [artifact['identity']['sources'][0], artifact['identity']['manifest']]:
            path = Path(item['path']); before = path.read_bytes(); path.write_bytes(before+b'\n')
            with self.assertRaisesRegex(ValueError, 'stale'):
                session.query('status')
            path.write_bytes(before)
        artifact['payload']['request']['program']['schema_version'] = 1
        artifact['payload_sha256'] = digest(canonical(artifact['payload']))
        session.path.write_bytes(canonical(artifact))
        with self.assertRaisesRegex(ValueError, 'IR/request'):
            Session(session.path)
        with self.assertRaisesRegex(ValueError, 'changed after opening'):
            session.query('status')
        kernel = self.root/'kernel-copy'; kernel.write_bytes(KERNEL.read_bytes()); kernel.chmod(0o755)
        artifact = capture(self.root/'manifest.json', kernel)
        session.path.write_bytes(canonical(artifact)); fresh = Session(session.path)
        kernel.write_bytes(kernel.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'stale'):
            fresh.query('status')

    def test_unknown_cross_and_stdio_mcp(self):
        artifact, session = self.session(self.fixture('@(initial_step)n=0; @(cross(V(u,r)-2,1))n=n+1; V(y,r)<+n;'))
        self.assertEqual(session.why_no_cross(0)['status'], 'unknown')
        messages = [dict(jsonrpc='2.0', id=1, method='initialize', params=dict(protocolVersion='2025-11-25', capabilities={}, clientInfo=dict(name='test', version='1'))),
                    dict(jsonrpc='2.0', method='notifications/initialized'),
                    dict(jsonrpc='2.0', id=2, method='tools/list'),
                    dict(jsonrpc='2.0', id=3, method='tools/call', params=dict(name='evas_why_no_cross', arguments=dict(event=0))),
                    dict(jsonrpc='2.0', id=4, method='tools/call', params=dict(name='evas_static', arguments=dict(section='operators', limit=True)))]
        source = ''.join(json.dumps(m)+'\n' for m in messages)
        result = subprocess.run(['python3','-B','-m','evas.mcp',str(session.path)], input=source, text=True, capture_output=True, check=True)
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r['id'] for r in replies], [1,2,3,4])
        self.assertEqual(replies[2]['result']['structuredContent']['status'], 'unknown')
        self.assertTrue(replies[3]['result']['isError'])
        self.assertEqual(result.stderr, '')
        output = io.StringIO()
        Server(session).serve(io.StringIO('not-json\n'), output)
        self.assertEqual(json.loads(output.getvalue())['error']['code'], -32700)

    def test_parallel_default_transport_is_identical(self):
        artifact = capture(self.fixture(), KERNEL)
        request = artifact['payload']['request']
        # Static requests share the same transport; thread instrumentation remains
        # explicitly scoped to the caller, never inventing worker factor counts.
        request.pop('transient'); request['samples'] = [[0.0],[0.5],[1.0]]
        request['program']['states']=[]; request['program']['events']=[]; request['program']['operators']=[]
        request['program']['contributions'][0]['rhs']=dict(op='affine',constant=0.0,terms=[dict(node=1,coefficient=1.0)])
        with patch.dict('os.environ', {'EVAS_STATIC_THREADS':'2'}):
            ordinary = _invoke(request, KERNEL)
            diagnostic = _invoke(request, KERNEL, diagnostics_path=self.root/'parallel.json')
        self.assertEqual(ordinary, diagnostic)
        self.assertEqual(json.loads((self.root/'parallel.json').read_text())['coverage'], 'calling_thread_only')

    def test_invalid_budget_and_existing_sidecar_fail_explicitly(self):
        request = capture(self.fixture(), KERNEL)['payload']['request']
        with patch.dict('os.environ', {'EVAS_DIAGNOSTICS_RECORDS':'bad'}):
            with self.assertRaises(KernelError) as error:
                _invoke(request, KERNEL, diagnostics_path=self.root/'invalid.json')
        self.assertEqual(error.exception.detail['kind'], 'invalid_config')
        report = json.loads((self.root/'invalid.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['records'])
        sidecar = self.root/'existing.json'
        sidecar.write_text('preserve')
        with self.assertRaises(KernelError) as error:
            _invoke(request, KERNEL, diagnostics_path=sidecar)
        self.assertEqual(error.exception.detail['kind'], 'diagnostic_io')
        self.assertEqual(sidecar.read_text(), 'preserve')

    def test_mcp_wire_budget_includes_escaped_text_content(self):
        class LargeSession:
            def query(self, *args, **kwargs):
                return dict(items=['\\'*250000])
        server = Server(LargeSession())
        server.phase = 'ready'
        message = dict(jsonrpc='2.0', id=1, method='tools/call',
                       params=dict(name='evas_trace', arguments={}))
        output = io.StringIO()
        server.serve(io.StringIO(json.dumps(message)+'\n'), output)
        self.assertLessEqual(len(output.getvalue().encode()), MAX_MESSAGE)
        self.assertTrue(json.loads(output.getvalue())['result']['isError'])
