#!/usr/bin/env python3
"""Regenerate the audited Python/Rust diagnostic source inventory; never execute EVAS.

IDs use path, lexical function and normalized source, not line numbers. Entries
are source audit, not reachability or execution coverage. Dynamic expressions
stay unresolved; categories come only from the explicit registry.
"""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evas/docs/diagnostic-inventory.json'


def registries():
    tree = ast.parse((ROOT / 'evas/src/evas/errors.py').read_text())
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ('RULES', '_KERNEL_CATEGORIES', '_KERNEL_CAPABILITIES'):
                values[node.targets[0].id] = ast.literal_eval(node.value)
    return values['RULES'], values['_KERNEL_CATEGORIES'], values['_KERNEL_CAPABILITIES']


def literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def name(node):
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ''


def python_entries(path):
    tree = ast.parse(path.read_text())
    wrappers = {}
    factories = {'CompileError', 'KernelError'}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(name(base) in factories for base in node.bases):
            factories.add(node.name)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in ('fail', '_fail'):
            args = [arg.arg for arg in node.args.args]
            defaults = dict(zip(args[len(args)-len(node.args.defaults):], node.args.defaults))
            defaults.update(zip([arg.arg for arg in node.args.kwonlyargs], node.args.kw_defaults))
            fixed = {literal(arg.value) for call in ast.walk(node) if isinstance(call, ast.Call)
                     and name(call.func) == 'CompileError' for arg in call.keywords if arg.arg == 'code'}
            default = literal(defaults.get('code'))
            if 'code' not in defaults and len(fixed) == 1:
                default = next(iter(fixed))
            wrappers[node.name] = (args, default)
    def walk(node, scope):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = scope + [node.name]
        form, reason = None, None
        if isinstance(node, ast.Call):
            target = name(node.func)
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'setdefault' and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'diagnostic':
                form = 'metadata_conversion'
            if target == 'dict' and any(arg.arg == 'diagnostic_version' for arg in node.keywords):
                form = 'metadata_conversion'
            if target in factories or target == 'diagnostic' or target in wrappers:
                form = 'constructor' if target in factories else 'metadata' if target == 'diagnostic' else 'wrapper_call'
                keywords = {arg.arg: arg.value for arg in node.keywords}
                if target == 'diagnostic':
                    reason = literal(node.args[0]) if node.args else None
                elif target == 'KernelError':
                    if node.args and isinstance(node.args[0], ast.Call):
                        reason = next((literal(arg.value) for arg in node.args[0].keywords if arg.arg == 'kind'), None)
                else:
                    if 'code' in keywords:
                        reason = literal(keywords['code'])
                    elif target in wrappers:
                        args, reason = wrappers[target]
                        if 'code' in args and args.index('code') < len(node.args):
                            reason = literal(node.args[args.index('code')])
                    else:
                        reason = 'compile_error' if target == 'CompileError' else None
                if target == 'KernelError':
                    form = 'kernel_constructor'
        elif isinstance(node, ast.ClassDef) and node.name in factories:
            form = 'factory_definition'
        elif isinstance(node, ast.ExceptHandler):
            # Broad ValueError/OSError catches can consume typed subclasses.
            if node.type is not None and any(name(item) in ('CompileError', 'KernelError', 'ValueError', 'OSError') for item in ast.walk(node.type)):
                form = 'handler'
        elif isinstance(node, ast.Raise) and node.exc is not None and not isinstance(node.exc, ast.Call):
            form = 'rethrow'
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Attribute) and target.attr in ('diagnostic', 'bundle_diagnostic') for target in node.targets):
            form = 'metadata_conversion'
        if form:
            yield dict(function='.'.join(scope) or '<module>', form=form,
                       reason=reason, expression=('except ' + ast.unparse(node.type) if isinstance(node, ast.ExceptHandler) else
                                   'class ' + node.name + '(' + ', '.join(ast.unparse(base) for base in node.bases) + ')' if isinstance(node, ast.ClassDef) else ast.unparse(node)))
        for child in ast.iter_child_nodes(node):
            yield from walk(child, scope)
    yield from walk(tree, [])


# Rust is tokenized rather than scanned by line. Comments/strings cannot invent
# Error::new calls; balanced item spans remove test modules even before later code.
TOKEN = re.compile(r'//[^\n]*|/\*|r(#+)?"|"(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z_0-9]*|::|==|=>|!=|<=|>=|&&|\|\||[^\s]', re.S)


def rust_tokens(text):
    tokens = []
    offset = 0
    while match := TOKEN.search(text, offset):
        token = match.group()
        offset = match.end()
        if token.startswith('//'):
            continue
        if token == '/*':
            depth = 1
            while depth:
                end = re.search(r'/\*|\*/', text[offset:])
                if end is None:
                    raise ValueError('unclosed Rust comment')
                depth += 1 if end.group() == '/*' else -1
                offset += end.end()
            continue
        if token.startswith('r') and token.endswith('"'):
            closing = '"' + (match.group(1) or '')
            end = text.find(closing, offset)
            if end < 0:
                raise ValueError('unclosed Rust raw string')
            token = text[match.start():end + len(closing)]
            offset = end + len(closing)
        tokens.append(token)
    return tokens


