"""Independent row-level oracle regression. This does not execute Verilog-A."""
from pathlib import Path
import importlib.util
import json
import math
import unittest
ROOT=Path(__file__).resolve().parents[3]
def module(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'benchmark/checkers'/f'first_batch_{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
V=module('verification');M=module('measurement')
def cases(task):return json.loads((ROOT/'benchmark/tasks'/task/'tests/cases.json').read_text())
def square(t,start,end):
 if start<=t<start+.1e-9:return (t-start)/.1e-9
 if start+.1e-9<=t<end:return 1
 if end<=t<end+.1e-9:return 1-(t-end)/.1e-9
 return 0

def rows(stop,step,fn):
 return [dict(time=t,**fn(t)) for t in [i*step for i in range(round(stop/step)+1)]]

class Oracles(unittest.TestCase):
 def test_sar(self):
  for c in cases('verify-sar-flow'):
   events=[];busy=0;count=0;code=0;last=0;d=0
   for tick in range(121):
    t=tick*10e-9;k=int((t+1e-15)/200e-9);phase=(t-k*200e-9)/1e-9
    start=(31<=phase<42 or 51<=phase<62);reset=(t<21e-9 or k==2 and 65<=phase<76)
    d=0
    if reset and c['fault']!=3:busy=0;count=0;code=0
    else:
     if busy:
      count-=1
      if count==0:busy=0;d=1
     if start and not last and (not busy or c['fault']==2) and not reset:
      busy=1;count=c['latency'];code=2*(k%6)+1
      if c['fault']==1:code=(code+1)%16
    events.append((t,code,d));last=start
   def wave(t):
    k=min(5,int((t+1e-15)/200e-9));phase=t-k*200e-9
    e=max(0,min(int((t+1e-15)/10e-9),120));old=events[max(0,e-1)];cur=events[e]
    f=min(1,max(0,(t-cur[0])/.1e-9))
    return dict(vin=(2*k+1.25)/16,start=square(phase,31e-9,42e-9)+square(phase,51e-9,62e-9),rst=0 if t<21e-9 or k==2 and 65e-9<=phase<76e-9 else 1,code=old[1]+f*(cur[1]-old[1]),done=old[2]+f*(cur[2]-old[2]),verdict=int(c['fault']!=0 and t>=900e-9))
   r=rows(c['stop'],.25e-9,wave);out=V.evaluate(r,c)
   self.assertTrue(out['passed'],(c['name'],out))
   for a in r:a['verdict']=1-a['verdict']
   self.assertFalse(V.evaluate(r,c)['passed'])
 def test_nonoverlap(self):
  for c in cases('verify-nonoverlap-stimulus'):
   p,d=c['period'],c['dead']
   def wave(t):
    k=int((t+1e-15)/p);phase=t-k*p;last=k*p+p/2+d+.05e-9
    capture=k*p+d+.05e-9 if t>=last else (k-1)*p+d+.05e-9
    z=0 if k==0 and t<last else .5+.3*math.sin(2*math.pi*capture/700e-9)
    return dict(p1=square(phase,d,p/2),p2=square(phase,p/2+d,p),vin=.5+.3*math.sin(2*math.pi*t/700e-9),z=z)
   r=rows(c['stop'],.1e-9,wave);out=V.evaluate(r,c);self.assertTrue(out['passed'],out)
   weak=[dict(a,p1=.49+.02*a['p1'],p2=.49+.02*a['p2']) for a in r]
   rejected=V.evaluate(weak,c)
   self.assertFalse(rejected['passed'])
   self.assertIn('phase stable electrical level',rejected['failures'])
   for a in r:a['p2']=a['p1']
   self.assertFalse(V.evaluate(r,c)['passed'])
 def test_comparator_stimulus(self):
  for c in cases('verify-comparator-overdrive'):
   def wave(t):
    k=int((t+1e-15)/100e-9);phase=t-k*100e-9;d=[.01,.025,.05][k%3];sign=1 if k%2==0 else -1
    return dict(vp=c['cm']+sign*d/2,vn=c['cm']-sign*d/2,clk=square(phase,20e-9,70e-9),q=square(phase,20e-9+.05e-9+1e-9+.1e-9/d,70e-9) if sign==1 else 0)
   r=rows(c['stop'],.1e-9,wave);out=V.evaluate(r,c);self.assertTrue(out['passed'],out)
   for a in r:a['vn']=a['vp']
   self.assertFalse(V.evaluate(r,c)['passed'])
 def test_pll_checker(self):
  for c in cases('verify-pll-lock-checker'):
   def wave(t):
    p=105e-9 if c['fault']==1 and t>=1e-6 else 100e-9;k=int((t+1e-15)/p);offset=(5-k)*4e-9 if k<5 else 0
    if c['fault']==3 and t>=2e-6:offset=10e-9
    q=square(t-k*p,offset,50e-9+offset)
    if c['fault']==2 and 2.2e-6<=t<2.3e-6:q=0
    kr=int((t+1e-15)/100e-9)
    return dict(ref=square(t-kr*100e-9,0,50e-9),clk=q,verdict=int(c['fault']!=0 and t>=900e-9))
   r=rows(c['stop'],.25e-9,wave);out=V.evaluate(r,c);self.assertTrue(out['passed'],out)
   for a in r:a['verdict']=1-a['verdict']
   self.assertFalse(V.evaluate(r,c)['passed'])
 def test_sh_checker(self):
  for c in cases('verify-sh-settling-checker'):
   def wave(t):
    k=int((t+1e-15)/500e-9);phase=t-k*500e-9;target=.8 if k%2==0 else .2;tau=60e-9 if c['fault']==1 else 20e-9
    out=.5+(target-.5)*(1-math.exp(-min(phase,250e-9)/tau))
    if c['fault']==2 and 180e-9<=phase<200e-9:out=target+.025
    if c['fault']==3 and phase>=250e-9:out-=2e5*(phase-250e-9)
    return dict(vin=target,track=int(phase<250e-9),y=out,verdict=int(c['fault']!=0 and t>=900e-9))
   r=rows(c['stop'],.25e-9,wave);out=V.evaluate(r,c);self.assertTrue(out['passed'],out)
   for a in r:a['verdict']=1-a['verdict']
   self.assertFalse(V.evaluate(r,c)['passed'])
 def test_adc_measurement(self):
  for c in cases('measure-adc-spectrum'):
   samples=[]
   for n in range(64):
    ph=2*math.pi*c['tone_bin']*n/64;samples.append(math.floor(2048+c['amp']*(math.sin(ph)+c['h2']*math.sin(2*ph)+c['h3']*math.cos(3*ph))))
   expected=M.spectrum(samples,c['tone_bin'])
   def wave(t):
    n=int((t+1e-15)/100e-9);phase=t-n*100e-9
    return dict(clk=square(phase,10e-9,60e-9),code=samples[n%64],vin=samples[n%64]/4096,**expected)
   r=rows(c['stop'],.05e-9,wave);out=M.evaluate(r,c);self.assertTrue(out['passed'],out)
   for a in r:a['sndr']+=1
   self.assertFalse(M.evaluate(r,c)['passed'])
 def test_adc_invalid_zero_code_rejected(self):
  c=cases('measure-adc-spectrum')[0]
  def wave(t):
   n=int((t+1e-15)/100e-9);phase=t-n*100e-9
   ph=2*math.pi*c['tone_bin']*t/6.4e-6
   analog=2048+c['amp']*(math.sin(ph)+c['h2']*math.sin(2*ph)+c['h3']*math.cos(3*ph))
   return dict(clk=square(phase,10e-9,60e-9),code=0,vin=analog/4096,sndr=0,sfdr=0,dc=0)
  answer=M.evaluate(rows(c['stop'],.05e-9,wave),c)
  self.assertIs(answer['passed'],False)
  self.assertIn('ADC raw observations differ from synthetic circuit',answer['failures'])
 def test_pll_missing_reference_rejected(self):
  c=cases('measure-pll-relock-jitter')[0]
  def wave(t):
   k=int((t+1e-15)/100e-9)
   return dict(ref=0,clk=square(t-k*100e-9,0,50e-9),relock_ns=0,jitter_ns=0)
  answer=M.evaluate(rows(c['stop'],.1e-9,wave),c)
  self.assertIs(answer['passed'],False)
  self.assertIn('PLL reference edge coverage',answer['failures'])
 def test_spectrum_formula(self):
  x=[1000+100*math.sin(2*math.pi*5*n/64)+10*math.cos(2*math.pi*10*n/64) for n in range(64)]
  o=M.spectrum(x,5);self.assertAlmostEqual(o['sndr'],20,places=10);self.assertAlmostEqual(o['sfdr'],20,places=10);self.assertAlmostEqual(o['dc'],1000)
 def test_sh_measurement(self):
  for c in cases('measure-sh-acquisition-droop'):
   expected={'settle_ns':math.log(100)*c['tau']/1e-9,'droop_mvus':c['droop']*.001}
   def wave(t):
    k=int((t+1e-15)/500e-9);phase=t-k*500e-9;target=.8 if k%2==0 else .2
    out=.5+(target-.5)*(1-math.exp(-min(phase,250e-9)/c['tau']))
    if phase>=250e-9:out-=c['droop']*(phase-250e-9)
    return dict(vin=target,track=int(phase<250e-9),y=out,**expected)
   r=rows(c['stop'],.25e-9,wave);out=M.evaluate(r,c);self.assertTrue(out['passed'],out)
   for a in r:a['droop_mvus']+=1
   self.assertFalse(M.evaluate(r,c)['passed'])
 def test_pll_measurement(self):
  for c in cases('measure-pll-relock-jitter'):
   # Alternating 19 periods have 10 short and 9 long intervals.
   ps=[100+(-2 if n%2==0 else 2)*c['jitter']/1e-9 for n in range(19)]
   mean=sum(ps)/19;rms=math.sqrt(sum((p-mean)**2 for p in ps)/19)
   expected={'relock_ns':c['settle_cycles']*100+.05,'jitter_ns':rms}
   def wave(t):
    k=int((t+1e-15)/100e-9);phase=t-k*100e-9;offset=0
    if 10<=k<10+c['settle_cycles']:offset=(10+c['settle_cycles']-k)*5e-9
    if k>=22:offset=2e-9+(c['jitter'] if k%2==0 else -c['jitter'])
    return dict(ref=square(phase,0,50e-9),clk=square(phase,offset,50e-9+offset),**expected)
   r=rows(c['stop'],.1e-9,wave);out=M.evaluate(r,c);self.assertTrue(out['passed'],out)
   for a in r:a['relock_ns']+=100
   self.assertFalse(M.evaluate(r,c)['passed'])
 def test_hysteresis_measurement(self):
  for c in cases('measure-comparator-delay-hysteresis'):
   h,d=c['hysteresis'],c['delay'];qr0=(.02+h/2)/1e5+d;qf0=400e-9+(.02+h/2)/1e5+d
   expected={'high_mv':h*500,'low_mv':-h*500,'rise_ns':d/1e-9+.05,'fall_ns':d/1e-9+.05}
   def wave(t):
    x=-.02+1e5*t if t<400e-9 else .02-1e5*(t-400e-9) if t<800e-9 else -.02 if t<1e-6 else .02 if t<1.2e-6 else -.02
    q=square(t,qr0,qf0)+square(t,1e-6+d,1.2e-6+d)
    return dict(vin=x,q=q,**expected)
   r=rows(c['stop'],.05e-9,wave);out=M.evaluate(r,c);self.assertTrue(out['passed'],out)
   for a in r:a['high_mv']=-a['high_mv']
   self.assertFalse(M.evaluate(r,c)['passed'])

if __name__=='__main__':unittest.main()
