"""Closed initial pow reaches physical relations with its outward error intact."""
GUARDS=['LANG','COMPOSE','NONLINEAR-TRANSIENT']
import unittest
from evas import Instance,compile_sources,transient
from test_affine import KERNEL


def source(body,decl='parameter real b=16; parameter real e=0.25; real gain;'):
    return '`include "disciplines.vams"\nmodule m(u,y,r);input u;output y;inout r;electrical u,y,r;'+decl+' analog begin '+body+' end endmodule'


class ConstantInitialPower(unittest.TestCase):
    def test_closed_initial_quarter_power_scales_original_voltage_relation(self):
        # The positive fourth root of16 is2, hence gain=1/2 exactly.
        p=compile_sources({'pow.va':source('@(initial_step) gain=1/pow(b,e); V(y,r)<+gain*V(u,r);')},
                          [Instance('dut','m',dict(u='u',y='y',r='0'))])
        r=transient(p,{'u':[[0,0.25],[1,0.75]]},[0,0.5,1],stop=1,max_step=1,
                    vabstol=1e-12,reltol=1e-10,kernel=KERNEL)
        y=r['nodes'].index('y')
        for row,want in zip(r['solutions'],[0.125,0.25,0.375]):
            self.assertAlmostEqual(row['voltages'][y],want,delta=1e-11)

    def program(self,body='@(initial_step) gain=1/pow(b,e); V(y,r)<+gain*V(u,r);',decl=None):
        return compile_sources({'pow.va':source(body,decl) if decl is not None else source(body)},
                               [Instance('dut','m',dict(u='u',y='y',r='0'))])

    def run_program(self,p,**kwargs):
        return transient(p,{'u':[[0,0.25],[1,0.75]]},[0,0.5,1],stop=1,max_step=1,kernel=KERNEL,**kwargs)

    def test_original_real_exponent_reference_lies_inside_every_root_box(self):
        from decimal import Decimal as D,localcontext
        attenuation=6.020599913279624
        p=self.program(decl='parameter real attenuation=6.020599913279624; real gain;',
            body='@(initial_step) gain=1/pow(10,attenuation/20);V(y,r)<+gain*V(u,r);')
        r=self.run_program(p,vabstol=1e-12,reltol=1e-10)
        with localcontext() as c:
            c.prec=120
            gain=(-D.from_float(attenuation)/D(20)*D(10).ln()).exp()
            y=r['nodes'].index('y')
            for x,box in zip([0.25,0.5,0.75],r['observation_evidence']['voltage_bounds_V']):
                self.assertIsNotNone(box)
                lo,hi=map(D.from_float,box[y]);want=gain*D.from_float(x)
                self.assertLessEqual(lo,want);self.assertGreaterEqual(hi,want)

    def test_zero_exponent_identity_and_negative_fractional_exponent(self):
        for exponent,expected in [(0,1),(-0.25,2)]:
            with self.subTest(exponent=exponent):
                p=self.program(decl=f'parameter real b=16;parameter real e={exponent};real gain;')
                r=self.run_program(p);y=r['nodes'].index('y')
                self.assertAlmostEqual(r['solutions'][0]['voltages'][y],0.25*expected,delta=1e-11)

    def test_same_module_parameters_and_origins_are_instance_local(self):
        text=source('@(initial_step) gain=1/pow(b,e); V(y,r)<+gain*V(u,r);')
        p=compile_sources({'pow.va':text},[Instance('a','m',dict(u='u',y='a',r='0')),
            Instance('b','m',dict(u='u',y='b',r='0'),dict(b=256))])
        r=self.run_program(p)
        for node,want in [('a',0.125),('b',0.0625)]:
            self.assertAlmostEqual(r['solutions'][0]['voltages'][r['nodes'].index(node)],want,delta=1e-11)

    def test_initial_observers_other_writers_and_ordinary_aliases_do_not_bind_early(self):
        from fractions import Fraction as Q
        from evas import CompileError
        initial='gain=1/pow(b,e);'
        for body,decl,wants,records in [
            ('@(initial_step)begin old=gain;'+initial+'end V(y,r)<+old;', 'real old;',
             [0.,0.,0.], [('initial_step',0.,[0.,0.],[.5,0.])]),
            ('@(initial_step)begin '+initial+'gain=3;end V(y,r)<+gain;', '',
             [3.,3.,3.], [('initial_step',0.,[0.],[3.])]),
            ('@(initial_step)'+initial+' @(timer(0.5))gain=3; V(y,r)<+gain;', '',
             [.5,3.,3.], [('initial_step',0.,[0.],[.5]),('timer',.5,[.5],[3.])]),
            ('@(initial_step)'+initial+' @(final_step)gain=3; V(y,r)<+gain;', '',
             [.5,.5,.5], [('initial_step',0.,[0.],[.5]),('final_step',1.,[.5],[3.])]),
            ('@(initial_step)'+initial+' alias=gain;V(y,r)<+alias;', 'real alias;',
             [.5,.5,.5], [('initial_step',0.,[0.],[.5])]),
        ]:
            with self.subTest(body=body):
                p=self.program(body,'parameter real b=16;parameter real e=0.25;real gain;'+decl)
                r=self.run_program(p);y=r['nodes'].index('y')
                # pow(16,1/4)=2 and 1/2 is exactly binary64. The observer
                # sees declaration zero, later writers keep their source order,
                # and final_step runs after the last observation at stop.
                self.assertEqual([row['voltages'][y] for row in r['solutions']],wants)
                for want,box in zip(wants,r['observation_evidence']['voltage_bounds_V'],strict=True):
                    self.assertLessEqual(Q(box[y][0]),Q(want));self.assertLessEqual(Q(want),Q(box[y][1]))
                actual=[(e['kind'],e['time'],[v.hex() for v in e['before']],[v.hex() for v in e['after']]) for e in r['transient']['events']]
                expected=[(kind,time,[v.hex() for v in before],[v.hex() for v in after]) for kind,time,before,after in records]
                self.assertEqual(actual,expected)
        # Declaration initialization still cannot read a mutable stored state.
        with self.assertRaises(CompileError):
            self.program('@(initial_step)'+initial+' V(y,r)<+gain;',
                         'parameter real b=16;parameter real e=0.25;real gain;real old=gain;')

    def test_hidden_function_argument_and_zero_weight_voltage_cannot_be_erased(self):
        from evas import CompileError
        for expression in ['pow(0*V(u,r)+16,0)','pow(16,0*V(u,r))',
                           'pow(16,0.25)+0*(1/0)']:
            with self.subTest(expression=expression),self.assertRaises(CompileError):
                self.program('@(initial_step)gain='+expression+';V(y,r)<+gain;')
        declaration='''real gain; analog function real f; input x;real x;begin f=pow(16,0.25);end endfunction'''
        with self.assertRaises(CompileError):
            self.program('@(initial_step)gain=f(1/0);V(y,r)<+gain;',declaration)

    def test_nonpositive_base_and_nonfinite_domains_remain_structured_rejections(self):
        from evas import CompileError,KernelError
        for base,exponent in [(-16,0.25),(0,0),(0,-0.25)]:
            with self.subTest(base=base,exponent=exponent),self.assertRaises(CompileError):
                self.program(decl=f'parameter real b={base};parameter real e={exponent};real gain;')
        with self.assertRaises(KernelError):
            self.run_program(self.program(decl='parameter real b=1e300;parameter real e=3.25;real gain;'))

    def test_gain_certificate_error_cannot_be_dropped_before_large_amplification(self):
        from evas import KernelError
        p=self.program('@(initial_step)gain=1/pow(b,e);V(y,r)<+1099511627776*(gain-0.5)*V(u,r);')
        with self.assertRaises(KernelError) as caught:
            self.run_program(p,vabstol=1e-12,reltol=0)
        self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')

    def test_raw_chain_rejects_cross_owner_forward_source_and_state_dependencies(self):
        import copy
        from evas import KernelError
        from evas.runtime import _invoke
        raw=self.program().to_dict()
        for mode in ['owner','forward','source','zero_source']:
            p=copy.deepcopy(raw)
            if mode=='owner':p['operators'][1]['origin']['instance']='other'
            elif mode=='forward':p['operators'][1]['input']['right']['operator']=1
            else:
                p['operators'][0]['input']['terms']=[dict(node=p['nodes'].index('u'),coefficient=1 if mode=='source' else 0)]
            with self.subTest(mode=mode),self.assertRaises(KernelError):
                _invoke(dict(program=p,driven=['u'],samples=[],transient=dict(pwl=[[[0,0.25],[1,0.75]]],
                    output_times=[0,1],stop=1,max_step=1)),KERNEL)

    def test_old_half_power_initial_state_keeps_existing_route(self):
        p=self.program('@(initial_step)gain=1/pow(b,e);V(y,r)<+gain;',
                       'parameter real b=16;parameter real e=0.5;real gain;')
        self.assertEqual(len(p.states),1)
        r=self.run_program(p);self.assertEqual(r['solutions'][0]['voltages'][r['nodes'].index('y')],0.25)

    def test_old_rounded_integer_and_half_exponents_keep_original_route(self):
        for exponent,want in [('2+tiny/huge',1/256),('0.5+tiny/huge',0.25)]:
            with self.subTest(exponent=exponent):
                p=self.program('@(initial_step)gain=1/pow(16,'+exponent+');V(y,r)<+gain;',
                    'parameter real tiny=1e-300;parameter real huge=1e300;real gain;')
                self.assertEqual(len(p.states),1)
                r=self.run_program(p)
                self.assertEqual(r['solutions'][0]['voltages'][r['nodes'].index('y')],want)

    def test_source_integer_arithmetic_is_not_reinterpreted_as_real_division(self):
        from fractions import Fraction as Q
        from evas import CompileError
        # Integer 1/2 truncates to zero, so the exponent remains1/4 and
        # gain is exactly1/2. A real-division rewrite would produce1/8.
        p=self.program('@(initial_step)gain=1/pow(16,0.25+n/2);V(y,r)<+gain;',
                       'parameter integer n=1;real gain;')
        r=self.run_program(p);y=r['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in r['solutions']],[.5,.5,.5])
        self.assertEqual(r['transient']['events'][0]['after'],[.5])
        for box in r['observation_evidence']['voltage_bounds_V']:
            self.assertLessEqual(Q(box[y][0]),Q(1,2));self.assertLessEqual(Q(1,2),Q(box[y][1]))
        with self.assertRaises(CompileError):
            self.program('@(initial_step)gain=1/pow(16,0.25+(2147483647+1));V(y,r)<+gain;',
                         'parameter integer n=1;real gain;')

    def test_large_old_initializer_never_enters_optional_proof(self):
        from unittest.mock import patch
        expression='1.0'
        for _ in range(14):
            expression='('+expression+'+'+expression+')'
        text=source('@(initial_step)gain='+expression+';V(y,r)<+gain;', 'real gain;')
        with patch('evas.initial_constant_math.binding',side_effect=AssertionError('old path entered new proof')):
            p=compile_sources({'old-no-pow.va':text},[Instance('d'+str(k),'m',dict(u='u',y='y'+str(k),r='0')) for k in range(4)])
        r=self.run_program(p)
        for node in ['y0','y1','y2','y3']:
            self.assertEqual(r['solutions'][0]['voltages'][r['nodes'].index(node)],16384)

    def test_new_proof_reuses_charged_bottom_up_source_types(self):
        from unittest.mock import patch
        from evas import initial_constant_math as proof
        expression='0'
        for _ in range(12):
            expression='('+expression+'+'+expression+')'
        original_type=proof.integer_type
        original_binding=proof.binding
        calls=0
        def typed(expr,*args,**kwargs):
            nonlocal calls
            calls+=1
            self.assertIn('child_types',kwargs)
            self.assertEqual(len(kwargs['child_types']),len(expr.args))
            return original_type(expr,*args,**kwargs)
        def binding(compiler,model):
            before=compiler.compilation.initial_math_work
            result=original_binding(compiler,model)
            self.assertLessEqual(calls,before-compiler.compilation.initial_math_work)
            self.assertGreater(compiler.compilation.initial_math_work,0)
            return result
        with patch.object(proof,'integer_type',typed),patch.object(proof,'binding',binding):
            self.program('@(initial_step)gain=1/pow(16,0.25+'+expression+');V(y,r)<+gain;')
        self.assertEqual(calls,8195)

    def test_closed_binding_proof_budget_is_shared_across_instances(self):
        from evas import CompileError
        # Repeated source instances cannot replenish the proof owner. The
        # actual emitted expression also remains subject to its old wire cap.
        exponent='0.25'+('+0'*30)
        text=source('@(initial_step)gain=1/pow(b,'+exponent+');V(y,r)<+gain*V(u,r);')
        with self.assertRaises(CompileError) as caught:
            compile_sources({'proof-budget.va':text},[Instance('m'+str(i),'m',dict(u='u',y='y'+str(i),r='0')) for i in range(1200)])
        self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')
        self.assertIn('source proof budget',str(caught.exception))

    def test_native_constant_chain_uses_the_existing_request_audit_limit(self):
        import copy
        from evas import KernelError
        from evas.runtime import _invoke
        raw=self.program().to_dict()
        raw['operators']=list(raw['operators'])
        prototype=copy.deepcopy(raw['operators'][0])
        for i in range(250):
            item=copy.deepcopy(prototype);item['origin']['expansion']=[['budget_copy',i]]
            raw['operators'].append(item)
        with self.assertRaises(KernelError) as caught:
            _invoke(dict(program=raw,driven=['u'],samples=[],transient=dict(pwl=[[[0,0.25],[1,0.75]]],
                output_times=[0,1],stop=1,max_step=1)),KERNEL)
        self.assertEqual(caught.exception.detail['kind'],'resource_budget')
