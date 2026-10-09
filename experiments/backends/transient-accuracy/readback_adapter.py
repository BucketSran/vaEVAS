"""Narrow unit adaptation for the frozen maintained Spectre settings reader.

Original log/PSF bytes stay unchanged. Every conversion is recorded explicitly.
"""
from decimal import Decimal
import re

UNITS={'ms':('time',Decimal('0.001')),'pV':('voltage',Decimal('1e-12')),'fA':('current',Decimal('1e-15'))}
FIELDS={'maxstep':'time','stop':'time','abstol(V)':'voltage','abstol(I)':'current'}

def normalize(text,role):
    changes=[];lines=text.splitlines()
    pat=re.compile(r'^(\s*("?)(maxstep|stop|abstol\(V\)|abstol\(I\))\2(?:\s*=\s*|\s+))([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(ms|pV|fA)\s*$')
    for i,line in enumerate(lines):
        m=pat.fullmatch(line)
        if not m:continue
        dimension,scale=UNITS[m[5]]
        if dimension!=FIELDS[m[3]]:raise ValueError('unit dimension mismatch')
        value=Decimal(m[4])*scale
        if not value.is_finite() or value<=0:raise ValueError('invalid control')
        lines[i]=m[1]+format(value,'E')
        changes.append({'role':role,'line':i+1,'original_raw':line,'normalized_raw':lines[i],'unit':m[5],'SI_value':str(value)})
    return '\n'.join(lines),changes

def spectre(reader,log,psf):
    l,lc=normalize(log,'log');p,pc=normalize(psf,'psf');result=reader.spectre(l,p)
    changes=lc+pc
    for section,role in [('effective','log'),('global_user','log'),('psf_effective','psf')]:
        for fact in result.get(section,{}).values():
            c=next((c for c in changes if c['role']==role and c['line']==fact['line']),None)
            if c:fact.update(raw=c['original_raw'],normalized_raw=c['normalized_raw'])
    result['unit_adaptations']=changes
    result['claim']='actual log/PSF settings with recorded SI unit conversion, not numeric/export qualification'
    return result
