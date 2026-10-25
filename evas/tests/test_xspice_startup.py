"""P1 public admission, final zero seed and bounded independent timer plans."""
GUARDS = ["LANG", "TIMER", "TRANSITION", "COMPOSE"]

from pathlib import Path
import re
import subprocess
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


class InitialProcedureExecution(unittest.TestCase):
    def check_initial_states(self, body, expected):
        # Execute the public artifact's DC state program with a C compiler.
        # Poison locals so a read before assignment fails deterministically.
        # This isolates source ordering from the optional ngspice SDK.
        source = ('`include "disciplines.vams"\nmodule m(u,y); input u; output y; '
                  'electrical u,y; real a,q,z; analog begin ' + body + ' end endmodule')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            meta = compile_model({"initial.va": source}, root / "model")
            generated = (root / "model/cfunc.mod").read_text()
            defines = "\n".join(re.findall(r"^#define .*$", generated, re.MULTILINE))
            helpers = generated.split("static Dual ad_const", 1)[1].split("static void request", 1)[0]
            dc = generated.split("if(ANALYSIS==MIF_DC) {", 1)[1].split("cur->guard=", 1)[0]
            indices = {name: index for index, name in enumerate(meta["state_names"])}
            assertions = "\n".join(
                f'if (!isfinite(states[{indices[name]}].v) || '
                f'fabs(states[{indices[name]}].v - ({value})) > 1e-12) return 1;'
                for name, value in expected.items()
            )
            harness = '''#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
''' + defines + '''
#define PARAM(name) 0
typedef struct { double v,d[IV]; } Dual;
typedef struct { double values[SV]; } Frame;
typedef struct { Frame previous_trial; int dc_injected; } Diagnostics;
static void fail(const char *message) { fputs(message, stderr); exit(2); }
static Dual ad_const''' + helpers + '''
int main(void) {
 Frame storage, *cur=&storage;
 Diagnostics diagnostic={0}, *d=&diagnostic;
 Dual inputs[IV], states[SV], locals[64]; int i;
 for (int trial=0; trial<2; ++trial) {
  double input=trial ? -0.625 : 1.25;
  inputs[0]=ad_input(input,0);
  memset(cur,0x55,sizeof(*cur));
  for(i=0;i<64;++i)locals[i]=ad_const(NAN);
''' + dc + assertions + '\n }\n return 0;\n}\n'
            (root / "check.c").write_text(harness)
            compiled = subprocess.run(["cc", "-std=c99", str(root / "check.c"), "-lm", "-o", str(root / "check")], capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            run = subprocess.run([str(root / "check")], capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_initial_event_reads_preceding_input_snapshot(self):
        self.check_initial_states('a=V(u); @(initial_step) q=a; V(y)<+q;', {"q": "input"})

    def test_local_between_initial_events_reads_updated_state(self):
        self.check_initial_states('@(initial_step) q=2; a=q*V(u); @(initial_step) z=a; V(y)<+z;', {"q": "2", "z": "2*input"})

    def test_later_initial_write_does_not_recompute_earlier_snapshot(self):
        self.check_initial_states('@(initial_step) q=2; a=q*V(u); @(initial_step) begin q=9; z=a; end V(y)<+z;', {"q": "9", "z": "2*input"})


if __name__ == "__main__":
    unittest.main()
