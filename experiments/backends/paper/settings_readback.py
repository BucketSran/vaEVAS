"""Scoped solver-control readback for frozen paper executions. No requested-value fallback; no waveform qualification."""
import hashlib
import math
import re

class ReadbackError(ValueError):
    pass

def numeric(token, dimension="dimensionless"):
    m = re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z]*)', token)
    if not m:
        raise ReadbackError('malformed numeric: ' + token)
    suffix = m[2]
    scale = {'':1., 's':1., 'V':1., 'A':1., 'ps':1e-12, 'ns':1e-9, 'us':1e-6, 'nV':1e-9, 'pA':1e-12}
    allowed={'dimensionless':{''}, 'time':{'','s','ps','ns','us'}, 'voltage':{'','V','nV'}, 'current':{'','A','pA'}}
    if suffix not in allowed[dimension]:
        raise ReadbackError('wrong dimension for '+dimension+': '+token)
    if suffix not in scale:
        raise ReadbackError('unsupported units: ' + suffix)
    v = float(m[1]) * scale[suffix]
    if not math.isfinite(v) or v <= 0:
        raise ReadbackError('nonpositive/nonfinite control')
    return v

def fact(value, line, raw, scope):
    return {'value':value, 'line':line, 'raw':raw, 'scope':scope}

def assignments(lines, mapping, scope, quoted=False):
    result = {}
    for n, raw in lines:
        for source, key in mapping.items():
            prefix = '"' + source + '"' if quoted else source
            if not re.match(r'^\s*' + re.escape(prefix) + r'(?:\s|=|$)', raw):
                continue
            pat = r'^\s*' + re.escape(prefix) + (r'\s+(.+?)\s*$' if quoted else r'\s*=\s*(.+?)\s*$')
            m = re.fullmatch(pat, raw)
            if not m:
                raise ReadbackError('malformed setting line: '+raw)
            if key == 'method' and quoted and not re.fullmatch(r'"[^"]+"',m[1]):
                raise ReadbackError('malformed quoted method')
            value = m[1].strip('"') if key == 'method' else numeric(m[1], {'vabstol_V':'voltage','iabstol_A':'current','maxstep_s':'time','stop_s':'time'}.get(key,'dimensionless'))
            if key == 'method' and value not in {'traponly','trap','gear2','gear2only'}:
                raise ReadbackError('unsupported/malformed method: '+value)
            if key in result:
                raise ReadbackError('duplicate/ambiguous setting: '+key)
            result[key] = fact(value, n, raw, scope)
    missing = set(mapping.values()) - set(result)
    if missing:
        raise ReadbackError('missing settings: '+str(sorted(missing)))
    return result

