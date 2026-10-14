"""Event decisions in expanded loops retain structural and binding checks."""
GUARDS = ["LANG", "EVENT-CONDITIONS", "EVENT-ORDER"]
import unittest

from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model


class EventPredicateStructure(unittest.TestCase):
    def compile(self, body, declarations="genvar i; real n;", instances=None):
        return compile_sources({"predicate.va": model(body, declarations)},
                               instances or [instance()])

    def run_values(self, program, node="y"):
        result = transient(program, {"u": [[0, -1], [1, -1]]}, [0, .75, 1],
                           stop=1, max_step=.25, kernel=KERNEL)
        return [row["voltages"][program.nodes.index(node)] for row in result["solutions"]]

    def test_abs_min_max_in_loop(self):
        program = self.compile("""@(timer(0.5)) for(i=0;i<1;i=i+1) begin
          if(abs(V(u,r))>0.5) n=n+1;
          if(min(V(u,r),0)<-0.5) n=n+10;
          if(max(V(u,r),0)<0.5) n=n+100;
          end V(y,r)<+n;""")
        self.assertEqual(self.run_values(program), [0, 111, 111])

    def test_reads_preceding_state_update(self):
        program = self.compile("""@(initial_step) n=-2;
          @(timer(0.5)) for(i=0;i<3;i=i+1) begin
          n=n+1; if(abs(n)<0.5) n=n+10; end V(y,r)<+n;""")
        self.assertEqual(self.run_values(program), [-2, 11, 11])

    def test_parameter_bindings_are_instance_local(self):
        source = """@(timer(0.5)) for(i=0;i<1;i=i+1)
          if(abs(OFFSET)>1) n=1; V(y,r)<+n;"""
        a = instance("a", connections={"u": "u", "y": "a", "r": "0"}, parameters={"OFFSET": 0})
        b = instance("b", connections={"u": "u", "y": "b", "r": "0"}, parameters={"OFFSET": -2})
        program = self.compile(source, "parameter real OFFSET=0; genvar i; real n;", [a, b])
        self.assertEqual(self.run_values(program, "a"), [0, 0, 0])
        self.assertEqual(self.run_values(program, "b"), [0, 1, 1])

    def test_unselected_or_erased_invalid_operands_still_reject(self):
        expressions = [("abs(V(missing,r))", "undeclared"), ("abs(idt(V(u,r),0))", "history/operator"),
                       ("min(V(u,r)*V(u,r),0)", "affine"), ("max(V(y,r),0)", "voltage network")]
        for count in (0, 1):
            for expr, reason in expressions:
                with self.subTest(count=count, expr=expr), self.assertRaisesRegex(CompileError, reason):
                    self.compile(f"@(timer(0.5)) for(i=0;i<{count};i=i+1) "
                                 f"if({expr}>0) n=1; V(y,r)<+n;")
