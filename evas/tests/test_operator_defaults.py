"""LRM 2.4 §§4.5.5/4.5.9 defaults, through public compile and Rust transient.

Analytic oracles use a constant integral modulo one and piecewise slope limits.
Explicit and omitted calls share no state; parameters bind separately per instance.
"""
GUARDS = ["LANG", "SLEW", "DYNAMICS"]

import unittest
from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model


def program(body, declarations='', instances=None, ports='u,y,r'):
    return compile_sources({'defaults.va': model(body, declarations, ports=ports, directions="input u; output " + ("y,z" if "z" in ports.split(",") else "y") + "; inout r;")},
                           instances or [instance()])


def values(result, node):
    i = result['nodes'].index(node)
    return [s['voltages'][i] for s in result['solutions']]


class OperatorDefaults(unittest.TestCase):
    def test_idtmod_default_zero_offset_matches_explicit_and_modulo_answer(self):
        # z=1/8-t/4; includes negative raw phase and two independent call sites.
        times = [0, 1, 2, 3, 4, 5]
        p = program('V(y,r)<+idtmod(V(u,r),ic,modulus); '
                    'V(z,r)<+idtmod(V(u,r),ic,modulus,0);',
                    'parameter real ic=0.125, modulus=1;', ports='u,y,z,r',
                    instances=[instance(connections=dict(u='u',y='y',z='z',r='0'))])
        result = transient(p, {'u': [[0,-0.25],[5,-0.25]]}, times,
                           stop=5, max_step=5, kernel=KERNEL)
        for node in ['y','z']:
            for actual,t in zip(values(result,node),times):
                self.assertAlmostEqual(actual,(0.125-t/4)%1,delta=2e-13)
        self.assertEqual(len(p.operators),2)
        self.assertNotEqual(p.operators[0].origin.column,p.operators[1].origin.column)

    def test_slew_default_symmetric_rates_matches_explicit_and_physical_answer(self):
        # u rises with slope 2 then falls with slope -4. y catches at 12/5,
        # then falls with -1 until reaching -4 at t=44/5.
        times=[0,1,2,2.5,3,4,6,8,9,10]
        p=program('V(y,r)<+slew(V(u,r),1); V(z,r)<+slew(V(u,r),1,-1);',
                  ports='u,y,z,r',instances=[instance(connections=dict(u='u',y='y',z='z',r='0'))])
        result=transient(p,{'u':[[0,0],[2,4],[4,-4],[10,-4]]},times,
                         stop=10,max_step=10,kernel=KERNEL)
        for node in ['y','z']:
            for actual,t in zip(values(result,node),times):
                answer=t if t<=2.4 else max(-4,4.8-t)
                self.assertAlmostEqual(actual,answer,delta=2e-13)
        self.assertEqual(len(p.operators),2)

    def test_explicit_offset_and_fall_are_not_overridden(self):
        p=program('V(y,r)<+idtmod(V(u,r),0.125,1,-0.5);')
        r=transient(p,{'u':[[0,0.25],[3,0.25]]},[0,2,3],stop=3,max_step=3,kernel=KERNEL)
        for actual,answer in zip(values(r,'y'),[0.125,-0.375,-0.125]):
            self.assertAlmostEqual(actual,answer,delta=2e-13)
        p=program('V(y,r)<+slew(V(u,r),1,-2);')
        r=transient(p,{'u':[[0,0],[2,4],[4,-4],[8,-4]]},[0,3,4,6],stop=8,max_step=8,kernel=KERNEL)
        for actual,answer in zip(values(r,'y'),[0,1.2,-0.8,-4]):
            self.assertAlmostEqual(actual,answer,delta=2e-13)

    def test_instance_constants_and_call_sites_keep_independent_histories(self):
        body='V(y,r)<+idtmod(V(u,r),ic,1); V(z,r)<+slew(V(u,r),rate);'
        insts=[instance(name=n,connections=dict(u=n+'u',y=n+'y',z=n+'z',r='0'),
                        parameters=dict(ic=ic,rate=rate))
               for n,ic,rate in [('a',0.125,0.25),('b',0.375,0.5)]]
        for order in [insts,insts[::-1]]:
            p=program(body,'parameter real ic=0.125,rate=1;',ports='u,y,z,r',instances=order)
            r=transient(p,{'au':[[0,1],[2,3]],'bu':[[0,-1],[2,-3]]},[0,0.5,1.5],
                        stop=2,max_step=2,kernel=KERNEL)
            for n,ic,rate,sign in [('a',0.125,0.25,1),('b',0.375,0.5,-1)]:
                for actual,t in zip(values(r,n+'y'),[0,0.5,1.5]):
                    self.assertAlmostEqual(actual,(ic+sign*(t+t*t/2))%1,delta=2e-13)
                for actual,t in zip(values(r,n+'z'),[0,0.5,1.5]):
                    self.assertAlmostEqual(actual,sign*(1+rate*t),delta=2e-13)
            self.assertEqual(len(p.operators),4)
            self.assertEqual({o.origin.instance for o in p.operators},{'a','b'})

    def test_unsupported_arities_and_domains_remain_rejected(self):
        calls=['idtmod(V(u,r))','idtmod(V(u,r),0)',
               'idtmod(V(u,r),0,1,0,1e-6)','idtmod(V(u,r),0,0)',
               'idtmod(V(u,r),0,-1)','idtmod(V(u,r),V(u,r),1)',
               'idtmod(V(u,r),0,V(u,r))','idtmod(V(u,r),0,1,V(u,r))',
               'slew(V(u,r))','slew(V(u,r),1,-1,0)',
               'slew(V(u,r),0)','slew(V(u,r),-1)','slew(V(u,r),V(u,r))',
               'slew(V(u,r),1,0)','slew(V(u,r),1,1)',
               'slew(V(u,r),1,V(u,r))','slew(V(u,r),1e309)',
               'idtmod(V(u,r),0,1e309)','idtmod(V(u,r),1e309,1)',
               'idtmod(V(u,r),0,1,1e309)']
        for call in calls:
            with self.subTest(call=call),self.assertRaises(CompileError):
                program('V(y,r)<+'+call+';')
