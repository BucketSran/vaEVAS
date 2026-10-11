"""Replace cosmetic alternatives with separate retained-state representations."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/benchmark_v2/spec_modeling/candidates';HEAD='`include "disciplines.vams"\n'
def write(sid,body):
 p=next(OUT.glob('v2-spec-'+sid+'-*'))/'alternative/dut.va';p.write_text(HEAD+body)
write('082','''module agc_receiver_leveling_loop(clk,rst,vin,out,metric,gain_mon,rssi_mon);
input clk,rst,vin;output out,metric,gain_mon,rssi_mon;electrical clk,rst,vin,out,metric,gain_mon,rssi_mon;
parameter real tr=100p,vth=0.45,target_amp=0.18,deadband=0.025;
real control,g,level,envelope,score,rssi;
analog begin
 @(initial_step)begin control=(2.2-0.45)/2.55;level=0.45;score=0;rssi=0;end
 @(cross(V(clk)-vth,+1))begin
 if(V(rst)>vth)begin control=(2.2-0.45)/2.55;level=0.45;score=0;rssi=0;end
 else begin
 g=0.45+2.55*control;level=min(0.88,max(0.02,0.45+g*(V(vin)-0.45)));envelope=abs(level-0.45);
 if(envelope>target_amp+deadband)control=control-0.18/2.55;
 if(envelope<target_amp-deadband)control=control+0.10/2.55;
 control=min(1.0,max(0.0,control));score=min(0.9,max(0.0,0.9-4*abs(envelope-target_amp)));rssi=0.9*envelope/0.43;
 end end
 V(out)<+transition(level,0,tr,tr);V(metric)<+transition(score,0,tr,tr);V(gain_mon)<+transition(0.9*control,0,tr,tr);V(rssi_mon)<+transition(rssi,0,tr,tr);
end
endmodule
''')
write('396','''module quadrature_lo_generator_divided_clock(clk_in,rst,enable,lo_i,lo_q,div_metric,quad_ok);
input clk_in,rst,enable;output lo_i,lo_q,div_metric,quad_ok;electrical clk_in,rst,enable,lo_i,lo_q,div_metric,quad_ok;
parameter real vdd=0.9,vss=0,vth=0.45,tr=200p;
integer ring,count,driven,i,q,k;
analog begin
 @(initial_step)begin ring=1;driven=0;count=0;i=0;q=0;k=0;end
 @(cross(V(clk_in)-vth,+1) or cross(V(rst)-vth,+1) or cross(V(enable)-vth,-1))begin
 if(V(rst)>vth || V(enable)<=vth)begin ring=1;driven=0;count=0;i=0;q=0;k=0;end
 else begin
 driven=ring;i=(driven&3)!=0;q=(driven&6)!=0;
 k=(driven==1)?0:(driven==2)?1:(driven==4)?2:3;
 ring=(ring==8)?1:ring<<1;count=count+1;
 end end
 V(lo_i)<+transition(i?vdd:vss,0,tr,tr);V(lo_q)<+transition(q?vdd:vss,0,tr,tr);
 V(div_metric)<+transition(vss+(vdd-vss)*k/3.0,0,tr,tr);V(quad_ok)<+transition(count>=8?vdd:vss,0,tr,tr);
end
endmodule
''')
write('186','''module sarfend_logic_4b(clks,dcomp,dcompb,test,dtest0,dtest1,dtest2,dtest3,clkc,dp1,dp2,dp3,dp4,dm1,dm2,dm3,dm4,dout0,dout1,dout2,dout3);
input clks,dcomp,dcompb,test,dtest0,dtest1,dtest2,dtest3;output clkc,dp1,dp2,dp3,dp4,dm1,dm2,dm3,dm4,dout0,dout1,dout2,dout3;
electrical clks,dcomp,dcompb,test,dtest0,dtest1,dtest2,dtest3,clkc,dp1,dp2,dp3,dp4,dm1,dm2,dm3,dm4,dout0,dout1,dout2,dout3;
integer pword,mword,published,override,k,request,decision,mask;
analog begin
 @(initial_step)begin pword=7;mword=7;published=0;override=0;k=3;request=0;end
 @(cross(V(clks)-0.45,+1))begin
 published=pword;pword=7;mword=7;k=3;request=0;
 override=(V(dtest0)>0.45)+2*(V(dtest1)>0.45)+4*(V(dtest2)>0.45)+8*(V(dtest3)>0.45);
 end
 @(cross(V(clks)-0.45,-1))request=1;
 @(cross(V(dcomp)+V(dcompb)-0.45,-1))if(V(clks)<0.45 && k>=0)request=1;
 @(cross(V(dcomp)+V(dcompb)-0.45,+1))begin
 if(V(clks)<0.45 && k>=0)begin
 mask=1<<k;decision=(V(test)>0.45)?((override&mask)!=0):(V(dcomp)>V(dcompb));
 pword=(pword & ~mask) | (decision?mask:0);mword=(mword & ~mask) | (decision?0:mask);
 k=k-1;request=0;
 end end
 V(dp1)<+transition((pword&1)?1:0,20p,10p,10p);V(dp2)<+transition((pword&2)?1:0,20p,10p,10p);V(dp3)<+transition((pword&4)?1:0,20p,10p,10p);V(dp4)<+transition((pword&8)?1:0,20p,10p,10p);
 V(dm1)<+transition((mword&1)?1:0,20p,10p,10p);V(dm2)<+transition((mword&2)?1:0,20p,10p,10p);V(dm3)<+transition((mword&4)?1:0,20p,10p,10p);V(dm4)<+transition((mword&8)?1:0,20p,10p,10p);
 V(dout0)<+transition((published&1)?1:0,0,10p,10p);V(dout1)<+transition((published&2)?1:0,0,10p,10p);V(dout2)<+transition((published&4)?1:0,0,10p,10p);V(dout3)<+transition((published&8)?1:0,0,10p,10p);
 V(clkc)<+transition(request,30p,10p,10p);
end
endmodule
''')
# Complement retained hysteretic state while preserving old-state bookkeeping.
p=next(OUT.glob('v2-spec-314-*'))/'alternative/dut.va'
reference=next((ROOT/'benchmark/tasks').glob('v2-spec-314-*'))/'solution/dut.va'
s=reference.read_text().replace('integer state,oldstate;','integer outside,oldstate;')
s=re.sub(r'\bstate=0', 'outside=1',s)
s=re.sub(r'\bstate=1', 'outside=0',s)
s=s.replace('oldstate=state','oldstate=outside').replace('state==0','outside==1').replace('state==1','outside==0').replace('state!=oldstate','outside!=oldstate').replace('state?vdd:vss','outside?vss:vdd')
p.write_text(s)
