"""Build VA models from public table fit, plus semantic negative controls."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'benchmark/tasks/v2-data-sampling-identification';CANDS=Path(__file__).parent/'candidates'/TASK.name

def model(count,alternative=False):
    data=json.loads((Path(__file__).parent/f'rate-table-{count}.json').read_text());us=data['input_grid_V'];ys=data['state_grid_V'];rates=data['rate_per_ns']
    text='`include "constants.vams"\n`include "disciplines.vams"\nmodule sampling_model(vin, clock, vhold);\ninput vin, clock; output vhold;\nelectrical vin, clock, vhold'+(', state;' if alternative else ';')+'\nreal vinit, rate, gate;\n'
    for i,row in enumerate(rates):
        text+=f'analog function real rate{i};\ninput z; real z;\nbegin\n'
        text+=f'if(z<={ys[0]:.12g}) rate{i}={row[0]:.12g};\n'
        for j in range(len(ys)-1):
            text+=f'else if(z<={ys[j+1]:.12g}) rate{i}={row[j]:.12g}+({row[j+1]-row[j]:.12g})*(z-{ys[j]:.12g})/{ys[j+1]-ys[j]:.12g};\n'
        text+=f'else rate{i}={row[-1]:.12g};\nend\nendfunction\n'
    text+='analog begin\n@(initial_step) vinit=V(vin);\n'
    state='V(state)' if alternative else 'V(vhold)'
    text+=f'if(V(vin)<={us[0]}) rate=rate0({state});\n'
    for i in range(len(us)-1):text+=f'else if(V(vin)<={us[i+1]}) rate=rate{i}({state})+(rate{i+1}({state})-rate{i}({state}))*(V(vin)-{us[i]})/{us[i+1]-us[i]:.12g};\n'
    text+=f'else rate=rate{len(us)-1}({state});\n'
    text+='gate=transition(V(clock)<0.9 ? 1.0 : 0.0,65p,35p,35p);\n'
    if alternative:text+='I(state) <+ 1e-12*ddt(V(state));\nI(state) <+ gate*(V(state)-V(vin))*rate*1e-3;\nV(vhold) <+ V(state);\n'
    else:text+='V(vhold) <+ idt(gate*(V(vin)-V(vhold))*rate*1e9,vinit);\n'
    return text+'$bound_step(10p);\nend\nendmodule\n'
ref=model(29);(TASK/'solution/dut.va').write_text(ref)
variants={'alternative':model(15,True),'wrong_phase':ref.replace('V(clock)<0.9','V(clock)>0.9'),'missing_acquisition':ref.replace('*rate*1e9','*rate*1e12'),'fixed_rc':ref.replace('gate*(V(vin)-V(vhold))*rate*1e9','gate*(V(vin)-V(vhold))*0.4e9'),'reset_history':ref.replace('vinit);','0.0,V(clock)>0.9 ? 1 : 0);')}
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
requests=[{'variant':'reference','candidate_dir':str((TASK/'solution').relative_to(ROOT)),'expected_pass':True,'behavior':'29-knot positive rate table with integrated retained state'}]
for name,text in variants.items():
    path=CANDS/name;path.mkdir(parents=True,exist_ok=True);(path/'dut.va').write_text(text)
    requests.append({'variant':name,'candidate_dir':str(path.resolve().relative_to(ROOT)),'expected_pass':name=='alternative','behavior':{'alternative':'15-knot model as capacitor + nonlinear conductance; different approximation and state equations','wrong_phase':'track/hold phase inverted','missing_acquisition':'acquisition 1000x too fast','fixed_rc':'input/state-dependent rate replaced by fixed rate','reset_history':'held state zeroed every hold','ideal_sampling':'instantaneous track and edge sample','public_replay':'replays only public selftest-0 history regardless of new vin/clock'}[name]})
(Path(__file__).parent/'calibration-request.json').write_text(json.dumps({'task':str(TASK.relative_to(ROOT)),'variants':requests},indent=2)+'\n')
