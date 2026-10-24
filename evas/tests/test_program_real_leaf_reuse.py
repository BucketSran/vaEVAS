"""Leaf sharing preserves rounded trees, request isolation and wire copies."""
GUARDS = ['LANG', 'EVENT-CONDITIONS']
import math
import unittest

from evas.ir import Affine, Origin, RealBinary, StateRef
from evas.native_audit import NativeAudit


class ProgramRealLeafReuse(unittest.TestCase):
    def emit(self, owner, cls, *args):
        return owner.emit_ir(cls, args, {}, 'emit')

    def test_signed_zero_and_compilation_owners_remain_distinct(self):
        first, second = NativeAudit(), NativeAudit()
        positive = self.emit(first, Affine, 0.0, ())
        negative = self.emit(first, Affine, -0.0, ())
        self.assertIsNot(positive, negative)
        self.assertEqual(math.copysign(1, negative.constant), -1)
        state = self.emit(first, StateRef, 0)
        self.assertIs(state, self.emit(first, StateRef, 0))
        self.assertIsNot(state, self.emit(first, StateRef, 1))
        self.assertIsNot(state, self.emit(second, StateRef, 0))

    def test_source_round_nodes_are_distinct_and_wire_expands_shared_leaves(self):
        owner = NativeAudit()
        value = self.emit(owner, Affine, 1.0, ())
        origin = Origin('model.va', 1, 1, 'dut')
        a = self.emit(owner, RealBinary, 'add', value, value, origin)
        b = self.emit(owner, RealBinary, 'add', value, value, origin)
        self.assertIsNot(a, b)
        wire = owner.materialize((a, b))
        self.assertIsNot(wire[0], wire[1])
        self.assertIsNot(wire[0]['left'], wire[0]['right'])
        self.assertEqual(wire[0], wire[1])
        self.assertEqual(owner.used, sum(owner.counts.values()))


if __name__ == '__main__':
    unittest.main()
