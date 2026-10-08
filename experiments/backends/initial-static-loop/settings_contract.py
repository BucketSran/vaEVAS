"""Fixed probe controls, checked after the shared log/PSF consistency reader."""
import math

REQUESTED={'reltol':1e-5,'vabstol_V':1e-7,'iabstol_A':1e-12,
           'stop_s':1.,'maxstep_s':.025,'method':'traponly','errpreset':'conservative'}
# This observed conservative profile belongs to this frozen Spectre probe.
# It is not a claim that all releases/presets map reltol this way.
EFFECTIVE={'reltol':1e-6,'vabstol_V':1e-7,'iabstol_A':1e-12,
           'stop_s':1.,'maxstep_s':.025,'method':'traponly'}


def qualify_settings(readback, requested=REQUESTED):
    if requested!=REQUESTED:
        raise ValueError('requested settings differ from frozen Spectre controls')
    checks=[]
    for scope, expected in (
        ('global_user',{key:requested[key] for key in ('reltol','vabstol_V','iabstol_A')}),
        ('effective',EFFECTIVE),('psf_effective',EFFECTIVE),
        ('psf_relative_metadata',{'tolerance.relative':requested['reltol']}),
    ):
        for key,wanted in expected.items():
            try: actual=readback[scope][key]['value']
            except (KeyError,TypeError) as error:
                raise ValueError('missing frozen setting '+scope+'.'+key) from error
            if isinstance(wanted,str): matches=actual==wanted
            else:
                matches=isinstance(actual,(int,float)) and not isinstance(actual,bool) and math.isfinite(actual) and math.isclose(actual,wanted,rel_tol=1e-12,abs_tol=0)
            if not matches:
                raise ValueError('frozen setting mismatch: '+scope+'.'+key)
            checks.append(dict(scope=scope,key=key,requested_or_effective=wanted,readback=actual,status='P'))
    return dict(status='P',requested=dict(REQUESTED),declared_effective=dict(EFFECTIVE),checks=checks,
                preset_mapping='This frozen conservative probe: requested global reltol=1e-5, observed/declared transient reltol=1e-6; not a universal preset mapping.')
