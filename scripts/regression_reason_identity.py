"""Capture source-selected stdlib assertion observations without rewriting diagnostics.

No existing raw report can be upgraded retrospectively. The public observer
executes a callback and retains the real exception diagnostic unchanged.
"""
import ast
from fractions import Fraction
import hashlib
import inspect
import json
import math
from pathlib import Path
import sys
import tempfile
import traceback
import unittest
import time
import types

_NUMERATOR_SLOT=Fraction.__dict__['_numerator']
_DENOMINATOR_SLOT=Fraction.__dict__['_denominator']
_NATIVE_ASSERTION_ERROR=AssertionError

_OPERANDS={'assertEqual':('first','second'),'assertIn':('member','container'),'assertGreaterEqual':('a','b')}
_ASSERTIONS={name:getattr(unittest.TestCase,name) for name in _OPERANDS}
_CODES={name:method.__code__ for name,method in _ASSERTIONS.items()}
_STDLIB=Path(unittest.case.__file__).resolve()
_STDLIB_SHA=hashlib.sha256(_STDLIB.read_bytes()).hexdigest()
_SOURCE_SHA={name:hashlib.sha256(inspect.getsource(method).encode()).hexdigest()
             for name,method in _ASSERTIONS.items()}
_FAIL=unittest.TestCase.fail
_FORMAT=unittest.TestCase._formatMessage
_EQ_CODES={getattr(unittest.TestCase,name).__code__ for name in
           ('_baseAssertEqual','assertMultiLineEqual','assertListEqual','assertTupleEqual','assertDictEqual')}
_TD=tempfile.TemporaryDirectory
_INIT=_TD.__init__.__code__
_ENTER=_TD.__enter__.__code__
_PROOF_TOKEN=object()
_PRODUCER_TOKEN=object()
_MONOTONIC=time.monotonic
_ROUND=round
_TEMP_SOURCE=Path(tempfile.__file__).resolve()
_TEMP_SHA=hashlib.sha256(_TEMP_SOURCE.read_bytes()).hexdigest()
_EXIT=_TD.__exit__.__code__


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _typed(value, *, active=None, depth=0):
    if depth>64:
        raise ValueError('typed value exceeds bounded depth')
    if active is None: active=set()
    kind=type(value)
    if value is None: return {'type':'none'}
    if kind is bool: return {'type':'bool','value':value}
    if kind is int: return {'type':'int','hex':hex(value)}
    if kind is float:
        if not math.isfinite(value): raise ValueError('nonfinite operand')
        return {'type':'float','hex':value.hex()}
    if kind is str: return {'type':'str','value':value}
    if kind is bytes: return {'type':'bytes','hex':value.hex()}
    if kind is Fraction:
        numerator=_NUMERATOR_SLOT.__get__(value,Fraction)
        denominator=_DENOMINATOR_SLOT.__get__(value,Fraction)
        if (type(numerator) is not int or type(denominator) is not int or denominator<=0
                or math.gcd(numerator,denominator)!=1):
            raise ValueError('invalid native Fraction slots')
        return {'type':'fraction','numerator':hex(numerator),'denominator':hex(denominator)}
    if kind not in (list,tuple,dict): raise ValueError('opaque operand type')
    if id(value) in active: raise ValueError('cyclic operand')
    active.add(id(value))
    try:
        if kind is dict:
            items=[[_typed(k,active=active,depth=depth+1),_typed(v,active=active,depth=depth+1)]
                   for k,v in value.items()]
            items.sort(key=lambda item:_json(item[0]))
            return {'type':'dict','items':items}
        return {'type':'list' if kind is list else 'tuple',
                'items':[_typed(item,active=active,depth=depth+1) for item in value]}
    finally:
        active.remove(id(value))


def _compiled_code_matches(frame):
    source=Path(frame.f_code.co_filename).read_text()
    module=compile(source,frame.f_code.co_filename,'exec',dont_inherit=True,optimize=sys.flags.optimize)
    pending=[module]
    while pending:
        code=pending.pop()
        if (code.co_qualname==frame.f_code.co_qualname and code.co_firstlineno==frame.f_code.co_firstlineno
                and code==frame.f_code):
            return True
        pending.extend(value for value in code.co_consts if type(value) is types.CodeType)
    return False


