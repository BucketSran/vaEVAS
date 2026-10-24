"""Source-only time predicate qualification must not depend on unrelated loops."""
GUARDS = ['LANG', 'EVENT-ORDER', 'TIMER']
import unittest
from evas import compile_sources,Instance,CompileError


def source(condition,loop=True):
    return ('`include "disciplines.vams"\nmodule m(y,z);output y,z;electrical y,z;'
        'parameter real eps=1e-12;integer s0_st;real s0_due;genvar i;analog begin '
        '@(initial_step)begin s0_st=4;s0_due=1;end '
        '@(timer(1))begin if('+condition+')s0_st=5;end '
        +('for(i=0;i<1;i=i+1)V(y)<+0;' if loop else 'V(y)<+0;')+'V(z)<+s0_st;end endmodule')


def compile_case(condition,loop=True):
    return compile_sources({'time.va':source(condition,loop)},[Instance('dut','m',dict(y='y',z='z'))])


def nodes(value):
    if isinstance(value,dict):
        yield value
        for item in value.values():yield from nodes(item)
    elif isinstance(value,(list,tuple)):
        for item in value:yield from nodes(item)


class LoopEventTime(unittest.TestCase):
    def test_unrelated_loop_does_not_change_simple_or_compound_admission(self):
        for condition in ('s0_due <= $abstime + eps',
                          's0_st == 4 && s0_due <= $abstime + eps'):
            programs=[compile_case(condition,loop).to_dict() for loop in (False,True)]
            self.assertEqual(programs[0]['events'],programs[1]['events'])
            self.assertEqual(programs[0]['states'],programs[1]['states'])

    def test_compound_time_keeps_sample_rn_operation_and_original_names(self):
        program=compile_case('s0_st == 4 && s0_due <= $abstime + eps').to_dict()
        self.assertIn('$abstime',program['nodes'])
        time_index=program['nodes'].index('$abstime')
        additions=[n for n in nodes(program['events']) if n.get('op')=='real_binary' and n.get('operation')=='add']
        self.assertEqual(len(additions),1)
        self.assertEqual(additions[0]['left']['kind'],'sample')
        self.assertEqual(list(additions[0]['left']['value']['terms']),[{'node':time_index,'coefficient':1.0}])
        self.assertEqual(additions[0]['right']['constant'],1e-12)
        self.assertEqual({s['name'] for s in program['states']},{'s0_st','s0_due'})

    def test_unknown_input_guard_is_preserved_without_nominal_selection(self):
        # Trajectory uncertainty is a runtime obligation; producer must retain
        # the complete predicate instead of replacing time by initial/nominal0.
        p=compile_case('s0_due <= $abstime + eps').to_dict()
        event=next(e for e in p['events'] if e['trigger']['kind']=='timer')
        condition=event['body'][0]
        self.assertEqual(condition['kind'],'if')
        self.assertTrue(any(n.get('kind')=='sample' for n in nodes(condition)))
        self.assertTrue(any(n.get('op')=='state' for n in nodes(condition)))

    def test_non_affine_invalid_names_and_feedback_remain_refused(self):
        for condition in ('$abstime*$abstime > 0','missing <= $abstime',
                          'V(missing) <= $abstime','V(z) <= $abstime'):
            with self.subTest(condition=condition),self.assertRaises(CompileError):
                compile_case(condition,True).to_dict()
        for condition in ('missing <= $abstime','V(missing) <= $abstime'):
            with self.subTest(no_loop=condition),self.assertRaises(CompileError):
                compile_case(condition,False).to_dict()
