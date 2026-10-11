"""Rebuild POR source properties from raw Spectre PSF and original ngspice data.

This verifies the original ramp/recovery experiment; it does not grade the full
closed-loop candidate. Cross-backend numeric differences are reported without
inventing an alignment tolerance after execution.
"""
from pathlib import Path
import argparse,json,sys,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'benchmark/checkers'))
from adc_linearity import read_psf
from v2_testing import Wave

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def original_rows(path):
    lines=path.read_text().splitlines()
    names=[name[2:-1] if name.startswith('v(') else name for name in lines[0].split()]
    return [dict(zip(names,map(float,line.split()))) for line in lines[1:] if line.strip()]
def qualify(rows):
    w=Wave(rows)
    assert abs(w.ts[0])<1e-15 and abs(w.ts[-1]-.004)<1e-12
    er=w.edges('por',threshold=.9);ef=w.edges('por',-1,threshold=.9)
    cr=w.edges('osc_ck',threshold=.9);pr=w.edges('pwup_filt',threshold=.9);pf=w.edges('pwup_filt',-1,threshold=.9)
    assert len(er)==len(ef)==len(pr)==2 and len(pf)==1 and len(cr)==26
    metrics=[]
    for i,(start,end) in enumerate([(0.,pf[0]),(pf[0],.004)]):
        clocks=[t for t in cr if start<t<end];rise,fall=er[i],ef[i]
        assert len(clocks)==13 and start<pr[i]<clocks[0]<rise<fall<end
        rise_count=sum(t<=rise for t in clocks);fall_count=sum(t<=fall for t in clocks)
        assert rise_count==6 and fall_count==13
        metrics.append(dict(response_us=(rise-clocks[0])*1e6,period_us=(clocks[8]-clocks[2])*1e6/6,width_us=(fall-rise)*1e6,rise_count=rise_count,fall_count=fall_count,first_clock=clocks[0],power_detected=pr[i],por_rise=rise,por_fall=fall))
    def avdd(t):
        if t<.002:return 3.3*t/.002
        if t<.003:return 3.3
        if t<.0030001:return 3.3-1.3*(t-.003)/.0000001
        if t<.0032:return 2.
        if t<.0032001:return 2.+1.3*(t-.0032)/.0000001
        return 3.3
    supply_error=max(abs(r['avdd']-avdd(r['time'])) for r in rows)
    assert supply_error<1e-6
    bounds={n:dict(minimum=min(r[n] for r in rows),maximum=max(r[n] for r in rows)) for n in ['avdd','por','osc_ck','pwup_filt']}
    return dict(rows=len(rows),source_properties_passed=True,metrics=metrics,power_lost=pf[0],supply_pwl_max_error_v=supply_error,voltage_bounds=bounds),w

def compare(spectre,ngspice):
    a,wa=qualify(read_psf(spectre));b,wb=qualify(original_rows(ngspice))
    differences=[{k:a['metrics'][i][k]-b['metrics'][i][k] for k in ['response_us','period_us','width_us']} for i in range(2)]
    edge_differences={n+('_rise' if direction==1 else '_fall'):max(abs(x-y) for x,y in zip(wa.edges(n,direction,threshold=.9),wb.edges(n,direction,threshold=.9)))*1e6 for n in ['por','osc_ck','pwup_filt'] for direction in [1,-1]}
    supply_cross_error=max(abs(wa.value(t,'avdd')-wb.value(t,'avdd')) for t in set(wa.ts+wb.ts))
    return dict(status='actual mixed source qualified; formal closed-loop benchmark not yet run',scope='original 4ms ramp, fast undervoltage and recovery with original analog/CDL cells and faithful VA digital boundary',spectre=a,ngspice=b,spectre_minus_ngspice_metrics=differences,max_matched_edge_difference_us=edge_differences,supply_waveform_max_difference_v=supply_cross_error,limitations='Numeric backend differences are descriptive, not a new calibrated tolerance. Internal analog bias/current waveforms are not saved. Discovery is intentionally unscored.',waveforms_sha256=dict(spectre=sha(spectre),ngspice=sha(ngspice)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spectre',type=Path,required=True);p.add_argument('--ngspice',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(compare(a.spectre,a.ngspice),indent=2)+'\n')
