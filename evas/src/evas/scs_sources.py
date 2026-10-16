"""Represent supported voltage sources as continuous PWL, without time sampling."""
from fractions import Fraction as Q
import math

POINT_BUDGET = 100_000


def _upper_float(exact, fail):
    try:
        value=float(exact)
    except OverflowError:
        fail('pulse source error bound is not finite')
    if not math.isfinite(value):
        fail('pulse source error bound is not finite')
    if Q(value)<exact:
        value=math.nextafter(value,math.inf)
    if not math.isfinite(value):
        fail('pulse source error bound is not finite')
    return value


def voltage_points(settings, stop, fail):
    kind = settings.get('type', 'dc')
    allowed = {'dc': {'type','dc'}, 'pwl': {'type','wave'},
               'pulse': {'type','val0','val1','delay','rise','fall','width','period','edgetype'}}
    if kind not in allowed:
        fail(f'unsupported vsource type {kind!r}', unsupported=True)
    unknown = set(settings)-allowed[kind]
    if unknown:
        fail(f'unsupported {kind} source settings: {sorted(unknown)}', unsupported=True)
    required = {'dc':{'dc'}, 'pwl':{'wave'},
                'pulse':{'val0','val1','rise','fall','width','period'}}[kind]
    if required-set(settings):
        fail(f'{kind} source requires explicit {sorted(required)}')
    for name,value in settings.items():
        if name not in ('type','edgetype','wave') and not isinstance(value,float):
            fail(f'{name} must be a scalar numeric source setting')
    if kind == 'dc':
        return [[0.,settings['dc']],[stop,settings['dc']]], 0., None
    if kind == 'pwl':
        wave = settings['wave']
        if not isinstance(wave,list) or len(wave)<2 or len(wave)%2:
            fail('wave must contain time/value pairs')
        points = [wave[i:i+2] for i in range(0,len(wave),2)]
        if points[0][0] != 0 or any(a[0]>=b[0] for a,b in zip(points,points[1:])):
            fail('PWL must start at zero with strictly increasing times; jumps are unsupported')
        if points[-1][0] < stop:
            points.append([stop,points[-1][1]])
        return points, 0., None

    if settings.get('edgetype','linear') != 'linear':
        fail('pulse only supports linear edges', unsupported=True)
    delay = Q(settings.get('delay', 0.))
    rise,fall,width,period = (Q(settings[n]) for n in ('rise','fall','width','period'))
    if delay<0 or rise<=0 or fall<=0 or width<0 or period<=0 or rise+width+fall>period:
        fail('pulse requires delay/width >= 0, rise/fall/period > 0 and rise+width+fall <= period')
    count = max(0, int((Q(stop)-delay)//period)+1)
    if 4*count+2 > POINT_BUDGET:
        fail('pulse point budget (100000) exceeded')
    low,high = settings['val0'],settings['val1']
    points, rounding, corners = [[0.,low]], Q(0), []
    for index in range(count):
        start = delay + index*period
        for exact,value in ((start,low),(start+rise,high),(start+rise+width,high),(start+rise+width+fall,low)):
            try:
                time = float(exact)
            except OverflowError:
                fail('pulse corner time is not finite')
            if not math.isfinite(time):
                fail('pulse corner time is not finite')
            delta=abs(Q(time)-exact)
            rounding = max(rounding,delta)
            corners.append(dict(exact_time_numerator=str(exact.numerator),
                                exact_time_denominator=str(exact.denominator),
                                rounded_time_seconds=time,
                                time_error_bound_seconds=_upper_float(delta,fail),value_V=value))
            if time == points[-1][0] and value == points[-1][1]:
                continue
            if time <= points[-1][0]:
                fail('pulse edges collapse at binary64 time resolution')
            points.append([time,value])
    if points[-1][0] < stop:
        points.append([stop,points[-1][1]])
    # Map each exact corner to its rounded corner and interpolate the time
    # displacement linearly. Its magnitude stays below the largest corner
    # displacement. The exact pulse is Lipschitz with this maximum slope,
    # so the nominal PWL differs everywhere by at most L * displacement.
    # Endpoint voltages are original binary64 inputs, with no value rounding.
    slope=abs(Q(high)-Q(low))/min(rise,fall)
    error=_upper_float(slope*rounding,fail)
    return points, _upper_float(rounding,fail), dict(corners=corners,
                voltage_error_bound_V=error,value_rounding_error_V=0.,
                maximum_slope_numerator=str(slope.numerator),maximum_slope_denominator=str(slope.denominator))
