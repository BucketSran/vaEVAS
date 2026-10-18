"""Branch temporaries through the public compiler and voltage solver.

Temporary assignments only matter when a later expression reads their value.
The numerical answers below follow source order and the selected branch.
"""
from pathlib import Path
import unittest

from evas import CompileError, Instance, compile_sources, solve

GUARDS = ["LANG"]
KERNEL = Path(__file__).resolve().parents[1] / "rust_core/target/debug/evas-kernel"


def compile_body(body):
    source = '''`include "disciplines.vams"
module m(u,v,o);
input u,v; output o;
electrical u,v,o;
real temporary, nested, result;
analog begin
''' + body + '\nend\nendmodule\n'
    return compile_sources({"branch-local.va": source}, [
        Instance("dut", "m", {"u": "u", "v": "v", "o": "o"})
    ])


class BranchLocalClosureContracts(unittest.TestCase):
    def assert_values(self, body, samples, expected):
        program = compile_body(body)
        response = solve(program, ["u", "v"], samples, kernel=KERNEL)
        output = response["nodes"].index("o")
        actual = [sample["voltages"][output] for sample in response["solutions"]]
        for observed, answer in zip(actual, expected, strict=True):
            self.assertAlmostEqual(observed, answer, places=12)

    def test_branch_temporary_used_only_inside_its_branch(self):
        self.assert_values('''
if (V(u) > 0.0) begin
    temporary = V(u) + 0.25;
    result = 2.0 * temporary;
end else result = -0.5;
V(o) <+ result;
''', [[-.4, 0], [0, 0], [.3, 0]], [-.5, -.5, 1.1])

    def test_branch_temporary_overwritten_before_outside_read(self):
        self.assert_values('''
if (V(u) > 0.0) temporary = V(u);
temporary = V(v) + 0.125;
V(o) <+ temporary;
''', [[-.4, .2], [.3, -.5]], [.325, -.375])

    def test_nested_temporaries_are_scoped_by_actual_reads(self):
        self.assert_values('''
if (V(u) > 0.0) begin
    if (V(v) > 0.0) begin
        nested = V(v) + 0.125;
        temporary = 2.0 * nested;
    end else temporary = -0.25;
    result = temporary + V(u);
end else result = -0.75;
V(o) <+ result;
''', [[-.4, .2], [.3, -.5], [.3, .2]], [-.75, .05, .95])

    def test_unread_branch_temporary_does_not_change_equation(self):
        self.assert_values('''
if (V(u) > 0.0) temporary = V(v);
V(o) <+ V(u) + 0.125;
''', [[-.4, .2], [.3, -.5]], [-.275, .425])

    def test_read_after_partial_assignment_still_rejects(self):
        with self.assertRaises(CompileError):
            compile_body('''
if (V(u) > 0.0) temporary = V(v);
V(o) <+ temporary;
''')

    def test_nested_missing_value_reaches_outer_read_and_rejects(self):
        with self.assertRaises(CompileError):
            compile_body('''
if (V(u) > 0.0) begin
    if (V(v) > 0.0) temporary = V(v);
    result = temporary;
end else result = 0.0;
V(o) <+ result;
''')

    def test_later_assignment_cannot_satisfy_an_earlier_read(self):
        with self.assertRaises(CompileError):
            compile_body('''
if (V(u) > 0.0) temporary = V(v);
result = temporary;
temporary = 0.125;
V(o) <+ result;
''')

    def test_unused_temporary_still_checks_conditional_history(self):
        with self.assertRaisesRegex(CompileError, "history waveform call sites must be unconditional"):
            compile_body('''
if (V(u) > 0.0) temporary = idt(V(v), 0);
V(o) <+ 0.0;
''')
