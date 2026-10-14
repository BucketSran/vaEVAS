"""Parameter specialization never erases the original event obligations."""
GUARDS = ["LANG", "EVENT-CONDITIONS", "EVENT-ORDER"]
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


class EventParameterSpecialization(unittest.TestCase):
    def compile(self, body, declarations="real x,q;", mode=1):
        source = model(body, "parameter integer mode=1; " + declarations)
        return compile_sources({"specialization.va": source}, [instance(parameters={"mode": mode})])

    def values(self, program):
        result = transient(program, {"u": [[0, 0], [1, 0]]}, [0, 0.75, 1],
                           stop=1, max_step=0.25, kernel=KERNEL)
        return [row["voltages"][program.nodes.index("y")] for row in result["solutions"]]

    def test_dead_pure_math_does_not_require_runtime_domain(self):
        for expression in ("sqrt(q)", "sqrt(-1.0)", "1.0/q", "q*q"):
            with self.subTest(expression=expression):
                program = self.compile(f"""@(initial_step) q=0;
                  @(timer(0.5)) if(mode==0) x={expression}; else x=2;
                  V(y,r)<+x;""")
                self.assertEqual(self.values(program), [0, 2, 2])

    def test_active_unsupported_math_still_rejects(self):
        with self.assertRaisesRegex(CompileError, "nonconstant mathematical"):
            self.compile("@(timer(0.5)) if(mode==0) x=sqrt(q); else x=2; V(y,r)<+x;", mode=0)

    def test_dead_integer_intermediate_in_real_value_is_not_erased(self):
        with self.assertRaisesRegex(CompileError, "integer intermediate"):
            self.compile("""@(initial_step) i=2147483647;
              @(timer(0.5)) if(mode==0) x=(i+1)-1; else x=2;
              V(y,r)<+x;""", "integer i; real x;")

    def test_erased_loop_names_indices_and_types_are_checked(self):
        cases = [("real x;", "x=sqrt(missing)", "unknown"),
                 ("real x,a[0:1];", "x=sqrt(a[2])", "outside"),
                 ("integer x;", "x=sqrt(-1.0)", "integral"),
                 ("real x,a[0:1]; integer b;", "x=a[b]", "use-site proof")]
        for declarations, statement, reason in cases:
            with self.subTest(statement=statement), self.assertRaisesRegex(CompileError, reason):
                self.compile(f"@(timer(0.5)) for(j=0;j<0;j=j+1) {statement}; V(y,r)<+1;",
                             "genvar j; " + declarations)

    def test_dead_control_keeps_kernel_dependency_checks(self):
        program = self.compile("""@(timer(0.5)) if(mode==1) q=2;
          else if(V(y,r)>0) q=3; V(y,r)<+q;""")
        with self.assertRaisesRegex(KernelError, "unsupported_condition"):
            self.values(program)

    def test_dead_decision_operand_keeps_input_scope(self):
        with self.assertRaisesRegex(CompileError, "input/inout"):
            self.compile("""@(timer(0.5)) if(mode==0)
              if(max(V(y,r),0.0)>0.0) x=1; V(y,r)<+1;""")

    def test_dead_assignment_decisions_keep_original_budget(self):
        value = "+".join(["abs(V(u,r))"] * 12)
        with self.assertRaisesRegex(CompileError, "expanded event decision budget"):
            self.compile(f"@(timer(0.5)) if(mode==0) x={value}; else x=2; V(y,r)<+x;")

    def test_dead_dynamic_writes_keep_dispatch_budget(self):
        with self.assertRaisesRegex(CompileError, "dispatch budget"):
            self.compile("""@(timer(0.5)) if(mode==0) begin a[b]=1; a[b]=2; end
              V(y,r)<+1;""", "integer b; real a[0:2048];")

    def test_static_real_index_type_is_not_inferred_from_value(self):
        for index in ("1.0", "idx"):
            with self.subTest(index=index), self.assertRaisesRegex(CompileError, "index"):
                self.compile(f"@(timer(0.5)) if(mode==0) x=a[{index}]; V(y,r)<+1;",
                             "real a[0:1],x; parameter real idx=1;")

    def test_erased_integer_intermediates_and_array_scalar_are_checked(self):
        for declarations, rhs, reason in (
            ("real x;", "sqrt((2147483647+1)-1)", "integer intermediate"),
            ("integer x;", "(2147483647+1)-1", "integer intermediate"),
            ("real x,a[0:1];", "sqrt(a)", "requires an index"),
        ):
            with self.subTest(rhs=rhs), self.assertRaisesRegex(CompileError, reason):
                self.compile(f"@(timer(0.5)) for(j=0;j<0;j=j+1) x={rhs}; V(y,r)<+1;",
                             "genvar j; " + declarations)

    def test_comparison_operands_and_equality_keep_decision_budget(self):
        values = ["(" + "+".join(["abs(V(u,r))"]*12) + ")>0.0",
                  "+".join(["0.5*(V(u,r)==0.0)"]*7)]
        for value in values:
            for mode in (0,1):
                with self.subTest(value=value,mode=mode), self.assertRaisesRegex(CompileError, "expanded event decision budget"):
                    self.compile(f"@(timer(0.5)) if(mode==0) x={value}; else x=2; V(y,r)<+x;",mode=mode)

    def test_typed_decision_arithmetic_remains_supported(self):
        for kind in ("integer", "real"):
            with self.subTest(kind=kind):
                p=self.compile("@(timer(0.5)) x=(V(u,r)>0.0)+1; V(y,r)<+x;",f"{kind} x;")
                result=transient(p,{"u":[[0,1],[1,1]]},[0,0.75,1],stop=1,max_step=0.25,kernel=KERNEL)
                self.assertEqual([row["voltages"][p.nodes.index("y")] for row in result["solutions"]],[0,2,2])

    def test_selection_value_arm_may_read_a_stateless_output(self):
        p=self.compile("@(timer(0.5)) if((V(u,r)>0.0 ? V(y,r):0.0)>0.0) x=1; V(y,r)<+1;","real x;")
        result=transient(p,{"u":[[0,1],[1,1]]},[0,0.75,1],stop=1,max_step=0.25,kernel=KERNEL)
        self.assertEqual(result["transient"]["states"],[[0],[1],[1]])

    def test_budget_surrogate_cannot_restrict_unused_mathematical_values(self):
        for rhs in ("sqrt(max(0.0,q*q))", "max(0.0,q/q)",
                    "max(0.0,sqrt(V(y,r)))"):
            with self.subTest(rhs=rhs):
                p=self.compile(f"@(timer(0.5)) if(mode==0) x={rhs}; else x=2; V(y,r)<+x;")
                self.assertEqual(self.values(p),[0,2,2])

    def test_resource_tree_preserves_typed_modulo(self):
        for rhs in ("abs(n%3)", "V(u,r)>0.0 ? n%3:0"):
            with self.subTest(rhs=rhs):
                p=self.compile(f"@(initial_step) n=5; @(timer(0.5)) x={rhs}; V(y,r)<+x;","integer n; real x;")
                result=transient(p,{"u":[[0,1],[1,1]]},[0,0.75,1],stop=1,max_step=0.25,kernel=KERNEL)
                self.assertEqual([row["voltages"][p.nodes.index("y")] for row in result["solutions"]],[0,2,2])

    def test_implicit_quotient_choices_keep_original_budget(self):
        for mode in (0,1):
            with self.subTest(mode=mode), self.assertRaisesRegex(CompileError,"expanded event decision budget"):
                self.compile("@(initial_step) if(V(u,r)>0.0) n=0; else n=64; @(timer(0.5)) if(mode==0) x=(n/1)+(n/1); V(y,r)<+x;","integer n; real x;",mode=mode)

    def test_resource_tree_does_not_invent_mathematical_overflow(self):
        p=self.compile("@(timer(0.5)) if(mode==0) x=max(0.0,sqrt(1.0e308)+sqrt(1.0e308)); else x=2; V(y,r)<+x;")
        self.assertEqual(self.values(p),[0,2,2])

    def test_resource_power_identity_preserves_boolean_decision_shape(self):
        rhs="+".join(["(pow((V(u,r)>0.0),1) ? 1.0:0.0)"]*4)
        p=self.compile(f"@(timer(0.5)) x={rhs}; V(y,r)<+x;","real x;")
        result=transient(p,{"u":[[0,1],[1,1]]},[0,0.75,1],stop=1,max_step=0.25,kernel=KERNEL)
        self.assertEqual([row["voltages"][p.nodes.index("y")] for row in result["solutions"]],[0,4,4])

    def test_resource_constant_power_preserves_boolean_decision_shape(self):
        rhs="+".join(["((V(u,r)>0.0 ? pow(1.0,2):pow(0.0,2)) ? 1.0:0.0)"]*4)
        p=self.compile(f"@(timer(0.5)) x={rhs}; V(y,r)<+x;","real x;")
        result=transient(p,{"u":[[0,1],[1,1]]},[0,0.75,1],stop=1,max_step=0.25,kernel=KERNEL)
        self.assertEqual([row["voltages"][p.nodes.index("y")] for row in result["solutions"]],[0,4,4])
