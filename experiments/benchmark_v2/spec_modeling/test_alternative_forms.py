"""Finite evaluation of authored discrete expressions, never VA simulation."""
import itertools
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent

def source(sid,file='dut.va'):
    task=next((ROOT/'benchmark/tasks').glob('v2-spec-'+sid+'-*'))
    return (OUT/'candidates'/task.name/'alternative'/file).read_text()

def rhs(text,name):
    return re.findall(r'\b'+name+r'\s*=(?!=)\s*([^;]+);',text)[-1]

def value(expr,state):
    return eval(expr.replace('||',' or ').replace('&&',' and '),{'__builtins__':{}},state)

class DifferentStateForms(unittest.TestCase):
    def test_packed_alexander_truth_table(self):
        s=source('001')
        for a,b,c in itertools.product((0,1),repeat=3):
            state={'samples':4*a+2*b+c}
            self.assertEqual(value(rhs(s,'u'),state),a!=b and b==c)
            self.assertEqual(value(rhs(s,'d'),state),a==b and b!=c)

    def test_packed_sar_four_decisions_and_previous_word(self):
        s=source('186')
        for bits in itertools.product((0,1),repeat=4):
            state=dict(pword=14,mword=14)
            for i,bit in enumerate(bits):
                state.update(pointer=i,dcmp=bit)
                state['pword']=value(rhs(s,'pword'),state)
                state['mword']=value(rhs(s,'mword'),state)
                for j in range(i+1):
                    self.assertEqual((state['pword']>>j)&1,bits[j])
                    self.assertEqual((state['mword']>>j)&1,1-bits[j])
            self.assertEqual(value(rhs(s,'outword'),state),sum(bit<<(3-i) for i,bit in enumerate(bits)))

    def test_settling_history_requires_three_consecutive_good_updates(self):
        s=source('370');expr=rhs(s,'good_history')
        for flags in itertools.product((False,True),repeat=6):
            history=0;run=0
            for good in flags:
                history=value(expr,dict(good_history=history,err_v=0 if good else 1,settle_tol=.04,absval=abs))
                run=run+1 if good else 0
                self.assertEqual(history==7,run>=3)

    def test_gain_integer_updates_preserve_clamped_controller(self):
        s=source('082')
        self.assertIn('integer gain_code;',s)
        down=next(e for e in re.findall(r'gain_code\s*=\s*([^;]+);',s) if '- 18' in e)
        up=next(e for e in re.findall(r'gain_code\s*=\s*([^;]+);',s) if '+ 10' in e)
        code=220
        for action in [-1]*20+[1]*40:
            code=max(45,min(300,value(down if action<0 else up,dict(gain_code=code))))
        self.assertEqual(code,300)
        self.assertNotRegex(s,r'\breal\s+gainv\b')

    def test_acquisition_deficit_two_ticks(self):
        s=source('071');expr=rhs(s,'deficit').replace('V(vin)','vin')
        deficit=0
        for expected in [.597,.68226]:
            deficit=value(expr,dict(deficit=deficit,alpha=.42,vinit=.45,vin=.8))
            self.assertAlmostEqual(.45-deficit,expected)

    def test_low_pass_accumulator_worked_samples(self):
        s=source('091','synchronous_lp_state.va')
        expr=next(e for e in re.findall(r'accumulator=(?!=)([^;]+);',s) if 'V(demod_sample)' in e).replace('V(demod_sample)','sample')
        accumulator=0
        for expected in [.075,.13125,.1734375]:
            accumulator=value(expr,dict(accumulator=accumulator,lp_alpha=.25,sample=.3))
            self.assertAlmostEqual(.25*accumulator,expected)

    def test_integrator_deviation_and_saturation(self):
        s=source('307','integrator_state_cell.va')
        expr=rhs(s,'deviation').replace('V(sample_node)','sample')
        deviation=0
        for sample,expected in [(.8,.52),(.1,.45),(10,.9),(-10,0)]:
            deviation=value(expr,dict(deviation=deviation,sample=sample,k_int=.2,vcm=.45,clip01=lambda x:max(0,min(.9,x))))
            self.assertAlmostEqual(.45+deviation,expected)

    def test_all_sixteen_authored_forms_exist(self):
        from experiments.benchmark_v2.spec_modeling.alternative_forms import REASONS,alternative
        for sid in REASONS:
            task=next((ROOT/'benchmark/tasks').glob('v2-spec-'+sid+'-*'))
            differences=[]
            for f in (task/'solution').glob('*.va'):
                generated=alternative(f.read_text(),sid,f.name)
                current=source(sid,f.name)
                self.assertEqual(current,generated)
                if current!=f.read_text():differences.append(f.name)
            self.assertTrue(differences,sid)

if __name__=='__main__':unittest.main()
