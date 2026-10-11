"""Independent observed-waveform converter contracts; no candidate/reference reads."""
import bisect
import math

def spectrum_metrics(x,tone):
 # Pairwise cosine autocorrelation computes power independently of VA DFT sums.
 n=len(x);mean=sum(x)/n;y=[v-mean for v in x]
 powers={k:sum(y[a]*y[b]*math.cos(2*math.pi*k*(a-b)/n) for a in range(n) for b in range(n))*(1 if k==n//2 else 2)/n**2 for k in range(1,n//2+1)}
 fund=powers.pop(tone);noise=sum(powers.values());spur=max(powers.values())
 if fund<=1e-8 or noise<=1e-8 or spur<=1e-8:return None
 sndr=10*math.log10(fund/noise)
 return dict(sndr=sndr,sfdr=10*math.log10(fund/spur),enob=(sndr-1.76)/6.02,dc=mean)

def linearity_metrics(x):
 lsb=(x[-1]-x[0])/(len(x)-1)
 if lsb<=0:return None
 return dict(dnl=max(abs((b-a)/lsb-1) for a,b in zip(x,x[1:])),inl=max(abs((v-x[0])/lsb-i) for i,v in enumerate(x)))

def evaluate(rows,case,work):
 rows=[{k.lower():v for k,v in r.items()} for r in rows]
 ts=[r['time'] for r in rows]
 if max(b-a for a,b in zip(ts,ts[1:]))>case['maxstep']*1.1:raise ValueError('insufficient temporal evidence')
 def at(t,key):
  i=max(0,min(len(rows)-2,bisect.bisect_right(ts,t)-1));a,b=rows[i],rows[i+1]
  return a[key]+(b[key]-a[key])*(t-a['time'])/(b['time']-a['time'])
 def edges(key):
  return [a['time']+(b['time']-a['time'])*(.5-a[key])/(b[key]-a[key]) for a,b in zip(rows,rows[1:]) if a[key]<.5<=b[key]]
 events=sorted([(t,'clk') for t in edges('clk')]+[(t,'rst') for t in edges('rst')])
 kind=case['kind'];out={'aout':case['initial']} if kind=='dac' else {n:0 for n in case['outputs']}
 history=[(0,dict(out))];samples=[];bad=False
 for t,key in events:
  if kind=='dac':
   if key=='clk':out['aout']=case['lo']+(case['hi']-case['lo'])*sum(w*(at(t,n)>.45) for n,w in zip(case['inputs'],case['weights']))/sum(case['weights'])
  elif key=='rst':samples=[];bad=False;out={n:0 for n in case['outputs']}
  elif at(t,'rst')<.5 and len(samples)<case['count']:
   if kind=='scan':
    code=int(round(at(t,'code')));bad=bad or code!=len(samples)
    samples.append(at(t,'observe'))
   else:
    x=at(t,'code');bad=bad or at(t,'sample_ok')<.5 or abs(x-round(x))>1e-4 or not 0<=x<=4095
    samples.append(round(x))
   if len(samples)==case['count']:
    q=None if bad else (linearity_metrics(samples) if kind=='scan' else spectrum_metrics(samples,case['tone']))
    out={n:0 for n in case['outputs']}
    if q:out.update(q);out['valid']=1
  history.append((t,dict(out)))
 # Inspect at every actual waveform point outside published output transition guard.
 ht=[t for t,q in history];errors={n:0 for n in out};checked=0
 for row in rows:
  i=bisect.bisect_right(ht,row['time'])-1
  if row['time']-ht[i]<case['guard']:continue
  checked+=1
  for n,want in history[i][1].items():errors[n]=max(errors[n],abs(row[n]-want))
 if not checked:raise ValueError('no settled observations')
 return dict(passed=all(e<=case['tolerances'].get(n,.001) for n,e in errors.items()),errors=errors,settled_points=checked,records=len(samples),invalid=bad)
