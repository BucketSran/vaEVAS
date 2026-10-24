"""Isolated event statistics are evaluated in source order by the Rust kernel."""
GUARDS = ["LANG", "EVENT-CONDITIONS", "EVENT-ORDER", "TIMER"]

import os
from pathlib import Path
import unittest

from evas import Instance, compile_sources, transient
from statistics_rn_oracle import check_body, check_regression, check_instances, check_constant

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get("EVAS_STATISTICS_KERNEL", ROOT / "rust_core/target/debug/evas-kernel"))


class EventStatistics(unittest.TestCase):
    def test_three_sample_regression_uses_prior_assignments(self):
        # Independent samples (-1,-1), (0,1), (1,3) lie on y=2*x+1.
        # Their regression has gain 2, offset 1 and zero residual RMS.
        source = '''`include "disciplines.vams"
module statistics(x,y); input x,y; electrical x,y;
integer n; real sx,sy,sxx,sxy,syy,xx,yy,den,gain,offset,rms;
analog begin
 @(initial_step) begin n=0;sx=0;sy=0;sxx=0;sxy=0;syy=0;end
 @(timer(0.25,0.25,1e-12)) begin
   xx=V(x);yy=V(y);n=n+1;sx=sx+xx;sy=sy+yy;
   sxx=sxx+xx*xx;sxy=sxy+xx*yy;syy=syy+yy*yy;
 end
 @(final_step) begin
   den=n*sxx-sx*sx;
   gain=(n*sxy-sx*sy)/den;
   offset=(sy-gain*sx)/n;
   rms=sqrt(max(0.0,(syy-gain*sxy-offset*sy)/n));
   $display("fit %d %.12g %.12g %.12g",n,gain,offset,rms);
 end
end endmodule'''
        program = compile_sources({"statistics.va": source}, [
            Instance("M", "statistics", {"x": "x", "y": "y"})])
        result = transient(program, {
            "x": [[0,-1],[.25,-1],[.5,0],[.75,1]],
            "y": [[0,-1],[.25,-1],[.5,1],[.75,3]],
        }, [0,.25,.5,.75], stop=.75, max_step=.25, kernel=KERNEL)
        records = result["transient"]["display_records"]
        self.assertEqual([record["text"] for record in records], ["fit 3 2 1 0"])
        check_regression(self, result, program.to_dict())

    def run_body(self, body, *, extra='', query_times=None, trace_case=None):
        source = '''`include "disciplines.vams"
module measure(x);input x;electrical x;real a,b;integer n;
analog begin @(initial_step)begin a=0;b=0;n=0;end
@(timer(0.5,0,1e-12))begin '''+body+''' end
'''+extra+''' end endmodule'''
        p=compile_sources({'measure.va':source},[Instance('M','measure',{'x':'x'})])
        result = transient(p,{'x':[[0,1],[1,1]]},query_times or [0,.5,1],
                         stop=1,max_step=.5,kernel=KERNEL)
        if trace_case is not None:
            check_body(self, result, p.to_dict(), query_times or [0,.5,1], trace_case)
        return result

    def test_numeric_assignment_and_direct_display_share_compensated_value(self):
        for operation in ('a*a', '1.0/a'):
            with self.subTest(operation=operation):
                expression = '(1e16+'+operation+')-1e16'
                r = self.run_body('a=1;b='+expression+';'
                                  '$display("same %g %g",b,'+expression+');', trace_case='cancel')
                self.assertEqual([d['text'] for d in r['transient']['display_records']],
                                 ['same 0 0'])

    def test_math_arguments_use_same_compensated_value(self):
        r = self.run_body('a=1;b=abs((1e16+a*a)-1e16);'
                          '$display("same %g %g",b,abs((1e16+a*a)-1e16));', trace_case='abs_cancel')
        self.assertEqual([d['text'] for d in r['transient']['display_records']],
                         ['same 0 0'])

    def test_math_point_does_not_replace_original_interval_domain(self):
        # RN(1e16+1) is 1e16, so the subtraction and sqrt both produce zero.
        from evas import CompileError
        r = self.run_body('a=1;b=sqrt((1e16+a*a)-1e16);', trace_case='sqrt_cancel')
        self.assertEqual(r['transient']['display_records'], [])
        # Both selected min/max arguments are evaluated. The literal 1/0
        # argument is already a static domain failure in the source frontend.
        for function in ('min', 'max'):
            with self.subTest(function=function):
                with self.assertRaisesRegex(CompileError, 'division by zero'):
                    self.run_body('a=1;b='+function+'(a,1.0/0.0);')

    def test_nested_numeric_select_does_not_evaluate_unselected_bad_domain(self):
        r = self.run_body('a=1;b=(a>0 ? (a<2 ? abs(a) : sqrt(-a)) : 1.0/0.0);'
                          '$display("selected %g",b);', trace_case='nested')
        self.assertEqual([d['text'] for d in r['transient']['display_records']],
                         ['selected 1'])

    def test_no_samples_guard_does_not_evaluate_invalid_arm(self):
        r=self.run_body('if(n>0) begin a=1.0/a;b=sqrt(-V(x));end '
                        'else $display("empty %d",n);', trace_case='empty')
        self.assertEqual([d['text'] for d in r['transient']['display_records']],['empty 0'])

    def test_selected_zero_denominator_is_a_domain_failure(self):
        from evas import KernelError
        with self.assertRaisesRegex(KernelError,'real_arithmetic.*DivisionByZero'):
            self.run_body('a=1.0/a;')

    def test_selected_negative_sqrt_is_a_domain_failure(self):
        from evas import KernelError
        with self.assertRaisesRegex(KernelError,'event_domain.*outside its domain'):
            self.run_body('a=sqrt(-V(x));')

    def test_interval_denominator_contains_zero_is_rejected(self):
        from evas import KernelError
        source='''`include "disciplines.vams"
module measure(x);input x;electrical x;real a;
analog begin @(initial_step)a=0;@(cross(V(x),1,0.001,0.001))a=1.0/V(x);end endmodule'''
        p=compile_sources({'zero.va':source},[Instance('M','measure',{'x':'x'})])
        with self.assertRaisesRegex(KernelError,'real_arithmetic.*DivisionByZero'):
            transient(p,{'x':[[0,-1],[1,2]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_math_uses_source_order_and_extra_queries_do_not_reexecute(self):
        body='a=V(x)+1;a=a*a;b=sqrt(a);a=max(-1.0,min(a,3.0));$display("math %g %g",a,b);'
        first=self.run_body(body, trace_case='math_order')
        dense=self.run_body(body,query_times=[0,.125,.25,.5,.625,.75,1], trace_case='math_order')
        self.assertEqual([d['text'] for d in first['transient']['display_records']],['math 3 2'])
        self.assertEqual(first['transient']['events'],dense['transient']['events'])

    def test_observer_math_cannot_feed_a_voltage_contribution_even_at_zero_weight(self):
        from evas import CompileError
        with self.assertRaisesRegex(CompileError,'nonconstant mathematical'):
            self.run_body('a=sqrt(V(x));',extra='V(x)<+0*a;')

    def test_zero_timer_keeps_the_existing_narrow_contract(self):
        from evas import KernelError
        source='''`include "disciplines.vams"
module measure(x);input x;electrical x;real a;
analog begin @(initial_step)a=0;@(timer(0,0,1e-12))a=sqrt(V(x));end endmodule'''
        p=compile_sources({'zero-timer.va':source},[Instance('M','measure',{'x':'x'})])
        with self.assertRaisesRegex(KernelError,'isolated observer'):
            transient(p,{'x':[[0,1],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_ternary_skips_invalid_constant_math_arm(self):
        r=self.run_body('a=(n==0?2.0:1.0/0.0);b=(n==0?sqrt(a*a):sqrt(-1.0));'
                        '$display("selected %g %g",a,b);', trace_case='ternary')
        self.assertEqual([d['text'] for d in r['transient']['display_records']],['selected 2 2'])

    def test_only_display_still_certifies_the_math_domain(self):
        from evas import KernelError
        with self.assertRaisesRegex(KernelError,'real_arithmetic.*DivisionByZero'):
            self.run_body('$display("bad %g",1.0/a);')

    def test_integer_abs_min_max_preserve_prior_supported_assignments(self):
        r=self.run_body('n=-2;n=abs(n);n=min(n,3);n=max(n,1);$display("n %d",n);', trace_case='integer')
        self.assertEqual([d['text'] for d in r['transient']['display_records']],['n 2'])

    def test_parameters_and_instances_keep_separate_math_state(self):
        source='''`include "disciplines.vams"
module measure(x);input x;electrical x;parameter real k=2;real a,b;
analog begin @(initial_step)begin a=0;b=0;end
@(timer(0.5,0,1e-12))begin a=k*V(x);b=sqrt(a*a);$display("instance %g",b);end
end endmodule'''
        p=compile_sources({'instances.va':source},[
            Instance('A','measure',{'x':'x'},parameters={'k':2}),
            Instance('B','measure',{'x':'x'},parameters={'k':3})])
        r=transient(p,{'x':[[0,1],[1,1]]},[0,.5,1],stop=1,max_step=.5,kernel=KERNEL)
        self.assertEqual([d['text'] for d in r['transient']['display_records']],['instance 2','instance 3'])
        check_instances(self, r, p.to_dict())

    def test_raw_ir_math_arity_origin_and_integer_type_reject(self):
        import copy
        import json
        import subprocess
        source='''`include "disciplines.vams"
module measure(x);input x;electrical x;real a;integer n;
analog begin @(initial_step)begin a=1;n=0;end
@(timer(0.5,0,1e-12))begin a=sqrt(V(x));n=n+1;end end endmodule'''
        p=compile_sources({'raw.va':source},[Instance('M','measure',{'x':'x'})]).to_dict()
        bad=[]
        item=copy.deepcopy(p);item['events'][0]['body'][0]['rhs']['args']=[];bad.append(item)
        item=copy.deepcopy(p);item['events'][0]['body'][0]['rhs']['origin']['instance']='other';bad.append(item)
        item=copy.deepcopy(p);item['events'][0]['body'][1]['rhs']={'op':'state','state':0};bad.append(item)
        item=copy.deepcopy(p)
        item['contributions']=[dict(branch=dict(instance='M',local_positive='x',local_negative='0',kind='voltage'),
            positive=1,negative=0,rhs=dict(op='multiply',left=dict(op='affine',constant=0,terms=[]),right=dict(op='state',state=0)),
            origin=item['events'][0]['origin'])]
        bad.append(item)
        for index, payload in enumerate(bad):
            payload['events'][0]['trigger']['start']=2.0
            with self.subTest(payload=payload):
                request=dict(program=payload,driven=['x'],samples=[],transient=dict(
                    pwl=[[[0,1],[1,1]]],output_times=[0,1],stop=1,max_step=1))
                process=subprocess.run([str(KERNEL)],input=json.dumps(request),capture_output=True,text=True)
                self.assertNotEqual(process.returncode,0)
                self.assertEqual(process.stdout,'')
                error = json.loads(process.stderr)
                expected = [
                    ('invalid_request', r'unknown field `args`'),
                    ('invalid_ir', 'source identity mismatch'),
                    ('unsupported_transient', 'integer assignments require integral state arithmetic'),
                    ('invalid_ir', 'contribution has no procedure capture owner'),
                ]
                self.assertEqual(error['kind'], expected[index][0])
                self.assertRegex(error['message'], expected[index][1])

    def test_condition_math_reads_prior_state_and_keeps_unselected_domain_lazy(self):
        r=self.run_body('a=4;if(sqrt(a)>1) b=abs(-a);else b=sqrt(-a);'
                        '$display("condition %g",b);', trace_case='condition')
        self.assertEqual([d['text'] for d in r['transient']['display_records']],['condition 4'])

    def test_affine_selection_assignment_enclosure_and_display_share_one_value(self):
        r=self.run_body('a=1;b=(1e16+a)-1e16;'
                        'if(b>0.5)$display("yes b=%g",b);else $display("no b=%g",b);'
                        'b=b+1;if(sqrt(b)>1)$display("sqrt b=%g",b);', trace_case='affine')
        self.assertEqual([d['text'] for d in r['transient']['display_records']],['no b=0'])

    def test_constant_math_keeps_zero_timer_and_integer_initial_contracts(self):
        for expression in ['sqrt(4.0)','abs(-2.0)','max(1.0,2.0)','min(2.0,3.0)']:
            with self.subTest(expression=expression):
                source='''`include "disciplines.vams"
module measure(x);input x;electrical x;real a;integer n;
analog begin @(initial_step)begin a=0;n=0;end
@(timer(0,0,1e-12))begin a='''+expression+''';$display("zero %g",a);end
@(timer(0.5,0,1e-12))begin n='''+expression+''';$display("integer %d",n);end
end endmodule'''
                p=compile_sources({'constant.va':source},[Instance('M','measure',{'x':'x'})])
                r=transient(p,{'x':[[0,1],[1,1]]},[0,.5,1],stop=1,max_step=.5,kernel=KERNEL)
                self.assertEqual([d['text'] for d in r['transient']['display_records']],['zero 2','integer 2'])
                check_constant(self, r, p.to_dict())

    def test_direct_display_and_mixed_arguments_keep_their_evaluation_paths(self):
        r=self.run_body('a=1;if((1e16+a)-1e16>0.5)'
                        '$display("mixed %g %g",(1e16+a)-1e16,sqrt(a));', trace_case='mixed')
        self.assertEqual([d['text'] for d in r['transient']['display_records']],[])

    def test_math_expression_uncertainty_cannot_choose_a_later_affine_condition(self):
        # Each source add rounds separately; there is no declared input band.
        r = self.run_body('a=1;b=sqrt(a)+(1e16+a)-1e16;'
                          'if(b>0.5)$display("yes %g",b);else $display("no %g",b);',
                          trace_case='math_cancel')
        self.assertEqual([d['text'] for d in r['transient']['display_records']], ['no 0'])
