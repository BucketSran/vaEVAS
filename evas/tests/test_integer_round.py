"""LRM 2.4 section 4.2.1.1 sampled direct-probe conversion contracts.

Oracle TSV uses exact Fraction.from_float plus integer quotient/remainder;
it covers signs, half ties, adjacent ULPs and signed32 conversion boundaries.
"""
GUARDS = ["LANG", "EVENT-ORDER", "TRANSITION", "COMPOSE"]
import json
from pathlib import Path
import struct
import subprocess
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient

EVAS=Path(__file__).resolve().parents[1]
KERNEL=EVAS/'rust_core/target/debug/evas-kernel'

def program(body, rhs=None):
    if rhs is not None:
        body='@(timer(1)) begin code='+rhs+'; $display("code=%d",code); end'
    source='`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; integer code; analog begin @(initial_step) code=0; '+body+' V(y)<+code; end endmodule'
    return compile_sources({'round.va':source},[Instance('dut','m',{'u':'u','y':'y'},{})])

def execute(p,x,**kw):
    return transient(p,{'u':[[0,x],[2,x]]},[0,1,2],stop=2,max_step=2,kernel=KERNEL,**kw)

class IntegerRoundContracts(unittest.TestCase):
    def test_direct_probe_half_ties_neighbors_and_signed32_before_clamp(self):
        p=program('',rhs='V(u)')
        for line in (EVAS/'tests/fixtures/integer-round-oracle.tsv').read_text().splitlines():
            bits,want=line.split('\t'); x=struct.unpack('>d',struct.pack('>Q',int(bits,16)))[0]
            with self.subTest(bits=bits):
                if want=='range':
                    with self.assertRaisesRegex(KernelError,'integer_range'):execute(p,x)
                else:
                    r=execute(p,x)
                    self.assertEqual([v['text'] for v in r['transient']['display_records']],['code='+want])

    def test_input_box_cannot_choose_nominal_rounding_bin(self):
        p=program('',rhs='V(u)')
        for lo,hi in [(1.5-1e-14,1.5+1e-14),(-1.5-1e-14,-1.5+1e-14),(2147483647.49,2147483647.51)]:
            with self.subTest(lo=lo,hi=hi), self.assertRaisesRegex(KernelError,'event_condition|integer_range'):
                execute(p,(lo+hi)/2,source_errors={'u':(hi-lo)/2})

    def test_constant_real_compound_and_hidden_original_integer_overflow_stay_rejected(self):
        for rhs in ['1.5','-1.5','V(u)+0.0','0.0*(2147483647+1)','(1 ? 0.0 : (2147483647+1))']:
            with self.subTest(rhs=rhs),self.assertRaises(CompileError):program('',rhs=rhs)

    def test_old_typed_integer_consumers_retain_values(self):
        for rhs in ['2','-2','2147483647','-2147483648']:
            with self.subTest(rhs=rhs):
                r=execute(program('',rhs=rhs),0)
                self.assertEqual([v['text'] for v in r['transient']['display_records']],['code='+rhs])

    def test_later_event_reads_committed_conversion_and_competing_writers_reject(self):
        p=program('@(timer(1)) code=V(u); @(timer(1.5)) $display("later=%d",code);')
        r=execute(p,-1.5)
        self.assertEqual([v['text'] for v in r['transient']['display_records']],['later=-2'])
        for first in ['1','V(u)']:
            with self.subTest(first=first),self.assertRaisesRegex((CompileError,KernelError),'writ'):
                execute(program('@(timer(1)) code='+first+'; @(timer(1)) code=2;'),1.5)

    def test_sampled_clamp_real_target_transition_and_whole_nonbinary_root_window(self):
        source='''`include "disciplines.vams"
module sampled(clk,u,y); input clk,u; output y; electrical clk,u,y; integer code; real lsb,vod;
analog begin @(initial_step) begin lsb=0.125; vod=-0.9375; end
@(cross(V(clk)-0.5,-1)) begin code=V(u); if(code<0) code=0; if(code>15) code=15; vod=code*lsb-1.0+0.0625; end
V(y)<+transition(vod/2.0,0,0.125,0.125); end endmodule'''
        p=compile_sources({'sampled.va':source},[Instance('dut','sampled',{'clk':'clk','u':'u','y':'y'},{})])
        for u,want in [(-1.5,-0.46875),(1.5,-0.34375),(14.5,0.46875),(20.,0.46875)]:
            with self.subTest(u=u):
                r=transient(p,{'clk':[[0,1],[0.5,1],[0.75,0],[2,0]],'u':[[0,u],[2,u]]},[0,1,2],stop=2,max_step=.125,kernel=KERNEL)
                self.assertEqual(r['solutions'][-1]['voltages'][p.nodes.index('y')],want)
        # The physical root t=1/3 has an enclosing time window. u=.5+3t
        # crosses the 1.5 cut over that complete window; no midpoint is a proof.
        with self.assertRaisesRegex(KernelError,'rounding bins'):
            transient(p,{'clk':[[0,1],[1,-0.5],[2,-0.5]],'u':[[0,0.5],[1,3.5],[2,3.5]]},[0,1,2],stop=2,max_step=.125,kernel=KERNEL)

    def test_raw_wire_version_and_conversion_structure_rejection(self):
        original=json.loads(json.dumps(program('',rhs='V(u)').to_dict()))
        def rejected(p):
            request=dict(program=p,driven=['u'],samples=[],transient=dict(pwl=[[[0,1.5],[2,1.5]]],output_times=[0,1,2],stop=2,max_step=2),tolerances=dict(vabstol=1e-12,reltol=1e-10))
            r=subprocess.run([str(KERNEL)],input=json.dumps(request),capture_output=True,text=True,timeout=15)
            self.assertNotEqual(r.returncode,0)
            return r.stdout+r.stderr
        p=json.loads(json.dumps(original));p['schema_version']=30
        self.assertIn('version',rejected(p))
        for kind in ['compound','constant-real','internal-node','invalid-origin']:
            with self.subTest(kind=kind):
                p=json.loads(json.dumps(original))
                v=next(a['rhs'] for e in p['events'] for a in e['body'] if a.get('kind')=='assign' and a['rhs'].get('op')=='integer_round')
                if kind=='compound':v['value']={'op':'add','left':v['value'],'right':{'op':'affine','constant':0.,'terms':[]}}
                if kind=='constant-real':v['value']={'op':'affine','constant':1.5,'terms':[]}
                if kind=='internal-node':v['value']['terms'][0]['node']=p['nodes'].index('y')
                if kind=='invalid-origin':v['origin']['line']=0
                rejected(p)
        # Conversion is an assignment action, not a general explicit cast.
        # Preserve the review's real-target and outer-Add counterexamples,
        # plus unselected and non-statement parents through the actual reader.
        for kind in ['real-target','outer-add','outer-checked','outer-select','outer-multiply','outer-power','outer-event-math','nested-round','display','trigger','contribution','operator','array-write']:
            with self.subTest(role=kind):
                p=json.loads(json.dumps(original))
                event=next(e for e in p['events'] if any(a.get('kind')=='assign' and a['rhs'].get('op')=='integer_round' for a in e['body']))
                assignment=next(a for a in event['body'] if a.get('kind')=='assign' and a['rhs'].get('op')=='integer_round')
                v=assignment['rhs']; c=lambda n:dict(op='affine',constant=n,terms=[])
                if kind=='real-target':p['states'][assignment['state']]['kind']='real'
                if kind=='outer-add':assignment['rhs']=dict(op='add',left=v,right=c(1))
                if kind=='outer-multiply':assignment['rhs']=dict(op='multiply',left=v,right=c(1))
                if kind=='outer-checked':assignment['rhs']=dict(op='checked_integer',value=v,origin=v['origin'])
                if kind=='outer-select':assignment['rhs']=dict(op='select',relation='lt',left=c(0),right=c(1),then_value=c(0),else_value=v,origin=v['origin'])
                if kind=='outer-power':assignment['rhs']=dict(op='power',base=v,exponent=1)
                if kind=='outer-event-math':assignment['rhs']=dict(op='event_math',function='floor',args=[v],origin=v['origin'])
                if kind=='nested-round':assignment['rhs']=dict(op='integer_round',value=v,origin=v['origin'])
                if kind=='display':event['body'].append(dict(kind='display',format='%d',args=[v],origin=v['origin']))
                if kind=='trigger':event['trigger']=dict(kind='cross',guard=v,direction=1,time_tolerance=1e-12,expression_tolerance=1e-12)
                if kind=='contribution':p['contributions'][0]['rhs']=v
                if kind=='operator':p['operators']=[dict(kind='transition',input=v,delay=0,rise=.125,fall=.125,origin=v['origin'])]
                if kind=='array-write':event['body'].append(dict(kind='array_write',states=[assignment['state']],index=c(0),rhs=v,first=0,last=0,origin=v['origin']))
                self.assertIn('RHS root of a scalar integer assignment',rejected(p))

if __name__=='__main__':unittest.main(verbosity=2)
