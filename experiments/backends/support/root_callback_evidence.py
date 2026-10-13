"""Reviewed SH-X committed callbacks, independently checked against native state.

The caller proves frozen source, compiled-program and kernel identity. This is an
accepted-state ledger, not a mathematical-root certificate or Spectre trace.
"""
from callback_evidence import _counter_state, _origin_label, _box, finite
from fractions import Fraction as F
from precision_v2 import load_contract
from root_windows import reference_roots
import math


def _cross_guard(trigger,program,card,root):
    """Prove the original clk-.5 affine guard on this actual rising segment."""
    if program['nodes'].count('clk')!=1 or program['nodes'].count('0')!=1:
        raise ValueError('cross input identity is ambiguous')
    clock=program['nodes'].index('clk');coefficients={};constant=F(0)
    def affine(expr):
        nonlocal constant
        if type(expr) is not dict:
            raise ValueError('invalid cross guard expression')
        if expr.get('op')=='add':
            affine(expr['left']);affine(expr['right'])
            return
        if expr.get('op')!='affine' or not finite(expr['constant']):
            raise ValueError('cross guard is not the original affine structure')
        constant+=F(expr['constant'])
        for term in expr['terms']:
            node=term['node'];gain=term['coefficient']
            if type(node) is not int or not 0<=node<len(program['nodes']) or not finite(gain):
                raise ValueError('invalid cross guard node/coefficient')
            if program['nodes'][node]=='0' or gain==0:continue
            if node!=clock:raise ValueError('cross guard depends on another input or output')
            coefficients[node]=coefficients.get(node,F(0))+F(gain)
    affine(trigger['guard'])
    if coefficients!={clock:F(1)} or constant!=F(-.5):
        raise ValueError('cross guard differs from original clk-.5')
    slope=coefficients[clock]*root.slope
    if (slope<=0 or type(trigger['direction']) is not int or
        trigger['direction']!=(1 if slope>0 else -1)):
        raise ValueError('cross direction differs from actual represented PWL slope')
    if (not finite(trigger['expression_tolerance']) or
        trigger['expression_tolerance']!=card['cross_expression_tolerance_V'] or
        not finite(trigger['time_tolerance']) or trigger['time_tolerance']!=card['event_late_s']):
        raise ValueError('cross tolerances differ from original contract')


def qualify(card,program,response,rows,*,producer_qualified=False):
    try:
        roots=reference_roots(card)
        if card['id']!='SH-X-RAMP' or not producer_qualified:
            raise ValueError('unreviewed SH-X producer')
        if (program['schema_version']!=response['schema_version'] or program['nodes']!=response['nodes'] or
            response['observation_evidence']['initial_settled'] is not True):
            raise ValueError('program/response or settled-state identity differs')
        state=_counter_state(program,'count');sample=_counter_state(program,'y')
        previous=[s['initial'] for s in program['states']]
        records=response['transient']['events']
        if len(records)!=card['expected_events']:raise ValueError('missing or extra committed callback')
        boxes={};history=[]
        for occurrence,record in enumerate(records,1):
            index=record['event']
            if type(index) is not int or not 0<=index<len(program['events']):raise ValueError('bad event index')
            event=program['events'][index];trigger=event['trigger']
            if (record['origin']!=_origin_label(event['origin']) or record['kind']!='cross' or
                trigger['kind']!='cross' or trigger['direction']!=1):raise ValueError('wrong event origin/kind/direction')
            _cross_guard(trigger,program,card,roots[occurrence-1])
            if (event['origin']['instance']!=program['states'][state]['instance'] or
                event['origin']['instance']!=program['states'][sample]['instance']):
                raise ValueError('event/counter/sample instance differs')
            guard=record.get('guard_value')
            if not finite(guard) or abs(guard)>trigger['expression_tolerance']:
                raise ValueError('unproved crossing guard')
            before,after=record['before'],record['after']
            if before!=previous or len(after)!=len(previous) or not all(finite(v) for v in before+after):
                raise ValueError('broken committed state chain')
            if before[state]!=occurrence-1 or after[state]!=occurrence:
                raise ValueError('wrong committed counter transition')
            if any(after[i]!=before[i] for i in range(len(after)) if i not in (state,sample)):
                raise ValueError('unexpected persistent state update')
            box=list(_box(record.get('observation_time_bounds',[record['time'],record['time']]),record['time'],card['stop_s']))
            if history and history[-1]['box_s'][1]>=box[0]:raise ValueError('callback order is unproved')
            boxes[occurrence]=box;history.append({'index':occurrence,'box_s':box,'before':before,'after':after})
            previous=after
        ulps=load_contract()['budgets']['time_serialization_ulps']
        if type(ulps) is not int or ulps<0:raise ValueError('invalid frozen time serialization budget')
        ut=ulps*math.ulp(card['stop_s'])
        for row in rows:
            if not finite(row.get('time')) or not finite(row.get('count')):raise ValueError('invalid native counter')
            minimum=sum(b[1]<row['time']-ut for b in boxes.values())
            maximum=sum(b[0]<=row['time']+ut for b in boxes.values())
            if not any(abs(row['count']-v)<=1e-9 for v in range(minimum,maximum+1)):
                raise ValueError('native counter contradicts committed callbacks')
        return {'status':'qualified','committed_callback_boxes':boxes,'history':history,
                'time_serialization_ulps':ulps,'time_serialization_bound_s':ut,
                'claim':'reviewed accepted-state callbacks; root timing and sampled voltages graded separately'}
    except (ValueError,KeyError,IndexError,TypeError,ArithmeticError) as exc:
        return {'status':'unknown','reason':str(exc)}
