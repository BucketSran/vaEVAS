"""Deterministic public sensor conversion sequences, not simulation orchestration."""
import json
from pathlib import Path


def level_pwl(pulses,stop,initial=0):
    points=[(0,initial)]
    for start,width in pulses:
        points.extend([(start,0),(start+.1e-9,1),(start+width,1),(start+width+.1e-9,0)])
    points.append((stop,0))
    return points


def case(name,stop,starts,resets,vref,bit_period,performance=False):
    start_points=level_pwl(starts,stop)
    reset_points=level_pwl(resets,stop)
    inputs=[(0,.17*vref)]
    # Quiet sample window, then change the input during conversion to test hold.
    accepted_inputs=[]
    for index,(t,_) in enumerate(starts):
        if index and t-starts[index-1][0]<12*bit_period:continue
        code=(index*997+731)%4096
        value=vref*(code+.375)/4096
        inputs.extend([(t-100e-9,inputs[-1][1]),(t-99.9e-9,value),
                       (t+200e-9,value),(t+200.1e-9,vref*(4095-code+.375)/4096)])
        accepted_inputs.append(code)
    inputs.append((stop,inputs[-1][1]))
    inputs.sort()
    def source(node,points):
        wave=' '.join(f'{t:.17g} {v:.17g}' for t,v in points)
        return f'V{node.upper()} ({node} 0) vsource type=pwl wave=[{wave}]\n'
    netlist='simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\n'
    for node,points in [('vin',inputs),('start',start_points),('reset',reset_points)]:netlist+=source(node,points)
    netlist+=f'DUT (vin start reset busy valid code dac) sensor_sar vref={vref} bit_period={bit_period}\n'
    netlist+='simulatorOptions options reltol=1e-6 vabstol=1e-9 iabstol=1e-14\n'
    netlist+=f'tran tran stop={stop} errpreset=conservative\nsave vin start reset busy valid code dac\n'
    return dict(name=name,netlist=netlist,stop=stop,signals=['vin','start','reset','busy','valid','code','dac'],
                controls=dict(vin=inputs,start=start_points,reset=reset_points),vref=vref,bit_period=bit_period,
                rise=.5e-9,edge_atol=2e-9,voltage_atol=4e-6,performance=performance)


def main():
    cases=[case('sensor-idle-throughput',100e-6,[(1e-6+i*5e-6,20e-9) for i in range(20)],[],1.,50e-9,True),
           case('busy-start-and-reset',20e-6,[(1e-6,20e-9),(1.25e-6,20e-9),(5e-6,20e-9),(6e-6,20e-9),(12e-6,20e-9)],[(5.325e-6,200e-9)],1.3,50e-9),
           case('different-bit-period',15e-6,[(1e-6,20e-9),(4e-6,20e-9),(9e-6,20e-9)],[(7e-6,200e-9)],.8,80e-9)]
    (Path(__file__).parent/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')

if __name__=='__main__':main()
