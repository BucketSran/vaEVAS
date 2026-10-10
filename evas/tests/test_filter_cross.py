"""Filter-root consumers must use physical history, independent of query grids."""
GUARDS = ["TIMER", "CROSS", "EVENT-ORDER", "TRANSITION", "DYNAMICS", "COMPOSE"]
import copy
import math
from pathlib import Path
import sys
import unittest
from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'validation/sample_edge_filter'))
import filter_cross as contract
import precision_oracle


class FilterCross(unittest.TestCase):
    def run_case(self, case, grid, strobes=None):
        p=compile_sources({'dut.va':contract.source(case)},[Instance('dut','dut',{n:n for n in contract.ports(case)})])
        inputs={n:[[t*contract.sef.T,v] for t,v in points] for n,points in [('u',contract.sef.INPUT),('clk',contract.sef.CLOCK),('rst',contract.sef.RESET)]}
        return transient(p,inputs,grid,stop=contract.sef.STOP,max_step=contract.sef.T/64,
                         strobetimes=strobes,vabstol=1e-7,reltol=0,kernel=KERNEL,timeout=90)

    def test_sampling_edge_filter_cross_preserves_counts_samples_and_query_grid(self):
        for case in contract.CASES:
            with self.subTest(case=case['id']):
                grids=[contract.times(case,root_centers=False),contract.times(case,True,root_centers=False)]
                answers=[]
                for grid in grids:
                    answer=self.run_case(case,grid)
                    rows=[dict(time=t,**dict(zip(answer['nodes'],s['voltages']))) for t,s in zip(answer['transient']['times'],answer['solutions'],strict=True)]
                    verdict=contract.assess(case,rows)
                    self.assertEqual(verdict['status'],'PASS',verdict)
                    answers.append(answer)
                self.assertEqual(answers[0]['solutions'],[answers[1]['solutions'][grids[1].index(t)] for t in grids[0]])
                self.assertEqual(answers[0]['transient']['events'],answers[1]['transient']['events'])

    def test_filter_root_direction_selection(self):
        for direction in (-1,1):
            case=copy.deepcopy(contract.CASES[0]);case['instances'][0]['direction']=direction
            answer=self.run_case(case,contract.times(case,root_centers=False))
            rows=[dict(time=t,**dict(zip(answer['nodes'],s['voltages']))) for t,s in zip(answer['transient']['times'],answer['solutions'],strict=True)]
            self.assertEqual(contract.assess(case,rows)['status'],'PASS')
            self.assertEqual(rows[-1]['ac'],1)

    def test_forced_points_use_committed_frames_after_filter_cross(self):
        for case in contract.CASES:
            with self.subTest(case=case['id']):
                grid=contract.times(case,True,root_centers=False)
                answer=self.run_case(case,[0,contract.sef.STOP],grid)
                evidence=answer['strobe_evidence']
                self.assertEqual(evidence['sample_origins'],['accepted_controller_frame']*len(grid))
                rows=[dict(time=t,**dict(zip(answer['nodes'],v))) for t,v in zip(evidence['times'],evidence['voltages_V'],strict=True)]
                verdict=contract.assess(case,rows)
                self.assertEqual(verdict['status'],'PASS',verdict)

    def test_root_centers_and_adjacent_floats_recover_without_changing_history(self):
        for case in contract.CASES:
            with self.subTest(case=case['id']):
                coarse=contract.times(case,root_centers=False)
                probes=[t for p in case['instances'] for r,_ in contract.roots(p)
                        for t in (math.nextafter(r*contract.sef.T,-math.inf),r*contract.sef.T,
                                  math.nextafter(r*contract.sef.T,math.inf))]
                grid=sorted(set(coarse+probes))
                base=self.run_case(case,coarse)
                answer=self.run_case(case,grid)
                self.assertEqual(base['transient']['events'],answer['transient']['events'])
                self.assertEqual(base['solutions'],[answer['solutions'][grid.index(t)] for t in coarse])
                rows=[dict(time=t,**dict(zip(answer['nodes'],s['voltages']))) for t,s in zip(grid,answer['solutions'],strict=True)]
                self.assertEqual(contract.assess(case,rows)['status'],'PASS')
                for p in case['instances']:
                    for index,(root,direction) in enumerate(contract.roots(p)):
                        center=root*contract.sef.T
                        for t in (math.nextafter(center,-math.inf),center,math.nextafter(center,math.inf)):
                            expected=index+int(precision_oracle.side(p,t)==direction)
                            self.assertEqual(rows[grid.index(t)][p['name']+'c'],expected,(p['name'],t))

    def test_query_proof_does_not_claim_forced_step_inside_event_cluster(self):
        # A proved phase query is not a committed continuous solver step.
        # Keep strobe's stronger contract while ordinary center queries recover.
        case=contract.CASES[0]
        center=contract.roots(case['instances'][0])[0][0]*contract.sef.T
        probes=[math.nextafter(center,-math.inf),center,math.nextafter(center,math.inf)]
        grid=sorted(set(contract.times(case,True,root_centers=False)+probes))
        with self.assertRaisesRegex(KernelError,'forced solve point falls inside an atomic causal event cluster'):
            self.run_case(case,[0,contract.sef.STOP],grid)

    def test_sub_femtosecond_queries_use_old_filter_history_without_rescheduling(self):
        for case in contract.CASES:
            with self.subTest(case=case['id']):
                coarse=contract.times(case,root_centers=False)
                extra=[t*contract.sef.T+d for p in case['instances']
                       for t,_ in contract.roots(p) for d in (-1e-19,1e-19)]
                fine=sorted(set(coarse+extra))
                a=self.run_case(case,coarse)
                b=self.run_case(case,fine)
                self.assertEqual(a['transient']['events'],b['transient']['events'])
                self.assertEqual(a['solutions'],[b['solutions'][fine.index(t)] for t in coarse])
                rows=[dict(time=t,**dict(zip(b['nodes'],s['voltages']))) for t,s in zip(fine,b['solutions'],strict=True)]
                self.assertEqual(contract.assess(case,rows)['status'],'PASS')
                # The engineering time window permits either side here. Check
                # the phase itself so a reversed sign proof cannot pass it.
                for p in case['instances']:
                    roots=[t*contract.sef.T for t,_ in contract.roots(p)]
                    for root in roots:
                        for delta in (-1e-19,1e-19):
                            t=root+delta
                            self.assertEqual(rows[fine.index(t)][p['name']+'c'],
                                             sum(r<=t for r in roots))
