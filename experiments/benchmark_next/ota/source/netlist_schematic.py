"""Translate the fixed JKU schematic using source symbol pin geometry.

Only the original transistor/ideal probe symbols occur in this source. Fail
closed on an unattached or ambiguously labelled pin; no model substitution.
"""
import re
from pathlib import Path
HERE=Path(__file__).resolve().parent

def netlist():
    text=(HERE/'ota-improved.sch').read_text()
    wires=[]
    for m in re.finditer(r'N (-?\d+) (-?\d+) (-?\d+) (-?\d+) \{([^}]*)\}',text):
        x,y,a,b=map(int,m.group(1,2,3,4)); lab=re.search(r'lab=([^\s}]+)',m[5])
        if lab:wires.append((x,y,a,b,lab[1].replace('#','')))
    def node(x,y):
        labs={lab for a,b,c,d,lab in wires if min(a,c)<=x<=max(a,c) and min(b,d)<=y<=max(b,d) and (a==c or b==d)}
        if not labs:return f"n_{x}_{abs(y)}"
        if len(labs)!=1:raise ValueError((x,y,labs))
        return labs.pop()
    result=['* (c) 2024-2025 Harald Pretl, Apache-2.0. Geometry transcription.','.subckt ota vinp vinn vout d_ena ibias_5u vdd vss']
    for m in re.finditer(r'C \{([^}]+)\} (-?\d+) (-?\d+) (\d) (\d) \{([^}]*)\}',text):
        symbol=m[1];x,y,r,f=map(int,m.group(2,3,4,5));props=m[6]
        def coord(a,b):
            if f:a=-a
            for _ in range(r):a,b=-b,a
            return node(x+a,y+b)
        name=re.search(r'name=([^\s]+)',props)[1]
        if '/sg13_lv_' in symbol:
            pm='pmos' in symbol
            pins=[coord(20,30 if pm else -30),coord(-20,0),coord(20,-30 if pm else 30),coord(20,0)]
            pars={k:re.search(r'\b'+k+r'=([^\s]+)',props)[1] for k in ('l','w','ng','m')}
            result.append('X'+name+' '+' '.join(pins)+' sg13_lv_'+('pmos' if pm else 'nmos')+' mm_ok=1 '+' '.join(k+'='+v for k,v in pars.items()))
        elif symbol.endswith('ammeter.sym'):
            result.append(name+' '+coord(0,-30)+' '+coord(0,30)+' 0')
    return '\n'.join(result+['.ends ota',''])
if __name__=='__main__':(HERE/'ota.spice').write_text(netlist())
