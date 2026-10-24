"""Independent exact-rational, per-operation binary64 oracle for statistics tests.

No EVAS evaluator is used. Source point values and each source operation are
rounded independently. Public voltage boxes are checked as complete enclosures;
state boxes are not exported by this protocol and are not invented here.
"""
from collections import Counter
from fractions import Fraction as F
import math
import struct


def bits(value):
    return struct.pack('>d', float(value))


def rn(value):
    exact = F(value)
    result = float(exact)
    candidates = [math.nextafter(result, -math.inf), result,
                  math.nextafter(result, math.inf)]
    distances = [(abs(F(candidate) - exact), candidate) for candidate in candidates]
    best = min(distance for distance, _ in distances)
    assert abs(F(result) - exact) == best
    tied = [candidate for distance, candidate in distances if distance == best]
    if len(tied) > 1:
        assert int.from_bytes(bits(result), 'big') & 1 == 0
    return result


def add(left, right): return rn(F(left) + F(right))
def sub(left, right): return rn(F(left) - F(right))
def mul(left, right): return rn(F(left) * F(right))
def div(left, right): return rn(F(left) / F(right))


def square_root(value):
    exact = F(value)
    if exact < 0:
        raise ValueError('sqrt domain')
    numerator, denominator = math.isqrt(exact.numerator), math.isqrt(exact.denominator)
    assert numerator * numerator == exact.numerator
    assert denominator * denominator == exact.denominator
    return rn(F(numerator, denominator))


def same(test, actual, expected):
    test.assertEqual(len(actual), len(expected))
    for found, wanted in zip(actual, expected):
        test.assertEqual(bits(found), bits(wanted), (found, wanted))


def _origin(origin):
    return f"{origin['source']}:{origin['line']}:{origin['column']} ({origin['instance']})"


