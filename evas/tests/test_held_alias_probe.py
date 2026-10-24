"""Irrelevant real aliases cannot spend a new whole-source proof allowance."""
GUARDS = ["LANG", "EVENT-ORDER", "TRANSITION", "COMPOSE"]
from floor_rn_contract import floor_contract
import hashlib,json,os,unittest
from pathlib import Path
from unittest.mock import patch
from evas import compile_sources,transient
from evas.ir import Program
KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',str(Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel')))
def source(width=16):
 return '`include "disciplines.vams"\nmodule ring(clk,data,bit0,y);input clk,data;output bit0;output ['+str(width-1)+':0]y;electrical clk,data,bit0;electrical ['+str(width-1)+':0]y;parameter real rail=1;integer n,j,code;genvar k;real threshold;real level[0:'+str(width-1)+'];analog begin threshold=0.5*rail; @(initial_step)begin n=0;code=0;for(j=0;j<'+str(width)+';j=j+1)level[j]=0;end @(cross(V(clk)-threshold,+1))begin code=floor(V(data)+0.5);if(code<0)code=0;else if(code>15)code=15;n=(n+1)%16;for(j=0;j<'+str(width)+';j=j+1)level[j]=((n-j+32)%16<3)?rail:0;end V(bit0)<+transition((code>>0)&1,0,0.01,0.01);for(k=0;k<'+str(width)+';k=k+1)V(y[k])<+transition(level[k],0,0.01,0.01);end endmodule'
def bindings(width):
 from evas import Instance
 return [Instance('ring','ring',dict(clk='clk',data='data',bit0='bit0',**{'y['+str(k)+']':'y'+str(k) for k in range(width)}))]

class HeldAliasProbe(unittest.TestCase):
 def test_public_ring_real_clock_alias_complete_transport_and_numeric_outputs(self):
     with floor_contract(self, 'ring'):
      text=source(32);p=compile_sources({'public-ring.va':text},bindings(32));owner=p._native_audit;before=owner.used
      old=Program.to_dict;wires=[]
      def materialize(program):
       result=old(program);wires.append(hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest());return result
      clock=[[0,0],[0.9,0],[1,1],[1.1,0],[1.9,0],[2,1],[2.1,0],[2.9,0],[3,1],[3.25,1]]
      with patch.object(Program,'to_dict',materialize):
       result=transient(p,{'clk':clock,'data':[[0,1],[3.25,1]]},[0,1.25,2.25,3.25],stop=3.25,max_step=0.125,kernel=KERNEL)
      self.assertTrue(owner.active);self.assertEqual(len(wires),1);self.assertIs(owner,p._native_audit);self.assertLessEqual(owner.used,100000)
      self.assertEqual(owner.counts.get('held_power2_alias_visit',0),0)
      for i,row in enumerate(result['solutions']):
       values=dict(zip(result['nodes'],row['voltages']));self.assertEqual(values['bit0'],float(i>0))
       for j in range(32):self.assertEqual(values['y'+str(j)],float(i>0 and (i-j+32)%16<3))
      print('PUBLIC_RING_RECEIPT '+json.dumps(dict(source_sha256=hashlib.sha256(text.encode()).hexdigest(),compile_used=before,wire_used=owner.used-before,total_used=owner.used,owner=id(owner),wire_sha256=wires[0],counts=dict(owner.counts),kernel=str(KERNEL),kernel_sha256=hashlib.sha256(KERNEL.read_bytes()).hexdigest(),solutions=4)))

 def test_supported_alias_still_pays_full_original_source_and_program_roles(self):
  from test_held_power2_targets import one,simple,primitive_count
  p=simple(one('n/(4/2)',last=3));owner=p._native_audit
  self.assertGreater(owner.counts.get('held_power2_alias_root',0),0)
  self.assertGreater(owner.counts.get('held_power2_alias_visit',0),0)
  self.assertGreater(owner.counts.get('held_power2_program_expr',0),0)
  self.assertGreater(primitive_count(p.operators),0)

 def test_ineligible_root_does_not_hide_invalid_original_children(self):
  from evas import CompileError
  from test_held_power2_targets import one,simple
  for rhs in ['(n%2)+0.0*V(y)','(n%2)+0.0*$abstime','0.0*((n+2147483647)-2147483647)']:
   with self.subTest(rhs=rhs),self.assertRaises(CompileError):simple(one(rhs))
