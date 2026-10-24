"""Check public producer provenance of the initial/zero lifecycle fixture.

This captures the real public transient transport before native execution. It
never edits schema fields or synthesizes an event body. --write regenerates it.
"""
from pathlib import Path
import argparse
import json
import sys
from unittest.mock import patch


def generated():
    fixtures = Path(__file__).resolve().parent
    sys.path.insert(0, str(fixtures.parents[2] / 'src'))
    from evas import compile_sources, Instance, transient
    program = compile_sources(
        {'initial-split-lifecycle.va': (fixtures / 'initial_split_lifecycle.va').read_text()},
        [Instance('dut', 'm', {'u': 'u', 'y': 'y', 'r': '0'})])
    class Captured(Exception):
        pass
    def capture(request, *_):
        raise Captured(request)
    with patch('evas.runtime._invoke', capture):
        try:
            transient(program, {'u': [[0, 0], [1, 0]]}, [0, .25, .5, 1],
                      stop=1, max_step=1, kernel='unused-captured-public-transport')
        except Captured as saved:
            return json.loads(json.dumps(saved.args[0]))
    raise AssertionError('public transport was not captured')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    options = parser.parse_args()
    result = generated()
    destination = Path(__file__).with_name('initial_split_lifecycle.request.json')
    if options.write:
        destination.write_text(json.dumps(result, indent=2) + '\n')
    else:
        assert result == json.loads(destination.read_text())
    print('initial split lifecycle public source transport matches')