def spectre(log, psf, analysis='tran'):
    """Only accepts one named transient and crosschecks its log/PSF header."""
    lines = list(enumerate(log.splitlines(),1))
    trans = [(i,n,raw) for i,(n,raw) in enumerate(lines) if re.match(r'^Transient Analysis `',raw)]
    if len(trans) != 1 or not trans[0][2].startswith('Transient Analysis `'+analysis+"':"):
        raise ReadbackError('missing/ambiguous transient analysis')
    sections = [i for i,(_,raw) in enumerate(lines) if raw.strip()=='Important parameter values:']
    if len(sections)!=1 or sections[0] < trans[0][0]:
        raise ReadbackError('missing/ambiguous Important parameter block')
    start=sections[0]+1
    end=next((i for i in range(start,len(lines)) if not lines[i][1].strip()),len(lines))
    mapping={'reltol':'reltol','abstol(V)':'vabstol_V','abstol(I)':'iabstol_A','maxstep':'maxstep_s','stop':'stop_s','method':'method'}
    effective=assignments(lines[start:end],mapping,'transient:'+analysis)
    gs=[i for i,(_,raw) in enumerate(lines) if raw.strip()=='Global user options:']
    if len(gs)!=1 or gs[0] >= trans[0][0]:
        raise ReadbackError('missing/ambiguous global block')
    ge=next((i for i in range(gs[0]+1,len(lines)) if not lines[i][1].strip()),len(lines))
    global_options=assignments(lines[gs[0]+1:ge],{'reltol':'reltol','vabstol':'vabstol_V','iabstol':'iabstol_A'},'global_user')
    plines=list(enumerate(psf.splitlines(),1))
    types=[i for i,(_,raw) in enumerate(plines) if raw=='TYPE']
    if not plines or plines[0][1]!='HEADER' or len(types)!=1:
        raise ReadbackError('missing/ambiguous PSF header')
    header=plines[1:types[0]]
    names=[raw for _,raw in header if raw.startswith('"analysis name"')]
    kinds=[raw for _,raw in header if raw.startswith('"analysis type"')]
    if names!=['"analysis name" "'+analysis+'"'] or kinds!=['"analysis type" "tran"']:
        raise ReadbackError('PSF analysis identity mismatch')
    psf_effective=assignments(header,mapping,'psf_transient:'+analysis,quoted=True)
    relative=assignments(header,{'tolerance.relative':'tolerance.relative'},'psf_header',quoted=True)
    for key,v in effective.items():
        w=psf_effective[key]['value']
        if isinstance(w,str): equal=w==v['value']
        else: equal=math.isclose(w,v['value'],rel_tol=1e-12,abs_tol=0.)
        if not equal: raise ReadbackError('log/PSF disagreement: '+key)
    return {'effective':effective,'global_user':global_options,'psf_effective':psf_effective,'psf_relative_metadata':relative}

