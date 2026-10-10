"""Forced timer consumers, reusing the unchanged sample/edge/filter contract.

The extra integral is a sum of exact rational rectangle areas. No EVAS history
or simulator output enters its reference. All exported points are checked.
"""
import copy
from fractions import Fraction as F
import json
import math
from pathlib import Path
import sys

VALIDATION = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(VALIDATION/'sample_edge_filter'), str(VALIDATION/'paper')]
import contract as sef
from precision_checker import assess as assess_hold

CASES = [copy.deepcopy(c) for c in sef.CASES if c['id'] != 'SEF-RESET']
INTEGRAL = copy.deepcopy(json.loads((VALIDATION/'paper/precision-v1.json').read_text())['cards'][0])
INTEGRAL.update(id='STROBE-TIMER-IDT', initial_V=.25,
                inputs={'u':[[t*sef.T,v] for t,v in sef.INPUT]})
INTEGRAL['parameters']['Q0'] = .25
INTEGRAL['ports'].append('i'); INTEGRAL['outputs'].append('i')
INTEGRAL['source'] = '''`include "disciplines.vams"
module probe(u,y,count,i);
inout u,y,count,i; electrical u,y,count,i;
parameter real T=1e-6, TT=1e-10, Q0=0.25;
real q; integer n;
analog begin
@(initial_step) begin q=Q0; n=0; end
@(timer(T,T,TT)) begin q=V(u); n=n+1; end
V(y)<+q; V(count)<+n; V(i)<+idt(q/T,0.05);
end endmodule
'''
# Same 100 uV engineering output budget as the preserved SEF cases. The
# original 12 precision requests retain their separate, tighter 1.01 uV/11 nV.
BUDGETS = copy.deepcopy(json.loads((VALIDATION/'paper/precision-v1.json').read_text())['budgets'])
BUDGETS.update(absolute_V=sef.VOLTAGE_BUDGET, relative=0.)
CASES.append(INTEGRAL)


def integral_value(time):
    t=F.from_float(time)/F.from_float(sef.T)
    value=F(1,20); previous=F(1,4); start=F(0)
    for k in range(1,9):
        end=min(t,F(k))
        value+=previous*max(F(0),end-start)
        if t<=k:return float(value)
        previous=sef.pwl(sef.INPUT,k); start=F(k)
    return float(value+previous*(t-start))


def assess(case, rows):
    if case['id'] != INTEGRAL['id']:
        report=sef.assess(case,rows)
        return {**report,'status':'pass' if report['status']=='PASS' else 'fail'}
    report=assess_hold(INTEGRAL,rows,BUDGETS)
    if report['status']!='pass':return report
    # Required i is already checked for type/finiteness by assess_hold.
    errors=[abs(r['i']-integral_value(r['time'])) for r in rows]
    maximum=max(errors)
    return {**report,'integral_error_V':maximum,
            'status':'pass' if maximum<=sef.VOLTAGE_BUDGET else 'numerical_error'}
