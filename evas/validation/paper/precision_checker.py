"""Finite engineering checks, independent of simulator code and its certificates.

The reference is the declared PWL stimulus and first-order differential equation.
Event brackets come from one run's exported counter. They are never interpolated
across jumps or fitted independently for individual output observations.
"""
from decimal import Decimal, localcontext
import math
from bisect import bisect_left


def dec(value):
    return Decimal(str(value))


def pwl(points, time):
    with localcontext() as ctx:
        ctx.prec = 80
        t = dec(time)
        for (a, y), (b, z) in zip(points, points[1:]):
            if t <= dec(a):
                return float(dec(y))
            if t <= dec(b):
                return float(dec(y) + (dec(z)-dec(y))*(t-dec(a))/(dec(b)-dec(a)))
        return float(points[-1][1])


def slope_bound(points):
    return max((abs((b[1]-a[1])/(b[0]-a[0])) for a,b in zip(points,points[1:])), default=0.)


class FirstOrder:
    """Variation-of-constants solution at 80 decimal digits, with DC initial state.

    y = a + m*(h-tau) + (y0-a+m*tau)*exp(-h/tau).
    This does not call an EVAS propagator or copy a backend's output.
    """
    def __init__(self, card):
        self.tau = dec(card['tau_s'])
        self.points = [(dec(t),dec(v)) for t,v in card['inputs']['u']]
        self.states = [dec(card['initial_V'])]
        with localcontext() as ctx:
            ctx.prec = 80
            for (a,u),(b,v) in zip(self.points,self.points[1:]):
                self.states.append(self.segment(u,(v-u)/(b-a),b-a,self.states[-1]))

    def segment(self, a, m, h, y0):
        return a+m*(h-self.tau)+(y0-a+m*self.tau)*(-h/self.tau).exp()

    def value(self, time):
        with localcontext() as ctx:
            ctx.prec = 80
            t = dec(time)
            for i,((a,u),(b,v)) in enumerate(zip(self.points,self.points[1:])):
                if t <= b:
                    return float(self.segment(u,(v-u)/(b-a),max(t-a,Decimal(0)),self.states[i]))
            a,u = self.points[-1]
            return float(self.segment(u,Decimal(0),t-a,self.states[-1]))


def time_uncertainty(t, card, budgets):
    # Guard for 17-digit export/decimal decoding, not a solver timing tolerance.
    return budgets['time_serialization_ulps'] * math.ulp(max(abs(t),card['stop_s']))


def voltage_uncertainty(value, card, budgets):
    # Includes binary conversion of the independent 80-digit reference.
    return budgets['voltage_serialization_ulps'] * math.ulp(max(abs(value),card['scale_V'])) + 1e-50


def error_bounds(value, lo, hi, uncertainty):
    return (max(0.,lo-value,value-hi)-uncertainty,
            max(abs(value-lo),abs(value-hi))+uncertainty)


