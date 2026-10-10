"""Source-expression translation checks, independent of simulator execution."""
import unittest
from prepare_por_spectre import expressions,geometry

class Translation(unittest.TestCase):
    def test_brace_double_quote_expression_has_one_delimiter(self):
        self.assertEqual(expressions('.model R r dw={"-tol/2-dw/2"}\n'), ".model R r dw='-tol/2-dw/2'\n")
    def test_plain_formula_and_comments_are_preserved(self):
        self.assertEqual(expressions('* {"comment"}\n.param a={x+y}\n'), "* {\"comment\"}\n.param a='x+y'\n")
    def test_geometry_is_exact_decimal(self):
        self.assertEqual(geometry('X a b M w=1.5e6u l=3.5e5u\n'), 'X a b M w=1.5 l=0.35\n')

if __name__=='__main__': unittest.main()
