"""Original source obligations for the narrow ordinary history consumer."""
from dataclasses import fields, is_dataclass
from .syntax import Expr, Loop, ContributionStatement, CompileError, OPERATOR_NAMES

def original_reads(model, node_ids, owner):
    """Visit every original arm/alias before loops or scalarization can discard it."""
    if model.arrays:
        raise CompileError("ordinary history consumers require original scalars without arrays")
    owner.debit("history_source_copy")
    reads=set()
    def debit(kind, amount=1, item=None):
        owner.debit(kind, amount, item)
    def expression(item):
        debit("history_source_visit",item=item)
        debit("history_source_copy",item=item)
        degrees=[]
        for arg in item.args:
            debit("history_source_copy",item=arg)
            degrees.append(expression(arg))
        if item.op=="voltage":
            if any(arg.op!="node" for arg in item.args):
                raise CompileError("ordinary history read requires an original scalar probe",token=item.token)
            for arg in item.args:
                if str(arg.value) not in node_ids:
                    raise CompileError("unknown original history probe",token=item.token)
                debit("history_source_copy",item=arg)
                reads.add(node_ids[str(arg.value)])
            return 1
        if item.op in OPERATOR_NAMES:
            if item.op!="transition":
                raise CompileError("ordinary history consumer requires Transition histories",token=item.token)
            return 1
        if item.op=="parameter":
            return int(item.value in model.variables)
        if item.op in ("number","node"):
            return 0
        if item.op=="*":
            if sum(degrees)>1:
                raise CompileError("original history expressions must be jointly affine in every arm",token=item.token)
            return sum(degrees)
        if item.op in ("/","%"):
            if len(degrees)!=2 or degrees[1]!=0:
                raise CompileError("original history division requires a constant divisor",token=item.token)
            divisor=item.args[1]
            if divisor.op=="number" and divisor.value==0:
                raise CompileError("original history division has a zero divisor",token=item.token)
            return degrees[0]
        if item.op=="power" and degrees and degrees[0]:
            raise CompileError("original history powers are outside affine scope",token=item.token)
        if item.op in ("call","index","array"):
            raise CompileError("original history expressions require scalar affine source operations",token=item.token)
        return max(degrees,default=0)
    def visit(item):
        debit("history_source_visit",item=item)
        if isinstance(item,Expr):
            expression(item)
        elif isinstance(item,Loop):
            raise CompileError("original history consumer loops require a separate proof",token=item.token)
        elif isinstance(item,dict):
            for value in item.values():visit(value)
        elif isinstance(item,(list,tuple,set,frozenset)):
            for value in item:visit(value)
        elif is_dataclass(item):
            for field in fields(item):
                if field.name in ("token","declaration_token","expansion"):
                    continue
                if isinstance(item,ContributionStatement) and field.name=="branch":
                    continue
                visit(getattr(item,field.name))
    visit(model)
    return reads
