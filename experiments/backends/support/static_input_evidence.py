"""Prove the exact driven inputs in the fixed F03/F04 stateless EVAS cards.

The caller separately verifies the model, compiler/kernel and lane manifest.
This adapter preserves the old assessment and all numerical budgets. It only
discharges the exact-input obligation after validating the physical input path.
"""
from copy import deepcopy
import math
import struct


def bits(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('nonfinite or invalid voltage')
    return struct.pack('>d', value)


def qualify(card, program, response, request, rows, *, producer_qualified=False):
    try:
        if not producer_qualified or card['group_id'] not in ('F03', 'F04'):
            raise ValueError('unreviewed producer or unsupported fixed group')
        if card.get('events') or card.get('counter_channels') or card.get('phase_obligations'):
            raise ValueError('dynamic or phase-dependent card is outside this proof')
        if any(program.get(key) for key in ('states', 'events', 'operators')):
            raise ValueError('program has state, event or historical operator')
        if program['schema_version'] != response['schema_version'] or program['nodes'] != response['nodes']:
            raise ValueError('program/response identity mismatch')
        evidence = response['observation_evidence']
        if evidence['nodes'] != program['nodes'] or evidence['initial_settled'] is not True:
            raise ValueError('unsettled initial observation or wrong node identity')
        times = response['transient']['times']
        solutions = response['solutions']
        bounds = evidence['voltage_bounds_V']
        if not rows or not len(rows) == len(times) == len(solutions) == len(bounds) == len(evidence['sample_origins']):
            raise ValueError('incomplete native observation mapping')
        if any(origin != 'stateless_working_point' for origin in evidence['sample_origins']):
            raise ValueError('sample did not use the stateless physical path')
        nodes = program['nodes']
        input_indexes = {nodes.index(name) for name in card['inputs']}
        allowed = input_indexes | {nodes.index('0')}
        def expression(expr):
            if expr['op'] == 'affine':
                if any(t['node'] not in allowed for t in expr['terms'] if t['coefficient']):
                    raise ValueError('consumer depends on an unproved internal node')
                return
            if expr['op'] not in ('add', 'multiply', 'select', 'logical_not', 'logical_and', 'logical_or'):
                raise ValueError('consumer expression is outside the static proof')
            def children(value):
                if isinstance(value, dict):
                    if 'op' in value:
                        expression(value)
                    else:
                        for child in value.values():
                            children(child)
                elif isinstance(value, (list, tuple)):
                    for child in value:
                        children(child)
            for value in expr.values():
                children(value)
        for contribution in program['contributions']:
            if contribution['positive'] in input_indexes or contribution['negative'] in input_indexes:
                raise ValueError('DUT also contributes to a driven input')
            expression(contribution['rhs'])
        request_inputs = request['inputs']
        if set(request_inputs) != set(card['inputs']):
            raise ValueError('driven input inventory differs')
        expected = {}
        for name, points in card['inputs'].items():
            actual_points = request_inputs[name]
            if (len(actual_points) != len(points)
                    or any(len(p) != 2 for p in actual_points)
                    or any(bits(t) != bits(a) or bits(v) != bits(b)
                           for (t, v), (a, b) in zip(actual_points, points, strict=True))
                    or any(bits(v) != bits(points[0][1]) for _, v in points)):
                raise ValueError('input is not the frozen constant PWL')
            expected[name] = bits(points[0][1])
        for row, time, solution, node_bounds in zip(rows, times, solutions, bounds, strict=True):
            if (bits(row['time']) != bits(time) or len(node_bounds) != len(nodes)
                    or len(solution['voltages']) != len(nodes)):
                raise ValueError('native time or bound mapping differs')
            for i, name in enumerate(nodes):
                if name == '0':
                    if (solution['voltages'][i] != 0. or node_bounds[i] != [0., 0.]
                            or ('0' in row and row['0'] != 0.)):
                        raise ValueError('physical ground is not exactly zero')
                    continue
                if (bits(row[name]) != bits(solution['voltages'][i]) or len(node_bounds[i]) != 2
                        or not all(math.isfinite(v) for v in node_bounds[i])
                        or not node_bounds[i][0] <= row[name] <= node_bounds[i][1]):
                    raise ValueError('native voltage or bound mapping differs')
            for name, target in expected.items():
                i = nodes.index(name)
                if (bits(row[name]) != target or bits(solution['voltages'][i]) != target
                        or any(bits(v) != target for v in node_bounds[i])):
                    raise ValueError('driven value or physical point enclosure differs')
        return {'status': 'qualified', 'scope': 'F03/F04 constant physical inputs, finite observations',
                'input_names': sorted(expected), 'observation_count': len(rows)}
    except (ValueError, KeyError, IndexError, TypeError, OverflowError) as error:
        return {'status': 'unknown', 'reason': str(error)}


def reanalyze(science, card, program, response, request, rows, contract, *, producer_qualified=False):
    result = {'original_assessment': science.assess(card, rows, contract)}
    proof = qualify(card, program, response, request, rows, producer_qualified=producer_qualified)
    result['exact_input_evidence'] = proof
    if proof['status'] == 'qualified':
        resolved = deepcopy(card)
        resolved.pop('input_exact_evidence_required', None)
        result['new_assessment'] = science.assess(resolved, rows, contract)
    return result


def qualify_spectre(card, executed_source, rows, *, producer_qualified=False):
    """Check finite values after an external review of the actual ELF/save path.

    Approval covers the same installed modules, deck and native double reader.
    Equal printed inputs alone never grant that approval.
    """
    try:
        if not producer_qualified or card['group_id'] not in ('F03', 'F04'):
            raise ValueError('unreviewed producer or unsupported fixed group')
        if executed_source != card['source']:
            raise ValueError('executed source differs from the frozen card')
        if card.get('events') or card.get('counter_channels') or card.get('phase_obligations'):
            raise ValueError('dynamic card is outside the reviewed static ELF path')
        if len(rows) < 3:
            raise ValueError('incomplete native observations')
        required = {'time', *card['inputs'], *card['outputs']}
        if any(any(type(row.get(name)) not in (int, float)
                   or not math.isfinite(row[name]) for name in required) for row in rows):
            raise ValueError('missing or nonfinite native observations')
        if any(a['time'] >= b['time'] for a, b in zip(rows, rows[1:])):
            raise ValueError('native times are not strictly increasing')
        for name, points in card['inputs'].items():
            target = bits(points[0][1])
            if any(bits(value) != target for _, value in points):
                raise ValueError('input is not the frozen constant PWL')
            if any(bits(row[name]) != target for row in rows):
                raise ValueError('native input differs from the reviewed consumed double')
        return {'status': 'qualified', 'scope': 'reviewed Spectre F03/F04 static ELF and native double observations',
                'input_names': sorted(card['inputs']), 'observation_count': len(rows)}
    except (ValueError, KeyError, IndexError, TypeError, OverflowError) as error:
        return {'status': 'unknown', 'reason': str(error)}


def reanalyze_spectre(science, card, executed_source, rows, contract, *, producer_qualified=False):
    result = {'original_assessment': science.assess(card, rows, contract)}
    proof = qualify_spectre(card, executed_source, rows, producer_qualified=producer_qualified)
    result['exact_input_evidence'] = proof
    if proof['status'] == 'qualified':
        resolved = deepcopy(card)
        resolved.pop('input_exact_evidence_required', None)
        result['new_assessment'] = science.assess(resolved, rows, contract)
    return result