def closing(tokens, index):
    pairs = {'(': ')', '{': '}', '[': ']'}
    stack = [pairs[tokens[index]]]
    for end in range(index + 1, len(tokens)):
        token = tokens[end]
        if token in pairs:
            stack.append(pairs[token])
        elif token == stack[-1]:
            stack.pop()
            if not stack:
                return end
    raise ValueError('unbalanced Rust source')


def rust_source(path):
    tokens = rust_tokens(path.read_text())
    ignored = set()
    for i in range(len(tokens) - 7):
        if tokens[i:i+7] == ['#', '[', 'cfg', '(', 'test', ')', ']']:
            start = next((j for j in range(i+7, len(tokens)) if tokens[j] in ('{', ';')), None)
            if start is not None:
                end = closing(tokens, start) if tokens[start] == '{' else start
                ignored.update(range(i, end + 1))
    functions = []
    for i in range(len(tokens)-1):
        if tokens[i] == 'fn' and i not in ignored:
            arguments = next(j for j in range(i+2, len(tokens)) if tokens[j] == '(')
            start = closing(tokens, arguments) + 1
            while start < len(tokens) and tokens[start] not in ('{', ';'):
                start = closing(tokens, start) + 1 if tokens[start] in ('[', '(') else start + 1
            if start < len(tokens) and tokens[start] == '{':
                functions.append(dict(start=start, end=closing(tokens, start), name=tokens[i+1],
                                      signature=tokens[i:start], index=i))
    imports, import_tokens = {}, set()
    def leaves(tree, prefix=()):
        parts = []
        for token in tree:
            if token == '{':
                break
            parts.append(token)
        if '{' in tree:
            opening = tree.index('{')
            end = closing(tree, opening)
            base = prefix + tuple(token for token in parts if token != '::')
            begin = opening+1
            depth = 0
            for index in range(begin, end+1):
                if tree[index] == '{': depth += 1
                if tree[index] == '}': depth -= 1
                if index == end or tree[index] == ',' and depth == 0:
                    yield from leaves(tree[begin:index], base)
                    begin = index+1
        elif tree:
            split = tree.index('as') if 'as' in tree else len(tree)
            target = prefix + tuple(token for token in tree[:split] if token != '::')
            alias = tree[split+1] if split < len(tree) else target[-1]
            yield alias, target
    for i, token in enumerate(tokens):
        if token == 'use' and i not in ignored:
            end = next(j for j in range(i+1, len(tokens)) if tokens[j] == ';')
            imports.update(leaves(tokens[i+1:end]))
            import_tokens.update(range(i, end+1))
    return dict(tokens=tokens, ignored=ignored, functions=functions,
                imports=imports, import_tokens=import_tokens)


def rust_module(path, rust):
    relative = path.relative_to(rust)
    index = relative.parts.index('src')
    module = relative.parts[index+1:]
    if module[-1] in ('lib.rs', 'main.rs', 'mod.rs'):
        module = module[:-1]
    else:
        module = (*module[:-1], path.stem)
    # Keep the workspace's separate IR crate out of kernel crate lookup.
    crate = tuple(relative.parts[:index])
    return crate, tuple(module)


def resolve_rust(target, module, imports):
    if target[0] in imports:
        target = imports[target[0]] + target[1:]
    if target[0] == 'crate':
        return target[1:]
    if target[0] == 'self':
        return module + target[1:]
    if target[0] == 'super':
        return module[:-1] + target[1:]
    return module + target


def rust_factories(sources, rust):
    factories = {}
    for path, source in sources.items():
        crate, module = rust_module(path, rust)
        aliases = {'Error'} | {alias for alias, target in source['imports'].items() if target[-1] == 'Error'}
        source['error_aliases'] = aliases
        tokens = source['tokens']
        for function in source['functions']:
            signature = function['signature']
            if len(signature) < 3 or signature[-3:-1] != ['-', '>'] or signature[-1] not in aliases:
                continue
            # Resolve only explicit constructor literals. Delegating/conditional
            # factory reasons remain unresolved instead of being guessed.
            body = tokens[function['start']+1:function['end']]
            if body[:1] == ['return']:
                body = body[1:]
            if body[-1:] == [';']:
                body = body[:-1]
            reason = None
            if (len(body) > 4 and body[0] in aliases and body[1:4] == ['::', 'new', '(']
                    and closing(body, 3) == len(body)-1 and body[4].startswith('"')):
                reason = json.loads(body[4])
            factories[(crate, module + (function['name'],))] = reason
    return factories


