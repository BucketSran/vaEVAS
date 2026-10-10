import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[3]/'benchmark/checkers/v2_testing.py'
spec=importlib.util.spec_from_file_location('meter',p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class HysteresisMeterSeam(unittest.TestCase):
    def test_delayed_bad_dut_is_measured_not_rejected(self):
        # Worked trace: input rises 0.4 -> 0.6; DUT output edge at vin=.58,
        # falls at .43. These are observed capture points, not ideal thresholds.
        rows=[dict(zip(['time','vin','cmp_out','begin','up','down','width','valid'],r)) for r in [
            [0,.4,0,0,0,0,0,0], [1,.5,0,0,0,0,0,0],
            [1.8,.58,.5,0,0,0,0,0], [1.9,.59,1,0,.58,0,0,0],
            [2,.6,1,0,.58,0,0,0], [3,.5,1,0,.58,0,0,0],
            [3.7,.43,.5,0,.58,0,0,0], [3.8,.42,0,0,.58,.43,.15,1],
            [4,.4,0,0,.58,.43,.15,1],
        ]]
        self.assertTrue(m.evaluate(rows,dict(kind='hysteresis',stop=4,guard=.09,atol=.001))['passed'])
    def test_target_constants_are_rejected_for_bad_dut(self):
        rows=[dict(time=t,vin=v,cmp_out=c,begin=0,up=.55,down=.45,width=.1,valid=1) for t,v,c in [(0,.4,0),(1,.5,0),(1.8,.58,.5),(1.9,.59,1),(2,.6,1),(3,.5,1),(3.7,.43,.5),(3.8,.42,0),(4,.4,0)]]
        self.assertFalse(m.evaluate(rows,dict(kind='hysteresis',stop=4,guard=.09,atol=.001))['passed'])

class DelaySeam(unittest.TestCase):
    def test_delay_is_observed_in_picoseconds(self):
        rows=[]
        for t,clk,out in [(0,0,0),(1e-9,0,0),(1.1e-9,1,0),(1.2e-9,1,0),(1.3e-9,1,1),(2e-9,1,1)]:
            rows.append(dict(time=t,clk=clk,outp=out,outn=0,vinp=.53,vinn=.47,delay_ps=200 if t>1.25e-9 else 0,overdrive_mv=60 if t>1.05e-9 else 0,polarity=1 if t>1.25e-9 else 0,valid=1 if t>1.25e-9 else 0))
        result=m.evaluate(rows,dict(kind='delay',stop=2e-9,guard=150e-12,atol=.01))
        self.assertTrue(result['passed'],result)

class RmsSeam(unittest.TestCase):
    def test_signed_square_window_and_disable(self):
        rows=[]
        for i in range(12):
            t=i*.5
            clk=float(i%2==1)
            x=[1.,-1.,1.,-1.][min(i//2,3)]
            completed=t>=3.5
            rows.append(dict(time=t,clk=clk,vinp=x,vinn=0,reset=0,enable=1,rms_out=1 if completed else 0,valid=1 if completed and t<4.5 else 0))
        result=m.evaluate(rows,dict(kind='rms',stop=5.5,threshold=.5,vhigh=1,guard=.3,atol=.01))
        self.assertTrue(result['passed'],result)

class DutySeam(unittest.TestCase):
    def test_rounds_actual_two_fifths_to_102(self):
        rows=[]
        for t,c in [(0,0),(1,0),(1.2,1),(3,1),(3.2,0),(6,0),(6.2,1),(7,1)]:
            code=102 if t>=6.2 else 0
            row=dict(time=t,clk_in=c,valid=1 if code else 0)
            row.update({f'duty{i}':float((code>>i)&1) for i in range(8)})
            rows.append(row)
        result=m.evaluate(rows,dict(kind='duty',stop=7,threshold=.5,vhigh=1,guard=.15,atol=.01))
        self.assertTrue(result['passed'],result)

class GainSeam(unittest.TestCase):
    def test_actual_span_ratio_is_two(self):
        rows=[]
        for t,x,g,v in [(0,0,0,0),(.99,.099,0,0),(1,.1,0,0),(1.01,.099,2,1),(2,-.1,2,1),(3,0,2,1)]:
            rows.append(dict(time=t,vinp=x,vinn=0,voutp=2*x,voutn=0,begin_round=0,gain_out=g,valid=v))
        result=m.evaluate(rows,dict(kind='gain',stop=3,start_time=0,sample_period=1,gain_scale=1,vhigh=1,min_input_span=.02,guard=.02,atol=.01))
        self.assertTrue(result['passed'],result)

class FrequencySeam(unittest.TestCase):
    def test_reads_edges_instead_of_target_code(self):
        # 100 MHz DCO and 50 MHz divided clock; a bad divider must report ratio 2.
        rows=[]
        for i in range(81):
            t=i*1e-9
            dco=1 if int(i/5)%2 else 0
            div=1 if int(i/10)%2 else 0
            freq=100 if i>=15 else 0
            ratio=2 if i>=30 else 0
            rows.append(dict(time=t,dco_clk=dco,div_clk=div,enable=1,reset=0,freq_mhz=freq,divider_ratio=ratio,valid=float(i>=30)))
        result=m.evaluate(rows,dict(kind='frequency',stop=80e-9,threshold=.5,guard=1.1e-9,atol=.01))
        self.assertTrue(result['passed'],result)

class SearchSeam(unittest.TestCase):
    def test_no_response_must_timeout_and_never_report_valid(self):
        rows=[]
        for t,req,status in [(0,0,0),(1,0,0),(1.02,1,0),(11.01,1,0),(11.03,0,2),(12,0,2)]:
            rows.append(dict(time=t,request=req,status=status,valid=0,offset_est=0,vinp=.5,vinn=.5,ready=0,dcmpp=0))
        result=m.evaluate(rows,dict(kind='search',stop=12,first_request=1.01,gap=1,timeout=10,iterations=7,step_initial=.064,guard=.04,atol=.001))
        self.assertTrue(result['passed'],result)

class TdcSeam(unittest.TestCase):
    def test_stop_latches_two_clock_edges_and_ignores_late_stop(self):
        rows=[]
        for t,start,clk,stop,code in [(0,0,0,0,0),(1,1,0,0,0),(2,0,1,0,0),(3,0,0,0,0),(4,0,1,0,0),(5,0,0,1,2),(6,0,1,0,2),(7,0,0,1,2),(8,0,0,0,2)]:
            row=dict(time=t,start=start,clk=clk,stop=stop,rst=0,valid=float(code>0),overflow=0)
            row.update({f'code_{i}':float((code>>i)&1) for i in range(8)})
            rows.append(row)
        result=m.evaluate(rows,dict(kind='tdc',stop=8,guard=.6,threshold=.5,vhigh=1,atol=.01))
        self.assertTrue(result['passed'],result)

class SettlingSeam(unittest.TestCase):
    def test_last_outside_sample_then_full_tail(self):
        rows=[]
        for t,x,static,dyn,launch,gain,settle,valid,status in [(0,1,2,2,0,0,0,0,0),(.98,1,2,2,0,0,0,0,0),(1.02,1,2,2,1,0,0,0,0),(1.1,2,4,2,0,0,0,0,0),(2,2,4,2.5,0,0,0,0,0),(3,2,4,3.5,0,0,0,0,0),(4,2,4,4,0,0,0,0,0),(4.99,2,4,4,0,0,0,0,0),(5.05,2,4,4,0,2,3,1,1),(6,2,4,4,0,2,3,1,1)]:
            rows.append(dict(time=t,vin=x,static_out=static,dynamic_out=dyn,launch=launch,gain=gain,gain_valid=valid,settling_ns=settle,settled=valid,status=status))
        result=m.evaluate(rows,dict(kind='settling',stop=6,sample_period=1,samples=4,tail_samples=2,settle_tol=.1,min_input_span=.02,time_scale=1,guard=.07,atol=.01))
        self.assertTrue(result['passed'],result)

class DutyQuantizationBoundary(unittest.TestCase):
    def trace(self,code):
        rows=[]
        for t,c in [(0,0),(1,0),(1.2,1),(2,1),(2.2,0),(7,0),(7.2,1),(8,1)]:
            report=code if t>=7.2 else 0
            row=dict(time=t,clk_in=c,valid=float(t>=7.2))
            row.update({f'duty{i}':float((report>>i)&1) for i in range(8)})
            rows.append(row)
        return rows
    def test_half_lsb_allows_only_two_complete_neighbors(self):
        case=dict(kind='duty',stop=8,threshold=.5,vhigh=1,guard=.15,atol=.01,edge_time_uncertainty=1e-14)
        for code in [42,43]:
            self.assertTrue(m.evaluate(self.trace(code),case)['passed'])
        for code in [41,44,255]:
            self.assertFalse(m.evaluate(self.trace(code),case)['passed'])

class SettlingSpanBoundary(unittest.TestCase):
    def test_mathematical_twenty_mv_span_is_invalid(self):
        rows=[]
        for t,x,launch,status in [(0,.44,0,0),(.98,.44,0,0),(1.02,.44,1,0),(1.1,.46,0,0),(4.99,.46,0,0),(5.05,.46,0,2),(6,.46,0,2)]:
            rows.append(dict(time=t,vin=x,static_out=2.5*x,dynamic_out=2.5*x,launch=launch,gain=0,gain_valid=0,settling_ns=0,settled=0,status=status))
        result=m.evaluate(rows,dict(kind='settling',stop=6,sample_period=1,samples=4,tail_samples=2,settle_tol=.002,min_input_span=.02,input_span_uncertainty=1e-12,time_scale=1,guard=.07,atol=.01))
        self.assertTrue(result['passed'],result)

if __name__=='__main__': unittest.main()
