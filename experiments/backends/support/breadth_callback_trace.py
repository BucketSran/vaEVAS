"""Separately identified read-only callback traces for frozen breadth cards.

Only the listed counter assignments are instrumented. This creates a new
attempt; it does not replace the original model or any archived observations.
No logged callback is discarded or deduplicated by this module.
"""
import re


COUNTERS = {
    'F07-base': ('n',), 'F19-base': ('n',),
    **{f'EC{i:02}-v1': ('n0',) for i in (1, 2, 3, 4, 5, 6, 7, 8, 10, 13, 21, 23, 24)},
    'EC06-v2': ('n0',), 'EC20-v1': ('a', 'b'),
}


def instrument(card, *, format_version=2):
    """Return source and exact replacement receipt, without changing the card."""
    if card['id'] not in COUNTERS or not card.get('events'):
        raise ValueError('unreviewed callback source')
    source = card['source']
    if 'EVAS_BREADTH_CALLBACK' in source:
        raise ValueError('source is already instrumented')
    if type(format_version) is not int or format_version not in (1, 2):
        raise ValueError('unknown trace format')
    replacements = []
    for counter in COUNTERS[card['id']]:
        assignment = f'{counter}={counter}+1;'
        count = source.count(assignment)
        if count == 0:
            raise ValueError('reviewed counter assignment is absent')
        # F07/F19 use real counters; other cards use integer counters. The
        # multiplication converts either to real without changing the state.
        trace = (f'$strobe("EVAS_BREADTH_CALLBACK {counter} %m %.17g %.17g",1.0*{counter},$abstime);'
                 if format_version == 2 else
                 f'$strobe("EVAS_BREADTH_CALLBACK {counter} %m %d %.17g",{counter},$abstime);')
        source = source.replace(assignment, assignment + ' ' + trace)
        replacements.append({'assignment': assignment, 'trace': trace, 'sites': count})
    return source, {'card': card['id'], 'format_version': format_version, 'replacements': replacements,
                    'change': 'append read-only strobe after counter update',
                    'scope': 'separate execution, original mathematics and observations retained'}


def parse(log):
    """Preserve every actual line, including retries and hidden child instances."""
    pattern = re.compile(r'EVAS_BREADTH_CALLBACK (\w+) (\S+) (\d+) ([+\-0-9.eE]+)')
    records = []
    for line in log.splitlines():
        if 'EVAS_BREADTH_CALLBACK' not in line:
            continue
        match = pattern.fullmatch(line.strip())
        if not match:
            raise ValueError('malformed callback trace')
        records.append({'counter_symbol': match[1], 'instance': match[2],
                        'index': int(match[3]), 'time_token': match[4]})
    return records