def rust_entries(path, source, factories, rust):
    tokens, ignored, functions = source['tokens'], source['ignored'], source['functions']
    crate, module = rust_module(path, rust)
    for function in functions:
        key = (crate, module + (function['name'],))
        if key in factories:
            yield dict(function=function['name'], form='factory_definition', reason=factories[key],
                       expression=' '.join(tokens[function['index']:function['end']+1]),
                       factory='::'.join(('crate', *module, function['name'])))
    for i, token in enumerate(tokens):
        if i in ignored:
            continue
        form, reason, end, expression_start, factory = None, None, i, i, None
        if token in source['error_aliases'] and tokens[i+1:i+4] == ['::', 'new', '(']:
            end = closing(tokens, i+3)
            form = 'kernel_constructor'
            if tokens[i+4].startswith('"'):
                reason = json.loads(tokens[i+4])
        elif token != 'map_err' and i+1 < len(tokens) and tokens[i+1] == '(' and i not in source['import_tokens'] and (i == 0 or tokens[i-1] != 'fn'):
            begin = i
            while begin >= 2 and tokens[begin-1] == '::':
                begin -= 2
            target = tuple(part for part in tokens[begin:i+1] if part != '::')
            key = (crate, resolve_rust(target, module, source['imports']))
            if key in factories:
                end = closing(tokens, i+1)
                form, reason = 'wrapper_call', factories[key]
                expression_start = begin
                factory = '::'.join(('crate', *key[1]))
        elif tokens[i:i+2] == ['map_err', '(']:
            end = closing(tokens, i+1)
            form = 'conversion'
        elif token in ('error', 'err') and tokens[i+1:i+3] in (['.', 'kind'], ['.', 'message'], ['.', 'sample']) and tokens[i+3:i+4] == ['=']:
            end = next(j for j in range(i+4, len(tokens)) if tokens[j] == ';')
            form = 'metadata_conversion'
            if tokens[i+2] == 'kind' and tokens[i+4].startswith('"'):
                reason = json.loads(tokens[i+4])
        if form:
            containing = [item for item in functions if item['start'] < i < item['end']]
            function = min(containing, key=lambda item: item['end']-item['start'])['name'] if containing else '<module>'
            row = dict(function=function, form=form, reason=reason,
                       expression=' '.join(tokens[expression_start:end+1]))
            if factory is not None:
                row['factory'] = factory
            yield row


def inventory(root):
    rules, kernel, capabilities = registries()
    entries, duplicates = [], Counter()
    paths = sorted((root/'evas/src/evas').glob('*.py'))
    rust = root/'evas/rust_core'
    paths += sorted(path for path in rust.rglob('*.rs')
                    if 'target' not in path.relative_to(rust).parts and 'src' in path.relative_to(rust).parts)
    paths = [path for path in paths if not path.name.endswith('_tests.rs') and path.name != 'tests.rs']
    sources = {path: rust_source(path) for path in paths if path.suffix == '.rs'}
    factories = rust_factories(sources, rust)
    for path in paths:
        for row in python_entries(path) if path.suffix == '.py' else rust_entries(path, sources[path], factories, rust):
            relative = path.relative_to(root).as_posix()
            kernel_reason = path.suffix == '.rs' or row['form'] == 'kernel_constructor'
            row['category'] = kernel.get(row['reason'], 'unknown') if kernel_reason else rules.get(row['reason'], ('unknown',))[0]
            row['exception'] = 'KernelError/Error' if kernel_reason else 'CompileError' if row['form'] in ('constructor', 'wrapper_call', 'metadata') else None
            row['kind'] = row['reason'] if kernel_reason else 'compile_error' if row['exception'] == 'CompileError' else None
            row['code'] = ('kernel.' + row['reason'] if kernel_reason else row['reason']) if row['reason'] is not None else None
            row['stage'] = 'kernel' if kernel_reason else rules.get(row['reason'], (None, None))[1]
            row['capability'] = capabilities.get(row['reason']) if kernel_reason else rules.get(row['reason'], (None, None, None))[2]
            row['path'] = relative
            row['evidence'] = 'source_audit'
            fingerprint = hashlib.sha256(row['expression'].encode()).hexdigest()[:16]
            key = f"{relative}:{row['function']}:{row['form']}:{fingerprint}"
            duplicates[key] += 1
            row['id'] = key + (f":{duplicates[key]}" if duplicates[key] > 1 else '')
            entries.append(row)
    return dict(inventory_version=1, scope='Python frontend/CLI and Rust workspace production source; excludes tests/build output',
                counts=dict(total=len(entries), forms=dict(sorted(Counter(row['form'] for row in entries).items())),
                            categories=dict(sorted(Counter(row['category'] for row in entries).items()))), entries=entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = inventory(args.root)
    entries = result.pop('entries')
    header = json.dumps(result, ensure_ascii=False)[:-1]
    text = header + ', "entries": [\n' + ',\n'.join(
        '  ' + json.dumps(row, ensure_ascii=False) for row in entries) + '\n]}\n'
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            parser.exit(1, 'diagnostic inventory is stale; run scripts/diagnostic_inventory.py --write\n')
    elif args.write:
        OUT.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
