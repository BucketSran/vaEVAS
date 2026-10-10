"""Prepare semantically described VA variants; only live calibration may certify them."""
from pathlib import Path
import json,re,shutil
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'benchmark/tasks';OUT=ROOT/'experiments/benchmark_v2/spec_modeling';requests=[]
changes={
'071':('held = held + alpha * (V(vin) - held);','held = (1.0-alpha)*held + alpha*V(vin);','convex combination acquisition state'),
'038':('raw = vcm + gain_value * (V(vin) - vcm);','raw = gain_value*V(vin)+(1.0-gain_value)*vcm;','affine gain form'),
'082':('gainv = gainv - 0.18;','gainv = gainv + (-0.18);','signed gain correction'),
'091':('baseband_q=baseband_q+lp_alpha*(V(demod_sample)-baseband_q);','baseband_q=(1-lp_alpha)*baseband_q+lp_alpha*V(demod_sample);','weighted low-pass recurrence'),
'307':('state_v + 1.0 * k_int * (V(sample_node) - vcm)','vcm + ((state_v-vcm) + k_int*(V(sample_node)-vcm))','integrator deviation state form'),
'308':('vcm + cds_gain * (V(vin) - reset_sample)','cds_gain*V(vin) + (vcm-cds_gain*reset_sample)','CDS affine difference'),
'370':('vout_v + alpha * (target - vout_v)','(1.0-alpha)*vout_v + alpha*target','weighted settling recurrence'),
'353':('vcm + main_amp * sym0 + tap_step * pre_code * sym1 - tap_step * post_code * sym2','main_value + pre_value + post_value - 2.0*vcm','sum independently computed cursor voltages'),
'055':('acc = acc + V(vin) / vref - bit_state;','acc = (acc - bit_state) + V(vin)/vref;','feedback-first accumulation'),
'002':('vdac_p_level = vcm + swing * (((code + 32 * cal) / 1023.0) - 0.5) * 0.5;','vdac_p_level = vcm + swing*(code+32*cal-511.5)/2046.0;','centered integer DAC arithmetic'),
'003':('vres_level = vcm + 2.0 * vin_rel;','vres_level = 2.0*vin_s - vcm;','direct sampled-voltage middle residue'),
'047':('state=(V(vin,VSS)>vlow && V(vin,VSS)<vhigh);','state=!(V(vin,VSS)<=vlow || V(vin,VSS)>=vhigh);','complement of two out-of-window predicates'),
'314':('state?vdd:vss','vss+(vdd-vss)*state','affine rail coding'),
'001':('u=(a!=b && b==c);d=(a==b && b!=c);','u=(a^b)&(!(b^c));d=(!(a^b))&(b^c);','XOR Alexander decision network'),
'396':('lo_i_state = 1;\n                    lo_q_state = 0;','lo_i_state = (phase_state < 2);\n                    lo_q_state = (phase_state == 1 || phase_state == 2);','phase-index boolean encoding'),
'186':('m[pointer]=1-dcmp;','m[pointer]=!dcmp;','logical complement of comparator bit'),
}
mutations={
'024':('cross(V(CLK, VSS) - vth, +1)','cross(V(CLK, VSS) - vth, -1)','samples falling edge'),
'071':('held + alpha * (V(vin) - held)','V(vin)','instantaneous acquisition'),
'186':('p[pointer]=dcmp','p[pointer]=1-dcmp','inverts comparator decision'),
'047':('V(vin,VSS)<vhigh','V(vin,VSS)<vhigh+0.1','wrong upper boundary'),
'314':('V(high_trip)+hyst','V(high_trip)-hyst','exits without outer hysteresis'),
'002':('32 * cal','16 * cal','half calibration weight'),
'003':('2.0 * vin_rel','1.0 * vin_rel','unity residue gain'),
'055':(' - bit_state',' + bit_state','positive feedback'),
'001':('u=(a!=b && b==c)','u=(a==b && b!=c)','swaps Alexander up direction'),
'375':('wait_ticks = dead_ticks;','wait_ticks = 0;','removes deadtime'),
'396':('phase_state = (phase_state + 1) % 4;','phase_state = (phase_state + 2) % 4;','skips quadrature states'),
'038':('gain_value = gain_high','gain_value = gain_low','ignores high gain'),
'082':('gainv = gainv - 0.18','gainv = gainv + 0.18','overload increases gain'),
'091':('sample_q=polarity*amplified','sample_q=amplified','omits demodulation'),
'308':('V(vin) - reset_sample','reset_sample - V(vin)','reverses correlated difference'),
'370':('alpha * (target - vout_v)','alpha * (vout_v - target)','diverges from target'),
'307':('state_v + 1.0 * k_int','state_v - 1.0 * k_int','integrates reversed sign'),
'183':('V(d) < 0.5 * vdd','V(d) > 0.5 * vdd','inverts keep decision'),
'353':('post_code * sym2','post_code * sym1','uses wrong history tap'),
}
for t in sorted(BASE.glob('v2-spec-*')):
 sid=t.name.split('-')[2];dest=OUT/'candidates'/t.name;files=list((t/'solution').glob('*.va'))
 for variant in ['alternative','semantic-mutant']:
  d=dest/variant;d.mkdir(parents=True,exist_ok=True)
  for f in files:shutil.copy2(f,d/f.name)
  applied=0
  if variant=='alternative' and sid=='024':
   (d/'dut.va').write_text('''`include "disciplines.vams"
module sample_hold(VDD,VSS,IN,CLK,OUT);
inout VDD,VSS;input IN,CLK;output OUT;electrical VDD,VSS,IN,CLK,OUT;
parameter real vth=.45,tedge=100p;
real old_value,next_value,sample_time,ratio;
analog begin
 @(initial_step)begin old_value=0;next_value=0;sample_time=-tedge;end
 @(cross(V(CLK,VSS)-vth,+1))begin old_value=next_value;next_value=V(IN,VSS);sample_time=$abstime;end
 ratio=($abstime-sample_time)/tedge;if(ratio<0)ratio=0;if(ratio>1)ratio=1;
 $bound_step(tedge/16);
 V(OUT,VSS)<+old_value+(next_value-old_value)*ratio;
end
endmodule
''');applied=1;description='explicit elapsed-time linear interpolation, rather than transition operator'
  elif variant=='alternative' and sid=='375':
   p=d/'dut.va';s=p.read_text().replace('wait_ticks = dead_ticks;','wait_ticks = $rtoi(ceil($abstime/tick)) + dead_ticks - 1;');s=s.replace('if (wait_ticks > 0)\n                    wait_ticks = wait_ticks - 1;\n                if (wait_ticks <= 0)', 'if ($abstime >= wait_ticks*tick)');p.write_text(s);applied=1;description='absolute global tick deadline instead of countdown'
  elif variant=='alternative' and sid=='183':
   p=d/'dut.va';p.write_text('''`include "disciplines.vams"
module foreground_rdac_calibrator(ck,d,vrefp,vrefn,dc0,dc1,dc2,dc3,dc4,dc5,dc6,cvinp,cvinn,en,enb);
input ck,d,vrefp,vrefn;output dc0,dc1,dc2,dc3,dc4,dc5,dc6,cvinp,cvinn,en,enb;
electrical ck,d,vrefp,vrefn,dc0,dc1,dc2,dc3,dc4,dc5,dc6,cvinp,cvinn,en,enb;
parameter real vdd=1.;integer word,k,active;
analog begin
 @(initial_step)begin word=64;k=6;active=1;end
 @(cross(V(ck)-vdd/2,+1))begin if(active)begin
 if(V(d)>=vdd/2)word=word & ~(1<<k);
 k=k-1;if(k>=0)word=word | (1<<k);else active=0;
 end end
 V(cvinp)<+V(vrefp);V(cvinn)<+V(vrefn);
 V(dc0)<+transition((word&1)?vdd:0,0,20p,20p);V(dc1)<+transition((word&2)?vdd:0,0,20p,20p);V(dc2)<+transition((word&4)?vdd:0,0,20p,20p);V(dc3)<+transition((word&8)?vdd:0,0,20p,20p);V(dc4)<+transition((word&16)?vdd:0,0,20p,20p);V(dc5)<+transition((word&32)?vdd:0,0,20p,20p);V(dc6)<+transition((word&64)?vdd:0,0,20p,20p);
 V(en)<+transition(active?vdd:0,0,20p,20p);V(enb)<+transition(active?0:vdd,0,20p,20p);
end
endmodule
''');applied=1;description='packed word and bitmask search instead of seven unrolled code variables'
  else:
   old,new,description=(changes if variant=='alternative' else mutations)[sid]
   for f in d.glob('*.va'):
    s=f.read_text()
    if old in s:f.write_text(s.replace(old,new));applied+=1
  if not applied:raise ValueError(f'{sid} {variant}: no semantic transformation')
  requests.append({'task':str(t),'variant':variant,'candidate_directory':str(d),'expected':'pass' if variant=='alternative' else 'fail','semantic_behavior':description,'certification':'pending-live-execution'})
