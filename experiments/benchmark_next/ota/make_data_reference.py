"""Write an input-driven fitted VA, without recording any output trajectory."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent

def create(fit,startup):
 knots=fit['knots'];omega,zeta,sat,asym,hi,lo,za=fit['dynamics'];tau,threshold,width,neg,center,nw,eth,ytau=startup['startup']
 cutoff,cutwidth=startup['shutdown']
 lines=['analog function real dc_curve;','input x; real x; begin']
 for i,((x,y),(xx,yy)) in enumerate(zip(knots,knots[1:])):
  lines.append(('if' if i==0 else 'else if')+f' (x<{xx:.14g}) dc_curve={y:.14g}+(x-{x:.14g})*{(yy-y)/(xx-x):.14g};')
 lines+=['else dc_curve='+str(knots[-1][1])+';','end endfunction']
 va='`include "disciplines.vams"\nmodule ota(vin,enable,vout);\ninput vin,enable;output vout;electrical vin,enable,vout,b,q,d;\nreal bias_drive,db,activation,target,err,om,damp,dq,dd,bias;\n'+ '\n'.join(lines)+'\nanalog begin\n'
 va+=f''' bias=($abstime-1.1u)/100n;if(bias<0)bias=0;if(bias>1)bias=1;
 bias_drive=(V(enable)>{eth:.14g})?bias:0;
 db=(bias_drive-V(b))/{tau:.14g}n;
 activation=1/(1+exp(-min(100,max(-100,(V(b)-{threshold:.14g})/{width:.14g}))));
 target=dc_curve(V(vin))*activation-{neg:.14g}*db*1n*exp(-pow((V(b)-{center:.14g})/{nw:.14g},2));
 err=target-V(q);
 om={omega:.14g}*(1+{asym:.14g}*tanh(err/0.05))*(1-{hi:.14g}/(1+exp(-min(100,max(-100,(V(q)-1.2)*30)))))*(1-{lo:.14g}/(1+exp(min(100,max(-100,(V(q)-0.5)*30)))));
 damp={zeta:.14g}*(1+{za:.14g}*tanh(err/0.05));
 dq=V(d)*1e9;dd=(om*om*{sat:.14g}*tanh(err/{sat:.14g})-2*damp*om*V(d))*1e9;
 if(V(b)<0.95) begin dq=err/{ytau:.14g}n;dd=-V(d)/1n;end
 if(V(enable)<0.8) begin dq=-V(q)*min(100,exp(({cutoff:.14g}-V(enable))/{cutwidth:.14g}))/1n;dd=-V(d)/0.1n;end
 V(b)<+idt(db,0);V(q)<+idt(dq,0);V(d)<+idt(dd,0);V(vout)<+V(q);
 $bound_step(0.05n);
end
endmodule
'''
 return va
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--fit',type=Path,required=True);p.add_argument('--startup',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(create(json.loads(a.fit.read_text()),json.loads(a.startup.read_text())))
