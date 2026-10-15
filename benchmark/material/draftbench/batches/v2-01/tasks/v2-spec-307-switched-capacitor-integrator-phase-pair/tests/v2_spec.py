"""Independent voltage-domain contracts. No candidate source or reference is read."""
import bisect
import math

OUTPUTS={'024':['out'],'071':['vout','metric'],'186':['clkc']+[f'{p}{i}' for p in ('dp','dm') for i in range(1,5)]+[f'dout{i}' for i in range(4)],'047':['out'],'314':['inside_flag','state_metric','toggled'],'002':['vdac_p','vdac_n'],'003':['vres','d1','d0'],'055':['bitout'],'001':['up','down','retimed'],'375':['phi1','phi2','deadtime_metric','valid'],'396':['lo_i','lo_q','div_metric','quad_ok'],'038':['out','metric'],'082':['out','metric','gain_mon','rssi_mon'],'091':['voutp','voutn','settled','offset_residual'],'308':['vout','offset_dbg','valid'],'370':['vout','error_metric','settled'],'307':['vout','phase_metric','valid'],'183':[f'dc{i}' for i in range(7)]+['cvinp','cvinn','en','enb'],'353':['vout','main_dbg','pre_dbg','post_dbg']}

def clip(x,a=0.,b=.9):return min(b,max(a,x))

