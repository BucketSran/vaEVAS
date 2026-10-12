"""Finite primitive contracts with independent rational/Decimal references.

This is a new test identity. Historical breadth cards and scores are untouched.
Trigonometric series use exact rational terms with a bounded remaining tail.
Decimal exp/ln/sqrt use correctly rounded operations and outward neighbours.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import math
from functools import lru_cache

from precision_reference import outward, pwl_exact

T = 1e-6
TIERS = {'Q1': 10.1e-6, 'Q2': 1.01e-6, 'Q3': 101e-9}
TRIG_TERMS = 40


@lru_cache(maxsize=4096)
def bounds(function, x, exponent=3):
    x = Fraction(x)
    if function in ('sin', 'cos'):
        if abs(x) > 13:
            raise ValueError('trigonometric reference range exceeded')
        term = x if function == 'sin' else Fraction(1)
        total = term
        offset = 1 if function == 'sin' else 0
        for k in range(1, TRIG_TERMS):
            term *= -x*x / ((2*k + offset - 1)*(2*k + offset))
            total += term
        # Terms are decreasing in magnitude here. Bound the alternating tail
        # by the first omitted term, conservatively on both sides.
        n=2*TRIG_TERMS+offset
        ratio = x*x / ((n-1)*n)
        if ratio >= 1: raise ValueError('alternating tail is not decreasing')
        tail = abs(term*ratio)
        return outward(total-tail, False), outward(total+tail, True)
    if function == 'pow' and exponent == 3:
        value = x**3
        return outward(value, False), outward(value, True)
    with localcontext() as ctx:
        ctx.prec = 80
        value = Decimal(x.numerator)/Decimal(x.denominator)
        # Division has a decimal rounding interval, so propagate its endpoints.
        lo, hi = value.next_minus(), value.next_plus()
        if x == 0:
            lo = hi = Decimal(0)
        operation = {'exp': Decimal.exp, 'ln': Decimal.ln, 'sqrt': Decimal.sqrt}
        if function == 'pow' and exponent == .5:
            function = 'sqrt'
        if function not in operation:
            raise ValueError('unknown reference function')
        if function == 'ln' and lo <= 0 or function == 'sqrt' and lo < 0:
            raise ValueError('outside mathematical domain')
        a, b = operation[function](lo), operation[function](hi)
        return outward(Fraction(a.next_minus()), False), outward(Fraction(b.next_plus()), True)


def cards():
    functions = [
        ('sin', [-4*math.pi, -math.pi/2, 0., math.pi/2, 4*math.pi]),
        ('cos', [-4*math.pi, -math.pi, 0., math.pi, 4*math.pi]),
        ('exp', [-4., -1., 0., 1., 4.]),
        ('ln', [1e-6, .25, 1., 2., 8.]),
        ('sqrt', [0., 1e-12, 1e-6, .25, 4.]),
        ('pow', [-2., -1., 0., 1., 2.]),
        ('pow-half', [0., 1e-12, 1e-6, .25, 4.]),
    ]
    result = []
    for function, values in functions:
        real_function = 'pow' if function == 'pow-half' else function
        exponent = .5 if function == 'pow-half' else 3
        expression = (f'pow(V(u), {exponent})' if real_function == 'pow'
                      else f'{real_function}(V(u))')
        result.append({'id': 'P-'+function, 'function': real_function,
                       'exponent': exponent, 'expression': expression,
                       'inputs': {'u': [[i*T, v] for i, v in enumerate(values)]},
                       'scope': 'finite sampled instants, including input corners and observed interior values'})
    result += [
        {'id': 'P-idt', 'function': 'idt', 'expression': 'idt(V(u)/1e-6, 0.125)',
         'inputs': {'u': [[0., 0.], [T, 1.], [2*T, -1.], [3*T, 0.]]},
         'scope': 'nonzero initial state and signed PWL integral'},
        {'id': 'P-ddt', 'function': 'ddt', 'expression': 'ddt(($abstime/1e-6)*($abstime/1e-6))*1e-6',
         'inputs': {'u': [[0., 0.], [T, 0.], [2*T, 0.], [3*T, 0.]]},
         'scope': 'smooth quadratic time expression; DC derivative and transient derivative'},
        {'id': 'P-ddt-input', 'function': 'ddt', 'expression': 'ddt(V(u)*V(u))*1e-6',
         'inputs': {'u': [[0., 0.], [4*T, 4.]]},
         'stop_s':3*T,
         'scope': 'smooth quadratic of a voltage ramp; terminal ramp continues beyond stop'},
    ]
    for card in result:
        card.update(top='va_primitive', ports=['u', 'y'], parameters={}, unit_s=T, scale_V=1.)
        card.setdefault('stop_s',card['inputs']['u'][-1][0])
        card['source'] = ('`include "disciplines.vams"\nmodule va_primitive(u,y);\n'
                          'input u; output y; electrical u,y;\n'
                          'analog begin V(y) <+ '+card['expression']+'; end\nendmodule\n')
    return result


def reference(card, t):
    if card['function'] == 'ddt':
        value = 2*Fraction(t)/Fraction(T)
        return outward(value, False), outward(value, True)
    if card['function'] == 'idt':
        end = Fraction(t)
        area = Fraction(.125)
        for (a, u), (b, v) in zip(card['inputs']['u'], card['inputs']['u'][1:]):
            a, b, u, v = map(Fraction, (a, b, u, v))
            h = max(Fraction(0), min(end, b)-a)
            area += (u*h + (v-u)*h*h/(2*(b-a)))/Fraction(T)
        return outward(area, False), outward(area, True)
    return bounds(card['function'], pwl_exact(card['inputs']['u'], t), card['exponent'])


def observed_input_reference(card, value):
    """Propagate serialization at the actual input scale through static maps.

    Also check the intended PWL answer. This independent second check prevents
    a small input error from hiding a larger operator error near sqrt/ln zero.
    """
    uncertainty=Fraction(16*math.ulp(value))
    a,b=Fraction(value)-uncertainty,Fraction(value)+uncertainty
    function=card['function']
    if function in ('sin','cos'):
        lo,hi=bounds(function,Fraction(value))
        # Both derivatives have absolute value at most one.
        return outward(Fraction(lo)-uncertainty,False),outward(Fraction(hi)+uncertainty,True)
    if function=='sqrt' or function=='pow' and card['exponent']==.5:
        if value < 0: raise ValueError('negative observed sqrt input')
        a=max(Fraction(0),a)
    lo,_=bounds(function,a,card['exponent'])
    _,hi=bounds(function,b,card['exponent'])
    return lo,hi


def assess(card, rows, tier):
    budget = TIERS[tier]
    issues = []
    errors = []
    lower_errors = []
    if not rows or any(any(isinstance(r.get(k), bool) or not isinstance(r.get(k), (int,float))
                           or not math.isfinite(r[k]) for k in ('time','u','y')) for r in rows):
        return {'status': 'evidence_insufficient', 'issues': ['missing or nonfinite observations'], 'budget_V': budget}
    times = [r['time'] for r in rows]
    if any(t<0 or t>card['stop_s'] for t in times):
        return {'status':'evidence_insufficient','issues':['observation outside frozen time range'],'budget_V':budget}
    if any(a >= b for a,b in zip(times,times[1:])):
        issues.append('nonmonotone or duplicate time')
    # Rows retain native exported times; this checker never interpolates or
    # snaps them to requested times. Missing corners are an evidence gap.
    # This protocol demands finite observation coverage, including every input
    # corner and both start/stop. It does not prove a whole trajectory bound.
    mandatory_times={0.,card['stop_s']} | {t for t,_ in card['inputs']['u'] if 0<=t<=card['stop_s']}
    for t in sorted(mandatory_times):
        if not any(abs(s-t) <= 8*math.ulp(max(abs(t), 1e-30)) for s in times):
            issues.append('missing mandatory corner: '+repr(t))
    if max((b-a for a,b in zip(times,times[1:])), default=math.inf) > T/8*(1+1e-12):
        issues.append('observation gap exceeds finite protocol')
    input_error = 0.
    # For idt, an allowed input uncertainty accumulates as area. Keep it in
    # the output upper bound so a near-budget result cannot hide cancellation.
    integral_input_allowance = max(32*math.ulp(max(1.,abs(r['u']))) for r in rows)
    for row in rows:
        expected_u = pwl_exact(card['inputs']['u'], row['time'])
        input_error = max(input_error, float(abs(Fraction(row['u'])-expected_u)))
        # Seventeen-digit exports identify binary64 representatives. Each input
        # must preserve the intended PWL value to this separate small allowance.
        if abs(Fraction(row['u'])-expected_u) > Fraction(32*math.ulp(max(1., abs(row['u'])))):
            issues.append('input differs from frozen PWL')
        references=[reference(card, row['time'])]
        if card['function']=='idt':
            lo,hi=references[0]
            area_allowance=integral_input_allowance*max(0.,row['time'])/T
            references.append((lo-area_allowance,hi+area_allowance))
        if card['function'] not in ('idt','ddt'):
            try: references.append(observed_input_reference(card,row['u']))
            except ValueError:
                return {'status':'numerical_error','issues':['observed input outside function domain'], 'budget_V':budget}
        serialization = 16*math.ulp(max(1., abs(row['y'])))
        for lo,hi in references:
            errors.append(max(abs(row['y']-lo),abs(row['y']-hi))+serialization)
            lower_errors.append(max(0.,row['y']-serialization-hi,lo-row['y']-serialization))
    error = max(errors)
    lower_error=max(lower_errors)
    return {'status': 'numerical_error' if lower_error > budget else
            'evidence_insufficient' if issues or error > budget else 'pass',
            'error_lower_V':lower_error,'error_upper_V': error, 'input_error_max_V': input_error, 'budget_V': budget,
            'rows': len(rows), 'issues': sorted(set(issues)),
            'scope': 'fixed finite observations; settings and sample origin are separate evidence axes'}
