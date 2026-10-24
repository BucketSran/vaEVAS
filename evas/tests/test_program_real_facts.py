"""Admission facts retain per-step rounding and source-read identity."""
GUARDS = ['LANG', 'EVENT-CONDITIONS']
import unittest

from evas.ir import Affine, Origin, RealBinary, RealBoundary, RealLocal, Select, StateRef, Term
from evas.native_audit import NativeAudit
from evas.program_real_facts import ProgramRealFacts

O = Origin('facts.va', 1, 1, 'dut')


class ProgramRealFactContracts(unittest.TestCase):
    def facts(self):
        owner = NativeAudit()
        return ProgramRealFacts(owner.ir_work), owner

    def test_closed_scalar_is_rounded_at_each_operation(self):
        facts, owner = self.facts()
        huge, one = Affine(9007199254740992.0, ()), Affine(1.0, ())
        value = RealBinary('subtract', RealBinary('add', huge, one, O), huge, O)
        result = facts.query(value)
        self.assertTrue(result.closed)
        self.assertEqual(result.value, 0.0)
        direct = facts.query(RealBinary('divide', Affine(3.0, ()), Affine(10.0, ()), O))
        reciprocal = facts.query(RealBinary('multiply', Affine(3.0, ()), Affine(0.1, ()), O))
        self.assertEqual(direct.value.hex(), '0x1.3333333333333p-2')
        self.assertEqual(reciprocal.value.hex(), '0x1.3333333333334p-2')
        self.assertEqual(owner.used, sum(owner.counts.values()))

    def test_same_binding_later_read_does_not_change_earlier_fact(self):
        facts, owner = self.facts()
        earlier, later = RealLocal(0), RealLocal(0)
        facts.record_read(earlier, (RealBoundary(Affine(2.0, ()), 'snapshot', O),))
        self.assertEqual(facts.query(earlier).value, 2.0)
        facts.record_read(later, (RealBoundary(Affine(0.0, (Term(1, 1.0),)), 'snapshot', O),))
        self.assertFalse(facts.query(later).closed)
        self.assertEqual(facts.query(earlier).value, 2.0)
        self.assertEqual(owner.used, sum(owner.counts.values()))

    def test_uniform_value_is_distinct_from_closed_source_and_mutable_state(self):
        facts, _ = self.facts()
        read = RealLocal(0)
        facts.record_read(read, (Affine(0.0, (Term(1, 1.0),)), Affine(0.5, ()),
                                Affine(2.0, ()), Affine(2.0, ())), relation='gt')
        result = facts.query(read)
        self.assertFalse(result.closed)
        self.assertEqual(result.value, 2.0)
        self.assertFalse(facts.query(StateRef(0)).closed)
        self.assertIsNone(facts.query(StateRef(0)).value)

    def test_transition_source_context_cannot_hide_output_feedback(self):
        facts, _ = self.facts()
        state = StateRef(0)
        sources = {0: [Affine(2.0, ())]}
        self.assertFalse(facts.query(state, 'continuous', state_sources=sources, generation=0))
        sources[0].append(Affine(1.0, (Term(2, 1.0),)))
        self.assertTrue(facts.query(state, 'continuous', state_sources=sources, generation=1))
        self.assertFalse(facts.query(state, 'dc', state_sources=sources, generation=1,
                                     allowed_nodes=frozenset((0, 1))))

    def test_signed_zero_follows_proved_branch_and_unknown_is_not_singleton(self):
        facts, _ = self.facts()
        plus, minus = Affine(0.0, ()), Affine(-0.0, ())
        for selected, expected in ((False, '-0x0.0p+0'), (True, '0x0.0p+0')):
            left, right = Affine(float(not selected), ()), Affine(float(selected), ())
            tree = Select('lt', left, right, plus, minus, O)
            self.assertEqual(facts.query(tree).value.hex(), expected)
            read = RealLocal(0)
            facts.record_read(read, (left, right, plus, minus), relation='lt')
            self.assertEqual(facts.query(read).value.hex(), expected)
        unknown = Affine(0.0, (Term(1, 1.0),))
        tree = Select('lt', unknown, plus, plus, minus, O)
        self.assertIsNone(facts.query(tree).value)
        read = RealLocal(0)
        facts.record_read(read, (unknown, plus, plus, minus), relation='lt')
        self.assertIsNone(facts.query(read).value)

    def test_piecewise_integer_leaf_image_is_not_a_closed_source(self):
        facts, _ = self.facts()
        choose = Select('gt', Affine(0.0,(Term(1,1.0),)), Affine(0.5,()),
                        Affine(1.0,()), Affine(2.0,()), O)
        value = RealBinary('add', choose, Affine(1.0,()), O)
        self.assertEqual(set(facts.query(value,'leaf_values')),{2.0,3.0})
        self.assertEqual(facts.query(value,'integer_range'),(2.0,3.0))
        self.assertFalse(facts.query(value).closed)
        self.assertIsNone(facts.query(value).value)
        fraction = RealBinary('divide',choose,Affine(2.0,()),O)
        self.assertIsNone(facts.query(fraction,'integer_range'))
        zeros = Select('gt',Affine(0.0,(Term(2,1.0),)),Affine(0.5,()),
                       Affine(0.0,()),Affine(-0.0,()),O)
        self.assertEqual({x.hex() for x in facts.query(zeros,'leaf_values')},
                         {'0x0.0p+0','-0x0.0p+0'})
        self.assertFalse(facts.query(zeros).closed)
        self.assertIsNone(facts.query(zeros).value)

    def test_leaf_proof_cycles_are_not_integer_certificates(self):
        facts, _ = self.facts()
        read=RealLocal(0)
        facts.record_read(read,(read,))
        self.assertIsNone(facts.query(read,'leaf_values'))
        self.assertIsNone(facts.query(read,'integer_range'))
        self.assertFalse(facts.active)

    def test_actual_leaf_enumeration_exhausts_same_owner_without_renewal(self):
        from evas import CompileError
        facts, owner = self.facts()
        value=Affine(0.0,())
        for index in range(16):
            choice=Select('gt',Affine(0.0,(Term(index+1,1.0),)),Affine(0.5,()),
                          Affine(0.0,()),Affine(float(2**index),()),O)
            value=RealBinary('add',value,choice,O)
        with self.assertRaises(CompileError):
            facts.query(value,'integer_range')
        self.assertTrue(owner.active)
        self.assertGreater(owner.used,100000)
        self.assertGreater(owner.counts['program_leaf_pair'],0)
        self.assertFalse(facts.active)
        for _ in range(2):
            used=owner.used
            with self.assertRaises(CompileError):
                facts.query(value,'integer_range')
            self.assertGreater(owner.used,used)
        self.assertEqual(owner.used,sum(owner.counts.values()))
        fresh,_=self.facts()
        self.assertEqual(fresh.query(Affine(2.0,()),'integer_range'),(2.0,2.0))


if __name__ == '__main__':
    unittest.main()
