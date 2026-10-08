"""Positive explicit rise with omitted fall: LRM 2.4 §4.5.8 anchors.

Independent values use tabulated affine segments, never four-arg IR equality.
"""
import unittest
from evas import CompileError,Instance,compile_sources,transient
from test_affine import KERNEL
GUARDS=['TRANSITION','TIMED-OPERATOR']
SOURCE='''module m(r,y,z); inout r,y,z; electrical r,y,z;
 parameter real d=0; parameter real tr=.5; real q,b;
 analog begin
 @(initial_step) begin q=0; b=0; end
 @(timer(.25,0,1e-18)) begin q=1; b=1; end
 @(timer(.5,0,1e-18)) b=0;
 @(timer(1.5,0,1e-18)) q=0;
 V(y,r)<+transition(q,d,tr);
 V(z,r)<+transition(b,d,tr);
 end endmodule'''
def instances():
 return [Instance('a','m',{'r':'0','y':'ay','z':'az'},{'d':0,'tr':.5}),
         Instance('b','m',{'r':'0','y':'by','z':'bz'},{'d':.125,'tr':1})]
class TransitionDefaultFall(unittest.TestCase):
 def test_rise_fall_and_reversal_two_instances_and_callsites(self):
  p=compile_sources({'original-three.va':SOURCE},instances())
  times=[0,.25,.375,.5,.625,.75,.875,1,1.375,1.5,1.625,1.75,2,2.625,3]
  expected={'ay':[0,0,.25,.5,.75,1,1,1,1,1,.75,.5,0,0,0],
            'az':[0,0,.25,.5,.25,0,0,0,0,0,0,0,0,0,0],
            'by':[0,0,0,.125,.25,.375,.5,.625,1,1,1,.875,.625,0,0],
            'bz':[0,0,0,.125,.25,.125,0,0,0,0,0,0,0,0,0]}
  for step in [3,.03125]:
   r=transient(p,{},times,stop=3,max_step=step,kernel=KERNEL)
   for n,values in expected.items():
    for row,v in zip(r['solutions'],values,strict=True):self.assertAlmostEqual(row['voltages'][r['nodes'].index(n)],v,delta=2e-12)
  for op in p.operators:
   self.assertEqual(op.rise,op.fall);self.assertEqual(op.origin.source,'original-three.va')
  self.assertEqual(len({(op.origin.instance,op.origin.line,op.origin.column) for op in p.operators}),4)
 def test_falling_interruption_reflects_rising_reversal(self):
  p=compile_sources({'reflected-three.va':SOURCE.replace('q=1; b=1;','q=1; b=-1;')},instances())
  r=transient(p,{},[.5,.625,.75,.875],stop=3,max_step=3,kernel=KERNEL)
  for n,values in [('az',[-.5,-.25,0,0]),('bz',[-.125,-.25,-.125,0])]:
   for row,v in zip(r['solutions'],values,strict=True):self.assertAlmostEqual(row['voltages'][r['nodes'].index(n)],v,delta=2e-12)
 def test_same_direction_extend_reflection_and_unchanged_target(self):
  for sign in [1,-1]:
   src=SOURCE.replace('begin q=1; b=1;',f'begin q=1; b={sign};').replace('@(timer(.5,0,1e-18)) b=0;',f'@(timer(.5,0,1e-18)) b={2*sign};\n @(timer(.875,0,1e-18)) b={2*sign};')
   p=compile_sources({'extend-three.va':src},instances())
   r=transient(p,{},[.5,.625,.75,.875,1,1.5,2],stop=3,max_step=3,kernel=KERNEL)
   for n,values in [('az',[.5,1,1.5,2,2,2,2]),('bz',[.125,.25,.5,.75,1,2,2])]:
    for row,v in zip(r['solutions'],values,strict=True):self.assertAlmostEqual(row['voltages'][r['nodes'].index(n)],sign*v,delta=2e-12)
 def test_unsupported_default_edges_remain_explicit_rejections(self):
  for expression in ['transition(q,d)','transition(q,d,0)','transition(q,d,-.5)']:
   with self.subTest(expression=expression),self.assertRaises(CompileError):compile_sources({'reject.va':SOURCE.replace('transition(q,d,tr)',expression)},instances())
 def test_state_timing_names_are_diagnosed_in_constant_namespace(self):
  # This is the actual public boundary, not a fabricated Select parameter.
  for expression in ['transition(q,d,q)','transition(q,q,.5)']:
   with self.subTest(expression=expression),self.assertRaisesRegex(CompileError,"unknown parameter 'q'"):
    compile_sources({'state-timing.va':SOURCE.replace('transition(q,d,tr)',expression)},instances())
if __name__=='__main__':unittest.main()
