"""Frontend dispatch checks; these tests never invoke a simulator kernel."""
import unittest

from evas import CompileError, Instance, compile_sources

GUARDS = ['LANG']

def compile_body(body):
    source = ('`include "disciplines.vams"\n'
              'module m(u,y); input u; output y; electrical u,y; real q; '
              'analog begin ' + body + ' end endmodule')
    return compile_sources({'dispatch.va': source}, [
        Instance('M', 'm', {'u': 'u', 'y': 'y'})]).to_dict()


class FrontendStatementDispatch(unittest.TestCase):
    def test_event_display_retains_arguments_and_source_order(self):
        program = compile_body('q=V(u); @(timer(0.5)) begin '
                               '$display("before=%g",q); q=q+1; '
                               '$display("after=%g",q); end V(y)<+q;')
        body = program['events'][0]['body']
        self.assertEqual([step['kind'] for step in body],
                         ['display', 'assign', 'display'])
        self.assertEqual([body[i]['format'] for i in (0, 2)],
                         ['before=%g', 'after=%g'])
        self.assertTrue(body[0]['args'])
        self.assertTrue(body[2]['args'])

    def test_uncaptured_ordinary_display_has_an_explicit_diagnostic(self):
        # This records the current boundary; it does not qualify ordinary
        # display or change the activation-scope test's kernel expectation.
        for body in ('q=V(u); $display("q=%g",q); V(y)<+q;',
                     'q=V(u); if(V(u)>0) $display("q=%g",q); V(y)<+q;'):
            with self.subTest(body=body):
                with self.assertRaises(CompileError) as caught:
                    compile_body(body)
                self.assertEqual(caught.exception.diagnostic['code'],
                                 'unsupported_event_context')
                self.assertIn('executable capture support', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
