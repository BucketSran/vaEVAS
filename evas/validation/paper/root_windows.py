"""Independent represented-input roots; finite resolution is not VA tolerance.

Only the two reviewed source contracts are qualified. All timestamps and PWL
endpoints denote their exact binary64 values. No backend implementation is used.
"""
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path

from precision_reference import outward


@dataclass(frozen=True)
class Root:
    bounds: tuple
    late: F
    exact: F | None = None
    unit: F | None = None
    slope: F | None = None

    def compare(self, value):
        """Sign of value minus the exact root, with rational arithmetic."""
        value=F(value)
        if self.exact is not None:
            d=value-self.exact
        elif value<0:
            return -1
        else:
            d=(value/self.unit)**2-2
        return (d>0)-(d<0)

    def record(self):
        fraction=lambda v: None if v is None else [v.numerator,v.denominator]
        return {'root_bounds_s':list(self.bounds),'exact_root_fraction':fraction(self.exact),
                'algebraic_root':'sqrt(2)*T' if self.unit is not None else None,
                'unit_fraction':fraction(self.unit),'late_fraction_s':fraction(self.late),
                'actual_slope_fraction_V_s':fraction(self.slope)}


def reference_roots(card):
    """Reject model/contract substitution before deriving roots."""
    directory=Path(__file__).parent
    contract=json.loads((directory/'precision-root-v3.json').read_text())
    if contract['id']!='root-window-v3' or card.get('id') not in contract['scope']:
        raise ValueError('root contract is outside the two reviewed sources')
    for name,digest in contract['historical_assets'].items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('historical root-checker dependency drift: '+name)
    if card.get('id')=='SH-X-RAMP':
        from precision_v2 import load_contract
        expected=next(c for c in load_contract()['cards'] if c['id']==card['id'])
        if card!=expected:raise ValueError('SH-X source or frozen physical contract differs')
        roots=[]
        for (a,u),(b,v) in zip(card['inputs']['clk'],card['inputs']['clk'][1:]):
            a,u,b,v=map(F,(a,u,b,v))
            if u<F(.5)<=v:
                slope=(v-u)/(b-a)
                root=a+(F(.5)-u)/slope
                late=min(F(card['event_late_s']),F(card['cross_expression_tolerance_V'])/slope)
                roots.append(Root((outward(root,False),outward(root,True)),late,exact=root,slope=slope))
        if len(roots)!=card['expected_events']:raise ValueError('root inventory differs')
        return roots
    if card.get('id')=='EC04-v1':
        from precision_breadth_composition import cards
        expected=next(c for c in cards() if c['id']==card['id'])
        if card!=expected:raise ValueError('EC04 source or frozen physical contract differs')
        T=F(card['unit_s']);event=card['events'][0];late=F(event['late_s'])
        with localcontext() as ctx:
            ctx.prec=90
            seed=float(Decimal(2).sqrt()*Decimal(T.numerator)/Decimal(T.denominator))
        lo=hi=seed
        while (F(lo)/T)**2>2:lo=math.nextafter(lo,-math.inf)
        while (F(hi)/T)**2<2:hi=math.nextafter(hi,math.inf)
        # Exact monotonic-square check proves the entire TT-delayed interval
        # also meets expression tolerance. No derivative linearization is used.
        if ((F(hi)+late)/T)**2-2>F(event['expression_tolerance_V']):
            raise ValueError('time window lacks exact nonlinear guard proof')
        return [Root((lo,hi),late,unit=T)]
    raise ValueError('root contract is outside the two reviewed sources')


def timing(root, box, stop, ulps):
    """Classify complete boxes against true roots, never against a fitted root.

S is the existing output-time resolution. Pass at that resolution does not
prove strict no-early VA semantics; that claim has a separate result.
"""
    if (not isinstance(box,(list,tuple)) or len(box)!=2 or
        any(type(x) not in (int,float) or not math.isfinite(x) for x in box)
        or box[0]>box[1] or type(ulps) is not int or ulps<0 or
        type(stop) not in (int,float) or not math.isfinite(stop) or stop<=0):
        raise ValueError('invalid complete callback box or serialization allowance')
    a,b=map(F,box);S=F(ulps)*F(math.ulp(stop))
    def classify(s, unresolved):
        if root.compare(b+s)<0 or root.compare(a-s-root.late)>0:return 'behavior_error'
        if root.compare(a+s)>=0 and root.compare(b-s-root.late)<=0:return 'pass'
        return unresolved
    return {**root.record(),'callback_bounds_s':list(box),'serialization_allowance_s':float(S),
            'strict_semantic_timing':classify(F(0),'unresolved'),
            'serialized_resolution_timing':classify(S,'evidence_insufficient'),
            'claim':'finite time-export resolution; S is not an early language tolerance'}


def reference_card(card, ulps):
    """Expand only reference evaluation metadata, independently of observations.

The independent timing() check owns acceptance. This precomputed domain lets
the unchanged historical reference evaluate whole boxes; it grants no pass.
"""
    roots=reference_roots(card)
    if card['id']!='EC04-v1':raise ValueError('composition reference adapter requires EC04')
    result=deepcopy(card);S=F(ulps)*F(math.ulp(card['stop_s']))
    for event,root in zip(result['events'],roots,strict=True):
        low=outward(F(root.bounds[0])-S,False)
        high=outward(F(root.bounds[1])+root.late+S,True)
        width=outward(F(high)-F(low),True)
        # The reference adds binary64 endpoints; callback adapters add their
        # exact represented fractions. Both must cover the same upper bound.
        while F(low+width)<F(high) or F(low)+F(width)<F(high):
            width=math.nextafter(width,math.inf)
        event.update(nominal_s=low,early_s=0.,late_s=width)
    return result
