"""Small independent checks of the immutable v0.8.7 export; not qualification.

Run with old repository's existing numpy-capable Python, -B; no pytest needed.
Analytic expectations are stated in each record. No new repository imports.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import sys
import traceback

OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'source-v0.8.7'
sys.path.insert(0, str(SOURCE))
os.environ['EVAS_RUST_CORE_LIB'] = str(OUT / 'rust-target/debug/libevas_rust_core.dylib')
from evas.compiler.parser import parse
from evas.compiler.preprocessor import preprocess
from evas.simulator.backend import compile_module, CompiledModel
from evas.simulator.engine import Simulator, dc, pwl
from evas.simulator.expr_ir import build_state_binding_ir
from evas.simulator.stmt_ir import lower_stmt, encode_body_stmt_ops
from evas.simulator.rust_program import _extend_bindings_with_stateful_function_slots
from evas.simulator.rust_backend import load_rust_backend, RustNodeIdBatch

records = []
def probe(name, expected, fn):
    try:
        value = fn()
        record = dict(id=name, independent_expectation=expected, observation=value, probe_status='completed')
    except Exception as exc:
        record = dict(id=name, independent_expectation=expected, exception=type(exc).__name__, message=str(exc), probe_status='exception')
    records.append(record)
    print(json.dumps(record, ensure_ascii=False), flush=True)

def va(body, declarations='real q;'):
    return f'module probe(u,r,y); input u,r; output y; electrical u,r,y; {declarations} analog begin {body} end endmodule'

def encode(body):
    m = parse(va(body))
    ir = lower_stmt(m.analog_block.body)
    bindings = _extend_bindings_with_stateful_function_slots(build_state_binding_ir(m), ir)
    program = encode_body_stmt_ops(ir, bindings, {'u':0, 'r':1, 'y':2})
    return {'accepted': program is not None,
            'ops': [vars(x) for x in program.stmt_ops] if program else [],
            'exprs': [vars(x) for x in program.expr_ops] if program else [],
            'bindings': [vars(b) for b in bindings.bindings]}

def sim(body, source=None, h=0.125, stop=1.0):
    s = Simulator()
    s.add_source('u', source or dc(1.0))
    s.add_source('r', dc(0.0))
    s.add_model(compile_module(parse(va(body)))())
    s.record('y')
    result = s.run(tstop=stop, tstep=h, record_step=h,
                   rust_full_model_fastpath=True, rust_full_model_required=True,
                   rust_required=True, skip_source_error_control=True)
    return {'time': [float(x) for x in result.time], 'y': [float(x) for x in result.signals['y']],
            'runtime_stats': {k:v for k,v in s._perf_stats.items() if k in ['rust_sim_program_enabled','rust_sim_program_event_transition_enabled']}}

probe('F01_timer2', 'syntax accepts two arguments', lambda: {'parsed': bool(parse(va('@(timer(0,1)) q=1;')))})
probe('F02_timer3', 'LRM timer tolerance is a third argument; this source path rejects it', lambda: {'parsed': bool(parse(va('@(timer(0,1,0.01)) q=1;')))})
for i,call in enumerate(['idt(V(u),0.25)', 'idt(V(u),0.25,1)', 'idtmod(V(u),0,1,0)', 'idtmod(V(u),0,1,-0.5)', 'idtmod(V(u),0)', 'idtmod(V(u),0,-1)']):
    probe(f'D0{i+1}_encode', 'observe exact accepted arity/defaults; idt reset and idtmod nonzero offset require explicit semantics', lambda c=call: {'call':c, **encode(f'q={c};')})
probe('D07_idt_constant', 'q=0.25+t (zero residual at all samples)', lambda: sim('q=idt(V(u),0.25); V(y)<+q;'))
probe('D08_idt_ramp', 'q=0.25+t^2/2 for u=t', lambda: sim('q=idt(V(u),0.25); V(y)<+q;', pwl([0.,1.],[0.,1.])))
probe('D09_idtmod_wrap', 'q=(0.125+1.5t) modulo 1', lambda: sim('q=idtmod(1.5,0.125,1,0); V(y)<+q;'))
probe('D10_idtmod_omitted_modulus', 'LRM omitted modulus is unbounded integration; q=1.5t', lambda: sim('q=idtmod(1.5,0); V(y)<+q;'))
probe('D11_two_calls_same_target', 'second independent call should determine final q=2t; sharing q must not merge histories', lambda: sim('q=idt(1,0); q=idt(2,0); V(y)<+q;'))
probe('D12_idt_reset_production', 'unsupported reset should fail closed', lambda: sim('q=idt(V(u),0.25,1); V(y)<+q;'))
probe('L01_single_nd_ramp_h4', 'y=t-1+exp(-t); at t=1 y=exp(-1)', lambda: sim("V(y)<+laplace_nd(V(u),'{1},'{1,1});", pwl([0.,1.],[0.,1.]),0.25))
probe('L02_single_nd_ramp_h8', 'same analytic y as L01; compare effect of halved step', lambda: sim("V(y)<+laplace_nd(V(u),'{1},'{1,1});", pwl([0.,1.],[0.,1.]),0.125))
probe('L03_differential_direct', 'V(u,r) with grounded r is identical input to L02', lambda: sim("V(y)<+laplace_nd(V(u,r),'{1},'{1,1});", pwl([0.,1.],[0.,1.])))
probe('L04_differential_assignment', 'assignment body uses different lowering; same physical first-order filter', lambda: sim("q=laplace_nd(V(u,r),'{1},'{1,1}); V(y)<+q;", pwl([0.,1.],[0.,1.])))
probe('L05_higher_order_nd', 'requires full second-order state; should reject unsupported shape', lambda: encode("q=laplace_nd(V(u),'{1},'{1,2,1});"))
probe('L06_np_extra_pole', 'two distinct poles must affect transfer response; inspect whether all coefficients survive', lambda: encode("q=laplace_np(V(u),'{1},'{-1,0,-2,0});"))
probe('L07_zp_extra_pole', 'second pole must not be ignored', lambda: encode("q=laplace_zp(V(u),'{0,0},'{-1,0,-2,0});"))
probe('L08_negative_tau', 'negative time constant must not be silently stabilized with abs', lambda: sim("q=laplace_nd(V(u),'{1},'{1,-1}); V(y)<+q;",pwl([0.,1.],[0.,1.])))
probe('L09_direct_with_event', 'inspect composition boundary between filter and event ABI', lambda: sim("@(timer(0,0.5)) q=1; V(y)<+laplace_nd(V(u),'{1},'{1,1});"))
probe('C01_contribution_order_ab', 'independent branch contribution sum=3', lambda: sim('V(y)<+1; V(y)<+2;'))
probe('C02_contribution_order_ba', 'same sum=3 after order reversal', lambda: sim('V(y)<+2; V(y)<+1;'))
probe('C03_implicit', 'y=1+0.5y requires y=2 at every sample', lambda: sim('V(y)<+V(u)+0.5*V(y);'))
probe('F03_macro_prefix', '`A must not alter distinct identifier `AB; expected 2', lambda: preprocess('`define A 1\n`define AB 2\n`AB')[0])
probe('F04_macro_string', 'macro name inside a quoted string stays literal', lambda: preprocess('`define A 1\n"`A"')[0])
probe('F05_macro_nested', 'function macro must preserve nesting and commas', lambda: preprocess('`define ADD(a,b) ((a)+(b))\n`ADD(f(1,2),3)')[0])
probe('F06_macro_missing_arg', 'bad macro arity should be diagnosed, not create empty expression', lambda: preprocess('`define ADD(a,b) ((a)+(b))\n`ADD(1)')[0])
def delay_helper():
    model = CompiledModel()
    values = [(t,model._absdelay('one',t,t,0.25)) for t in [0.0,0.5,1.0]]
    return {'samples':values,'expected_linear_history':[0.,0.25,0.75]}
probe('H01_delay_helper', 'continuous ramp with d=.25 gives 0,.25,.75 at 0,.5,1', delay_helper)
probe('H02_delay_production', 'Python helper does not imply production Rust accepts absdelay', lambda: sim('V(y)<+absdelay(V(u),0.25);',pwl([0.,1.],[0.,1.])))
rb=load_rust_backend()
probe('N01_nonfinite_error_ratio', 'NaN must not be certified as zero error',lambda: {'ratio':rb.max_err_ratio([float('nan')],[0.],RustNodeIdBatch([0]),1e-3,1e-6)})
probe('N02_finite_error_ratio', '|2-1|/(.1*2+.01)=100/21',lambda: {'ratio':rb.max_err_ratio([2.],[1.],RustNodeIdBatch([0]),.1,.01)})
def cross_trace():
    a=dict(prev_values=[0.],prev_times=[0.],pprev_values=[0.],pprev_times=[0.],initialized_flags=[0],directions=[1],last_cross_times=[-float('inf')],current_values=[0.],triggered_flags=[0],cross_times=[0.],trigger_directions=[0],went_beyond_flags=[0])
    trace=[]
    for t,x in [(0.,-.3),(0.5,-.15),(1.,0.),(1.5,.15),(2.,.3)]:
        a['current_values'][0]=x
        rb.cross_detector_step(**a,time=t,time_tol=1.,expr_tol=.2)
        trace.append({'t':t,'x':x,'candidate':a['triggered_flags'][0],'last_cross_time':str(a['last_cross_times'][0]),'direction_rejection_at_negative_x':bool(a['triggered_flags'][0] and x<0)})
    return trace
probe('E01_cross_candidate_history', 'a direction-rejected early candidate must not consume the later actual crossing',cross_trace)

receipt={'python':sys.version,'source':str(SOURCE),'binary':str(rb.library_path),'binary_sha256':hashlib.sha256(rb.library_path.read_bytes()).hexdigest(),
         'core_version':rb.core_version,'build_revision':rb.build_revision,'records':records}
(OUT/'evidence/python-probes.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
