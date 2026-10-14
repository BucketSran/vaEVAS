"""Dynamic mesh requests on event-free DAEs; independent y=t reference."""
GUARDS = ["DYNAMICS", "LANG"]
from copy import deepcopy
from fractions import Fraction as F
import json
from pathlib import Path
import tempfile
import unittest
from evas import Instance, KernelError, compile_sources
from evas.runtime import _invoke
KERNEL=Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel'

def program(bound):
    source='''`include "disciplines.vams"
module m(u,y); input u; output y; electrical u,y; real z;
analog begin z=idt(1+2*V(y),0); V(y)<+z-V(y)*V(y); %s end
endmodule''' % bound
    return compile_sources({'implicit-bound.va':source},[Instance('dut','m',{'u':'u','y':'y'})])

def run(bound, times=(0.,.125,.25), sources=None):
    return run_program(program(bound).to_dict(), times, sources)

def run_program(data, times=(0.,.125,.25), sources=None):
    req=dict(program=data,driven=['u'],samples=[],
             transient=dict(pwl=[sources or [[0.,1.],[.25,1.]]],output_times=list(times),stop=.25,max_step=.125),
             tolerances=dict(absolute=1e-8,relative=0.))
    with tempfile.TemporaryDirectory() as d:
        diagnostic=Path(d)/'trace.json'
        result=_invoke(req,KERNEL,diagnostics_path=diagnostic)
        records=json.loads(diagnostic.read_text())['records']
    segments=[r for r in records if r['kind']=='nonlinear_candidate' and r['outcome']=='certified']
    return result,segments

class ImplicitBoundStep(unittest.TestCase):
    def check_wave(self,result,times):
        self.assertEqual(result['transient']['times'],list(times))
        self.assertEqual(len(result['solutions']),len(times))
        for t,s in zip(times,result['solutions'],strict=True):
            self.assertLessEqual(abs(s['voltages'][result['nodes'].index('y')]-t),1e-8)
    def test_dynamic_voltage_bound_caps_each_internal_segment(self):
        result,segments=run('$bound_step(0.03125/(1+V(y)));')
        self.check_wave(result,(0.,.125,.25));self.assertTrue(segments)
        self.assertEqual(segments[-1]['end'],.25)
        for s in segments:
            self.assertLessEqual(F(s['end'])-F(s['start']),F(.03125)/(1+F(s['start'])))
    def test_operator_time_and_source_bounds_use_their_own_coordinates(self):
        cases=[('$bound_step(0.03125/(1+z));',lambda t:F(.03125)/(1+t+t*t)),
               ('$bound_step(0.03125/(1+$abstime));',lambda t:F(.03125)/(1+t)),
               ('$bound_step(0.03125/(1+V(u)));',lambda t:F(.03125)/(2+t))]
        for bound,cap in cases:
            with self.subTest(bound=bound):
                result,segments=run(bound,sources=[[0.,1.],[.25,1.25]])
                self.check_wave(result,(0.,.125,.25));self.assertTrue(segments)
                for s in segments:self.assertLessEqual(F(s['end'])-F(s['start']),cap(F(s['start'])))
    def test_mesh_only_condition_releases_and_queries_do_not_drive_it(self):
        bound='if(V(u)>0) $bound_step(0.015625);'
        source=[[0.,1.],[.125,0.],[.25,0.]]
        result,segments=run(bound,sources=source)
        self.check_wave(result,(0.,.125,.25))
        self.assertTrue(any(s['start']>=.125 and s['end']-s['start']>.015625 for s in segments))
        for s in segments:
            if s['start']<.125:self.assertLessEqual(F(s['end'])-F(s['start']),F(.015625))
        dense=[i/64 for i in range(17)]
        second,more=run(bound,times=dense,sources=source)
        self.check_wave(second,dense)
        self.assertEqual(segments,more)
    def test_invalid_active_bound_rejects_but_inactive_value_is_skipped(self):
        for bound in ('$bound_step(V(u)-1);','$bound_step(V(u)-2);'):
            with self.subTest(bound=bound),self.assertRaisesRegex(KernelError,'invalid_bound_step'):
                run(bound)
        result,_=run('if(V(u)<0) $bound_step(V(u)-2);')
        self.check_wave(result,(0.,.125,.25))

    def test_raw_ir_mesh_predicates_keep_source_affine_admission(self):
        original = program('if(V(u)>0) $bound_step(0.015625);').to_dict()
        affine = lambda node: dict(op="affine", constant=1., terms=[dict(node=node, coefficient=1.)])
        predicates = {
            "internal_voltage": affine(2),
            "operator": dict(op="operator", operator=0),
            "nonlinear_source": dict(op="power", base=affine(1), exponent=2),
        }
        # Both activation and numeric-value Select must obey the same scope.
        # Inactive arms still require structural validation.
        for field in ("active", "value"):
            for name, predicate in predicates.items():
                for inactive in (False, True):
                    with self.subTest(field=field, predicate=name, inactive=inactive):
                        data = deepcopy(original)
                        request = data["step_bounds"][0]
                        selected = deepcopy(request["active"]["then_value"])
                        selected["left"] = predicate
                        if field == "value":
                            selected["then_value"]["constant"] = .015625
                            selected["else_value"]["constant"] = .03125
                            request["value"] = selected
                        else:
                            request["active"]["then_value"] = selected
                        if inactive:
                            request["active"]["left"]["constant"] = 0.
                        with self.assertRaises(KernelError) as caught:
                            run_program(data)
                        self.assertEqual(caught.exception.detail["kind"], "unsupported_transient")

    def test_raw_ir_mesh_references_and_select_owner_are_validated(self):
        original = program('if(V(u)>0) $bound_step(0.015625);').to_dict()
        for fault in ("operator_owner", "node_index", "select_owner"):
            with self.subTest(fault=fault):
                data = deepcopy(original)
                request = data["step_bounds"][0]
                if fault == "operator_owner":
                    request["origin"]["instance"] = "other"
                    request["value"] = dict(op="operator", operator=0)
                elif fault == "node_index":
                    request["value"] = dict(op="affine", constant=0.,
                                            terms=[dict(node=99, coefficient=1.)])
                else:
                    request["active"]["then_value"]["origin"]["instance"] = "other"
                with self.assertRaises(KernelError) as caught:
                    run_program(data)
                self.assertEqual(caught.exception.detail["kind"], "invalid_ir")

    def test_filter_alias_bound_includes_direct_feedthrough(self):
        # H(s)=(1+s)/(1+2s) has DC output h=1 for constant input 1.
        # Its physical filter state alone does not equal that full output.
        # y+y²=.75 selects the stationary root y=.5; the requested cap is 1/64.
        source = """`include "disciplines.vams"
module m(u,y); input u; output y; electrical u,y; real z,h;
analog begin
    z=idt(0,0.75); h=laplace_nd(V(u),'{1,1},'{1,2});
    V(y)<+z-V(y)*V(y); $bound_step(0.03125/(1+h));
end
endmodule"""
        compiled = compile_sources({'filter-bound.va': source},
                                   [Instance('dut', 'm', {'u': 'u', 'y': 'y'})])
        result, segments = run_program(compiled.to_dict())
        self.assertTrue(segments)
        self.assertEqual(segments[-1]['end'], .25)
        for segment in segments:
            self.assertLessEqual(F(segment['end'])-F(segment['start']), F(1,64))
        for solution in result['solutions']:
            self.assertLessEqual(abs(solution['voltages'][result['nodes'].index('y')]-.5), 1e-8)

if __name__=='__main__':unittest.main()