plan=json.loads((OUT/'run-plan.json').read_text());plan=[x for x in plan if x['variant']=='reference']+requests;(OUT/'run-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
# Representative failure mechanisms are separate candidates, not syntax errors.
extra={'024':{
 'tracking':('V(OUT, VSS) <+ transition(held, 0, tedge, tedge);','V(OUT, VSS) <+ V(IN,VSS);','continuously tracks input'),
 'wrong-initial':('held = 0.0;','held = 0.45;','wrong initial held value'),
 },'375':{
 'overlap':('active_phase == 1','active_phase != 0','both phases high during phase2'),
 'cancel-missed':('@(cross(V(rst)-vth,+1) or cross(V(enable)-vth,-1)) begin\n active_phase=0;pending_phase=0;wait_ticks=0;valid_state=0;\n end','', 'short disable pulse fails to cancel pending phase'),
 'restart-deadlock':('else if (pending_phase != 0)','else if (pending_phase != 0 && valid_state != 0)','never completes first handoff after restart'),
 }}
plan=json.loads((OUT/'run-plan.json').read_text())
for sid,variants in extra.items():
 t=next(BASE.glob('v2-spec-'+sid+'-*'))
 for name,(old,new,reason) in variants.items():
  d=OUT/'candidates'/t.name/name;d.mkdir(parents=True,exist_ok=True);s=(t/'solution/dut.va').read_text()
  if old not in s:raise ValueError(name)
  (d/'dut.va').write_text(s.replace(old,new));plan.append({'task':str(t),'variant':name,'candidate_directory':str(d),'expected':'fail','semantic_behavior':reason,'certification':'pending-live-execution'})
(OUT/'run-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
# Spectre VACOMP requires an integer digit before the fractional point in authored VA.
for p in (OUT/'candidates').rglob('*.va'):
 p.write_text('\n'.join(x.rstrip() for x in re.sub(r'(?<![\w.])\.(\d)',r'0.\1',p.read_text()).splitlines())+'\n')
