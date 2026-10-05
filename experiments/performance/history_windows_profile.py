#!/usr/bin/env python3
"""Emit an instrumented source copy for an unreported F2 profiling build.

This tool never edits the supplied source. Build the result in a temporary
checkout. The counters describe linear traversal candidates, excluding binary
search comparisons, and evaluated segments. Do not time this build as production.
"""
import argparse
from pathlib import Path


def instrument(source, indexed):
    for method in ['range_bounds', 'derivative_bounds']:
        needle = '    pub(crate) fn ' + method + '(&self, time: I) -> Result<Vec<I>, Error> {'
        assert source.count(needle) == 1, method
        source = source.replace(needle, needle + '\n        let _span = crate::diagnostics::span("f2_' + method + '");')
    traversal = 'self.intersecting_segments(time)' if indexed else '&self.segments'
    length = 'self.intersecting_segments(time).len()' if indexed else 'self.segments.len()'
    needle = '        for segment in ' + traversal + ' {'
    if not indexed:
        needle += '\n            let lo = time.lo.max(segment.start);'
    assert source.count(needle) == 2, 'expected exactly two history traversals'
    source = source.replace(needle,
        '        crate::diagnostics::counter("f2_history_queries", 1);\n'
        '        crate::diagnostics::counter("f2_segments_examined", ' + length + ');\n' + needle)
    needle = '            let values = self.eval_segment_rows(segment, I { lo, hi }, Query::'
    assert source.count(needle) == 2, 'expected exactly two evaluations'
    return source.replace(needle,
        '            crate::diagnostics::counter("f2_segments_evaluated", 1);\n' + needle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--indexed', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must not exist')
    args.output.write_text(instrument(args.source.read_text(), args.indexed))


if __name__ == '__main__':
    main()
