"""Exact physical DC coefficient projection: original cross units and owners."""
GUARDS=['CROSS','TRANSITION','COMPOSE','EVENT-ORDER']
from pathlib import Path
import os,unittest
from evas import compile_sources,Instance,transient,KernelError
from test_affine import KERNEL as DEFAULT_KERNEL
K=Path(os.environ.get('EVAS_DC_FACTOR_KERNEL',DEFAULT_KERNEL))
SOURCE='''`include "disciplines.vams"
module driver(a,b,u,c);input a,b,u;output c;electrical a,b,u,c;integer s;
analog begin @(initial_step)s=0;@(cross(V(u)-0.25,+1))s=1;
V(c,b)<+transition(s,0,0.25,0.25)*V(a,b);end endmodule
module reader(a,b,u,c,y);input a,b,u,c;output y;electrical a,b,u,c,y;real q;
analog begin @(initial_step)q=0;@(cross(V(c,b)-0.5*V(a,b),0))q=V(u);
V(y)<+q;end endmodule'''
def run(a=.9,b=0.,sources=None,source=SOURCE,atol=1e-10,times=None,**opts):
 p=compile_sources({'dc-factor.va':source},[Instance('d','driver',dict(a='a',b='b',u='u',c='c'),{}),Instance('r','reader',dict(a='a',b='b',u='u',c='c',y='y'),{})])
 return transient(p,sources or dict(a=[[0,a],[1,a]],b=[[0,b],[1,b]],u=[[0,0],[1,1]]),times or [0,.25,.375,.5,1],stop=1,max_step=1,kernel=K,vabstol=atol,reltol=0,**opts)
class DcFactor(unittest.TestCase):
 def test_original_scale_cross_instance(self):
  for a,b in [(.9,0),(.75,.25),(.25,.75)]:
   with self.subTest(a=a,b=b):
    r=run(a,b);self.assertEqual([x['voltages'][r['nodes'].index('y')] for x in r['solutions']],[0,0,.375,.375,.375])
 def test_zero_nonrepresentable_and_error_refuse(self):
  for a,b in [(.75,.75),(.9,.1)]:
   with self.subTest(a=a,b=b),self.assertRaises(KernelError):run(a,b)
  with self.assertRaises(KernelError):run(source_errors={'a':1e-9})
 def test_entire_domain_not_last_query(self):
  with self.assertRaises(KernelError):run(sources=dict(a=[[0,.9],[.8,.9],[.9,1],[1,.9]],b=[[0,0],[1,0]],u=[[0,0],[1,1]]))
 def test_shape_positive_band_refuses_even_with_exact_physical_curve(self):
  shape=[dict(time_numerator=str(t),time_denominator='1',value_V=.9) for t in [0,1]]
  with self.assertRaisesRegex(KernelError,'unsupported_source_uncertainty'):
   run(source_shapes={'a':shape},source_errors={'a':.1})
  self.assertEqual(run(source_shapes={'a':shape},source_errors={'a':0})['solutions'][-1]['voltages'][-1],.375)
 def test_old_linear_history_with_variable_supply_stays_legacy(self):
  r=run(source=SOURCE.replace('*V(a,b)','+V(a,b)'),sources=dict(a=[[0,5],[1,6]],b=[[0,2],[1,2]],u=[[0,0],[1,1]]))
  self.assertEqual([x['voltages'][r['nodes'].index('y')] for x in r['solutions']],[0]*5)
 def test_original_zero_weight_source_dependencies_and_owner_are_audited(self):
  from types import SimpleNamespace
  for fault in ['hidden','owner','dead-arm']:
   p=compile_sources({'audit.va':SOURCE},[Instance('d','driver',dict(a='a',b='b',u='u',c='c'),{}),Instance('r','reader',dict(a='a',b='b',u='u',c='c',y='y'),{})]).to_dict()
   if fault=='hidden':
    p['contributions'][0]['rhs']['right']['right']['terms']=list(p['contributions'][0]['rhs']['right']['right']['terms'])+[dict(node=p['nodes'].index('c'),coefficient=0.)]
   elif fault=='owner':p['operators'][0]['origin']['instance']='r'
   else:
    # A foreign reader state in an unselected driver target arm is invalid.
    p['operators'][0]['input']=dict(op='select',relation='gt',left=dict(op='affine',constant=1,terms=[]),right=dict(op='affine',constant=0,terms=[]),then_value=p['operators'][0]['input'],else_value=dict(op='state',state=1),origin=p['operators'][0]['origin'])
   with self.subTest(fault=fault),self.assertRaises(KernelError):
    transient(SimpleNamespace(nodes=p['nodes'],to_dict=lambda:p),dict(a=[[0,.9],[1,.9]],b=[[0,0],[1,0]],u=[[0,0],[1,1]]),[0,1],stop=1,max_step=1,kernel=K)
 def test_original_root_error_survives_future_voltage_amplification(self):
  from fractions import Fraction as F
  source=SOURCE.replace('V(c,b)-0.5*V(a,b)','V(c,b)-0.5*V(a,b)+0.000000001').replace('V(y)<+q','V(y)<+1073741824*q')
  exact=(F(3,8)-F(1e-9)/(4*F(.9)))*2**30
  with self.assertRaisesRegex(KernelError,'waveform_accuracy'):run(source=source,atol=1e-9,times=[.5,1])
  a=run(source=source,atol=1e-4,times=[.5,1]);i=a['nodes'].index('y')
  for boxes in a['observation_evidence']['voltage_bounds_V']:
   lo,hi=boxes[i];self.assertLessEqual(F(lo),exact);self.assertLessEqual(exact,F(hi))
 def test_nearby_different_history_roots_remain_distinct(self):
  delay=2**-35
  source=SOURCE.replace('electrical a,b,u,c;integer s;','electrical a,b,u,c;integer s;parameter real td=0;').replace('transition(s,0,0.25','transition(s,td,0.25')
  instances=[]
  for name,td in [('x',0),('z',delay)]:
   instances += [Instance('d'+name,'driver',dict(a='a',b='b',u='u',c='c'+name),dict(td=td)),Instance('r'+name,'reader',dict(a='a',b='b',u='u',c='c'+name,y='y'+name),{})]
  p=compile_sources({'roots.va':source},instances)
  a=transient(p,dict(a=[[0,.9],[1,.9]],b=[[0,0],[1,0]],u=[[0,0],[1,1]]),[0,.5,1],stop=1,max_step=1,kernel=K,vabstol=1e-10,reltol=0)
  for name,want in [('x',.375),('z',.375+delay)]:
   i=a['nodes'].index('y'+name);self.assertEqual(a['solutions'][-1]['voltages'][i],want)
   lo,hi=a['observation_evidence']['voltage_bounds_V'][-1][i];self.assertLessEqual(lo,want);self.assertLessEqual(want,hi)
 def test_zero_operator_factor_keeps_legacy_plateau_rejection(self):
  # Same IR on frozen11fad and this kernel: preserve the old calendar refusal,
  # rather than introducing an earlier optionalDC admission or claiming PASS.
  with self.assertRaisesRegex(KernelError,'dynamic cross plateau'):
   run(source=SOURCE.replace('*V(a,b)','*0*V(a,b)'),sources=dict(a=[[0,.9],[1,1]],b=[[0,0],[1,0]],u=[[0,0],[1,1]]))
 def test_non_affine_supply_tree_is_not_partially_rounded(self):
  with self.assertRaises(KernelError):run(source=SOURCE.replace('*V(a,b)','*(0.7*V(a,b))'))
if __name__=='__main__':unittest.main()