def assess(card, rows, budgets):
    budget = budgets['absolute_V']+budgets['relative']*card['scale_V']
    input_budget = budgets['input_absolute_V']+budgets['input_relative']*card['scale_V']
    result = {'condition':card['id'],'voltage_budget_V':budget,'input_budget_V':input_budget,
              'claim':'finite exported observations and key boundaries; no whole-trajectory proof',
              'status':'evidence_insufficient'}
    required = ['time',*card['inputs'],*card['outputs']]
    if len(rows)<3 or any(any(type(r.get(k)) not in (float,int) or not math.isfinite(r[k]) for k in required) for r in rows):
        return {**result,'reason':'missing or nonfinite observations'}
    times = [r['time'] for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])):
        return {**result,'reason':'timestamps are not strictly increasing'}
    ut = time_uncertainty(card['stop_s'],card,budgets)
    if abs(times[0])>ut or abs(times[-1]-card['stop_s'])>ut:
        return {**result,'reason':'incomplete start/stop coverage','extent_s':[times[0],times[-1]]}
    max_gap = max(b-a for a,b in zip(times,times[1:]))
    result.update(row_count=len(rows),extent_s=[times[0],times[-1]],max_gap_s=max_gap,
                  time_observation_allowance_s=ut)
    if max_gap > card['unit_s']*budgets['global_gap_units']+2*ut:
        return {**result,'reason':'observation gap exceeds frozen limit'}
    boundaries=sorted({t for pts in card['inputs'].values() for t,v in pts} | set(card.get('events_s',[])))
    distance=budgets['boundary_distance_s']
    for t in boundaries:
        i=bisect_left(times,t)
        nearby=times[max(0,i-1):i+1]
        if not nearby or min(abs(q-t) for q in nearby)>distance+ut:
            return {**result,'reason':'missing required boundary observation','boundary_s':t}
        if 0<t<card['stop_s']:
            before=[q for q in times[max(0,i-2):i+1] if q<t-ut]
            after=[q for q in times[i:i+3] if q>t+ut]
            if not before or not after or t-max(before)>distance+ut or min(after)-t>distance+ut:
                return {**result,'reason':'missing required boundary left/right observations','boundary_s':t}
    input_errors = {}
    for name,points in card['inputs'].items():
        slope = slope_bound(points)
        err = max(abs(r[name]-pwl(points,r['time']))+
                  voltage_uncertainty(r[name],card,budgets)+slope*ut for r in rows)
        input_errors[name] = err
        # The unit-amplitude clock has its own fixed scale.
        limit = budgets['input_absolute_V']+budgets['input_relative']*(1. if name=='clk' else card['scale_V'])
        if err > limit:
            return {**result,'status':'input_mismatch','reason':'actual stimulus does not meet the shared requirement',
                    'input_error_upper_V':input_errors,'failed_input':name,'failed_input_budget_V':limit}
    result['input_error_upper_V'] = input_errors
    if 'bench_ref' in rows[0] and max(abs(r['bench_ref']) for r in rows)>budgets['input_absolute_V']:
        return {**result,'status':'input_mismatch','reason':'nonzero testbench ground alias'}
    if card['family']=='first_order':
        reference = FirstOrder(card)
        lower=upper=0.; witness=None
        for row in rows:
            expected=reference.value(row['time'])
            uncertainty=voltage_uncertainty(row['y'],card,budgets)+2*card['scale_V']/card['tau_s']*ut
            lo,hi=error_bounds(row['y'],expected,expected,uncertainty)
            lower=max(lower,lo)
            if hi>upper:
                upper=hi; witness={'time_s':row['time'],'actual_V':row['y'],'reference_V':expected}
        result.update(error_lower_V=lower,error_upper_V=upper,worst=witness,
                      status='pass' if upper<=budget else 'numerical_error' if lower>budget else 'evidence_insufficient')
        return result

    counts=[round(r['count']) for r in rows]
    if any(abs(r['count']-n)>budgets['count_V'] for r,n in zip(rows,counts)):
        return {**result,'status':'behavior_error','reason':'counter is not an integer-valued state'}
    if counts[0]!=0 or counts[-1]!=card['expected_events'] or any(b-a not in (0,1) for a,b in zip(counts,counts[1:])):
        return {**result,'status':'behavior_error','reason':'initial/final count, missing, repeated, or reversed event',
                'initial_count':counts[0],'final_count':counts[-1]}
    groups=[[] for _ in range(card['expected_events']+1)]
    transitions={}
    for i,(row,n) in enumerate(zip(rows,counts)):
        if n<0 or n>=len(groups):
            return {**result,'status':'behavior_error','reason':'counter outside expected range'}
        groups[n].append(row)
        if i and n!=counts[i-1]:
            transitions[n]=(rows[i-1]['time']-ut,row['time']+ut)
    initial_error=max(abs(r['y']-card['initial_V'])+voltage_uncertainty(r['y'],card,budgets) for r in groups[0])
    initial_lower=max(max(0.,abs(r['y']-card['initial_V'])-voltage_uncertainty(r['y'],card,budgets)) for r in groups[0])
    if initial_lower>budget:
        return {**result,'status':'behavior_error','reason':'incorrect initial state or update before first counted event',
                'initial_error_upper_V':initial_error}
    event_records=[]; maximum=initial_error; lower_max=0.; max_drift=0.; drift_lower_max=0.; unknown=initial_error>budget
    for k,nominal in enumerate(card['events_s'],1):
        if k not in transitions or not groups[k]:
            return {**result,'status':'behavior_error','reason':'missing observable event'}
        a,b=transitions[k]
        # One common callback interval constrains every output in this holding stage.
        early=card['event_early_s']; late=card['event_late_s']
        if card['clock']=='cross':
            late=min(late,card['cross_expression_tolerance_V']/card['clock_slope_V_s'])
        lo=max(a,nominal-early-ut); hi=min(b,nominal+late+ut)
        if lo>hi:
            return {**result,'status':'behavior_error','reason':'event outside allowed time interval',
                    'event_index':k,'observed_bracket_s':[a,b],'allowed_s':[nominal-early,nominal+late]}
        if b-a>card['event_bracket_max_s']+2*ut:
            unknown=True
        values=[pwl(card['inputs']['u'],t) for t in (lo,hi)]
        values.extend(v for t,v in card['inputs']['u'] if lo<t<hi)
        vlow,vhigh=min(values),max(values)
        stage_lower=stage_upper=0.
        for row in groups[k]:
            low,up=error_bounds(row['y'],vlow,vhigh,voltage_uncertainty(row['y'],card,budgets))
            stage_lower=max(stage_lower,low); stage_upper=max(stage_upper,up)
        drift=max(r['y'] for r in groups[k])-min(r['y'] for r in groups[k])
        drift_u=2*max(voltage_uncertainty(r['y'],card,budgets) for r in groups[k])
        drift_lower_max=max(drift_lower_max,max(0.,drift-drift_u))
        drift+=drift_u
        max_drift=max(max_drift,drift); maximum=max(maximum,stage_upper); lower_max=max(lower_max,stage_lower)
        event_records.append({'index':k,'nominal_s':nominal,'counter_bracket_s':[a,b],
                              'common_legal_interval_s':[lo,hi],'sample_reference_range_V':[vlow,vhigh],
                              'sample_error_lower_V':stage_lower,'sample_error_upper_V':stage_upper,
                              'hold_drift_upper_V':drift,'observations':len(groups[k])})
    if lower_max>budget or drift_lower_max>budget:
        status='numerical_error'
    elif unknown or maximum>budget or max_drift>budget:
        status='evidence_insufficient'
    else:
        status='pass'
    result.update(status=status,initial_error_upper_V=initial_error,error_lower_V=lower_max,
                  error_upper_V=maximum,hold_drift_upper_V=max_drift,event_records=event_records,
                  timing_claim='one narrow native counter bracket per event intersects its legal window; all holding observations satisfy the entire common interval',
                  nominal_time_shift_bound_V=slope_bound(card['inputs']['u'])*card['event_late_s'])
    return result
