"""SEF extension: filter-root callbacks under the unchanged engineering budgets."""
import copy
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import contract as sef

CASES = copy.deepcopy(sef.CASES)
for c in CASES:
    c['id'] = c['id'].replace('SEF-', 'SFC-')
    for p in c['instances']:
        p['threshold'] = .45 if p['name']=='a' else -.06
        p['direction'] = 0


def roots(p):
    """Each affine forcing segment has at most one derivative zero.

    y'=m+(y'(a)-m)*exp(-(t-a)/tau). Split at that explicit stationary
    point, then bisect the independent analytical convolution on monotone arcs.
    No EVAS solver or output contributes to this oracle.
    """
    knots=sef.segments(p); result=[]; tau=p['tau']; threshold=p['threshold']
    for i,(a,edge,m) in enumerate(knots):
        a=float(a); b=float(knots[i+1][0]) if i+1<len(knots) else 8.5
        if b<=a:continue
        m=float(m); d0=(float(edge)-sef.filter_value(p,a))/tau
        cuts=[a,b]
        ratio=-m/(d0-m) if d0!=m else -1
        if 0<ratio<1:
            critical=a-tau*math.log(ratio)
            if a<critical<b:cuts.insert(1,critical)
        for left,right in zip(cuts,cuts[1:]):
            fl=sef.filter_value(p,left)-threshold
            fr=sef.filter_value(p,right)-threshold
            if fl*fr>=0:continue
            direction=1 if fl<fr else -1
            if p['direction'] not in (0,direction):continue
            for _ in range(80):
                mid=(left+right)*.5
                if mid==left or mid==right:break
                fm=sef.filter_value(p,mid)-threshold
                if (fm<0)==(fl<0):left=mid
                else:right=mid
            result.append(((left+right)*.5,direction))
    return result


def ports(c):return ['u','clk','rst',*[p['name']+x for p in c['instances'] for x in 'hefncs']]


def source(c):
    text=sef.source(c)
    for p in c['instances']:
        name=p['name']
        text=text.replace(f'module cell_{name}(u,clk,rst,h,e,f,n);', f'module cell_{name}(u,clk,rst,h,e,f,n,c,s);')
        text=text.replace(f'cell_{name} {name}(u,clk,rst,{name}h,{name}e,{name}f,{name}n);', f'cell_{name} {name}(u,clk,rst,{name}h,{name}e,{name}f,{name}n,{name}c,{name}s);')
        begin=text.index(f'module cell_{name}(');end=text.index('end endmodule',begin)
        body=text[begin:end]
        body=body.replace('output h,e,f,n; electrical u,clk,rst,h,e,f,n;', 'output h,e,f,n,c,s; electrical u,clk,rst,h,e,f,n,c,s;')
        body=body.replace('real q; integer count;', 'real q,sample; integer count,cross_count;')
        body=body.replace('count=0; end', 'count=0; cross_count=0; sample=0; end')
        body+=f'@(cross(V(f)-({p["threshold"]}),{p["direction"]},1e-13,1e-10)) begin cross_count=cross_count+1; sample=V(u); end\nV(c)<+cross_count; V(s)<+sample;\n'
        text=text[:begin]+body+text[end:]
    old=[p['name']+x for p in c['instances'] for x in 'hefn'];new=ports(c)[3:]
    text=text.replace('module dut('+','.join(['u','clk','rst',*old])+');', 'module dut('+','.join(ports(c))+');')
    text=text.replace('output '+','.join(old)+'; electrical '+','.join(['u','clk','rst',*old])+';', 'output '+','.join(new)+'; electrical '+','.join(ports(c))+';')
    return text


def times(c,dense=False,*,root_centers=True):
    ts=set(sef.times(c,dense))
    for p in c['instances']:
        for t,_ in roots(p):
            offsets = [-4e-12,-2e-12,2e-12,4e-12]
            if root_centers: offsets.append(0)
            ts.update(t*sef.T+d for d in offsets)
    return sorted(ts)


def assess(c,rows):
    result=sef.assess(c,rows)
    failures=result['failures']; errors=result.get('maximum_errors_V',{})
    if not rows or 'missing or nonfinite observation' in failures:
        return result
    def fail(reason):
        if reason not in failures:failures.append(reason)
    for p in c['instances']:
        name=p['name']; expected=roots(p); prev=0;last_t=0
        errors[name+'s']=0.;brackets=[]
        for r in rows:
            count=r.get(name+'c',math.nan); actual=r.get(name+'s',math.nan);t=r['time']
            if (not isinstance(count,(int,float)) or not isinstance(actual,(int,float)) or
                not math.isfinite(count) or abs(count-round(count))>1e-10 or not math.isfinite(actual)):
                fail('invalid cross observation '+name);continue
            count=round(count)
            legal=[i for i in range(len(expected)+1) if (i==0 or expected[i-1][0]*sef.T<=t+sef.TIME_BUDGET) and (i==len(expected) or expected[i][0]*sef.T>=t-sef.TIME_BUDGET)]
            if count not in legal:fail('cross count/time '+name)
            if count<prev or count>prev+1:fail('cross order '+name)
            if count==prev+1:
                target=expected[count-1][0]*sef.T if count<=len(expected) else math.inf
                brackets.append({'lo_s':last_t,'hi_s':t,'nominal_s':target})
                if last_t<target-sef.TIME_BUDGET or t>target+sef.TIME_BUDGET:fail('cross bracket '+name)
            nominal=0 if count==0 else float(sef.pwl(sef.INPUT,expected[count-1][0])) if 0<count<=len(expected) else math.inf
            error=abs(actual-nominal);errors[name+'s']=max(errors[name+'s'],error)
            if error>sef.VOLTAGE_BUDGET:fail('cross sample '+name)
            prev=count;last_t=t
        if prev!=len(expected):fail('cross final count '+name)
        result.setdefault('cross_brackets',{})[name]=brackets
    result['status']='PASS' if not failures else 'FAIL'
    result['maximum_errors_V']=errors
    return result

if __name__=='__main__':
    for c in CASES:print(c['id'], {p['name']:roots(p) for p in c['instances']})
