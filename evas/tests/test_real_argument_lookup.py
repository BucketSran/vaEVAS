"""Actual real-argument contexts reuse correct lookups without value reuse."""
GUARDS = ['LANG','COMPOSE','EVENT-CONDITIONS']
import unittest
from evas import Instance,compile_sources
from evas.ir import RealBinary
from test_function_compatibility_dag import compile,nodes


class RealArgumentLookup(unittest.TestCase):
    def test_correct_program_context_keeps_all_calls_and_avoids_copy_work(self):
        for body in ('f=x;','f=x+x;'):
            source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;real q;'
                    'analog function real f;input x;real x;begin '+body+'end endfunction '
                    'analog begin @(initial_step)q=1;@(timer(1))q=f(q);V(y)<+q;end endmodule')
            p=compile_sources({'lookup.va':source},[Instance('M','m',dict(y='y'))]);p.to_dict()
            self.assertGreater(p._native_audit.counts['real_call_argument_context'],0)
            self.assertEqual(p._native_audit.counts.get('real_call_argument_lookup_copy',0),0)
            self.assertEqual(p._native_audit.used,sum(p._native_audit.counts.values()))

    def test_physical_context_still_pays_for_exactly_needed_lexical_copy(self):
        identity='analog function real ident;input x;real x;begin ident=x;end endfunction '
        p=compile(identity,'ident((V(u)+1.0)-V(u))');p.to_dict()
        self.assertEqual(p._native_audit.counts['real_call_argument_context'],1)
        self.assertGreater(p._native_audit.counts['real_call_argument_lookup_copy'],0)
        operations=[n.operation for n in nodes(p.contributions) if isinstance(n,RealBinary)]
        self.assertIn('add',operations);self.assertIn('subtract',operations)
