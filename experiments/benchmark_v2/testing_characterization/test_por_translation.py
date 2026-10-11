"""Source-expression translation checks, independent of simulator execution."""
import unittest
from prepare_por_spectre import expressions,geometry,instance_parameters

class Translation(unittest.TestCase):
    def test_brace_double_quote_expression_has_one_delimiter(self):
        self.assertEqual(expressions('.model R r dw={"-tol/2-dw/2"}\n'), ".model R r dw='-tol/2-dw/2'\n")
    def test_plain_formula_and_comments_are_preserved(self):
        self.assertEqual(expressions('* {"comment"}\n.param a={x+y}\n'), "* {\"comment\"}\n.param a='x+y'\n")
    def test_geometry_is_exact_decimal(self):
        self.assertEqual(geometry('X a b M w=1.5e6u l=3.5e5u\n'), 'X a b M w=1.5 l=0.35\n')

    def test_instance_geometry_expressions_bind_to_sibling_values(self):
        source="X1 d g s b mos W=2 nf=4 ad='int((nf+1)/2)*W/nf*0.29'\n"
        self.assertEqual(instance_parameters(source),"X1 d g s b mos W=2 nf=4 ad='int(((4)+1)/2)*(2)/(4)*0.29'\n")
    def test_instance_geometry_does_not_modify_comment_or_external_parameter(self):
        source="* X1 mos W=2 ad='W'\nX2 d g s b mos w='width' nf=1 ad='w*external'\n"
        self.assertEqual(instance_parameters(source),"* X1 mos W=2 ad='W'\nX2 d g s b mos w='width' nf=1 ad='(width)*external'\n")

if __name__=='__main__': unittest.main()
