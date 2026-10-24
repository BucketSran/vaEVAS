"""Source capture identity after static expansion; compile/IR only, no kernel."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']
from dataclasses import replace
import unittest
from unittest.mock import patch
from evas import CompileError, Instance, compile_sources
from evas.ir import (Affine, Binary, RealBoundary, RealBinary, RealLocal, RealBind,
                     ContributionCapture, ProcedureConditional, ProcedureStep)
from evas.procedural import ProcedureBuilder


def compile_body(body, count=3, instances=1):
    source=('`include "disciplines.vams"\nmodule m(u,y,r); input u; output ['+str(count-1)+':0] y;'
            'inout r; electrical u,r; electrical ['+str(count-1)+':0] y; real q; genvar i,j; analog begin '+body+' end endmodule')
    bindings=[Instance('d'+str(n),'m',dict(u='u'+str(n),r='0',**{'y['+str(i)+']':'y'+str(n)+'_'+str(i) for i in range(count)})) for n in range(instances)]
    program=compile_sources({'capture.va':source},bindings)
    program.to_dict()
    return program


def all_steps(body):
    for step in body:
        yield step
        if isinstance(step.action,ProcedureConditional):
            yield from all_steps(step.action.then_body)
            yield from all_steps(step.action.else_body)


def values_at_captures(program, voltage):
    """Small independent interpreter for the arithmetic/branch test's IR subset.

    This oracle checks producer source order and slot snapshots, not EVAS runtime.
    The expected numeric results are derived from the literal source statements.
    """
    slots={}; captures=[]
    def value(v):
        if isinstance(v,Affine):return v.constant+sum(t.coefficient*voltage.get(program.nodes[t.node],0.) for t in v.terms)
        if isinstance(v,RealBoundary):return value(v.value)
        if isinstance(v,RealLocal):return slots[v.binding]
        if isinstance(v,(RealBinary,Binary)):
            a,b=value(v.left),value(v.right)
            return {'add':lambda:a+b,'subtract':lambda:a-b,'multiply':lambda:a*b,'divide':lambda:a/b}[v.operation if isinstance(v,RealBinary) else v.op]()
        raise AssertionError(type(v))
    def body(steps):
        for step in steps:
            a=step.action
            if isinstance(a,RealBind):slots[a.binding]=value(a.value)
            elif isinstance(a,ContributionCapture):
                c=program.contributions[a.contribution]
                captures.append((c.branch.instance,c.branch.local_positive,c.branch.local_negative,value(c.rhs)*(1. if c.branch.local_positive.startswith('y[') else -1.)))
            elif isinstance(a,ProcedureConditional):
                l,r=value(a.left),value(a.right)
                yes={'lt':l<r,'le':l<=r,'gt':l>r,'ge':l>=r}[a.relation]
                body(a.then_body if yes else a.else_body)
            else:raise AssertionError(type(a))
    for proc in program.procedures:body(proc.body)
    return captures


class ContributionOccurrences(unittest.TestCase):
    def test_genvar_capture_reads_slot_before_next_source_write(self):
        p=compile_body('q=V(u,r); for(i=0;i<3;i=i+1) begin V(y[i],r)<+q+i; q=q+1.0; end')
        got=values_at_captures(p,{'u0':0.25})
        self.assertEqual([x[3] for x in got],[0.25,2.25,4.25])
        self.assertEqual([next(n for n in x[1:3] if n.startswith('y[')) for x in got],['y[0]','y[1]','y[2]'])
        self.assertEqual([c.origin.expansion for c in p.contributions],[(('i',0),),(('i',1),),(('i',2),)])
        self.assertEqual(len({(x[1],x[2]) for x in got}),3)

    def test_nested_genvars_guards_and_instances_preserve_every_static_capture(self):
        body=('q=V(u,r); for(i=0;i<2;i=i+1) for(j=0;j<2;j=j+1) '
              'if(V(u,r)>0.5) V(y[2*i+j],r)<+q+2*i+j; else V(y[2*i+j],r)<+q-2*i-j;')
        p=compile_body(body,count=4,instances=2)
        captures=[s.action.contribution for a in p.procedures for s in all_steps(a.body) if isinstance(s.action,ContributionCapture)]
        self.assertEqual(sorted(captures),list(range(16)))
        self.assertEqual(len(captures),16)
        got=values_at_captures(p,{'u0':0.25,'u1':0.75})
        self.assertEqual([x[3] for x in got],[0.25,-0.75,-1.75,-2.75,0.75,1.75,2.75,3.75])
        self.assertEqual([x[0] for x in got],['d0']*4+['d1']*4)
        self.assertEqual([next(n for n in x[1:3] if n.startswith('y[')) for x in got],['y[0]','y[1]','y[2]','y[3]']*2)
        for proc in p.procedures:
            ordinals=[s.expanded_statement_ordinal for s in all_steps(proc.body)]
            self.assertEqual(ordinals,list(range(len(ordinals))))

    def test_repeated_explicit_contributions_are_kept_and_not_merged(self):
        p=compile_body('q=1.0;V(y[0],r)<+q;q=2.0;V(y[0],r)<+q;',count=1)
        self.assertEqual([x[3] for x in values_at_captures(p,{})],[1.0,2.0])
        self.assertEqual(len(p.contributions),2)

    def test_raw_duplicate_capture_still_rejected(self):
        p=compile_body('V(y[0],r)<+1.0;',count=1)
        proc=p.procedures[0];number=len(proc.body)
        invalid=replace(p,procedures=(replace(proc,body=proc.body+(ProcedureStep(number,ContributionCapture(0)),)),))
        with self.assertRaisesRegex(CompileError,'more than one capture'):invalid.to_dict()

    def test_invalid_producer_duplicate_is_not_hidden(self):
        original=ProcedureBuilder.contribution
        def twice(builder,source,index):
            original(builder,source,index)
            original(builder,source,index)
        with patch.object(ProcedureBuilder,'contribution',twice):
            with self.assertRaisesRegex(CompileError,'more than one capture'):
                compile_body('V(y[0],r)<+1.0;',count=1)


if __name__=='__main__':unittest.main()
