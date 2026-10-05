"""Strict Spectre-style voltage-testbench adapter into the existing EVAS API.

Every statement/option is consumed or rejected. Source corner construction is
separate from the output grid; this module never evaluates a circuit in Python.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
import math
from pathlib import Path
import re

from .errors import CompileError
from .frontend import Instance, compile_sources, parse_sources
from .node_elaboration import scalarize_nodes
from .parameters import bind_parameters
from .runtime import DEFAULT_TIMEOUT, transient
from .scs_sources import POINT_BUDGET, voltage_points
from .syntax import Token, _SUFFIX

_LEX = re.compile(r'(?P<space>[ \t\r]+)|(?P<continuation>\\[ \t]*\n)|(?P<comment>//[^\n]*)'
                  r'|(?P<newline>\n)|(?P<string>"[^"\n]*")'
                  r'|(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[TGMkKmunpfa]?)'
                  r'|(?P<name>[A-Za-z_][A-Za-z_0-9]*)|(?P<symbol>[()\[\]=+\-])')


def _fail(message, token, *, unsupported=False):
    raise CompileError(f'{token.source}:{token.line}:{token.column}: {message}',
                       code='unsupported_scs' if unsupported else 'scs_input', token=token)


def _statements(text, source):
    if len(text)>1_000_000:
        _fail('netlist exceeds 1 MB character budget',Token('', '',1,1,source))
    line,column,offset,count = 1,1,0,0
    statement,stack = [],[]
    while offset<len(text):
        match=_LEX.match(text,offset)
        token=Token(text[offset:offset+20], '',line,column,source)
        if match is None:
            _fail(f'unsupported netlist token {token.text!r}',token,unsupported=True)
        value,kind=match.group(),match.lastgroup
        token=Token(value,kind,line,column,source)
        if kind=='newline' and not stack:
            if statement:
                yield statement
                statement=[]
        elif kind not in ('space','continuation','comment','newline'):
            count+=1
            if count>100_000:
                _fail('netlist token budget (100000) exceeded',token)
            if value in ('(', '['):
                stack.append(')' if value=='(' else ']')
                if len(stack)>64:
                    _fail('netlist nesting budget exceeded',token)
            elif value in (')',']') and (not stack or stack.pop()!=value):
                _fail('unbalanced netlist delimiter',token)
            statement.append(token)
        if '\n' in value:
            line+=value.count('\n');column=len(value.rsplit('\n',1)[1])+1
        else:
            column+=len(value)
        offset=match.end()
    if stack:
        _fail('unclosed netlist delimiter',statement[-1])
    if statement:
        yield statement


class _Statement:
    def __init__(self,tokens,constants):
        self.tokens=tokens
        self.index=0
        self.constants=constants

    @property
    def token(self):
        return self.tokens[min(self.index,len(self.tokens)-1)]

    def fail(self,message,*,unsupported=False):
        _fail(message,self.token,unsupported=unsupported)

    def take(self,expected=None):
        if self.index==len(self.tokens):
            self.fail('incomplete netlist statement')
        token=self.token
        if expected is not None and token.text!=expected:
            self.fail(f'expected {expected!r}, got {token.text!r}')
        self.index+=1
        return token

    def done(self):
        if self.index!=len(self.tokens):
            self.fail('unsupported trailing netlist syntax',unsupported=True)

    def number(self):
        sign=1
        if self.token.text in ('+','-'):
            sign=-1 if self.take().text=='-' else 1
        token=self.take()
        if token.kind=='number':
            suffix=token.text[-1]
            value=float(token.text[:-1] if suffix in _SUFFIX else token.text)*_SUFFIX.get(suffix,1.)
        elif token.text in self.constants:
            value=self.constants[token.text]
        else:
            self.fail(f'expected a finite numeric literal or preceding constant, got {token.text!r}',unsupported=True)
        value*=sign
        if not math.isfinite(value):
            self.fail('numeric value must be finite')
        return value

    def settings(self):
        result={}
        while self.index<len(self.tokens):
            key=self.take()
            if key.kind!='name' or key.text in result:
                self.fail('duplicate or invalid setting name')
            self.take('=')
            if key.text in ('type','edgetype'):
                value=self.take().text
            elif self.token.text=='[':
                self.take('['); value=[]
                while self.token.text!=']':
                    value.append(self.number())
                self.take(']')
            else:
                value=self.number()
            result[key.text]=value
        return result


@dataclass
class ScsTestbench:
    sources: dict[str,str]
    manifest: dict
    save: list[str]
    metadata: dict


def load_scs(path: str | Path) -> ScsTestbench:
    path=Path(path).resolve()
    try:
        text=path.read_bytes().decode('utf-8')
    except (OSError,UnicodeError) as exc:
        _fail(str(exc),Token('', '',1,1,str(path)))
    constants, sources, devices, names = {},{},[],set()
    saved,tolerances,source_specs = [],{},[]
    transient_spec=None
    for tokens in _statements(text,str(path)):
        s=_Statement(tokens,constants)
        first=s.take()
        if first.text=='simulator':
            s.take('lang');s.take('=');s.take('spectre');s.done()
        elif first.text=='global':
            s.take('0');s.done()
        elif first.text=='ahdl_include':
            requested=s.take()
            if requested.kind!='string':
                s.fail('ahdl_include requires a quoted file path')
            s.done()
            model_path=(path.parent/requested.text[1:-1]).resolve()
            try:
                content=model_path.read_bytes().decode('utf-8')
            except (OSError,UnicodeError) as exc:
                _fail(f'cannot read ahdl_include: {exc}',requested)
            if str(model_path) in sources:
                s.fail('duplicate ahdl_include')
            sources[str(model_path)]=content
        elif first.text=='parameters':
            values=s.settings()
            if set(values)&constants.keys() or any(not isinstance(v,float) for v in values.values()):
                s.fail('duplicate or non-scalar netlist constant')
            constants.update(values)
        elif first.text=='save':
            while s.index<len(s.tokens):
                net=s.take()
                if net.kind not in ('name','number'):
                    s.fail('save supports scalar node names only',unsupported=True)
                if net.text not in saved:
                    saved.append(net.text)
        elif s.index<len(s.tokens) and s.token.text=='(':
            if first.text in names:
                s.fail('duplicate device/instance name')
            names.add(first.text)
            s.take('('); nodes=[]
            while s.token.text!=')':
                token=s.take()
                if token.kind not in ('name','number'):
                    s.fail('only scalar net connections are supported',unsupported=True)
                nodes.append(token.text)
            s.take(')');module=s.take().text;settings=s.settings()
            if module=='vsource':
                if len(nodes)!=2 or (nodes[0]!='0' and nodes[1]!='0') or nodes[0]==nodes[1]:
                    s.fail('vsource requires one ground terminal and one distinct driven node',unsupported=True)
                source_specs.append((nodes,settings,first))
            elif module in ('resistor','capacitor','inductor','isource','r','c','l'):
                s.fail(f'{module} requires electrical network support (#68)',unsupported=True)
            else:
                if any(not isinstance(v,float) for v in settings.values()):
                    s.fail('instance parameters must be scalar numeric constants')
                devices.append((first,nodes,module,settings))
        elif s.index<len(s.tokens) and s.token.text in ('options','tran'):
            kind=s.take().text
            settings=s.settings()
            allowed={'vabstol','reltol'} if kind=='options' else {'stop','maxstep'}
            if set(settings)-allowed:
                s.fail(f'unsupported {kind} settings: {sorted(set(settings)-allowed)}',unsupported=True)
            if any(not isinstance(v,float) for v in settings.values()):
                s.fail('analysis settings must be scalar numbers')
            if kind=='options':
                if set(settings)&tolerances.keys():
                    s.fail('duplicate tolerance setting')
                tolerances.update(settings)
            else:
                if transient_spec is not None or set(settings)!=allowed:
                    s.fail('exactly one tran with explicit stop and maxstep is required')
                transient_spec=settings
        else:
            s.fail(f'unsupported netlist statement {first.text!r}',unsupported=True)

    eof=Token('', '',max(1,len(text.splitlines())),1,str(path))
    def fail(message,*,unsupported=False):
        _fail(message,eof,unsupported=unsupported)
    if not sources or not devices or transient_spec is None:
        fail('testbench requires ahdl_include, a VA instance, and tran')
    stop,step=transient_spec['stop'],transient_spec['maxstep']
    if stop<=0 or step<=0 or any(v<0 for v in tolerances.values()):
        fail('stop/maxstep must be positive; tolerances must be nonnegative')
    count=int(Q(stop)//Q(step))
    if count+2>POINT_BUDGET:
        fail('output point budget (100000) exceeded; increase maxstep')
    times=[float(i*Q(step)) for i in range(count+1) if i*Q(step)<Q(stop)]+[stop]
    if any(a>=b for a,b in zip(times,times[1:])):
        fail('output times collapse at binary64 resolution')
    waveforms,rounding={},{}
    for nodes,settings,token in source_specs:
        def source_fail(message,*,unsupported=False):
            _fail(message,token,unsupported=unsupported)
        net=nodes[0] if nodes[1]=='0' else nodes[1]
        if net in waveforms:
            source_fail('multiple voltage sources drive the same node')
        points,error=voltage_points(settings,stop,source_fail)
        waveforms[net]=[[t,v if nodes[1]=='0' else -v] for t,v in points]
        rounding[token.text]=error
    models=parse_sources(sources)
    instances=[]
    for token,nodes,name,settings in devices:
        if name not in models:
            _fail(f'unknown VA module or unsupported device {name!r}',token,unsupported=True)
        module=models[name]
        parameters=bind_parameters(module,settings,token.text)
        expanded,_=scalarize_nodes(module,parameters)
        if len(nodes)!=len(expanded.ports):
            _fail(f'instance {token.text!r} requires {len(expanded.ports)} scalar ports in declared order',token)
        instances.append(dict(name=token.text,module=name,connections=dict(zip(expanded.ports,nodes)),parameters=settings))
    available={'0',*waveforms,*[net for i in instances for net in i['connections'].values()]}
    if not set(saved)<=available:
        fail(f'save names unknown scalar nodes: {sorted(set(saved)-available)}')
    if not set(waveforms)<=set(net for i in instances for net in i['connections'].values()):
        fail('every driven source must connect to a declared model port')
    effective=dict(vabstol=1e-12,reltol=1e-10)
    effective.update(tolerances)
    manifest=dict(models=list(sources),instances=instances,tolerances=effective,
                  transient=dict(sources=waveforms,output_times=times,stop=stop,max_step=step))
    metadata=dict(input_format='spectre-voltage-subset',path=str(path),sha256=hashlib.sha256(text.encode()).hexdigest(),
                  model_sha256={p:hashlib.sha256(t.encode()).hexdigest() for p,t in sources.items()},
                  effective_tolerances=effective,output_grid='0, k*maxstep below stop, stop',
                  pulse_corner_rounding_seconds=rounding)
    return ScsTestbench(sources,manifest,saved,metadata)


def simulate_scs(path: str | Path, *, kernel, timeout=DEFAULT_TIMEOUT):
    bench=load_scs(path)
    program=compile_sources(bench.sources,[Instance(**i) for i in bench.manifest['instances']])
    result=transient(program,kernel=kernel,timeout=timeout,
                     **bench.manifest['transient'],**bench.manifest['tolerances'])
    saved=bench.save or list(result['nodes'])
    indices=[result['nodes'].index(n) for n in saved]
    return dict(result,testbench=bench.metadata,saved=dict(nodes=saved,times=bench.manifest['transient']['output_times'],
                values=[[row['voltages'][i] for i in indices] for row in result['solutions']]))
