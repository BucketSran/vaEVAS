"""Saving-policy and analytic-voltage checks; no interpolation or nearest rows."""
import math


def check(rows, *, policy, forced, stop=1., window=None, ordinary_times=None, voltage_budget=1e-10):
    times=[row['time'] for row in rows]
    if not times or any(not math.isfinite(t) or t<0 or t>stop for t in times):
        raise ValueError('invalid saved time')
    if any(a>=b for a,b in zip(times,times[1:])):
        raise ValueError('saved times must strictly increase')
    if not set(forced+[stop])<=set(times):
        raise ValueError('missing exact forced or terminal time')
    if forced and policy=='strobeonly':
        allowed=set(forced+[stop])
        if window is None:
            if set(times)!=allowed:
                raise ValueError('non-strobe row inside the saving window')
        else:
            start,end=window
            if any(start<=t<=end and t not in allowed for t in times):
                raise ValueError('non-strobe row inside the saving window')
            if ordinary_times is not None:
                outside={t for t in [*ordinary_times,*forced,stop] if t<start or t>end}
                if outside!={t for t in times if t<start or t>end}:
                    raise ValueError('ordinary rows outside the window differ')
    elif ordinary_times is not None and set(times)!=set(ordinary_times).union(forced,[stop]):
        raise ValueError('ordinary and forced row union differs')
    for row in rows:
        t=row['time']
        u=8*(t-.25) if .25<t<=.375 else 1-16*(t-.375) if .375<t<.4375 else 0.
        for name,answer in [('u',u),('y',3*u)]:
            value=row.get(name)
            if not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value-answer)>voltage_budget:
                raise ValueError('analytic voltage mismatch at '+name)
    return dict(rows=len(rows),forced_times=forced,terminal_retained=True)