def evaluate(rows,case,work):
 rows=[{k.lower():v for k,v in r.items()} for r in rows];case={**case,'signals':[x.lower() for x in case.get('signals',[])]}
 sid=str(case['source_id']).zfill(3);p=case.get('params',{});vth=p.get('vth',.45);hi=p.get('vdd',.9);lo=p.get('vss',0.);cm=p.get('vcm',.45);tr=p.get('tr',p.get('tedge',p.get('tt',2e-10)))
 if sid in ('183','055'):tr=p.get('tr',2e-11)
 if sid=='001':tr=p.get('trf',1e-11)
 if sid=='353':tr=p.get('tr',1.2e-10)
 if sid=='091':tr=p.get('tr',1e-10)
 if sid=='082':tr=p.get('tr',1e-10)
 if sid=='024':tr=p.get('tedge',1e-10)
 if sid=='002':tr=p.get('tt',2e-11)
 if len(rows)<2:raise ValueError('missing waveform')
 ts=[r['time'] for r in rows]
 required=set(case['signals'])|set(OUTPUTS[sid])
 if any(not required.issubset(r) for r in rows):raise ValueError('missing required signals')
 if any(not math.isfinite(v) for r in rows for v in r.values()):raise ValueError('nonfinite evidence')
 if any(a>=b for a,b in zip(ts,ts[1:])):raise ValueError('waveform time must increase')
 if ts[0]>1e-15 or abs(ts[-1]-case['stop'])>max(1e-15,case['stop']*1e-6):raise ValueError('incomplete transient')
 # Resolution is an environment obligation. Candidate failure cannot repair it.
 if max(b-a for a,b in zip(ts,ts[1:]))>case.get('resolution',tr/4)*1.05:raise ValueError('insufficient waveform resolution')
 def at(t,n):
  j=max(0,min(len(rows)-2,bisect.bisect_right(ts,t)-1));a,b=rows[j],rows[j+1];return a[n]+(b[n]-a[n])*(t-a['time'])/(b['time']-a['time'])
 def val(t,n):return at(t,n) if n in rows[0] else 0.
 def bit(t,n,threshold=vth):return int(val(t,n)>threshold)
 events=[]
 def crossings(n,threshold=vth,ref=None):
  if n not in rows[0]:return
  for a,b in zip(rows,rows[1:]):
   av=a[n]-(a[ref] if ref else 0)-threshold;bv=b[n]-(b[ref] if ref else 0)-threshold
   if av<0<=bv or av>0>=bv:
    t=a['time']+(b['time']-a['time'])*(-av)/(bv-av);events.append((t,n,1 if bv>av else -1))
 ref='vss' if sid in ('024','002','047') else None
 clock={'024':'clk','002':'clk','003':'phi1','055':'vclk','001':'clk','396':'clk_in','038':'clk','082':'clk','091':'chop_clk','308':'clk','307':'phi1','183':'ck','353':'clk','186':'clks','375':'clk_in'}.get(sid)
 if clock:crossings(clock,p.get('vth_clk',.45) if sid=='055' else p.get('vdd',1)/2 if sid=='183' else vth,ref)
 for n in ('rst','enable','hold','sample','phi2','dcomp','dcompb'):
  if n!=clock:crossings(n)
 if sid=='314':
  for n,threshold in [('vin',val(0,'low_trip')+p.get('hyst',.01)),('vin',val(0,'high_trip')-p.get('hyst',.01)),('vin',val(0,'low_trip')-p.get('hyst',.01)),('vin',val(0,'high_trip')+p.get('hyst',.01))]:crossings(n,threshold)
 if sid=='047':
  crossings('vin',p.get('vlow',.3),ref);crossings('vin',p.get('vhigh',.6),ref)
 tick=p.get('tick',1e-9 if sid=='071' else 5e-10 if sid=='047' else 2e-10 if sid=='375' else 2.5e-10)
 if sid in ('047','071','375','370'):
  for i in range(int(ts[-1]/tick)+1):events.append((i*tick,'tick',1))
 events.sort();out={n:lo for n in OUTPUTS[sid]};history=[(0.,dict(out))];s={'gain':2.2 if sid=='082' else 1.,'acc':0.,'bit':0,'q':cm,'count':0,'phase':0,'n':0,'sample':cm,'sample_valid':False,'reset_sample':cm,'pair':False,'symbols':[0,0,0],'ptr':4,'pending':0,'wait':0,'prev_clk':0,'a':0,'b':0,'c':0}
 if sid=='024':out['out']=val(0,'vss')
 if sid=='071':out.update(vout=p.get('vinit',.45),metric=0);s['q']=out['vout'];s['tracking']=False
 if sid=='003':out['vres']=p.get('vdd',.9)/2;s['sample']=0.
 if sid=='002':out.update(vdac_p=val(0,'vss')+cm,vdac_n=val(0,'vss')+cm)
 if sid=='038':out['out']=cm
 if sid=='186':out.update({f'{q}{i}':0 if i==4 else 1 for q in ('dp','dm') for i in range(1,5)})
 if sid=='082':out.update(out=.45,gain_mon=.9*(2.2-.45)/2.55)
 if sid in ('307','308','370','353'):out.update({n:cm for n in OUTPUTS[sid] if n not in ('valid','settled')})
 if sid=='308':out['offset_dbg']=lo
 if sid=='370':out['error_metric']=cm
 if sid=='091':out.update(voutp=cm,voutn=cm)
 if sid=='183':out.update(dc6=p.get('vdd',1),en=p.get('vdd',1));s['code']=64;s['ptr']=6
 if sid=='047':out['out']=val(0,'vdd') if p.get('vlow',.3)<val(0,'vin')-val(0,'vss')<p.get('vhigh',.6) else val(0,'vss')
 history=[(0.,dict(out))];toggles=[]
 for t,n,d in events:
  # A tiny look-ahead resolves the direction at the crossing without sampling future analog input.
  bt=lambda name:bit(min(t+1e-16,ts[-1]),name)
  reset=bt('rst');enabled=bt('enable') if 'enable' in rows[0] else 1
  rising=n==clock and d==1
  if sid=='024' and rising:out['out']=val(t,'in')
  elif sid=='071':
   if n=='sample':s['tracking']=d==1 and not reset
   if n=='tick':
    if reset:s['q']=p.get('vinit',.45);s['tracking']=False
    elif s['tracking']:s['q']=(1-p.get('alpha',.42))*s['q']+p.get('alpha',.42)*val(t,'vin')
   out.update(vout=s['q'],metric=.9 if s['tracking'] else 0)
  elif sid=='047' and n=='tick':out['out']=val(t,'vdd') if p.get('vlow',.3)<val(t,'vin')-val(t,'vss')<p.get('vhigh',.6) else val(t,'vss')
  elif sid=='314':
   before=out['inside_flag'];x=val(min(t+1e-16,ts[-1]),'vin');h=p.get('hyst',.01)
   if reset or not enabled:out.update(inside_flag=lo,state_metric=lo,toggled=lo)
   else:
    if before==lo and val(t,'low_trip')+h<x<val(t,'high_trip')-h:out['inside_flag']=hi
    elif before==hi and (x<val(t,'low_trip')-h or x>val(t,'high_trip')+h):out['inside_flag']=lo
    out['state_metric']=out['inside_flag'];out['toggled']=hi if before!=out['inside_flag'] else lo
    if before!=out['inside_flag']:toggles.append(t)
  elif sid=='002' and rising:
   code=sum((val(t,f'd{i}')-val(t,'vss')>.45)*2**i for i in range(10));cal=(val(t,'cal0')-val(t,'vss')>.45)+2*(val(t,'cal1')-val(t,'vss')>.45);dv=p.get('swing',.6)*((code+32*cal)/1023-.5)/2;out.update(vdac_p=val(t,'vss')+cm+dv,vdac_n=val(t,'vss')+cm-dv)
  elif sid=='003':
   if rising:s['sample']=val(t,'vin')
   if n=='phi2' and d==1:
    c=val(t,'vdd')/2;v=s['sample']-c;r=val(t,'vref');region=1 if v>r/4 else -1 if v<-r/4 else 0;out.update(vres=clip(c+2*v-region*r/2,val(t,'vss'),val(t,'vdd')),d1=val(t,'vdd') if region==1 else val(t,'vss'),d0=val(t,'vdd') if region==0 else val(t,'vss'))
  elif sid=='055' and rising:
   s['acc']+=val(t,'vin')/p.get('vref',1)-s['bit'];s['bit']=int(s['acc']>=0);out['bitout']=s['bit']*p.get('vh',.9)
  elif sid=='001':
   if reset or not enabled:s.update(a=0,b=0,c=0);out.update(up=0,down=0,retimed=0)
   elif n=='clk' and d<0:s['b']=bt('data')
   elif n=='clk' and d>0:s['a']=s['c'];s['c']=bt('data');out.update(up=hi*int(s['a']!=s['b'] and s['b']==s['c']),down=hi*int(s['a']==s['b'] and s['b']!=s['c']),retimed=hi*s['c'])
  elif sid=='375':
   if reset or not enabled:s.update(pending=0,wait=0);out.update(phi1=lo,phi2=lo,deadtime_metric=lo,valid=lo)
   elif n=='clk_in':s.update(pending=1 if d>0 else 2,wait=p.get('dead_ticks',5));out.update(phi1=lo,phi2=lo,deadtime_metric=hi)
   elif n=='tick' and s['pending']:
    s['wait']-=1
    if s['wait']<=0:out.update(phi1=hi if s['pending']==1 else lo,phi2=hi if s['pending']==2 else lo,deadtime_metric=lo,valid=hi);s['pending']=0
  elif sid=='396':
   if reset or not enabled:s.update(phase=0,n=0);out.update(lo_i=lo,lo_q=lo,div_metric=lo,quad_ok=lo)
   elif rising:
    k=s['phase'];s['n']+=1;out.update(lo_i=hi if k<2 else lo,lo_q=hi if k in (1,2) else lo,div_metric=lo+(hi-lo)*k/3,quad_ok=hi if s['n']>=8 else lo);s['phase']=(k+1)%4
  elif sid=='038' and rising:s['gain']=1 if reset else p.get('gain_high',2.4) if bt('gain_sel') else p.get('gain_low',.8)
  elif sid=='082' and rising:
   if reset:s['gain']=2.2;out.update(out=.45,metric=0,gain_mon=.9*(2.2-.45)/2.55,rssi_mon=0)
   else:
    y=clip(.45+s['gain']*(val(t,'vin')-.45),.02,.88);env=abs(y-.45);s['gain']=clip(s['gain']+(-.18 if env>p.get('target_amp',.18)+p.get('deadband',.025) else .10 if env<p.get('target_amp',.18)-p.get('deadband',.025) else 0),.45,3);out.update(out=y,gain_mon=.9*(s['gain']-.45)/2.55,rssi_mon=.9*env/.43,metric=clip(.9-4*abs(env-p.get('target_amp',.18))))
  elif sid=='091':
   if reset or not enabled:s.update(q=0,count=0);out.update(voutp=cm,voutn=cm,settled=lo,offset_residual=0)
   elif n=='chop_clk' and not bt('hold'):
    desired=p.get('gain',3)*(val(t,'vinp')-val(t,'vinn'));sample=desired+(1 if d>0 else -1)*p.get('gain',3)*p.get('vos_amp',.02);s['q']=(1-p.get('lp_alpha',.25))*s['q']+p.get('lp_alpha',.25)*sample;err=s['q']-desired;s['count']=s['count']+1 if abs(err)<=p.get('settle_tol',.02) else 0;out.update(voutp=clip(cm+s['q']/2,lo,hi),voutn=clip(cm-s['q']/2,lo,hi),offset_residual=err,settled=hi if s['count']>=p.get('settle_cycles',3) else lo)
  elif sid=='308':
   if reset:s.update(reset_sample=cm,pair=False);out.update(vout=cm,offset_dbg=lo,valid=lo)
   elif rising:
    if bt('sample_reset'):s['reset_sample']=val(t,'vin');s['pair']=True
    if bt('sample_signal') and s['pair']:out.update(vout=clip(cm+p.get('cds_gain',1)*(val(t,'vin')-s['reset_sample']),lo,hi),offset_dbg=s['reset_sample'],valid=hi)
  elif sid=='370' and n=='tick':
   level=bt('clk')
   if reset or not enabled:s.update(q=cm,count=0);out.update(vout=cm,error_metric=cm,settled=lo)
   elif level and not s['prev_clk']:
    code=sum(bt(f'gain_{i}')*2**i for i in range(3));target=clip(cm+(1+p.get('gain_lsb',.5)*code)*(val(t,'vin')-cm),lo,hi);s['q']=(1-p.get('alpha',.3))*s['q']+p.get('alpha',.3)*target;err=target-s['q'];s['count']=s['count']+1 if abs(err)<p.get('settle_tol',.04) else 0;out.update(vout=s['q'],error_metric=cm+err,settled=hi if s['count']>=3 else lo)
   s['prev_clk']=level
  elif sid=='307':
   if reset or not enabled:s.update(q=cm,sample=cm,sample_valid=False);out.update(vout=cm,phase_metric=cm,valid=lo)
   elif n=='phi1' and d>0:s['sample_valid']=not bt('phi2');s['sample']=val(t,'vin') if s['sample_valid'] else s['sample']
   elif n=='phi2' and d>0:
    if not bt('phi1') and s['sample_valid']:s['q']=clip(s['q']+p.get('k_int',.2)*(s['sample']-cm),lo,hi);out.update(vout=s['q'],phase_metric=clip(s['sample'],lo,hi),valid=hi);s['sample_valid']=False
    else:out['valid']=lo
  elif sid=='183' and rising and s['ptr']>=0:
   k=s['ptr'];s['code']&=~(2**k) if bit(t,'d',p.get('vdd',1)/2) else -1;s['ptr']-=1
   if s['ptr']>=0:s['code']|=2**s['ptr']
   rail=p.get('vdd',1);out.update({f'dc{i}':rail*int(bool(s['code']&2**i)) for i in range(7)});out.update(en=rail if s['ptr']>=0 else 0,enb=0 if s['ptr']>=0 else rail)
  elif sid=='353' and rising:
   if reset:s['symbols']=[0,0,0];out.update({n:cm for n in OUTPUTS[sid]})
   else:
    z=s['symbols']=[1 if bt('data') else -1,*s['symbols'][:2]];pre=bt('pre_0')+2*bt('pre_1');post=bt('post_0')+2*bt('post_1');a=p.get('main_amp',.18)*z[0];b=p.get('tap_step',.04)*pre*z[1];c=-p.get('tap_step',.04)*post*z[2];out.update(vout=clip(cm+a+b+c,lo,hi),main_dbg=cm+a,pre_dbg=cm+b,post_dbg=cm+c)
  elif sid=='186':
   if n=='clks' and d>0:
    out.update({f'dout{i}':out[f'dp{i+1}'] for i in range(4)});out.update({f'{q}{i}':0 if i==4 else 1 for q in ('dp','dm') for i in range(1,5)});out['clkc']=0;s['ptr']=4;s['testword']=[bt(f'dtest{i}') for i in range(4)]
   elif not bt('clks') and s['ptr']>0:
    a=bt('dcomp');b=bt('dcompb')
    if a!=b:
     k=s['ptr'];x=s.get('testword',[0]*4)[k-1] if bt('test') else a;out.update({f'dp{k}':x,f'dm{k}':1-x});out['clkc']=0;s['ptr']-=1
    elif not a:out['clkc']=1
  if dict(out)!=history[-1][1]:history.append((t,dict(out)))
 failures=[];checks=0;change_times=[x[0] for x in history]
 # PGA output is continuous; only its clipping monitor has a smoothed target.
 pga_gain=[(0.,1.)];pga_metric_changes=[]
 if sid=='038':
  for et,en,ed in events:
   if en=='clk' and ed>0:
    gain=1. if bit(min(et+1e-16,ts[-1]),'rst') else p.get('gain_high',2.4) if bit(et,'gain_sel') else p.get('gain_low',.8)
    pga_gain.append((et,gain))
  gain_times=[x[0] for x in pga_gain]
  def pga_raw(t,gain=None):
   if gain is None:gain=pga_gain[bisect.bisect_right(gain_times,t)-1][1]
   return cm+gain*(val(t,'vin')-cm)
  def pga_metric(t):
   raw=pga_raw(t)
   return 0. if bit(t,'rst') else .9*int(raw<p.get('vmin',0) or raw>p.get('vmax',.9))
  if pga_metric(ts[0])!=0.:pga_metric_changes.append(ts[0])
  controls=[et for et,en,ed in events if en=='rst']+gain_times
  breaks=sorted(set(ts+controls))
  def record_metric_change(t):
   before=pga_metric(max(ts[0],t-1e-16));after=pga_metric(min(ts[-1],t+1e-16))
   if before!=after:pga_metric_changes.append(t)
  for t in controls:record_metric_change(t)
  for a,b in zip(breaks,breaks[1:]):
   mid=(a+b)/2
   if bit(mid,'rst'):continue
   gain=pga_gain[bisect.bisect_right(gain_times,mid)-1][1]
   x=pga_raw(a,gain);y=pga_raw(b,gain)
   for level in (p.get('vmin',0),p.get('vmax',.9)):
    if x<level<=y or x>level>=y:record_metric_change(a+(b-a)*(level-x)/(y-x))
  pga_metric_changes.sort()
 for r in rows:
  t=r['time'];j=bisect.bisect_right(change_times,t)-1;start,expected=history[j]
  if sid=='375':
   checks+=1
   if r['phi1']>(hi+lo)/2 and r['phi2']>(hi+lo)/2:
    if len(failures)<20:failures.append({'kind':'phase_overlap','time':t,'phi1':r['phi1'],'phi2':r['phi2']})
  if sid!='038' and t<start+tr*(4.1 if sid=='091' else 1.15):continue
  expected=dict(expected)
  if sid=='314':
   width=p.get('pulse',1e-9);last=max((x for x in toggles if x<=t),default=-1.)
   if abs(t-last-width)<tr*1.15:continue
   expected['toggled']=hi if last<=t<last+width and last>=0 and not bit(t,'rst') and bit(t,'enable') else lo
  if sid=='038':
   raw=pga_raw(t)
   expected.update(out=cm if bit(t,'rst') else clip(raw,p.get('vmin',0),p.get('vmax',.9)),metric=pga_metric(t))
   k=bisect.bisect_right(pga_metric_changes,t)-1
   if k>=0 and t<pga_metric_changes[k]+tr*1.15:
    # This exception is local to metric; the continuous output remains scored.
    del expected['metric']
    checks+=1
    if r['metric'] < -case.get('atol',.002) or r['metric']>.9+case.get('atol',.002):
     if len(failures)<20:failures.append({'kind':'metric_overshoot','time':t,'actual':r['metric']})
  if sid=='183':expected.update(cvinp=r['vrefp'],cvinn=r['vrefn'])
  for node,x in expected.items():
   checks+=1
   if abs(r[node]-x)>case.get('atol',.002):
    if len(failures)<20:failures.append({'time':t,'node':node,'expected':x,'actual':r[node]})
 if checks==0:raise ValueError('no scored hold observations')
 if sid=='024':
  eps=case.get('atol',.002);span=rows[0]['vdd']-rows[0]['vss']
  for k in range(1,len(history)):
   start,target=history[k];old=history[k-1][1]['out'];new=target['out'];end=history[k+1][0] if k+1<len(history) else ts[-1]
   window=[r for r in rows if start-0.1*tr<=r['time']<=min(end,start+1.2*tr)]
   if len(window)<4:raise ValueError('insufficient sample transition evidence')
   if any(r['out']<min(old,new)-eps or r['out']>max(old,new)+eps for r in window):failures.append({'kind':'sample_overshoot','event':start})
   sign=1 if new>=old else -1
   if any(sign*(b['out']-a['out']) < -eps for a,b in zip(window,window[1:])):failures.append({'kind':'sample_nonmonotonic','event':start})
   if abs(new-old)>=.1*span:
    began=next((r['time'] for r in window if abs(r['out']-old)>eps),None);finished=next((r['time'] for r in window if abs(r['out']-new)<=eps),None)
    if began is None or abs(began-start)>.1*tr+case.get('resolution',tr/4):failures.append({'kind':'sample_start','event':start,'actual':began})
    if finished is None or abs(finished-start-tr)>.1*tr+case.get('resolution',tr/4):failures.append({'kind':'sample_finish','event':start,'actual':finished})
 return {'passed':not failures,'checks':checks,'failures':failures,'source_id':sid,'contract_events':len(history)-1}