def _binding(policy, frame, line, kind, operation):
    base={'schema_version','id','version','kind','source_sha256','function','assertion_line','operation'}
    extra={'native-assertion':set(),'diagnostic-duration':{'message_path','role','producer'},
           'temporary-directory-root':{'target'}}
    if (not isinstance(policy,dict) or kind not in extra or set(policy)!=base|extra[kind]
            or type(policy.get('schema_version')) is not int or policy.get('schema_version')!=1
            or type(policy.get('version')) is not int or policy.get('version')!=1
            or policy.get('kind')!=kind or not isinstance(policy.get('id'),str) or not policy['id']
            or policy.get('operation')!=operation or policy.get('function')!=frame.f_code.co_qualname
            or policy.get('assertion_line')!=line):
        raise ValueError('unknown policy schema or selected assertion site mismatch')
    actual=hashlib.sha256(Path(frame.f_code.co_filename).read_bytes()).hexdigest()
    if policy.get('source_sha256')!=actual or not _compiled_code_matches(frame):
        raise ValueError('selected assertion source/code identity mismatch')
    return {'id':policy['id'],'version':policy['version'],'source_sha256':actual}


def capture_reason(exc_info, *, site_policy=None, timing_policy=None, tempdir_policy=None, proofs=()):
    """Capture typed identity only for an explicitly registered native assertion."""
    error=exc_info[1]
    try:
        message=str(error)
    except Exception:
        message='<exception string unavailable>'
    reason=dict(kind='assertion' if isinstance(error,AssertionError) else 'exception',
                exception_type=type(error).__module__+'.'+type(error).__qualname__,
                message=message,traceback=''.join(traceback.format_exception(*exc_info)),
                comparison_state='unselected',comparison_complete=False)
    if site_policy is None:
        return reason
    reason['comparison_state']='incomplete'
    try:
        frames=list(traceback.walk_tb(exc_info[2]))
        match=next((i,name) for i,(frame,_) in enumerate(frames) for name,method in _ASSERTIONS.items()
                   if frame.f_code is _CODES[name])
        index,operation=match
        frame,_=frames[index]
        if index==0: raise ValueError('assertion lacks a source caller')
        caller,line=frames[index-1]
        if (Path(frame.f_code.co_filename).resolve()!=_STDLIB
                or hashlib.sha256(_STDLIB.read_bytes()).hexdigest()!=_STDLIB_SHA
                or frame.f_globals.get('__name__')!='unittest.case'):
            raise ValueError('assertion is not bound to verified stdlib code')
        if (isinstance(site_policy,dict) and site_policy.get('schema_version')==1
                and site_policy.get('function')==caller.f_code.co_qualname
                and site_policy.get('assertion_line')!=line
                and site_policy.get('source_sha256')==hashlib.sha256(Path(caller.f_code.co_filename).read_bytes()).hexdigest()):
            reason['comparison_state']='unselected'
            return reason
        instance=frame.f_locals['self']
        if (inspect.getattr_static(type(instance),'__getattribute__') is not object.__getattribute__
                or inspect.getattr_static(type(instance),'__getattr__',None) is not None):
            raise ValueError('dynamic assertion attribute lookup is not a native failure proof')
        if (type(error) is not _NATIVE_ASSERTION_ERROR or exc_info[0] is not _NATIVE_ASSERTION_ERROR
                or inspect.getattr_static(instance,'failureException') is not _NATIVE_ASSERTION_ERROR):
            raise ValueError('custom failure exception cannot replace its semantic diagnostic')
        if (inspect.getattr_static(instance,'fail') is not _FAIL
                or inspect.getattr_static(instance,'_formatMessage') is not _FORMAT):
            raise ValueError('custom assertion failure/message behavior')
        if operation=='assertEqual':
            implementation=frame.f_locals.get('assertion_func')
            if (type(implementation) is not types.MethodType or implementation.__self__ is not instance
                    or implementation.__func__.__code__ not in _EQ_CODES):
                raise ValueError('custom assertEqual implementation')
        refs=[_binding(site_policy,caller,line,'native-assertion',operation)]
        operands={name:_typed(frame.f_locals[name]) for name in _OPERANDS[operation]}
        message=_typed(frame.f_locals.get('msg'))
        raw_operands,raw_message=operands,message
        if timing_policy is not None:
            refs.append(_binding(timing_policy,caller,line,'diagnostic-duration',operation))
            msg=frame.f_locals.get('msg')
            if (operation!='assertEqual' or timing_policy['message_path']!=['elapsed_s']
                    or timing_policy['role']!='duration-seconds' or type(msg) is not dict
                    or any(type(key) is not str for key in msg)
                    or type(msg.get('elapsed_s')) is not float
                    or not math.isfinite(msg['elapsed_s']) or msg['elapsed_s']<0):
                raise ValueError('diagnostic duration policy does not prove exact role')
            producer=timing_policy['producer']
            proof=next(p for p in proofs if p.get('_token') is _PRODUCER_TOKEN
                       and p['owner'] is caller and p['exception'] is error
                       and p['record'] is msg and type(msg['elapsed_s']) is type(p['value'])
                       and msg['elapsed_s']==p['value']
                       and p['producer_sha256']==producer['source_sha256']
                       and p['message_snapshot']==raw_message)
            refs.append({'id':timing_policy['id']+':producer','version':1,
                         'source_sha256':proof['producer_sha256']})
            message=_typed(msg)
            entry=next(pair for pair in message['items'] if pair[0]=={'type':'str','value':'elapsed_s'})
            entry[1]={'type':'diagnostic-role','role':'duration-seconds',
                      'value_type':'float' if type(msg['elapsed_s']) is float else 'int'}
        if tempdir_policy is not None:
            refs.append(_binding(tempdir_policy,caller,line,'temporary-directory-root',operation))
            if operation!='assertIn' or type(frame.f_locals['container']) is not str:
                raise ValueError('tempdir normalization only supports typed assertIn container')
            proof=next(proof for proof in proofs if proof.get('_token') is _PROOF_TOKEN
                       and proof['owner'] is caller and proof['exception'] is error
                       and proof['source_sha256']==tempdir_policy['source_sha256']
                       and proof['symbol']==tempdir_policy['target'])
            operands=dict(operands)
            operands['container']=_symbolic_string(frame.f_locals['container'],proof)
        identity=dict(schema_version=1,kind='unittest-assertion',operation=operation,
                      operation_source_sha256=_SOURCE_SHA[operation],operands=operands,
                      message=message,policies=refs)
        reason.update(comparison_identity=identity,comparison_complete=True,comparison_state='complete',
                      assertion_observation={'operands':raw_operands,'message':raw_message})
    except (OSError,ValueError,TypeError,KeyError,StopIteration) as error:
        reason['comparison_error']=str(error)
    return reason


