"""Independent frontend/utility probes of source-v0.8.7 only."""
from pathlib import Path
import json
import os
import sys

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT/'source-v0.8.7'))
os.environ['EVAS_RUST_CORE_LIB']=str(OUT/'rust-target/debug/libevas_rust_core.dylib')
from evas.compiler.parser import parse
from evas.compiler.lexer import tokenize
from evas.simulator.engine import pulse,pwl
from evas.simulator.expr_ir import build_state_binding_ir
from evas.simulator.stmt_ir import lower_stmt,encode_body_stmt_ops,StatementLoweringContext
from evas.simulator.rust_backend import load_rust_backend
rb=load_rust_backend()
rows=[]
def check(name,expected,fn):
    try: row={'id':name,'expectation':expected,'observation':fn()}
    except Exception as e: row={'id':name,'expectation':expected,'exception':type(e).__name__,'message':str(e)}
    rows.append(row)
    print(json.dumps(row,ensure_ascii=False))

def run_body(source,inputs):
    m=parse(source)
    ir=lower_stmt(m.analog_block.body,StatementLoweringContext.veriloga_body(user_functions=m.functions))
    bindings=build_state_binding_ir(m)
    p=encode_body_stmt_ops(ir,bindings,{'u':0,'y':1})
    if p is None:return {'encoded':False}
    b=rb.make_body_ir_batch(stmt_ops=p.stmt_ops,expr_ops=p.expr_ops)
    result=[]
    count=1+max([x.slot for x in bindings.bindings if x.kind=='state_scalar'] or [0])
    # These probes have no parameters/arrays and at most two scalar states.
    count=max(count,2)
    for x in inputs:
        nodes=[x,0.];state=[0.]*count
        rb.evaluate_body_ir(b,nodes,state,[])
        result.append({'x':x,'y':nodes[1]})
    return result

function='''module f(u,y); input u; output y; electrical u,y; real q;
analog function real twice; input x; real x; begin twice=2*x; end endfunction
analog begin q=twice(V(u)); V(y)<+q; end endmodule'''
check('F07_pure_function','y=2x at -1,.125,3',lambda:run_body(function,[-1.,.125,3.]))
loop='''module f(u,y); input u; output y; electrical u,y; integer i; real q;
analog begin q=0; for(i=0;i<3;i=i+1) q=q+V(u); V(y)<+q; end endmodule'''
check('F08_bounded_loop','y=3x at -1,.125,3',lambda:run_body(loop,[-1.,.125,3.]))
check('F09_based_invalid','8\'hGG is invalid and should be rejected',lambda:[{'kind':x.type.name,'value':x.value,'raw':x.raw} for x in tokenize("8'hGG")])
check('F10_based_unknown','4\'b10x1 contains unknown logic; do not silently relabel as ordinary numeric value',lambda:[{'kind':x.type.name,'value':x.value,'raw':x.raw} for x in tokenize("4'b10x1")])
check('H03_pulse_plateau','with rise=1,width=2,fall=1, points at 0,.5,1,2,3,3.5,4 are 0,.5,1,1,1,.5,0',lambda:[pulse(0.,1.,10.,rise=1.,fall=1.,width=2.)(t) for t in [0.,.5,1.,2.,3.,3.5,4.]])
check('H04_pwl_basic','linear interpolation and held ends -> 1,1,2,3,3',lambda:[pwl([0.,2.],[1.,3.])(t) for t in [-1.,0.,1.,2.,3.]])
check('H05_pwl_overflow','midpoint of -1e308,+1e308 is zero',lambda:str(pwl([0.,1.],[-1e308,1e308])(.5)))
check('H06_pwl_nonfinite','nonfinite knot should be rejected at construction',lambda:str(pwl([0.,float('nan')],[0.,1.])(.5)))
(OUT/'evidence/frontend-waveform-probes.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
