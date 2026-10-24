"""Floor's coefficient visits consume the original request allowance."""
GUARDS = ['LANG']
import unittest
from unittest.mock import patch

from evas import finite_floor as ff
from evas.errors import CompileError
from evas.ir import Affine, Origin, Select, Term
from evas.native_audit import NativeAudit


class FloorWorkAccounting(unittest.TestCase):
    origin = Origin('floor-work.va', 1, 1, 'dut')

    def argument(self, count):
        value = Affine(0., tuple(Term(i+1, 1.) for i in range(count)))
        low, high = Affine(0., ()), Affine(1., ())
        lower = Select('lt', value, low, low, value, self.origin)
        return Select('gt', lower, high, high, lower, self.origin)

    def owner(self):
        owner = NativeAudit()
        owner.activate(self.origin)
        return owner

    def test_actual_coefficient_visits_have_distinct_costs(self):
        rows = []
        for count in (1, 1000):
            owner = self.owner()
            with patch.object(ff, '_binary_scale', wraps=ff._binary_scale) as observed:
                ff.floor_table(self.argument(count), self.origin, work=owner.ir_work)
            self.assertEqual(observed.call_count, count)
            self.assertEqual(owner.counts['floor_shape_term'], count)
            rows.append(owner.used)
        self.assertEqual(rows[1]-rows[0], 999)

    def test_rejection_charges_only_the_coefficients_actually_inspected(self):
        owner = self.owner()
        value = Affine(0., (Term(1, .3),) + tuple(Term(i+2, 1.) for i in range(999)))
        with patch.object(ff, '_binary_scale', wraps=ff._binary_scale) as observed:
            with self.assertRaises(CompileError) as error:
                ff.floor_table(value, self.origin, work=owner.ir_work)
        self.assertEqual(error.exception.diagnostic['code'], 'unsupported_floor')
        self.assertEqual(observed.call_count, 1)
        self.assertEqual(owner.counts['floor_shape_term'], 1)

    def test_natural_scan_exhaustion_keeps_same_owner_on_two_retries(self):
        owner, argument = self.owner(), self.argument(1000)
        successful = 0
        while True:
            try:
                ff.floor_table(argument, self.origin, work=owner.ir_work)
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'], 'resource_budget')
                break
            successful += 1
        self.assertGreater(successful, 0)
        self.assertLess(successful, 100)
        self.assertGreater(owner.counts['floor_shape_term'], 90000)
        for _ in range(2):
            spent = owner.used
            with self.assertRaises(CompileError) as error:
                ff.floor_table(argument, self.origin, work=owner.ir_work)
            self.assertEqual(error.exception.diagnostic['code'], 'resource_budget')
            self.assertGreater(owner.used, spent)

    def test_legacy_constant_fast_path_keeps_its_cost(self):
        owner = self.owner()
        before = owner.used
        result = ff.floor_table(Affine(1.5, ()), self.origin, work=owner.ir_work)
        self.assertEqual(result.constant, 1.)
        self.assertEqual(owner.used, before)
