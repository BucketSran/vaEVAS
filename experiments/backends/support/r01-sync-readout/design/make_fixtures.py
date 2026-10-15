"""Local exact/Decimal design fixtures. No simulator or production imports."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D, localcontext
import json, hashlib, math
ROOT=Path(__file__).resolve().parent
T=2.0**-20
TT=1e-12
variants=[('ramp',False,1),('ramp-g1000',False,1000),('history',False,1),('filter',False,1),('filter-interrupt',True,1)]
manifest=[]
for ident,interrupt,gain in variants:
    kind=ident.split('-')[0]
    ports=['h','edge','y','qout','count'] + (['other'] if kind=='history' else []) + (['f'] if kind=='filter' else [])
    header='`include "disciplines.vams"\nmodule product_card('+','.join(ports)+');\ninout '+','.join(ports)+';\nelectrical '+','.join(ports)+';\n'
    header+=f'parameter real T={T:.17g};\nparameter real TT={TT:.17g};\nparameter real G={gain};\ninteger q,n; real e;\nanalog begin\n'
    events=['@(initial_step) begin q=0; n=0; end', '@(timer(T,0,TT)) begin q=1; n=n+1; end']
    if interrupt:events+=['@(timer(1.5*T,0,TT)) begin q=0; n=n+1; end']
    body=events[:]
    body += ['e=transition(q,0,T,T);', 'V(h)<+idt(1/T,0.25);' if kind=='history' else 'V(h)<+2+$abstime/T;']
    body += ['V(edge)<+e;','V(y)<+G*V(h)*e;','V(qout)<+q;','V(count)<+n;']
    if kind=='history': body+=['V(other)<+idt(-0.5/T,-0.125);']
    if kind=='filter': body += ["V(f)<+laplace_nd(V(y),'{1},'{1,T});"]
    source=header+'\n'.join(body)+'\nend\nendmodule\n'
    folder=ROOT/ident;folder.mkdir(exist_ok=True)
    (folder/'dut.va').write_text(source)
    trace=source.replace('n=n+1; end','n=n+1; $strobe("PRODUCT_CALLBACK %0d %.17g %0d",n,$abstime,q); end')
    (folder/'dut-callback.va').write_text(trace)
    centers=sorted([0.,T,2*T,3*T] + ([1.5*T] if interrupt else []))
    times=set(i*T/64 for i in range(193))
    for t in centers:
        times.add(t)
        if t>0:times.add(t-2e-12)
        if t<3*T:times.add(t+2e-12)
    for t in centers[1:-1]:
        times.add(math.nextafter(t,-math.inf));times.add(math.nextafter(t,math.inf))
    times=sorted(times)
    nodes=' '.join(ports)
    deck='simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\n'
    deck+=f'X_DUT ({nodes}) product_card\n'
    deck+='simulatorOptions options reltol=1e-9 vabstol=1e-11 iabstol=1e-15 precision="%24.17g"\n'
    deck+='tran tran stop='+format(3*T,'.17g')+' maxstep='+format(T/128,'.17g')+' errpreset=conservative method=gear2only strobeoutput=all strobetimes=['+' '.join(format(t,'.17g') for t in times)+']\n'
    deck+='save '+nodes+'\n'
    (folder/'tb.scs').write_text(deck)
    (folder/'tb-callback.scs').write_text(deck.replace('"dut.va"','"dut-callback.va"'))
    (folder/'observations.json').write_text(json.dumps({'unit_s':T,'stop_s':3*T,'times_s':times,'boundary_centers_nominal_s':centers,'native_only':True,'callback_relative_boundaries_required_after_pilot':True},indent=2)+'\n')
    manifest.append({'id':ident,'kind':kind,'interrupt':interrupt,'gain':gain,'scale_V':1,'counter_final':2 if interrupt else 1,'simulation_status':'not_run','recipe_status':'unqualified_pilot_only','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}})

def rational(x,kind,interrupt,gain):
    e=max(F(0),min(F(1),x-1))
    if interrupt and x>=F(3,2):e=max(F(0),2-x)
    h=F(1,4)+x if kind=='history' else 2+x
    row={'h_V':str(h),'edge_V':str(e),'y_V':str(gain*h*e)}
    if kind=='history':row['other_V']=str(-F(1,8)-x/2)
    return row

def filt(x,interrupt):
    with localcontext() as c:
        c.prec=90
        x=D(x.numerator)/D(x.denominator)
        if x<=1:return D(0)
        if not interrupt:
            if x<=2:return x*x-x-1+(-(x-1)).exp()
            return x+1+((-D(1)).exp()-2)*(-(x-2)).exp()
        if x<=D('1.5'):return x*x-x-1+(-(x-1)).exp()
        if x<=2:return -x*x+2*x+2+((-D('.5')).exp()-3)*(-(x-D('1.5'))).exp()
        return (2+(-D(1)).exp()-3*(-D('.5')).exp())*(-(x-2)).exp()
anchors=[]
for ident,interrupt,gain in variants:
    kind=ident.split('-')[0]
    for x in map(F,['0','1','5/4','3/2','7/4','2','5/2','3']):
        row={'id':ident,'x':str(x),**rational(x,kind,interrupt,gain)}
        if kind=='filter':row['f_V_decimal_90digits']=str(filt(x,interrupt))
        anchors.append(row)
(ROOT/'anchors.json').write_text(json.dumps(anchors,indent=2)+'\n')
negative='''`include "disciplines.vams"
module singular(y,edge,count);
inout y,edge,count; electrical y,edge,count;
parameter real T=9.5367431640625e-7; parameter real TT=1e-12;
integer q,n; real e;
analog begin
@(initial_step) begin q=0; n=0; end
@(timer(T,0,TT)) begin q=1; n=n+1; end
e=transition(q,0,T,T);
V(edge)<+e;
V(y)<+e*V(y)+1;
V(count)<+n;
end
endmodule
'''
(ROOT/'singular.va').write_text(negative)
(ROOT/'manifest.json').write_text(json.dumps({'basis':'main 2eda4be73b1d7a5f651acd4ff69580187897398f; production not changed','unit_s':T,'tier_budget_V':{'Q1':10.1e-6,'Q2':1.01e-6,'Q3':101e-9},'independent_development_conditions':manifest,'not_holdout':True,'original_regressions_counted_separately':['r01-integrate-sync/core-boundary','r01-integrate-sync/c0'],'singular_source_sha256':hashlib.sha256(negative.encode()).hexdigest()},indent=2)+'\n')
print('Created five unrun positive design conditions, one singular source and rational/Decimal anchors.')
