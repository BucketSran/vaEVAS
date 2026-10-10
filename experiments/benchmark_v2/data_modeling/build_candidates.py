"""Build VA models from public table fit, plus semantic negative controls."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'benchmark/tasks/v2-data-sampling-identification';CANDS=Path(__file__).parent/'candidates'/TASK.name

def model(count,alternative=False):
    data=json.loads((Path(__file__).parent/f'rate-table-{count}.json').read_text());us=data['input_grid_V'];ys=data['state_grid_V'];rates=data['correction']
    fit=json.loads((Path(__file__).parent/'switch-fit.json').read_text());p=fit['parameters'];up,down=fit['tau_ns']
    text='`include "constants.vams"\n`include "disciplines.vams"\nmodule sampling_model(vin, clock, vhold);\ninput vin, clock; output vhold;\nelectrical vin, clock, vhold, invstate'+(', state;' if alternative else ';')+'\nreal vinit, gateinit, correction, rate, target, tau;\n'
    for name,kind in [('channel_n',0),('channel_p',1)]:
        k,vt,body,lam,theta=[p[j] for j in ([0,2,4,6,8] if kind==0 else [1,3,5,7,9])]
        text+=f'analog function real {name};\ninput u,y,g; real u,y,g;\nreal lo,hi,delta,over,drain;\nbegin\nlo=min(u,y); hi=max(u,y); delta=hi-lo;\n'
        if kind==0:text+=f'over=max(0.0,g-lo-{vt:.12g}-{body:.12g}*(sqrt(0.7+lo)-sqrt(0.7)));\n'
        else:text+=f'over=max(0.0,hi-g-{vt:.12g}-{body:.12g}*(sqrt(2.5-hi)-sqrt(0.7)));\n'
        text+=f'drain=min(delta,over);\nif(delta>1e-8) {name}={k:.12g}*(over-0.5*drain)*drain/delta*(1.0+{lam:.12g}*delta)/(1.0+{theta:.12g}*over);\nelse {name}={k:.12g}*over/(1.0+{theta:.12g}*over);\nend\nendfunction\n'
    for i,row in enumerate(rates):
        text+=f'analog function real adjust{i};\ninput z; real z;\nbegin\n'
        text+=f'if(z<={ys[0]:.12g}) adjust{i}={row[0]:.12g};\n'
        for j in range(len(ys)-1):text+=f'else if(z<={ys[j+1]:.12g}) adjust{i}={row[j]:.12g}+({row[j+1]-row[j]:.12g})*(z-{ys[j]:.12g})/{ys[j+1]-ys[j]:.12g};\n'
        text+=f'else adjust{i}={row[-1]:.12g};\nend\nendfunction\n'
    text+='analog begin\n@(initial_step) begin vinit=V(vin); gateinit=1.8-V(clock); end\n'
    state='V(state)' if alternative else 'V(vhold)'
    text+=f'if(V(vin)<={us[0]:.12g}) correction=adjust0({state});\n'
    for i in range(len(us)-1):text+=f'else if(V(vin)<={us[i+1]:.12g}) correction=adjust{i}({state})+(adjust{i+1}({state})-adjust{i}({state}))*(V(vin)-{us[i]:.12g})/{us[i+1]-us[i]:.12g};\n'
    text+=f'else correction=adjust{len(us)-1}({state});\n'
    text+=f'target=1.8-V(clock);\ntau=(target>V(invstate)) ? {up:.12g}e-9 : {down:.12g}e-9;\n'
    text+=f'rate=correction*(channel_n(V(vin),{state},V(invstate))+channel_p(V(vin),{state},V(clock)));\n'
    if alternative:text+='I(invstate) <+ 1e-12*ddt(V(invstate));\nI(invstate) <+ 1e-12*(V(invstate)-target)/tau;\nI(state) <+ 1e-12*ddt(V(state));\nI(state) <+ rate*(V(state)-V(vin))*1e-3;\nV(vhold) <+ V(state);\n'
    else:text+='V(invstate) <+ idt((target-V(invstate))/tau,gateinit);\nV(vhold) <+ idt(rate*(V(vin)-V(vhold))*1e9,vinit);\n'
    return text+'$bound_step(5p);\nend\nendmodule\n'
ref=model(29);(TASK/'solution/dut.va').write_text(ref)
variants={'alternative':model(15,True),'wrong_phase':ref.replace('V(clock)','(1.8-V(clock))'),'missing_acquisition':ref.replace('rate*(V(vin)-V(vhold))*1e9','rate*(V(vin)-V(vhold))*1e12'),'fixed_rc':ref.replace('rate*(V(vin)-V(vhold))*1e9','(V(clock)<0.9 ? 0.4e9 : 0.0)*(V(vin)-V(vhold))'),'reset_history':ref.replace('vinit);','0.0,V(clock)>0.9 ? 1 : 0);')}
variants['ideal_sampling']='''`include "disciplines.vams"
module sampling_model(vin,clock,vhold);
input vin,clock; output vhold; electrical vin,clock,vhold;
real held;
analog begin
@(initial_step) held=V(vin);
@(cross(V(clock)-0.9,+1)) held=V(vin);
V(vhold)<+transition(V(clock)<0.9 ? V(vin) : held,0,10p,10p);
$bound_step(10p);
end
endmodule
'''
# A memory-only candidate may replay a public trajectory, but cannot predict new sequences.
rows=list(csv.DictReader((TASK/'environment/public/data/selftest-0.csv').open()))
points=[(float(r['time_s']),float(r['vhold_V'])) for r in rows[::20]]
points.append((float(rows[-1]['time_s']),float(rows[-1]['vhold_V'])))
replay='`include "disciplines.vams"\nmodule sampling_model(vin,clock,vhold);\ninput vin,clock;output vhold;electrical vin,clock,vhold;\nreal replay;\nanalog begin\n'
replay+=f'if($abstime<={points[0][0]}) replay={points[0][1]};\n'
for (a,x),(b,y) in zip(points,points[1:]):
    if b<=a:continue
    replay+=f'else if($abstime<={b:.12g}) replay={x:.12g}+({y-x:.12g})*($abstime-{a:.12g})/{b-a:.12g};\n'
replay+=f'else replay={points[-1][1]:.12g};\nV(vhold)<+replay;\n$bound_step(10p);\nend\nendmodule\n'
variants['public_replay']=replay
requests=[{'variant':'reference','candidate_dir':str((TASK/'solution').relative_to(ROOT)),'expected_pass':True,'behavior':'split-channel law, 29-knot positive public correction and integrated inverter/held state'}]
for name,text in variants.items():
    path=CANDS/name;path.mkdir(parents=True,exist_ok=True);(path/'dut.va').write_text(text)
    requests.append({'variant':name,'candidate_dir':str(path.resolve().relative_to(ROOT)),'expected_pass':name=='alternative','behavior':{'alternative':'15-knot public correction with capacitor states and split nonlinear conductance; different approximation and state equations','wrong_phase':'track/hold phase inverted','missing_acquisition':'acquisition 1000x too fast','fixed_rc':'input/state-dependent rate replaced by fixed rate','reset_history':'held state zeroed every hold','ideal_sampling':'instantaneous track and edge sample','public_replay':'replays only public selftest-0 history regardless of new vin/clock'}[name]})
(Path(__file__).parent/'calibration-request.json').write_text(json.dumps({'task':str(TASK.relative_to(ROOT)),'variants':requests},indent=2)+'\n')
