"""Independent continuous-time and synchronous waveform contracts for #149.

No candidate parsing, reference replay, or DUT-reported pass flags. State models
use measured input interpolation and RK4, unlike the VA implicit integration.
"""
import cmath
import math


def response(f, fz, fp1, fp2, gain):
    return gain*(1+1j*f/fz)/((1+1j*f/fp1)*(1+1j*f/fp2))


def phasor(rows, signal, frequency):
    # Trapezoid quadrature on actual nonuniform simulator times.
    terms=[r[signal]*cmath.exp(-2j*math.pi*frequency*r['time']) for r in rows]
    area=sum((b['time']-a['time'])*(u+v)/2 for a,b,u,v in zip(rows,rows[1:],terms,terms[1:]))
    return 2*area/(rows[-1]['time']-rows[0]['time'])


def integrate(rows, initval, derivative, transform, reset=None):
    state=list(initval)
    out=[transform(state,rows[0])]
    for left,right in zip(rows,rows[1:]):
        dt=right['time']-left['time']
        def row_at(frac):
            return {k:left[k]+frac*(right[k]-left[k]) for k in left}
        # Eight substeps reduce stiff high-pole and edge interpolation errors.
        for sub in range(8):
            t=sub/8
            r0,rm,r1=row_at(t),row_at(t+1/16),row_at(t+1/8)
            h=dt/8
            if reset is not None and reset(rm):
                state=list(initval); continue
            a=derivative(state,r0)
            b=derivative([x+h*y/2 for x,y in zip(state,a)],rm)
            c=derivative([x+h*y/2 for x,y in zip(state,b)],rm)
            d=derivative([x+h*y for x,y in zip(state,c)],r1)
            state=[x+h*(a0+2*b0+2*c0+d0)/6 for x,a0,b0,c0,d0 in zip(state,a,b,c,d)]
        out.append(transform(state,right))
    return out


def compare(rows, signal, expected, tolerance, skip=None):
    errors=[abs(r[signal]-v) for r,v in zip(rows,expected) if skip is None or not skip(r)]
    if not errors: raise ValueError('empty observation window')
    return {'signal':signal,'max_error':max(errors),'rms_error':math.sqrt(sum(e*e for e in errors)/len(errors)),
            'tolerance':tolerance,'passed':max(errors)<=tolerance}


def evaluate(rows, case, work):
    p=case['parameters']; kind=case['kind']; checks=[]
    w=lambda f:2*math.pi*f
    if kind=='ctle':
        a,b,z=w(p['fp1']),w(p['fp2']),w(p['fz'])
        expected=integrate(rows,[p['x1init'],p['x2init']],
            lambda s,r:[a*(r['u']-s[0]),b*(s[0]-s[1])],
            lambda s,r:p['gain']*(s[1]+b/z*(s[0]-s[1])))
        checks.append(compare(rows,'y',expected,.006))
        window=[r for r in rows if r['time']>=case['stop']/2]
        for frequency in p['tones']:
            observed=phasor(window,'y',frequency)/phasor(window,'u',frequency)
            target=response(frequency,p['fz'],p['fp1'],p['fp2'],p['gain'])
            error=abs(observed-target)
            checks.append({'frequency':frequency,'complex_error':error,'tolerance':.03*max(1,abs(target)),
                           'passed':error<=.03*max(1,abs(target))})
    elif kind=='programmable':
        expected=integrate(rows,[p['initval']],lambda s,r:[w(p['base']*2**int(min(3,max(0,math.floor(r['code']+.5)))))*(r['u']-s[0])],
                           lambda s,r:s[0],lambda r:r['reset']>.5)
        checks.append(compare(rows,'y',expected,.008,lambda r: abs(r['reset']-.5)<.49))
    elif kind=='iq':
        up=[p['gain']*(r['i']*r['lc']-r['q']*r['ls']) if r['en']>.5 else 0 for r in rows]
        checks.append(compare(rows,'up',up,.002))
        expected=integrate(rows,[0,0],lambda s,r:[w(p['fbw'])*(2*r['rf']*r['lc']-s[0]),w(p['fbw'])*(-2*r['rf']*r['ls']-s[1])],lambda s,r:tuple(s))
        for n,node in enumerate(('di','dq')):
            checks.append(compare(rows,node,[s[n] if r['en']>.5 else 0 for s,r in zip(expected,rows)],.008))
        # The actual mixed output must contain the prescribed sum sideband.
        window=[r for r in rows if r['time']>.003 and r['time']<.007]
        carrier=p['flo']+p['fbb']
        amp=abs(phasor(window,'up',carrier))
        checks.append({'sum_sideband_amplitude':amp,'passed':abs(amp-p['gain']*.18)<.015})
    elif kind=='envelope':
        expected=integrate(rows,[p['initval']],lambda s,r:[w(p['bandwidth'])*((r['i']**2+r['q']**2 if r['en']>.5 else 0)-s[0])],lambda s,r:math.sqrt(max(s[0],0)),lambda r:r['reset']>.5)
        checks.append(compare(rows,'env',expected,.01,lambda r:abs(r['reset']-.5)<.49))
    elif kind=='sweep':
        previous={'gain':0.,'phase':0.,'valid':0.}
        for idx,freq in enumerate(p['frequencies']):
            start=idx*p['slot']; finish=start+p['slot']
            settled=start+p['settle']; end=settled+p['window']
            window=[r for r in rows if settled<=r['time']<=end]
            measured_in=phasor(window,'drive',freq)
            measured_out=phasor(window,'sense',freq)
            qualifying=abs(measured_in)>=.01 and p['window']*freq>=6 and p['settle']>=.003
            reports=[r for r in rows if end+2*case['step']<=r['time']<=finish-case['step']]
            if not reports: raise ValueError('missing held sweep report')
            early=[r for r in rows if start+2*case['step']<=r['time']<=end-2*case['step']]
            checks.append({'tone':idx,'report_held_until_window_end':True,'passed':all(abs(r[node]-previous[node])<.001 for r in early for node in previous)})
            previous={node:reports[-1][node] for node in previous}
            if qualifying:
                ratio=measured_out/measured_in
                phase=cmath.phase(ratio)
                checks.append({'tone':idx,'passed':all(abs(r['gain']-abs(ratio))<.035 and abs(math.atan2(math.sin(r['phase']-phase),math.cos(r['phase']-phase)))<.035 and r['valid']>.9 for r in reports),'measured_gain':abs(ratio),'measured_phase':phase})
            else:
                checks.append({'tone':idx,'passed':all(abs(r['valid'])<.1 for r in reports),'invalid_reason':'low-amplitude or inadequate settling/window'})
            # Observe excitation independently, including coverage and waveform.
            active=[r for r in rows if start+2*case['step']<r['time']<finish-2*case['step']]
            errors=[abs(r['drive']-p['amplitudes'][idx]*math.sin(2*math.pi*freq*(r['time']-start))) for r in active]
            checks.append({'tone':idx,'excitation_max_error':max(errors),'passed':max(errors)<.002})
    else: raise ValueError('unknown filter contract')
    return {'passed':all(c['passed'] for c in checks),'checks':checks}
