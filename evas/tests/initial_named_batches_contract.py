"""Source-derived named states for initial and subsequent exact-zero batches."""
from dataclasses import asdict
from initial_source_sequence_contract import check_initial_source_sequence


def check_named_initial_batches(result,program,initial_values,zero_steps):
    wire=program if isinstance(program,dict) else asdict(program)
    names=[s['name'].split(':')[-1] for s in wire['states']]
    assert len(names)==len(set(names)), 'one instance, unambiguous named source states'
    assert set(names)<=set(initial_values), 'all retained states have source-derived expectations'
    declaration=[0]*len(names)  # These fixtures have no declaration initializers.
    initial=[initial_values[name] for name in names]
    expected=[(0,'initial_step',declaration,initial)]
    previous=initial
    values=dict(initial_values)
    for ordinal,kind,changes,*extra in zero_steps:
        values.update(changes)
        after=[values[name] for name in names]
        expected.append((ordinal,kind,previous,after,*extra))
        previous=after
    return check_initial_source_sequence(result,wire,declaration,expected)
