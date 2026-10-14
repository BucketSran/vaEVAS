"""Only proved consumers can require a physical continuous-history restart."""
GUARDS = ["DYNAMICS", "CROSS", "TRANSITION", "COMPOSE"]

import math
import os
from pathlib import Path
import unittest

from evas import compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL, instance, model

KERNEL = Path(os.environ.get("EVAS_CAUSAL_KERNEL", DEFAULT_KERNEL))
TIMES = [0.0, 0.5, 0.75, 1.0]


def execute(body, declarations="real rate,q,k;electrical z;", times=TIMES):
    program = compile_sources({"parameter-identity.va": model(body, declarations)}, [instance()])
    return transient(program, {"u": [[0.0, 0.0], [1.0, 3.0]]}, times,
                     stop=1.0, max_step=0.125, vabstol=1e-8, reltol=0.0, kernel=KERNEL)


def value(result, time, node):
    row = result["solutions"][TIMES.index(time)]
    return row["voltages"][result["nodes"].index(node)]


class CausalParameterIdentity(unittest.TestCase):
    def test_uncertain_readout_event_does_not_remap_unchanged_selected_flow(self):
        result = execute("""
            @(initial_step) q=0;
            @(cross(V(u,r)-1,+1)) q=V(z,r);
            if(V(u,r)>2) rate=2/(1+V(u,r)*V(u,r));
            else rate=1/(1+V(u,r)*V(u,r));
            V(z,r)<+idt(rate,0.25);
            V(y,r)<+transition(q,0,0.125);
        """)
        for t in TIMES:
            expected = 0.25 + math.atan(min(3*t,2))/3
            if t > 2/3:
                expected += 2*(math.atan(3*t)-math.atan(2))/3
            self.assertLessEqual(abs(value(result,t,"dut:z")-expected),1e-8)
        sampled = 0.25 + math.atan(1)/3
        for t in TIMES[1:]:
            self.assertLessEqual(abs(value(result,t,"y")-sampled),1e-8)

    def test_parameter_in_a_future_unselected_arm_remains_live(self):
        result = execute("""
            @(initial_step) k=1;
            @(timer(0.5,0)) k=2;
            if(V(u,r)>2) rate=k/(1+V(u,r)*V(u,r));
            else rate=1/(1+V(u,r)*V(u,r));
            V(z,r)<+idt(rate,0.25);
            V(y,r)<+transition(k,0,0.125);
        """)
        for t in TIMES:
            expected = 0.25 + math.atan(min(3*t,2))/3
            if t > 2/3:
                expected += 2*(math.atan(3*t)-math.atan(2))/3
            self.assertLessEqual(abs(value(result,t,"dut:z")-expected),1e-8)


if __name__ == "__main__":
    unittest.main()
