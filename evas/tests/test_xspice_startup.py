"""P1 public admission, final zero seed and bounded independent timer plans."""
GUARDS = ["LANG", "TIMER", "TRANSITION", "COMPOSE"]

from pathlib import Path
import tempfile
import unittest

from evas.xspice import compile_model
from evas import CompileError

SOURCE = (Path(__file__).resolve().parents[1] / "examples/xspice/clock1800/zero_start.va").read_text()


class ZeroPeriodicAdmission(unittest.TestCase):
    def test_zero_periodic_timer_with_nonidempotent_private_counter_is_admitted(self):
        # Native lifecycle validation separately checks final seed/count at t0.
        with tempfile.TemporaryDirectory() as d:
            compile_model({"zero_start.va": SOURCE}, Path(d) / "model")

    def test_complete_parameterized_clock_preserves_32_event_identities(self):
        import json
        source = (Path(__file__).resolve().parents[1] / "examples/xspice/clock1800/clock1800_standard.va").read_text()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "model"
            compile_model({"clock.va": source}, out)
            self.assertEqual(len(json.loads((out / "ir.json").read_text())["events"]), 32)

    def test_conflicting_zero_and_conditional_dependency_batches_are_rejected(self):
        for body in (
            '@(timer(0,10n)) a=1; @(timer(0,10n)) a=2;',
            '@(timer(0,10n)) a=1; @(timer(0,10n)) if(a>0) b=2;',
            '@(timer(0,10n)) a=1; @(timer(0,10n)) b=(a>0)?1:2;',
        ):
            text='`include "disciplines.vams"\nmodule m(y); output y; electrical y; real a,b; analog begin @(initial_step) begin a=0;b=0;end '+body+' V(y)<+transition(a+b,0,20p,20p); end endmodule'
            with self.subTest(body=body), tempfile.TemporaryDirectory() as d, self.assertRaises(CompileError):
                compile_model({"batch.va":text},Path(d)/'model')

    def test_42_event_variant_and_over_capacity_are_distinguished(self):
        import json
        source=(Path(__file__).resolve().parents[1]/"examples/xspice/clock1800/clock1800_standard.va").read_text()
        for count in (4,7):
            with self.subTest(count=count),tempfile.TemporaryDirectory() as d:
                params={k+'_num':count for k in ('S','SS','NC_AZ','NC','CONV')}
                params['RST_period']=2400e-9 if count==4 else 4200e-9
                if count==7:
                    with self.assertRaisesRegex(CompileError,'at most64'):
                        compile_model({'clock.va':source},Path(d)/'model',parameters=params)
                else:
                    compile_model({'clock.va':source},Path(d)/'model',parameters=params)
                    self.assertEqual(len(json.loads((Path(d)/'model/ir.json').read_text())['events']),42)


if __name__ == "__main__":
    unittest.main()