def _display_nodes(value):
    if isinstance(value, dict):
        if value.get('kind') == 'display':
            yield value
        for item in value.values():
            yield from _display_nodes(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _display_nodes(item)


def _pwl(knots, time):
    time = F(time)
    if time <= F(knots[0][0]): return F(knots[0][1])
    for (t0, y0), (t1, y1) in zip(knots, knots[1:]):
        if time <= F(t1):
            return F(y0) + (time-F(t0))*(F(y1)-F(y0))/(F(t1)-F(t0))
    return F(knots[-1][1])


def _participants(test, program, source, specs):
    # IDs are fixture coordinates, not participant semantics. Bind each one to
    # the source-owned role before looking at any response record.
    for event_id, owner, kind, line, column, start, period in specs:
        event = program['events'][event_id]
        origin = event['origin']
        test.assertEqual((origin['source'], origin['instance'], origin['line'], origin['column']),
                         (source, owner, line, column))
        test.assertEqual(event['trigger']['kind'], kind)
        if kind == 'timer':
            test.assertEqual(bits(event['trigger']['start']), bits(start))
            test.assertEqual(bits(event['trigger']['period']), bits(period))
            test.assertEqual(bits(event['trigger']['time_tolerance']), bits(1e-12))


def check_trace(test, result, program, sources, times, states, events, displays,
                participant_groups=None, unordered_displays=False):
    """events includes every initial record; nothing is removed from result."""
    transient = result['transient']
    same(test, transient['times'], times)
    test.assertEqual(len(transient['states']), len(states))
    for actual, expected in zip(transient['states'], states): same(test, actual, expected)
    records = transient['events']
    test.assertEqual(len(records), len(events))
    test.assertEqual(sum(record['kind'] == 'initial_step' for record in records),
                     sum(kind == 'initial_step' for kind, *_ in events))
    # Only the caller's explicit source-owned phases can be unordered. Never
    # infer an occurrence from equal response floats or overlapping windows.
    groups = participant_groups or tuple((spec[4],) for spec in events)
    paired = []
    cursor = 0
    for group in groups:
        expected_phase = events[cursor:cursor+len(group)]
        actual_phase = records[cursor:cursor+len(group)]
        test.assertEqual(tuple(spec[4] for spec in expected_phase), tuple(group))
        test.assertEqual(len(set(group)), len(group))
        test.assertEqual(Counter(record['event'] for record in actual_phase), Counter(group))
        expected_by_id = {spec[4]: spec for spec in expected_phase}
        paired.extend((record, expected_by_id[record['event']]) for record in actual_phase)
        cursor += len(group)
    test.assertEqual(cursor, len(events))
    for record, (kind, time, before, after, event_id, owner) in paired:
        test.assertEqual(record['kind'], kind)
        test.assertEqual(bits(record['time']), bits(time))
        same(test, record['before'], before)
        same(test, record['after'], after)
        test.assertEqual(record['event'], event_id)
        event = program['events'][event_id]
        test.assertEqual(event['origin']['instance'], owner)
        test.assertEqual(event['trigger']['kind'], kind)
        test.assertEqual(record['origin'], _origin(event['origin']))
    output = transient['display_records']
    if unordered_displays:
        expected_keys = [(text,bits(time),event_id) for text,time,event_id,_,_ in displays]
        actual_keys = [(item['text'],bits(item['time']),item['event']) for item in output]
        test.assertEqual(len(set(expected_keys)), len(expected_keys))
        test.assertEqual(Counter(actual_keys), Counter(expected_keys))
        by_key = dict(zip(expected_keys, displays))
        display_pairs = [(item,by_key[key]) for item,key in zip(output,actual_keys)]
    else:
        test.assertEqual([item['text'] for item in output], [spec[0] for spec in displays])
        display_pairs = zip(output,displays)
    for item, (text, time, event_id, owner, position) in display_pairs:
        test.assertEqual(item['event'], event_id)
        test.assertEqual(bits(item['time']), bits(time))
        event = program['events'][event_id]
        test.assertEqual(event['origin']['instance'], owner)
        test.assertTrue(any(expected_id == event_id and bits(expected_time) == bits(time)
                            for _, expected_time, _, _, expected_id, _ in events))
        nodes = list(_display_nodes(event['body']))
        test.assertGreaterEqual(position, 0)
        test.assertLess(position, len(nodes))
        expected_origin = nodes[position]['origin']
        test.assertEqual(expected_origin['instance'], owner)
        test.assertEqual(item['origin'], _origin(expected_origin))
    evidence = result['observation_evidence']
    test.assertIs(evidence['initial_settled'], True)
    test.assertEqual(result['nodes'], ['0', *sources])
    test.assertEqual(evidence['nodes'], result['nodes'])
    boxes = evidence['voltage_bounds_V']
    test.assertEqual(len(boxes), len(times))
    test.assertEqual(len(result['solutions']), len(times))
    for time, solution, row in zip(times, result['solutions'], boxes):
        expected = [F(0), *(_pwl(knots, time) for knots in sources.values())]
        same(test, solution['voltages'], [rn(value) for value in expected])
        test.assertEqual(len(row), len(expected))
        for bound, value in zip(row, expected):
            test.assertEqual(len(bound), 2)
            test.assertTrue(all(math.isfinite(endpoint) for endpoint in bound))
            test.assertLessEqual(F(bound[0]), value)
            test.assertGreaterEqual(F(bound[1]), value)


def body_oracle(case):
    one = rn(1)
    cancellation = sub(add(rn(1e16), mul(one, one)), rn(1e16))
    inverse = sub(add(rn(1e16), div(one, one)), rn(1e16))
    assert bits(cancellation) == bits(0.) == bits(inverse)
    values = {
        'cancel': ([one,cancellation,0.], ['same 0 0']),
        'abs_cancel': ([one,abs(cancellation),0.], ['same 0 0']),
        'sqrt_cancel': ([one,square_root(cancellation),0.], []),
        'nested': ([one,abs(one),0.], ['selected 1']),
        'empty': ([0.,0.,0.], ['empty 0']),
        'math_order': ([min(mul(add(one,one),add(one,one)),3.),square_root(4.),0.], ['math 3 2']),
        'ternary': ([2.,square_root(mul(2.,2.)),0.], ['selected 2 2']),
        'integer': ([0.,0.,2.], ['n 2']),
        'condition': ([4.,abs(-4.),0.], ['condition 4']),
        'affine': ([one,add(cancellation,one),0.], ['no b=0']),
        'mixed': ([one,0.,0.], []),
        'math_cancel': ([one,sub(add(square_root(one),add(rn(1e16),one)),rn(1e16)),0.], ['no 0']),
    }
    return values[case]


def check_body(test, result, program, times, case):
    _participants(test,program,'measure.va',[
        (1,'M','initial_step',3,14,None,None),(0,'M','timer',4,1,.5,0.)])
    after, displays = body_oracle(case)
    zero = [0.,0.,0.]
    states = [zero if time < .5 else after for time in times]
    events = [('initial_step',0.,zero,zero,1,'M'),('timer',.5,zero,after,0,'M')]
    # Source display positions are explicit. The false branch is position1;
    # all remaining displayed body cases have one source display at position0.
    position = 1 if case in ('affine','math_cancel') else 0
    display_specs = [(text,.5,0,'M',position) for text in displays]
    check_trace(test,result,program,{'x':[[0,1],[1,1]]},times,states,events,display_specs)


def regression_oracle():
    state = [0.] * 12
    states = [state.copy()]
    events = [('initial_step',0.,state.copy(),state.copy(),2,'M')]
    for time, xx, yy in [(.25,-1.,-1.),(.5,0.,1.),(.75,1.,3.)]:
        before = state.copy()
        state[6], state[7] = rn(xx),rn(yy)
        state[0] += 1
        state[1],state[2] = add(state[1],state[6]),add(state[2],state[7])
        state[3] = add(state[3],mul(state[6],state[6]))
        state[4] = add(state[4],mul(state[6],state[7]))
        state[5] = add(state[5],mul(state[7],state[7]))
        events.append(('timer',time,before,state.copy(),0,'M'))
        states.append(state.copy())
    before = state.copy()
    n,sx,sy,sxx,sxy,syy = state[:6]
    state[8] = sub(mul(n,sxx),mul(sx,sx))
    state[9] = div(sub(mul(n,sxy),mul(sx,sy)),state[8])
    state[10] = div(sub(sy,mul(state[9],sx)),n)
    state[11] = square_root(max(0.,div(sub(sub(syy,mul(state[9],sxy)),mul(state[10],sy)),n)))
    events.append(('final_step',.75,before,state.copy(),1,'M'))
    return states,events


def check_regression(test,result,program):
    _participants(test,program,'statistics.va',[
        (2,'M','initial_step',5,2,None,None),(0,'M','timer',6,2,.25,.25),
        (1,'M','final_step',10,2,None,None)])
    states,events = regression_oracle()
    check_trace(test,result,program,{'x':[[0,-1],[.25,-1],[.5,0],[.75,1]],
                                   'y':[[0,-1],[.25,-1],[.5,1],[.75,3]]},
                [0,.25,.5,.75],states,events,[('fit 3 2 1 0',.75,1,'M',0)])


def check_instances(test,result,program):
    _participants(test,program,'instances.va',[
        (2,'A','initial_step',3,14,None,None),(3,'B','initial_step',3,14,None,None),
        (0,'A','timer',4,1,.5,0.),(1,'B','timer',4,1,.5,0.)])
    zero=[0.,0.,0.,0.];after=[mul(2.,1.),square_root(mul(2.,2.)),mul(3.,1.),square_root(mul(3.,3.))]
    check_trace(test,result,program,{'x':[[0,1],[1,1]]},[0,.5,1],[zero,after,after],
                [('initial_step',0.,zero,zero,2,'A'),('initial_step',0.,zero,zero,3,'B'),
                 ('timer',.5,zero,after,0,'A'),('timer',.5,zero,after,1,'B')],
                [('instance 2',.5,0,'A',0),('instance 3',.5,1,'B',0)],
                participant_groups=((2,3),(0,1)), unordered_displays=True)


def check_constant(test,result,program):
    _participants(test,program,'constant.va',[
        (2,'M','initial_step',3,14,None,None),(0,'M','timer',4,1,0.,0.),
        (1,'M','timer',5,1,.5,0.)])
    zero=[0.,0.];after_zero=[2.,0.];after_timer=[2.,2.]
    check_trace(test,result,program,{'x':[[0,1],[1,1]]},[0,.5,1],
                [after_zero,after_timer,after_timer],
                [('initial_step',0.,zero,zero,2,'M'),('timer',0.,zero,after_zero,0,'M'),
                 ('timer',.5,after_zero,after_timer,1,'M')],
                [('zero 2',0.,0,'M',0),('integer 2',.5,1,'M',0)])
