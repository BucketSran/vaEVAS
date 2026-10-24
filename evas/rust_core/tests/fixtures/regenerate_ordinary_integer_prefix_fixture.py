"""Regenerate the original ordinary integer fixture through public compilation.

The oracle rounds every source real operation with integer quotient/remainder;
it does not use EVAS evaluation or float(Fraction). Physical PWL interpolation
and Transition remain exact rational mathematics between source RN boundaries.
"""
from fractions import Fraction as R
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys


def rn(value):
    value=R(value)
    if not value:return 0.
    sign=-1 if value<0 else 1
    value=abs(value);n,d=value.numerator,value.denominator
    exponent=n.bit_length()-d.bit_length()
    if (n<d<<exponent) if exponent>=0 else (n<<(-exponent)<d):exponent-=1
    shift=max(exponent-52,-1074)
    numerator,denominator=(n,d<<shift) if shift>=0 else (n<<(-shift),d)
    quotient,remainder=divmod(numerator,denominator)
    if 2*remainder>denominator or (2*remainder==denominator and quotient%2):quotient+=1
    return sign*math.ldexp(float(quotient),shift)


def prefix(value):
    sample=rn(value)
    divide=rn(R(sample)/R(.9))
    multiply=rn(R(divide)*15)
    add=rn(R(multiply)+R(1,2))
    return max(1,math.floor(add)),[sample,divide,multiply,add]


def input_at(time,points):
    time=R(time)
    for (t0,v0),(t1,v1) in zip(points,points[1:]):
        if R(t0)<=time<=R(t1):return R(v0)+(R(v1)-R(v0))*(time-R(t0))/(R(t1)-R(t0))
    return R(points[0][1] if time<R(points[0][0]) else points[-1][1])


def oracle(request):
    assert rn(R(2**53+1))==float(2**53)
    assert rn(R(2**53+3))==float(2**53+4)
    assert rn(R(1)+R(1,2**53))==1.
    points=request['transient']['pwl'][0]
    rows=[]
    for time in [.125,.5,.875]:
        q,steps=prefix(input_at(time,points));rows.append({'time':time,'ratio':q,'q':q,'bit':q&1,'steps':[x.hex() for x in steps],'display':f'ratio={q} q={q} keep=7'})
    assert [x['q'] for x in rows]==[1,3,3]
    assert [x['bit'] for x in rows]==[1,1,1]
    assert math.floor(R(.15)/R(.9)*15+R(1,2))==2
    return {'callbacks':rows,'old_continuous_mathematical_floor_at_binary_point15':2,'new_each_source_operation_RN_floor_at_binary_point15':3}


def generated():
    fixtures=Path(__file__).resolve().parent
    source=fixtures/'ordinary_integer_prefix_joint.va'
    assert hashlib.sha256(source.read_bytes()).hexdigest()=='90661323d08a953b0190224bd5bfa2a5504756930d5fd35b8738a5d2db1c06fe'
    sys.path.insert(0,str(fixtures.parents[2]/'src'))
    from evas import compile_sources,Instance
    request=json.loads((fixtures/'ordinary_integer_prefix_joint.request.json').read_text())
    request['program']=compile_sources({source.name:source.read_text()},[Instance('M','joint',dict(u='u',y='y',h='h'))]).to_dict()
    return request


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');parser.add_argument('--oracle-only',action='store_true');args=parser.parse_args()
    path=Path(__file__).resolve().with_name('ordinary_integer_prefix_joint.request.json')
    request=json.loads(path.read_text()) if args.oracle_only else generated()
    print(json.dumps(oracle(request),indent=2))
    if not args.oracle_only:
        data=json.dumps(request,indent=2)+'\n'
        if args.write:path.write_text(data)
        else:assert path.read_text()==data,'fixture differs from current public compiler output'


if __name__=='__main__':main()
