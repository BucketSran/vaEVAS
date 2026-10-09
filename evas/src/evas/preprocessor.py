"""Bounded token preprocessing of the caller-provided source inventory.

No filesystem lookup. Tokens retain invocation/include locations and expansion
paths, so preprocessing cannot collapse operator call-site identities.
"""
from dataclasses import dataclass, replace
import posixpath
import re
from .errors import CompileError
from .limits import MAX_IR_ITEMS, MAX_SOURCE_NESTING
from .syntax import Token, _tokens
from .standard_headers import STANDARD_HEADERS


@dataclass(frozen=True)
class Macro:
    arguments: tuple[str, ...] | None
    body: tuple[Token, ...]


def preprocess_sources(sources):
    files = {}
    for path, text in sources.items():
        key = posixpath.normpath(path)
        if key in files:
            raise CompileError(f'duplicate normalized source path {key!r}')
        files[key] = _tokens(text, key, tolerant=True)[:-1]
    macros = {'__VAMS_ENABLE__':Macro(None,()), '__LINE__':Macro(None,()), '__FILE__':Macro(None,())}
    count = 0

    def fail(message, token, *, code="compile_error"):
        raise CompileError(f'{token.source}:{token.line}:{token.column}: {message}', code=code, token=token)

    def include_path(token):
        match = re.fullmatch(r'`include[ \t]+"([^"\n]+)"', token.text)
        if not match:
            fail('include requires one quoted source path', token)
        return posixpath.normpath(posixpath.join(posixpath.dirname(token.source),match[1]))

    # Inventory headers are not also compiled as independent roots. This
    # structural include graph is independent of mapping order and macro state.
    included = {include_path(t) for body in files.values() for t in body if t.kind == 'include'}
    roots = [name for name in files if name not in included]
    if not roots and files:
        roots = [next(iter(files))]  # A cycle still reports its include site.

    def expand(tokens, stack=()):
        nonlocal count
        if len(stack) >= MAX_SOURCE_NESTING:
            fail('macro expansion depth budget exceeded', tokens[0], code="resource_budget")
        output, i = [], 0
        while i < len(tokens):
            token = tokens[i]
            i += 1
            if token.kind not in ('directive','macro'):
                count += 1
                if count > MAX_IR_ITEMS:
                    fail('preprocessor token expansion budget exceeded', token, code="resource_budget")
                output.append(token)
                continue
            name = token.text[1:]
            if name not in macros:
                fail(f'undefined or unsupported macro {name!r}',token)
            if name in stack:
                fail('recursive macro expansion is unsupported',token)
            if name in ('__LINE__','__FILE__'):
                value = str(token.line) if name == '__LINE__' else '"'+token.source+'"'
                output.extend(expand((replace(token,text=value,kind='number' if name == '__LINE__' else 'string'),),stack))
                continue
            macro = macros[name]
            arguments = {}
            if macro.arguments is not None:
                if i == len(tokens) or tokens[i].text != '(':
                    fail(f'macro {name!r} requires an argument list',token)
                i += 1
                values, current, nesting = [], [], []
                while i < len(tokens):
                    item = tokens[i]; i += 1
                    if item.text == ')' and not nesting:
                        if current or values or macro.arguments:
                            values.append(tuple(current))
                        break
                    if item.text == ',' and not nesting:
                        values.append(tuple(current)); current=[]
                        continue
                    if item.text in ('(','[','{',"'{"):
                        nesting.append('}' if item.text == "'{" else {'(':')','[':']','{':'}'}[item.text])
                    elif item.text in (')',']','}'):
                        if not nesting or nesting.pop() != item.text:
                            fail('unbalanced macro argument',item)
                    current.append(item)
                else:
                    fail('unterminated macro argument list',token)
                if len(values) != len(macro.arguments) or any(not value for value in values):
                    fail(f'macro {name!r} argument count or empty argument is unsupported',token)
                # A nested invocation in an argument is expanded before the
                # outer body. F(F(1)) is finite, unlike F's body calling F.
                arguments = {formal:tuple(expand(value,stack)) for formal,value in zip(macro.arguments,values)}
            replacement = []
            for index, item in enumerate(macro.body):
                path = (*token.expansion,(f'_macro_{name}',index))
                if item.kind == 'name' and item.text in arguments:
                    for arg in arguments[item.text]:
                        identity = (*arg.expansion,*path)
                        if len(identity) > MAX_SOURCE_NESTING:
                            fail('macro call-site identity depth budget exceeded', token, code="resource_budget")
                        replacement.append(replace(arg, expansion=identity))
                else:
                    if len(path) > MAX_SOURCE_NESTING:
                        fail('macro call-site identity depth budget exceeded', token, code="resource_budget")
                    replacement.append(replace(item,source=token.source,line=token.line,column=token.column,expansion=path))
            if replacement:
                output.extend(expand(replacement,(*stack,name)))
        return output

    def file_tokens(name, ancestry=(), include_expansion=()):
        if name in ancestry or len(ancestry) >= MAX_SOURCE_NESTING:
            token = files[name][0] if files[name] else Token('', 'eof',1,1,name)
            fail('recursive or over-budget source include', token,
                 code='compile_error' if name in ancestry else 'resource_budget')
        tokens = [replace(t, expansion=(*include_expansion, *t.expansion)) for t in files[name]]
        output, conditional, i = [], [], 0
        active = True
        while i < len(tokens):
            token = tokens[i]
            name_of = token.text[1:] if token.kind == 'directive' else None
            if name_of in ('ifdef','ifndef','elsif','else','endif'):
                i += 1
                if name_of in ('ifdef','ifndef','elsif'):
                    if i == len(tokens) or tokens[i].kind != 'name' or tokens[i].line != token.line:
                        fail('conditional directive requires a macro name',token)
                    symbol = tokens[i].text; i += 1
                    selected = symbol in macros
                    if name_of == 'ifndef': selected = not selected
                if name_of in ('ifdef','ifndef'):
                    if len(conditional) >= MAX_SOURCE_NESTING:
                        fail('conditional directive nesting budget exceeded', token, code="resource_budget")
                    conditional.append([active,selected,False])
                    active = active and selected
                else:
                    if not conditional:
                        fail('conditional directive has no matching ifdef',token)
                    parent, taken, seen_else = conditional[-1]
                    if name_of == 'endif':
                        conditional.pop(); active=parent
                    else:
                        if seen_else:
                            fail('duplicate else or elsif after else',token)
                        use = not taken and (name_of == 'else' or selected)
                        conditional[-1] = [parent,taken or use,name_of == 'else']
                        active = parent and use
                continue
            if not active:
                if name_of == 'define':
                    line = token.line
                    i += 1
                    while i < len(tokens) and tokens[i].line == line:
                        if tokens[i].text == '\\': line += 1
                        i += 1
                    continue
                i += 1
                continue
            if token.kind == 'include':
                i += 1
                target = include_path(token)
                requested = token.text.split('"')[1]
                if requested in STANDARD_HEADERS and target not in files:
                    files[target] = _tokens(STANDARD_HEADERS[requested], target, tolerant=True)[:-1]
                if target not in files:
                    fail(f'include source {target!r} was not provided',token)
                # The same source location can occur through several include
                # edges. Preserve each edge in the instantiated call-site path;
                # source/line/column still identify the included source itself.
                path = (*token.expansion, ('_include', i-1))
                if len(path) > MAX_SOURCE_NESTING:
                    fail('include call-site identity depth budget exceeded', token, code="resource_budget")
                output.extend(file_tokens(target,(*ancestry,name),path))
                continue
            if name_of in ('define','undef'):
                i += 1
                if i == len(tokens) or tokens[i].kind != 'name' or tokens[i].line != token.line:
                    fail('macro directive requires an identifier',token)
                identifier = tokens[i]; i += 1
                if name_of == 'undef':
                    if not identifier.text.startswith('__VAMS_'):
                        macros.pop(identifier.text,None)
                    continue
                if identifier.text.startswith('__VAMS_'):
                    fail('predefined __VAMS_ macro names cannot be redefined',identifier)
                arguments = None
                if (i < len(tokens) and tokens[i].text == '(' and tokens[i].line == identifier.line
                        and tokens[i].column == identifier.column+len(identifier.text)):
                    i += 1; arguments=[]
                    while i < len(tokens) and tokens[i].text != ')':
                        if tokens[i].kind != 'name' or tokens[i].text in arguments:
                            fail('macro formals require distinct identifiers',tokens[i])
                        arguments.append(tokens[i].text); i += 1
                        if i == len(tokens) or tokens[i].text != ',': break
                        i += 1
                    if i == len(tokens) or tokens[i].text != ')':
                        fail('unterminated macro formal list',identifier)
                    i += 1; arguments=tuple(arguments)
                body, line = [], token.line
                while i < len(tokens) and tokens[i].line == line:
                    if tokens[i].text == '\\':
                        if i+1 < len(tokens) and tokens[i+1].line == line:
                            fail('macro continuation must terminate its line',tokens[i])
                        line += 1; i += 1
                        continue
                    body.append(tokens[i]); i += 1
                macros[identifier.text] = Macro(arguments,tuple(body))
                continue
            # Expand a run up to the next directive. Definitions and conditionals
            # are processed in order; later definitions cannot affect earlier use.
            end = i+1
            while end < len(tokens):
                t = tokens[end]
                if t.kind == 'include' or t.kind == 'directive' and t.text[1:] in ('define','undef','ifdef','ifndef','elsif','else','endif'):
                    break
                end += 1
            output.extend(expand(tokens[i:end])); i=end
        if conditional:
            fail('unterminated conditional directive',tokens[-1])
        return output

    result = []
    for name in roots:
        tokens=file_tokens(name)
        # Validate only tokens retained by preprocessing. An unused macro
        # argument or inactive branch is not part of the compiled program.
        for token in tokens:
            if token.kind == 'number' and not re.fullmatch(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[TGMkKmunpfa]?', token.text):
                fail('real literal requires digits on both sides of the decimal point', token, code='syntax_error')
        if tokens:
            tokens.append(Token('<eof>','eof',tokens[-1].line,tokens[-1].column,name))
            result.append((name,tokens))
    return result
