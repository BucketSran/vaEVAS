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
import warnings

from .errors import CompileError
from .frontend import Instance, compile_sources, parse_sources
from .node_elaboration import scalarize_nodes
from .parameters import bind_parameters
from .runtime import DEFAULT_TIMEOUT, transient
from .scs_sources import POINT_BUDGET, voltage_points, analytic_source
from .syntax import Token, _SUFFIX
from .strobe import FIELDS as STROBE_FIELDS, expand as expand_strobe

_LEX = re.compile(r'(?P<space>[ \t\r]+)|(?P<continuation>\\[ \t]*\n)|(?P<comment>//[^\n]*)'
                  r'|(?P<newline>\n)|(?P<string>"[^"\n]*")'
                  r'|(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:Meg|[TGMkKmunpfa])?)'
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
        self.setting_tokens={}

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
            if token.text.endswith('Meg'):
                value=float(token.text[:-3])*1e6
            else:
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

    def settings(self, *, symbolic=()):
        result={}
        while self.index<len(self.tokens):
            key=self.take()
            if key.kind!='name' or key.text in result:
                self.fail('duplicate or invalid setting name')
            self.setting_tokens[key.text]=key
            self.take('=')
            if key.text in ('type','edgetype') or key.text in symbolic:
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

    def voltage_expression(self):
        """Consume the bounded subset V(node) [+- constant] used by bsource."""
        self.take('v');self.take('=');self.take('V');self.take('(')
        node=self.take()
        if node.kind not in ('name','number'):
            self.fail('bsource requires a scalar voltage node',unsupported=True)
        self.take(')')
        offset=0.
        if self.index<len(self.tokens) and self.token.text in ('+','-'):
            sign=-1 if self.take().text=='-' else 1
            grouped=self.token.text=='('
            if grouped:
                self.take('(')
            offset=sign*self.number()
            if grouped:
                self.take(')')
        self.done()
        return node,offset


def _zero_current_source(token, nodes, settings, statement):
    """Prove only a literal zero, preserving every consumed field's source."""
    if len(nodes)!=2 or nodes[0]==nodes[1]:
        _fail('isource requires two distinct scalar terminals',token,unsupported=True)
    if set(settings)-{'type','dc'} or 'dc' not in settings or settings.get('type','dc')!='dc':
        _fail('isource accepts only explicit exact-zero dc and optional type=dc',token,unsupported=True)
    if not isinstance(settings['dc'],float):
        _fail('isource dc requires a scalar exact-zero numeric literal',token,unsupported=True)
    # General settings parsing above already consumed/rejected all syntax and
    # numeric legality. Only accepted <=2 fields are inspected again here.
    positions={id(value):i for i,value in enumerate(statement.tokens)}
    starts=sorted((positions[id(value)],key) for key,value in statement.setting_tokens.items())
    fields=[]
    for k,(start,key) in enumerate(starts):
        end=starts[k+1][0] if k+1<len(starts) else len(statement.tokens)
        values=statement.tokens[start+2:end]
        fields.append(dict(name=key,value=settings[key],
            location=dict(source=statement.tokens[start].source,line=statement.tokens[start].line,
                          column=statement.tokens[start].column),
            tokens=[dict(text=x.text,kind=x.kind,source=x.source,line=x.line,column=x.column) for x in values]))
        if key=='dc':
            dc_tokens=values
    original=''.join(value.text for value in dc_tokens)
    number=dc_tokens[1:] if dc_tokens and dc_tokens[0].text in ('+','-') else dc_tokens
    if len(number)!=1 or number[0].kind!='number':
        _fail('isource zero proof requires an original numeric literal, not a parameter',token,unsupported=True)
    spelling=number[0].text
    if spelling[-1] in _SUFFIX:
        spelling=spelling[:-1]
    mantissa=re.split('[eE]',spelling,maxsplit=1)[0]
    # A decimal/SI literal is zero iff every mantissa digit is zero. The
    # exponent/suffix cannot turn nonzero into exact zero, even if float underflows.
    if any(digit in '123456789' for digit in mantissa):
        _fail('nonzero isource requires electrical network support (#68)',token,unsupported=True)
    return dict(name=token.text,device='isource',terminals=list(nodes),settings=dict(settings),fields=fields,
                origin=dict(source=token.source,line=token.line,column=token.column),
                proof=dict(kind='exact_zero_dc_literal',dc_literal=original,current_A='0'))


OUTPUT_GRID=('union of 0, k*h below stop with h=min(maxstep, positive unconditional constant $bound_step), '
             'stop, source corners within stop')


@dataclass
class ScsTestbench:
    sources: dict[str,str]
    manifest: dict
    save: list[str]
    metadata: dict
    tran_token: Token | None = None


def _regular_times(stop,step):
    # A mathematical interior point can round to stop. It denotes the same
    # binary64 observation, so retain the explicit endpoint exactly once.
    count=int(Q(stop)//Q(step))
    if count+2>POINT_BUDGET:
        return None
    return [t for i in range(count+1) if (t:=float(i*Q(step)))<stop]+[stop]


def _saved_output_times(times,stop,strobe,save_policy,forced):
    if not forced:
        return times
    regular=times
    if save_policy=='strobeonly':
        start,end=strobe.get('skipstart',0.),strobe.get('skipstop',stop)
        regular=[t for t in times if t<start or t>end] if 'strobeperiod' in strobe else []
    # Spectre retains the terminal observation even when it is not a
    # forced point; outside the periodic window ordinary rows remain.
    return sorted(set(regular).union(forced,[stop]))


def _bound_step(program,step):
    """Grid spacing implied by unconditional constant $bound_step requests.

    LRM 2.4 makes $bound_step the model's own maximum time step. Only a
    positive constant with a constant nonzero activation has a fixed grid; a
    dynamic or zero request still limits the kernel step but adds no rows."""
    from .ir import Affine
    h=step
    for bound in program.step_bounds:
        value,active=bound.value,bound.active
        if (isinstance(value,Affine) and isinstance(active,Affine) and not value.terms
                and not active.terms and active.constant!=0 and value.constant>0):
            h=min(h,value.constant)
    return h


class ScsIgnoredOptionWarning(UserWarning):
    """An accepted SCS setting with no effect on the voltage-domain request."""

    def __init__(self, report):
        self.report=report
        super().__init__(report['message'])


def _warn_ignored(token,value,message,reports,**details):
    report=dict(code='ignored_scs_option',severity='warning',option=token.text,requested_value=value,
                message=message,location=dict(source=token.source,line=token.line,column=token.column),**details)
    reports.append(report)
    warnings.warn_explicit(ScsIgnoredOptionWarning(report),ScsIgnoredOptionWarning,token.source,token.line)


def load_scs(path: str | Path) -> ScsTestbench:
    path=Path(path).resolve()
    try:
        text=path.read_bytes().decode('utf-8')
    except (OSError,UnicodeError) as exc:
        _fail(str(exc),Token('', '',1,1,str(path)))
    constants, sources, devices, names = {},{},[],set()
    sine_source_origins={}
    saved,tolerances,source_specs = [],{},[]
    seen_options,warning_reports=set(),[]
    behavioral_sources=[]
    zero_current_sources=[]
    preset=None
    save_policy=None
    transient_spec,tran_token=None,None
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
            s.take(')');module=s.take().text
            if module=='bsource':
                if len(nodes)!=2 or (nodes[0]!='0' and nodes[1]!='0') or nodes[0]==nodes[1]:
                    s.fail('bsource requires one ground terminal and one distinct output node',unsupported=True)
                reference,offset=s.voltage_expression()
                behavioral_sources.append((first,nodes,reference,offset))
                continue
            settings=s.settings()
            if module=='vsource':
                if len(nodes)!=2 or nodes[0]==nodes[1]:
                    s.fail('vsource requires two distinct scalar terminals',unsupported=True)
                source_specs.append((nodes,settings,first))
                if settings.get('type')=='sine':
                    sine_source_origins[first.text]=dict(
                        dialect='spectre-native',analysis='tran',settings=dict(settings),
                        tokens=[dict(text=t.text,kind=t.kind,source=t.source,
                                     line=t.line,column=t.column) for t in s.tokens])
            elif module=='isource':
                zero_current_sources.append(_zero_current_source(first,nodes,settings,s))
            elif module in ('resistor','capacitor','inductor','r','c','l'):
                s.fail(f'{module} requires electrical network support (#68)',unsupported=True)
            else:
                if any(not isinstance(v,float) for v in settings.values()):
                    s.fail('instance parameters must be scalar numeric constants')
                devices.append((first,nodes,module,settings))
        elif s.index<len(s.tokens) and s.token.text in ('options','tran'):
            kind=s.take().text
            settings=s.settings(symbolic={'errpreset','strobeoutput'} if kind=='tran' else ())
            allowed={'vabstol','reltol','iabstol'} if kind=='options' else {'stop','maxstep','errpreset','strobeoutput'} | STROBE_FIELDS
            if set(settings)-allowed:
                s.fail(f'unsupported {kind} settings: {sorted(set(settings)-allowed)}',unsupported=True)
            if any(not isinstance(v,list if k=='strobetimes' else str if k in ('errpreset','strobeoutput') else float) for k,v in settings.items()):
                s.fail('analysis settings must be scalar numbers')
            if kind=='options':
                if set(settings)&seen_options:
                    s.fail('duplicate tolerance setting')
                seen_options.update(settings)
                if 'iabstol' in settings:
                    value=settings.pop('iabstol')
                    if value<0:
                        s.fail('iabstol must be nonnegative')
                    _warn_ignored(s.setting_tokens['iabstol'],value,
                                  'iabstol is ignored and has no effect: EVAS has no current unknowns.',warning_reports)
                tolerances.update(settings)
            else:
                if transient_spec is not None or not {'stop','maxstep'} <= settings.keys():
                    s.fail('exactly one tran with explicit stop and maxstep is required')
                if 'errpreset' in settings:
                    value=settings.pop('errpreset')
                    if value not in ('liberal','moderate','conservative'):
                        s.fail('errpreset must be liberal, moderate, or conservative',unsupported=True)
                    preset=(s.setting_tokens['errpreset'],value)
                if 'strobeoutput' in settings:
                    save_policy=settings.pop('strobeoutput')
                    if save_policy not in ('all','strobeonly'):
                        s.fail('strobeoutput must be all or strobeonly',unsupported=True)
                transient_spec,tran_token=settings,first
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
    effective=dict(vabstol=1e-12,reltol=1e-10)
    effective.update(tolerances)
    if preset:
        token,value=preset
        _warn_ignored(token,value,
                      f'errpreset={value} is ignored: Spectre preset adjustments are not applied. '
                      f'EVAS uses reltol={effective["reltol"]:g}, vabstol={effective["vabstol"]:g}, max_step={step:g}.',
                      warning_reports,effective_controls=dict(effective,max_step=step))
    strobe={k:v for k,v in transient_spec.items() if k in STROBE_FIELDS}
    try:
        forced=expand_strobe(stop,**strobe) if strobe else []
    except ValueError as exc:
        fail(str(exc))
    times=_regular_times(stop,step)
    if times is None:
        fail('output point budget (100000) exceeded; increase maxstep')
    if any(a>=b for a,b in zip(times,times[1:])):
        fail('output times collapse at binary64 resolution')
    waveforms,rounding,source_errors,pulse_proofs,source_shapes={},{},{},{},{}
    analytic_sources={}
    occupied={'0',*saved,*[n for nodes,_,_ in source_specs for n in nodes],
              *[n for _,nodes,_,_ in devices for n in nodes],
              *[n for _,nodes,_,_ in behavioral_sources for n in nodes],
              *[reference.text for _,_,reference,_ in behavioral_sources],
              *[node for entry in zero_current_sources for node in entry['terminals']]}
    internal_source_nodes=[]
    for nodes,settings,token in source_specs:
        def source_fail(message,*,unsupported=False):
            _fail(message,token,unsupported=unsupported)
        floating='0' not in nodes
        net=nodes[0] if nodes[1]=='0' else nodes[1]
        if floating:
            # Preserve the source's differential equation in the coupled solve.
            # The original waveform and its uncertainty drive a private input;
            # no reference voltage is guessed or sampled in the adapter.
            net='__evas_scs_voltage'
            while net in occupied:
                net+='_'
            occupied.add(net)
            internal_source_nodes.append(net)
            reference=Token(net,'name',token.line,token.column,token.source)
            behavioral_sources.append((token,nodes,reference,0.))
        if net in waveforms:
            source_fail('multiple voltage sources drive the same node')
        if settings.get('type')=='sine':
            analytic_sources[net]=analytic_source(settings,nodes,token.text,source_fail)
            sine_source_origins[token.text]['parameter_origin']=analytic_sources[net]['parameter_origin']
            waveforms[net]=[]
            continue
        points,error,proof=voltage_points(settings,stop,source_fail)
        waveforms[net]=[[t,v if floating or nodes[1]=='0' else -v] for t,v in points]
        rounding[token.text]=error
        if proof is not None:
            shape = proof.pop('source_shape',None)
            pulse_proofs[token.text]=proof
            if proof['voltage_error_bound_V']>0:
                source_errors[net]=proof['voltage_error_bound_V']
                if shape is not None:
                    sign = 1 if floating or nodes[1]=='0' else -1
                    source_shapes[net]=[dict(knot,value_V=sign*knot['value_V']) for knot in shape]
    # Keep the physical PWL definition intact. Saving every source corner
    # prevents a later linear interpolation of the saved drive from skipping
    # a pulse or replacing a piecewise-linear segment by a different line.
    times=sorted(set(times).union(t for points in waveforms.values() for t,_ in points if 0<=t<=stop))
    if len(times)>POINT_BUDGET:
        fail('output point budget (100000) exceeded after including source corners')
    saved_times=times
    if save_policy is not None:
        if (save_policy=='strobeonly' and 'strobeperiod' in strobe
                and not expand_strobe(stop,**{k:v for k,v in strobe.items() if k!='strobetimes'})):
            fail('strobeonly with an empty periodic schedule is not yet supported',unsupported=True)
        saved_times=_saved_output_times(times,stop,strobe,save_policy,forced)
        if len(saved_times)>POINT_BUDGET:
            fail('saved output point budget (100000) exceeded')
    models=parse_sources(sources)
    instances=[]
    for token,nodes,name,settings in devices:
        if name not in models:
            _fail(f'unknown VA module or unsupported device {name!r}',token,unsupported=True)
        module=models[name]
        try:
            parameters=bind_parameters(module,settings,token.text)
            expanded,_=scalarize_nodes(module,parameters)
        except CompileError as exc:
            # Preserve a more precise VA origin, otherwise identify the SCS instance.
            exc.diagnostic.setdefault('location', dict(source=token.source, line=token.line, column=token.column))
            exc.diagnostic.setdefault('instance', token.text)
            raise
        if len(nodes)!=len(expanded.ports):
            _fail(f'instance {token.text!r} requires {len(expanded.ports)} scalar ports in declared order',token)
        instances.append(dict(name=token.text,module=name,connections=dict(zip(expanded.ports,nodes)),parameters=settings))
    model_sha256={p:hashlib.sha256(t.encode()).hexdigest() for p,t in sources.items()}
    generated_sha256={}
    # Build original VA/source topology once. Zero-current branches never add
    # nodes, voltage constraints, inputs or generated instances to this set.
    available={'0',*waveforms,*[net for i in instances for net in i['connections'].values()],
               *[net for _,nodes,_,_ in behavioral_sources for net in nodes]}
    if behavioral_sources:
        driven=set(waveforms)
        module_name='__evas_scs_bsource'
        while module_name in models:
            module_name+='_'  # Do not shadow a user model.
        generated_path=str(path)+'.bsource.va'
        while generated_path in sources:
            generated_path+='.va'
        generated=('`include "disciplines.vams"\n'
                   f'module {module_name}(p,n,u,g); inout p,n,g; input u; electrical p,n,u,g; '
                   'parameter real offset=0; analog begin V(p,n)<+V(u,g)+offset; end endmodule\n')
        for token,nodes,reference,offset in behavioral_sources:
            net=nodes[0] if nodes[1]=='0' else nodes[1]
            if '0' in nodes:
                if net in driven:
                    _fail('multiple voltage sources drive the same node',token)
                driven.add(net)
            if reference.text not in available:
                _fail(f'bsource references unknown scalar node {reference.text!r}',reference)
            instances.append(dict(name=token.text,module=module_name,
                                  connections=dict(p=nodes[0],n=nodes[1],u=reference.text,g='0'),parameters=dict(offset=offset)))
        sources[generated_path]=generated
        generated_sha256[generated_path]=hashlib.sha256(generated.encode()).hexdigest()
    if zero_current_sources:
        private_inputs=set(internal_source_nodes)
        for entry in zero_current_sources:
            if any(node not in available or node in private_inputs for node in entry['terminals']):
                location=entry['origin']
                _fail('zero isource terminals require independently existing VA/source topology; '
                      'a zero current cannot anchor or create a node',
                      Token(entry['name'],'name',location['line'],location['column'],location['source']),
                      unsupported=True)
    # A non-node time selector needs no voltage column: the transient axis is
    # already exported as saved.times. A real electrical node named time still
    # belongs to available and retains its voltage through the normal path.
    unknown=set(saved)-{'time'}-available
    if unknown:
        fail(f'save names unknown scalar nodes: {sorted(unknown)}')
    manifest=dict(models=list(sources),instances=instances,tolerances=effective,
                  transient=dict(sources=waveforms,output_times=times,stop=stop,max_step=step,**strobe))
    if analytic_sources:
        manifest['transient']['analytic_sources']=analytic_sources
    if source_errors:
        manifest['transient']['source_errors']=source_errors
    if source_shapes:
        manifest['transient']['source_shapes']=source_shapes
    metadata=dict(input_format='spectre-voltage-subset',path=str(path),sha256=hashlib.sha256(text.encode()).hexdigest(),
                  model_sha256=model_sha256,
                  effective_tolerances=effective,output_grid=OUTPUT_GRID,
                  pulse_corner_rounding_seconds=rounding)
    if sine_source_origins:
        metadata['sine_source_origins']=sine_source_origins
    if zero_current_sources:
        metadata['zero_current_sources']=zero_current_sources
    if internal_source_nodes:
        metadata['internal_source_nodes']=internal_source_nodes
    if pulse_proofs:
        metadata['pulse_corner_proofs']=pulse_proofs
    if save_policy is not None:
        metadata.update(strobeoutput=save_policy,saved_output_times=saved_times)
    if generated_sha256:
        metadata['generated_model_sha256']=generated_sha256
    if warning_reports:
        metadata['warnings']=warning_reports
    if strobe:
        metadata['strobe_controls']=strobe
        metadata['forced_times']=forced
    return ScsTestbench(sources,manifest,saved,metadata,tran_token)


def _grid_fail(bench,message):
    token=bench.tran_token or Token('', '',1,1,bench.metadata['path'])
    _fail(message,token)


def simulate_scs(path: str | Path, *, kernel=None, timeout=DEFAULT_TIMEOUT):
    bench=load_scs(path)
    program=compile_sources(bench.sources,[Instance(**i) for i in bench.manifest['instances']],
                            external_nodes=bench.manifest['transient']['sources'])
    config=dict(bench.manifest['transient'])
    stop,step=config['stop'],config['max_step']
    times=config['output_times']
    bound=_bound_step(program,step)
    if bound<step:
        regular=_regular_times(stop,bound)
        if regular is None:
            _grid_fail(bench,'output point budget (100000) exceeded by the $bound_step output grid')
        times=sorted(set(times).union(regular))
        if len(times)>POINT_BUDGET:
            _grid_fail(bench,'output point budget (100000) exceeded by the $bound_step output grid')
    result=transient(program,kernel=kernel,timeout=timeout,**dict(config,output_times=times),
                     **bench.manifest['tolerances'])
    metadata=dict(bench.metadata)
    if bound<step:
        metadata['bound_step_output_spacing_s']=bound
    saved_times=times
    if 'strobeoutput' in metadata:
        strobe=metadata.get('strobe_controls',{})
        saved_times=_saved_output_times(times,stop,strobe,metadata['strobeoutput'],metadata.get('forced_times',[]))
        if len(saved_times)>POINT_BUDGET:
            _grid_fail(bench,'saved output point budget (100000) exceeded')
        metadata['saved_output_times']=saved_times
    saved=[n for n in bench.save if n!='time' or n in result['nodes']] or [
        n for n in result['nodes'] if n not in bench.metadata.get('internal_source_nodes',())]
    indices=[result['nodes'].index(n) for n in saved]
    rows=dict(zip(times,(row['voltages'] for row in result['solutions'])))
    if 'strobeoutput' in metadata and result.get('strobe_evidence'):
        receipt=result['strobe_evidence']
        rows.update(zip(receipt['times'],receipt['voltages_V']))
    return dict(result,testbench=metadata,saved=dict(nodes=saved,times=saved_times,
                values=[[rows[t][i] for i in indices] for t in saved_times]))
