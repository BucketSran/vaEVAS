"""Exact dyadic answers expose LU rounding, independent of EVAS."""
GUARDS = ["LIN", "SPARSE"]
import copy
import json
from pathlib import Path
import subprocess
import unittest
from test_affine import KERNEL

MATRIX = [
 [-473,373,250,376,294,-152,-394,-293],
 [-257,257,-198,-316,-184,503,-249,280],
 [44,-140,259,-382,-412,-387,-130,-387],
 [-173,94,51,-355,-301,-387,-320,424],
 [166,164,386,-171,-254,-348,142,-410],
 [37,241,-132,-368,-280,96,501,228],
 [376,-428,456,337,-341,221,-252,-336],
 [-197,117,-289,357,395,-435,-212,-507],
]
ROOTS = [-3.5,.5,-1.75,3.375,1.875,-2.5,3.25,3.875]


def request(blocks=1):
    contributions=[]
    for block in range(blocks):
        for i,row in enumerate(MATRIX):
            index=8*block+i
            contributions.append(dict(
                branch=dict(instance=f'block{block}',local_positive=f'a{i}',local_negative='r',kind='voltage'),
                positive=index+1,negative=0,
                rhs=dict(op='affine',constant=sum(a*x for a,x in zip(row,ROOTS)),
                         terms=[dict(node=8*block+j+1,coefficient=(i==j)-a) for j,a in enumerate(row)]),
                origin=dict(source='refinement.va',line=index+1,column=1,instance=f'block{block}')))
    return dict(program=dict(schema_version=16,nodes=['0']+[f'y{i}' for i in range(8*blocks)],contributions=contributions),
                driven=[],samples=[[]],tolerances=dict(absolute=1e-13,relative=0))


class RefinementContracts(unittest.TestCase):
    def test_exact_dyadic_solution_after_refinement_dense_and_sparse(self):
        # Ten dense 8x8 blocks form an 80x80 sparse matrix (density .1).
        for blocks in [1,10]:
            with self.subTest(blocks=blocks):
                p=subprocess.run([str(KERNEL)],input=json.dumps(request(blocks)),text=True,capture_output=True,check=False)
                self.assertEqual(p.returncode,0,p.stderr)
                solved=json.loads(p.stdout)['solutions'][0]
                for actual,expected in zip(solved['voltages'],[0]+ROOTS*blocks):
                    self.assertAlmostEqual(actual,expected,delta=1e-13)
                self.assertLessEqual(solved['max_residual_ratio'],1)

    def test_inconsistent_redundant_relation_is_still_rejected(self):
        req=request()
        extra=copy.deepcopy(req['program']['contributions'][0])
        extra['branch']['instance']='contradiction'
        extra['origin']['instance']='contradiction'
        extra['rhs']['constant']+=1
        req['program']['contributions'].append(extra)
        p=subprocess.run([str(KERNEL)],input=json.dumps(req),text=True,capture_output=True,check=False)
        self.assertNotEqual(p.returncode,0)
        self.assertEqual(json.loads(p.stderr)['kind'],'residual_failure')

if __name__=='__main__': unittest.main()
