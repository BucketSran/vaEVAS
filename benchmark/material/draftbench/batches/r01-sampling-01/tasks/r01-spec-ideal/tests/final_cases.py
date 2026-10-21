"""Author-only exploratory extensions. Freeze after the public domain is resolved."""
import copy
from cases import public_cases, control, inst, NS

def final_cases():
    # Rerun public examples. These are trusted new executions, not self-reported results.
    cases=public_cases()
    varied=copy.deepcopy(cases[1])
    varied['name']='heldout_irregular'
    varied['instances'][0].update(
        vin=[[0,1.3],[7*NS,.15],[19*NS,1.45],[31*NS,.4],[60*NS,1.1]],
        track=control(0,[(1.3,1.8),(9.7,0),(17.1,1.8),(18.4,0),(34,1.8),(55,0)]),
        vth=0.72,vinit=0.48)
    cases.append(varied)
    cases.append(dict(name='heldout_reset_orders',stop=60*NS,instances=[
        inst('first',control(1.8,[(5,0),(23,1.8),(47,0)]),
             control(1.8,[(13,0),(31,1.8),(44,0)]),vinit=.25),
        inst('second',control(0,[(4,1.8),(14,0),(31,1.8),(46,0)]),
             control(0,[(11,1.8),(25,0)]),vinit=1.25)]))
    # Strict crossings near both endpoints, without excluding startup or the stop.
    cases.append(dict(name='heldout_endpoint',stop=60*NS,instances=[
        inst('early_late',control(0,[(.4,1.8),(59.6,0)],width=.1),
             control(0,[]),vin=[[0,.1],[60*NS,1.5]],vinit=.75)]))
    return cases
