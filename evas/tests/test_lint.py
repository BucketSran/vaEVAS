"""Compile-only preflight and origin-specific diagnostic contracts."""
GUARDS = ['LANG', 'TIMER', 'DYNAMICS', 'DEV:compile-only-lint']

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from evas import CompileError, KernelError
from test_affine import KERNEL, model

ROOT = Path(__file__).resolve().parents[1]


class LintCLI(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'m.va'
        self.source.write_text(model('V(y,r)<+2*V(u,r)+0.25;'))
        self.data=dict(models=['m.va'],instances=[dict(name='dut',module='m',connections=dict(u='u',y='y',r='0'))])
        self.path=self.root/'sim.json'
        self.path.write_text(json.dumps(self.data))

    def cli(self,*args):
        return subprocess.run([sys.executable,'-B','-m','evas',*map(str,args)],
                              env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),
                              capture_output=True,text=True,timeout=15)

    def test_affine_lint_without_kernel_and_no_process_invocation(self):
        script='''
import subprocess,sys
from evas.__main__ import main
class ForbiddenProcess:
    def __init__(self,*args,**kwargs):
        raise AssertionError('lint tried to start a process')
subprocess.Popen=ForbiddenProcess
sys.argv=['evas','lint',sys.argv[1]]
raise SystemExit(main())
'''
        result=subprocess.run([sys.executable,'-B','-c',script,str(self.path)],cwd=self.root,
                              env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['status'],'lint_passed')
        self.assertEqual(report['not_checked'],['numerical_request_validity','dynamic_support','numerical_acceptance','external_simulator_compatibility'])
        self.assertIn('parameter_binding',report['checks'])
        self.assertNotIn('simulation_valid',report)

    def test_origin_specific_input_parameter_and_resource_rejections(self):
        cases=[
            ('source', model('V(y,r)<+1;'), None, None, 'source_io','infrastructure',None),
            ('shape', model('V(y,r)<+1;'), None, dict(instances=[]), 'manifest_input','invalid_input',None),
            ('override', model('V(y,r)<+a;','parameter real a=1;'), dict(unknown=2), None, 'parameter_override','invalid_input','unknown parameter override'),
            ('cycle', model('V(y,r)<+a;','parameter real a=b+1; parameter real b=a+1;'), None, None, 'parameter_dependency','invalid_input','cyclic parameter defaults'),
            ('expand', model('x=V(u,r);'+'x=x+x;'*30+'V(y,r)<+x;','real x;'), None,None,'resource_budget','resource','expanded IR size limit'),
        ]
        for name,source,overrides,mutation,code,category,message in cases:
            with self.subTest(name=name):
                self.source.write_text(source)
                data=json.loads(json.dumps(self.data))
                if overrides is not None:
                    data['instances'][0]['parameters']=overrides
                if mutation:
                    data.update(mutation)
                self.path.write_text(json.dumps(data))
                if name=='source':
                    self.source.unlink()
                result=self.cli('lint',self.path)
                self.assertEqual(result.returncode,2,result.stderr)
                error=json.loads(result.stderr)
                self.assertEqual(error['diagnostic_version'],1)
                self.assertEqual(error['code'],code)
                self.assertEqual(error['category'],category)
                if message:
                    self.assertIn(message,error['message'])
                if name in ('cycle','expand'):
                    self.assertEqual(error['location']['source'],str(self.source.resolve()))
                    self.assertGreater(error['location']['line'],0)
                self.assertNotIn('Traceback',result.stderr)

    def test_unknown_prefix_and_extra_kernel_fields_remain_unknown(self):
        self.assertEqual(CompileError('legacy reason').diagnostic['category'],'unknown')
        future=CompileError('new raw reason',code='future_reason').diagnostic
        self.assertEqual(future['category'],'unknown')
        self.assertEqual(future['code'],'future_reason')
        self.assertEqual(future['message'],'new raw reason')
        raw=dict(kind='unsupported_future_reason',message='unregistered reason',sample=2,future={'extra':42})
        error=KernelError(raw)
        self.assertEqual(error.detail,raw)
        detail=error.diagnostic
        self.assertEqual(detail['category'],'unknown')
        for key,value in raw.items():
            self.assertEqual(detail[key],value)
        for kind in ('unsupported_analysis','unsupported_condition','unsupported_operator','unsupported_transient','unsupported_cross','unsupported_timer','unsupported_implicit_dynamics'):
            self.assertEqual(KernelError(dict(kind=kind,message='typed origin')).diagnostic['category'],'unsupported')

    def test_unregistered_stage_is_unknown_but_registered_legacy_stage_survives(self):
        from evas.errors import diagnostic
        detail = diagnostic('future_parse_reason', 'raw message')
        self.assertIsNone(detail['stage'])
        self.assertEqual(detail['category'], 'unknown')
        self.assertEqual(detail['message'], 'raw message')
        self.assertEqual(diagnostic('compile_error', 'legacy')['stage'], 'compile')
        self.assertEqual(diagnostic('syntax_error', 'syntax')['stage'], 'parse')

    def test_lint_rejects_explicit_execution_options(self):
        for option in (['--kernel', '/missing/kernel'], ['--timeout', '3'], ['--timeout=3']):
            with self.subTest(option=option):
                result = self.cli('lint', self.path, *option)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                detail = json.loads(result.stderr)
                self.assertEqual(detail['code'], 'input_error')
                self.assertEqual(detail['message'], 'lint does not accept --kernel or --timeout; no kernel is checked or executed')

    def test_api_lint_then_real_kernel_rejects_frozen_dynamic_limitation(self):
        from evas.lint import lint_manifest
        self.source.write_text(model('''@(initial_step) q=1;
            @(timer(0.5,0,1e-12)) q=2;
            V(y,r)<+idt(q+2*V(y,r),0)-pow(V(y,r),2);''','real q;'))
        self.data['transient']=dict(sources=dict(u=[[0,0],[1,0]]),output_times=[0,1],stop=1,max_step=1)
        self.path.write_text(json.dumps(self.data))
        report=lint_manifest(self.path)
        self.assertEqual(report['status'],'lint_passed')
        self.assertIn('dynamic_support',report['not_checked'])
        result=self.cli('lint',self.path)
        self.assertEqual(result.returncode,0,result.stderr)
        result=self.cli('transient',self.path,'--kernel',KERNEL)
        self.assertEqual(result.returncode,2,result.stderr)
        detail=json.loads(result.stderr)
        self.assertEqual(detail['kind'],'unsupported_implicit_dynamics')
        self.assertEqual(detail['category'],'unsupported')
        self.assertEqual(detail['capability'],'DYNAMICS')
        self.assertEqual(detail['message'],'index-one polynomial DAE currently requires an event-free network')

    def test_registered_messages_and_locations_preserve_original_reasons(self):
        from evas.lint import compile_manifest
        cases=[(dict(unknown=1),'dut: unknown parameter override','parameter_override'),
               (dict(a='text'),"dut: parameter 'a' must be numeric",'parameter_override')]
        for overrides,message,code in cases:
            self.source.write_text(model('V(y,r)<+a;','parameter real a=1;'))
            self.data['instances'][0]['parameters']=overrides
            self.path.write_text(json.dumps(self.data))
            with self.assertRaises(CompileError) as caught:
                compile_manifest(self.path)
            self.assertEqual(str(caught.exception),message)
            self.assertEqual(caught.exception.diagnostic['message'],message)
            self.assertEqual(caught.exception.diagnostic['code'],code)
            self.assertEqual(caught.exception.diagnostic['instance'],'dut')
            if 'a' in overrides:
                self.assertEqual(caught.exception.diagnostic['location']['source'],str(self.source.resolve()))
            else:
                self.assertNotIn('location',caught.exception.diagnostic)

    def test_parameter_depth_is_resource_not_language_rejection(self):
        declarations=' '.join(f'parameter real p{i}='+('1;' if i==69 else f'p{i+1}+1;') for i in range(70))
        self.source.write_text(model('V(y,r)<+p0;',declarations))
        result=self.cli('lint',self.path)
        self.assertEqual(result.returncode,2,result.stderr)
        detail=json.loads(result.stderr)
        self.assertEqual(detail['code'],'resource_budget')
        self.assertEqual(detail['category'],'resource')
        self.assertIn('parameter dependency depth limit (64) exceeded',detail['message'])
        self.assertEqual(detail['location']['source'],str(self.source.resolve()))

    def test_numerical_request_is_not_validated_by_compile_only_lint(self):
        self.data.update(driven=['not_a_node'],samples=[['not_numeric']])
        self.path.write_text(json.dumps(self.data))
        result=self.cli('lint',self.path)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('numerical_request_validity',json.loads(result.stdout)['not_checked'])

    def test_file_access_and_encoding_reasons_are_not_guessed_from_messages(self):
        self.path.unlink()
        result=self.cli('lint',self.path)
        self.assertEqual(result.returncode,2,result.stderr)
        detail=json.loads(result.stderr)
        self.assertEqual(detail['code'],'manifest_io')
        self.assertEqual(detail['category'],'infrastructure')
        self.assertIn(str(self.path),detail['message'])
        self.path.write_bytes(b'\xff')
        result=self.cli('lint',self.path)
        detail=json.loads(result.stderr)
        self.assertEqual(detail['code'],'manifest_input')
        self.assertEqual(detail['category'],'invalid_input')
        self.path.write_text(json.dumps(self.data))
        self.source.write_bytes(b'\xff')
        result=self.cli('lint',self.path)
        self.assertEqual(result.returncode,2,result.stderr)
        detail=json.loads(result.stderr)
        self.assertEqual(detail['code'],'source_input')
        self.assertEqual(detail['category'],'invalid_input')
        self.assertIn("'utf-8' codec",detail['message'])