def ngspice(log, deck):
    """Final readback tied to exactly option→tran→wrdata→option script order.

    The first snapshot precedes .options application; final snapshot reports the
    loaded circuit. No intervening mutator is allowed. A failed run remains failed.
    """
    dl=list(enumerate(deck.splitlines(),1))
    begin=[i for i,(_,r) in enumerate(dl) if r.strip().lower()=='.control']
    end=[i for i,(_,r) in enumerate(dl) if r.strip().lower()=='.endc']
    if len(begin)!=1 or len(end)!=1 or end[0]<=begin[0]:
        raise ReadbackError('missing/ambiguous control block')
    commands=[(n,r.strip()) for n,r in dl[begin[0]+1:end[0]] if r.strip() and not r.lstrip().startswith('*')]
    def setup_command(command):
        return (command in {'set filetype=ascii','set wr_singlescale','set wr_vecnames'}
                or re.fullmatch(r'set numdgt=\d+',command)
                or re.fullmatch(r'pre_osdi [\w./-]+',command))
    for _,r in commands:
        if (r not in {'option','quit'} and not setup_command(r)
                and not r.startswith('tran ')
                and not re.fullmatch(r'wrdata [\w./-]+(?: v\([\w.#]+\))+',r)):
            raise ReadbackError('unsupported/mutable control command: '+r)
    opts=[i for i,(_,r) in enumerate(commands) if r=='option']
    trans=[i for i,(_,r) in enumerate(commands) if r.startswith('tran ')]
    if not opts or any(not setup_command(r) for _,r in commands[:opts[0]]):
        raise ReadbackError('unsupported pre-analysis commands')
    if len(opts)!=2 or len(trans)!=1 or trans[0]!=opts[0]+1 or opts[1]!=trans[0]+2 or not commands[trans[0]+1][1].startswith('wrdata '):
        raise ReadbackError('ambiguous analysis/options ordering or intervening command')
    if [r for _,r in commands[opts[1]+1:]] != ['quit']:
        raise ReadbackError('mutator/analysis after final readback')
    tokens=commands[trans[0]][1].split()
    if len(tokens)!=5 or tokens[3]!='0':
        raise ReadbackError('unsupported tran command shape')
    numeric(tokens[1], 'time'); stop=numeric(tokens[2], 'time'); maxstep=numeric(tokens[4], 'time')
    lines=list(enumerate(log.splitlines(),1))
    heads=[i for i,(_,r) in enumerate(lines) if r.strip()=='* Current simulation options *']
    if len(heads)!=2:
        raise ReadbackError('missing/ambiguous option snapshots')
    if any(re.match(r'^\s*(?:ngspice\s+\d+\s*->\s*)?(?:alter|reset|source)(?:\s|$)',r,re.I) for _,r in lines):
        raise ReadbackError('mutable command evidence in log')
    positions=[i for i,(_,r) in enumerate(lines) if 'Doing analysis at TEMP' in r]
    if len(positions)!=1 or not heads[0] < positions[0] < heads[1]:
        raise ReadbackError('missing/ambiguous analysis log')
    mapping={'reltol':'reltol','vntol':'vabstol_V','abstol':'iabstol_A'}
    def snapshot(start,end,scope):
        out={}
        for n,r in lines[start:end]:
            m=re.fullmatch(r'\s*(reltol|vntol|abstol)\s+\([^)]*\)\s*=\s*(.*)',r)
            if m:
                k=mapping[m[1]]
                if k in out: raise ReadbackError('duplicate/ambiguous snapshot setting')
                out[k]=fact(numeric(m[2], {'vabstol_V':'voltage','iabstol_A':'current'}.get(k,'dimensionless')),n,r,scope)
            elif re.match(r'\s*(reltol|vntol|abstol)\b',r):
                raise ReadbackError('malformed snapshot setting')
            if r.strip().startswith('Integration Method'):
                if 'method' in out: raise ReadbackError('ambiguous method')
                mm=re.fullmatch(r'\s*Integration Method = (TRAPEZOIDAL|GEAR)\s*',r)
                if not mm: raise ReadbackError('malformed/unsupported method')
                out['method']=fact({'TRAPEZOIDAL':'trap','GEAR':'gear'}[mm[1]],n,r,scope)
        if set(out)!={'reltol','vabstol_V','iabstol_A','method'}:
            raise ReadbackError('missing snapshot controls')
        return out
    initial=snapshot(heads[0],heads[1],'pre_analysis_initial_snapshot')
    final=snapshot(heads[1],len(lines),'post_analysis_loaded_circuit')
    return {'effective':final,'initial_snapshot':initial,'invocation_controls':{'stop_s':fact(stop,*commands[trans[0]],'deck_invocation_only'),'maxstep_s':fact(maxstep,*commands[trans[0]],'deck_invocation_only')},'limit':'maxstep/stop are deck invocation, not runtime readback; post snapshot alone does not prove successful run'}

def gnucap(log, parse_number):
    """Conservative global readback. Conflicting repeated values are ambiguous.

    Only the calibrated caret-question diagnostic format is recognized here.
    Its absence does not establish acceptance of every possible parser format.
    """
    if re.search(r'^\s*\^\s*\?\s*',log,re.M):
        raise ReadbackError('Gnucap deck parse error; settings are not qualified')
    actual={}; evidence={}
    for source,key in [('reltol','reltol'),('vntol','vabstol'),('abstol','iabstol')]:
        occurrences=[]
        for line,raw in enumerate(log.splitlines(),1):
            for match in re.finditer(r'\b'+source+r'=\s*(\S+)',raw):
                value=parse_number(match[1])
                if not math.isfinite(value) or value<=0:
                    raise ReadbackError('invalid Gnucap setting: '+source)
                occurrences.append(fact(value,line,raw,'global_options_occurrence'))
        if not occurrences:
            raise ReadbackError('missing effective setting: '+source)
        values=[item['value'] for item in occurrences]
        if any(not math.isclose(v,values[0],rel_tol=1e-12,abs_tol=0) for v in values):
            raise ReadbackError('ambiguous Gnucap setting: '+source)
        actual[key]=values[0]; evidence[key]=occurrences
    return {'actual':actual,'occurrences':evidence}

def file_identity(path):
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
