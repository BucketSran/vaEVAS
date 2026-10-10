"""Translate nominal SPICE expression delimiters / numeric suffixes for Spectre.

No parameter values or circuit topology are changed. This prepares another
source calibration; successful syntax translation is not behavioral evidence.
"""
from pathlib import Path
import argparse,re,json,hashlib
from decimal import Decimal

def active_blocks(text, convert):
    lines=[];block=[]
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith('*'):
            if block: lines.append(convert(''.join(block)));block=[]
            lines.append(line)
        else: block.append(line)
    if block: lines.append(convert(''.join(block)))
    return ''.join(lines)

def expressions(text):
    def quoted(match):
        formula=match[1]
        # Upstream resistor DW uses {"formula"}; one quote delimiter is
        # sufficient in SPICE and keeps the exact mathematical expression.
        if formula.strip().startswith('"') and formula.strip().endswith('"'):
            formula=formula.strip()[1:-1]
        return "'"+formula+"'"
    return active_blocks(text,lambda block: re.sub(r'\{([^{}]*)\}',quoted,block))

def geometry(text):
    # Spectre ignores suffix after exponent; raw SKY130 cell view expresses
    # micron geometries as e.g. 1.5e+06u. Rewrite its mathematical value 1.5.
    return active_blocks(text,lambda block: re.sub(r'(?<![\w.])([0-9]+(?:\.[0-9]*)?[eE][+-]?[0-9]+)[uU]\b',lambda m:format(Decimal(m[1])*Decimal('1e-6'),'f'),block))


def instance_parameters(text):
    """Expand sibling instance parameters in expressions at the call site.

    Ngspice resolves e.g. AD={...W/nf...} against this instance's W/nf.
    Spectre resolves a subcircuit call expression in the enclosing scope.
    Parenthesized substitution preserves the original arithmetic and values.
    """
    assignment=re.compile(r"([A-Za-z_]\w*)\s*=\s*('[^']*'|\"[^\"]*\"|[^\s]+)")
    identifier=re.compile(r'\b[A-Za-z_]\w*\b')
    def convert(lines):
        original=''.join(lines)
        logical=re.sub(r'\n\s*\+\s*',' ',original)
        pairs=list(assignment.finditer(logical))
        params={m[1].lower():m[2] for m in pairs}
        def bind(formula,excluded):
            def replace(match):
                name=match[0].lower()
                if name not in params or name in excluded:return match[0]
                value=params[name]
                if value[:1] in ["'",'"']:value=value[1:-1]
                return '('+bind(value,excluded|{name})+')'
            return identifier.sub(replace,formula)
        edits=[]
        for match in pairs:
            value=match[2]
            if value[:1] not in ["'",'"']:continue
            changed=value[0]+bind(value[1:-1],{match[1].lower()})+value[-1]
            if changed!=value:edits.append((match.start(2),match.end(2),changed))
        if not edits:return original
        for start,end,value in reversed(edits):logical=logical[:start]+value+logical[end:]
        return logical
    output=[];pending=[]
    for line in text.splitlines(keepends=True):
        if pending and line.lstrip().startswith('+'):pending.append(line);continue
        if pending:output.append(convert(pending));pending=[]
        if re.match(r'\s*[xX]\S+\s',line):pending=[line]
        else:output.append(line)
    if pending:output.append(convert(pending))
    return ''.join(output)

def configure_netlist(text):
    text=instance_parameters(expressions(text))
    if 'sourceCompat options redefinedparams=warning' not in text:
        text=text.replace('global 0\n','global 0\nsourceCompat options redefinedparams=warning\n',1)
    return text

def prepare(task):
    path=task/'tests/cases.json';cases=json.loads(path.read_text())
    changes=[]
    for case in cases:
        case['netlist']=configure_netlist(case['netlist'])
        for name,text in case.get('support',{}).items():
            if name.endswith('.spice'):
                changed=instance_parameters(geometry(expressions(text)))
                case['support'][name]=changed
                changes.append(dict(case=case['name'],asset=name,before_sha256=hashlib.sha256(text.encode()).hexdigest(),after_sha256=hashlib.sha256(changed.encode()).hexdigest()))
    path.write_text(json.dumps(cases,indent=2)+'\n')
    (task/'syntax-translation.json').write_text(json.dumps(dict(operations=['brace expressions to equivalent SPICE single quotes','exponent-plus-u to equal numeric micron value'],assets=changes),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--task',type=Path,required=True);a=p.parse_args();prepare(a.task)