def _symbolic_string(value,proof):
    roots=sorted({proof['root'],proof['resolved_root']},key=len,reverse=True)
    pieces=[]
    position=0
    while True:
        matches=[(value.find(root,position),root) for root in roots if value.find(root,position)>=0]
        if not matches: break
        index,root=min(matches,key=lambda item:(item[0],-len(item[1])))
        end=index+len(root)
        if ((index and (value[index-1].isalnum() or value[index-1] in '/._-'))
                or (end<len(value) and value[end] not in '/:')):
            raise ValueError('proven root is not at a complete path boundary')
        if index>position: pieces.append(value[position:index])
        pieces.append({'type':'temporary-directory-root','symbol':proof['symbol'],
                       'with_line':proof['with_line']})
        position=end
    if not pieces: raise ValueError('diagnostic does not contain proven root')
    if position<len(value): pieces.append(value[position:])
    return {'type':'str-parts','items':pieces}


class ObservationSession:
    """Observe selected-method lifetime; bind temp proof to the actual exception.

    An occupied trace/profile hook disables temp proof rather than replacing
    another callback. Normal __exit__ may happen before capture in addSubTest.
    """
    def __init__(self, *, site_policy=None,timing_policy=None,tempdir_policy=None):
        self.site_policy=site_policy
        self.timing_policy=timing_policy
        self.tempdir_policy=tempdir_policy
        self._active={}
        self._constructed={}
        self._proofs={}
        self._duration_frames={}
        self._duration_records={}
        self._callback=self._trace
        self._installed=False
        self._blocked=None

    def __enter__(self):
        if self.site_policy is not None and (self.tempdir_policy is not None or self.timing_policy is not None):
            if sys.gettrace() is not None or sys.getprofile() is not None:
                self._blocked='existing trace/profile callback prevents proof observation'
            else:
                sys.settrace(self._callback)
                self._installed=True
        return self

    def __exit__(self,*exc):
        if self._installed and sys.gettrace() is self._callback:
            sys.settrace(None)
        self._active.clear()
        self._constructed.clear()
        self._proofs.clear()
        self._duration_frames.clear()
        self._duration_records.clear()

    def _with_binding(self,owner,root):
        policy=self.tempdir_policy
        _binding(policy,owner,policy['assertion_line'],'temporary-directory-root',policy['operation'])
        module=owner.f_locals.get('tempfile',owner.f_globals.get('tempfile'))
        if (module is not tempfile or module.TemporaryDirectory is not _TD
                or hashlib.sha256(_TEMP_SOURCE.read_bytes()).hexdigest()!=_TEMP_SHA
                or any(Path(code.co_filename).resolve()!=_TEMP_SOURCE for code in (_INIT,_ENTER,_EXIT))):
            raise ValueError('with source is not bound to actual stdlib tempfile')
        tree=ast.parse(Path(owner.f_code.co_filename).read_text())
        for node in ast.walk(tree):
            if not isinstance(node,ast.With) or not node.lineno<=owner.f_lineno<=node.end_lineno:
                continue
            if not node.lineno<policy['assertion_line']<=node.end_lineno: continue
            for item in node.items:
                call=item.context_expr
                if (isinstance(item.optional_vars,ast.Name) and item.optional_vars.id==policy['target']
                        and isinstance(call,ast.Call) and not call.args and not call.keywords
                        and isinstance(call.func,ast.Attribute) and call.func.attr=='TemporaryDirectory'
                        and isinstance(call.func.value,ast.Name) and call.func.value.id=='tempfile'
                        and call.lineno<=owner.f_lineno<=call.end_lineno):
                    return dict(_token=_PROOF_TOKEN,owner=owner,root=root,
                                resolved_root=str(Path(root).resolve(strict=True)),symbol=policy['target'],
                                with_line=node.lineno,end_line=node.end_lineno,
                                source_sha256=policy['source_sha256'])
        raise ValueError('no matching with tempfile.TemporaryDirectory() as target AST')

    def _producer_state(self,frame):
        policy=self.timing_policy['producer']
        if (type(policy) is not dict or set(policy)!={'source_sha256','function','assignment_line'}
                or frame.f_code.co_qualname!=policy['function']
                or hashlib.sha256(Path(frame.f_code.co_filename).read_bytes()).hexdigest()!=policy['source_sha256']
                or type(frame.f_globals.get(frame.f_code.co_name)) is not types.FunctionType
                or frame.f_globals[frame.f_code.co_name].__code__ is not frame.f_code
                or not _compiled_code_matches(frame)
                or frame.f_globals.get('time') is not time or time.monotonic is not _MONOTONIC
                or frame.f_globals.get('round',frame.f_builtins.get('round')) is not _ROUND):
            raise ValueError('producer code/source binding is not exact')
        tree=ast.parse(Path(frame.f_code.co_filename).read_text())
        assignment=next(node for node in ast.walk(tree) if isinstance(node,ast.Assign)
                        and node.lineno==policy['assignment_line'])
        expected=ast.parse("record['elapsed_s']=round(time.monotonic()-started,3)").body[0]
        if ast.dump(assignment,include_attributes=False)!=ast.dump(expected,include_attributes=False):
            raise ValueError('unsupported producer elapsed assignment')
        function=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef)
                      and node.name==frame.f_code.co_name and node.lineno==frame.f_code.co_firstlineno)
        expected_start=ast.dump(ast.parse('started=time.monotonic()').body[0],include_attributes=False)
        start=next(node for node in ast.walk(function) if isinstance(node,ast.Assign)
                   and node.lineno<assignment.lineno
                   and ast.dump(node,include_attributes=False)==expected_start)
        return dict(assignment_line=assignment.lineno,start_line=start.lineno,
                    pending_start=False,started=None,pending=False,record=None,
                    producer_sha256=policy['source_sha256'])

    def _producer_event(self,frame,event,arg):
        if self.timing_policy is None: return
        producer=self.timing_policy.get('producer')
        if type(producer) is not dict or frame.f_code.co_qualname!=producer.get('function'): return
        if event=='call': self._duration_frames[id(frame)]=self._producer_state(frame)
        state=self._duration_frames.get(id(frame))
        if state is None: return
        if event in ('line','return'):
            if state['pending_start']:
                value=frame.f_locals.get('started')
                if type(value) is not float: raise ValueError('producer start clock not observed')
                state.update(started=value,pending_start=False)
            if state['pending']:
                record=frame.f_locals.get('record')
                if (type(record) is not dict or any(type(key) is not str for key in record)
                        or type(record.get('elapsed_s')) is not float
                        or not math.isfinite(record['elapsed_s'])):
                    raise ValueError('producer elapsed write not observed')
                state.update(record=record,value=record['elapsed_s'],pending=False)
        if event=='line' and frame.f_lineno==state['start_line']:
            state['pending_start']=True
        if event=='line' and frame.f_lineno==state['assignment_line']:
            if state['started'] is None or frame.f_locals.get('started')!=state['started']:
                raise ValueError('producer start binding changed')
            state['pending']=True
        if event=='return':
            if (type(arg) is dict and state['record'] is arg
                    and any(type(key) is not str for key in arg) is False
                    and arg.get('elapsed_s')==state.get('value')):
                self._duration_records[id(arg)]=dict(_token=_PRODUCER_TOKEN,record=arg,
                    value=state['value'],producer_sha256=state['producer_sha256'])
            self._duration_frames.pop(id(frame),None)

    def _trace(self,frame,event,arg):
        try:
            self._producer_event(frame,event,arg)
            if event=='return' and frame.f_code is _INIT:
                instance=frame.f_locals['self']
                if type(instance) is _TD and _compiled_code_matches(frame):
                    self._constructed[id(instance)]=frame.f_back
            elif event=='return' and frame.f_code is _ENTER:
                instance=frame.f_locals['self']
                owner=frame.f_back
                if (type(instance) is _TD and type(arg) is str and arg==instance.name
                        and _compiled_code_matches(frame) and self._constructed.get(id(instance)) is owner):
                    self._active[id(instance)]=self._with_binding(owner,arg)
            elif event=='call' and frame.f_code is _EXIT:
                self._active.pop(id(frame.f_locals['self']),None)
            elif event=='exception' and any(frame.f_code is code for code in _CODES.values()):
                error=arg[1]
                caller=frame.f_back
                proven=[]
                for proof in self._active.values():
                    if (proof['owner'] is caller and caller.f_locals.get(proof['symbol'])==proof['root']
                            and proof['with_line']<caller.f_lineno<=proof['end_line']):
                        proven.append(dict(proof,exception=error))
                message=frame.f_locals.get('msg')
                duration=self._duration_records.get(id(message))
                if duration is not None and duration['record'] is message:
                    proven.append(dict(duration,owner=caller,exception=error,message_snapshot=_typed(message)))
                if proven: self._proofs[id(error)]=proven
        except (OSError,ValueError,TypeError,KeyError,StopIteration):
            self._duration_frames.pop(id(frame),None)
            # Absence of proof is an explicit incomplete selected observation.
            pass
        return self._callback

    def capture(self,exc_info):
        reason=capture_reason(exc_info,site_policy=self.site_policy,timing_policy=self.timing_policy,
                              tempdir_policy=self.tempdir_policy,
                              proofs=self._proofs.get(id(exc_info[1]),()))
        if (reason['comparison_state']!='unselected' and (self.tempdir_policy is not None or self.timing_policy is not None)
                and (self._blocked or sys.gettrace() is not self._callback)):
            reason.pop('comparison_identity',None)
            reason.update(comparison_state='incomplete',comparison_complete=False,
                          comparison_error=self._blocked or 'observer lost trace ownership')
        return reason


def observe_failure(callback, *, site_policy=None,timing_policy=None,tempdir_policy=None):
    """Execute one failure callback in a scoped session; never alter other hooks."""
    with ObservationSession(site_policy=site_policy,timing_policy=timing_policy,tempdir_policy=tempdir_policy) as session:
        try:
            callback()
        except Exception:
            return session.capture(sys.exc_info())
    raise ValueError('callback did not produce a failure')
