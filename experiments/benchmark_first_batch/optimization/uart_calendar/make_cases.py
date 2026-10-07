"""Fixed UART messages, drift, false starts, framing failures and reset."""
import json
from pathlib import Path


def pwl_levels(changes,stop,initial,rise=10e-9):
    points=[(0.,initial)];previous=initial
    for t,value in sorted(changes):
        if value==previous:continue
        points.extend([(t,previous),(t+rise,value)]);previous=value
    points.append((stop,previous));return points


def case(name,stop,bit_period,frames,glitches=(),resets=(),performance=False):
    changes=[]
    for t,code,drift,good in frames:
        period=bit_period*(1+drift)
        changes.append((t,0))
        changes.extend((t+(i+1)*period,(code>>i)&1) for i in range(8))
        changes.extend([(t+9*period,int(good)),(t+10*period,1)])
    for t,width in glitches:changes.extend([(t,0),(t+width,1)])
    reset_changes=[]
    for t,width in resets:reset_changes.extend([(t,1),(t+width,0)])
    controls=dict(rx=pwl_levels(changes,stop,1),reset=pwl_levels(reset_changes,stop,0))
    net='simulator lang=spectre\nglobal 0\nahdl_include "dut.va"\n'
    for node,points in controls.items():
        wave=' '.join(f'{t:.17g} {v}' for t,v in points)
        net+=f'V{node.upper()} ({node} 0) vsource type=pwl wave=[{wave}]\n'
    net+=f'DUT (rx reset busy valid error data shift) uart_receiver bit_period={bit_period}\n'
    net+='simulatorOptions options reltol=1e-6 vabstol=1e-9 iabstol=1e-14\n'
    net+=f'tran tran stop={stop} errpreset=conservative\nsave rx reset busy valid error data shift\n'
    return dict(name=name,stop=stop,netlist=net,signals=['rx','reset','busy','valid','error','data','shift'],
                controls=controls,bit_period=bit_period,rise=10e-9,edge_atol=.08*bit_period,
                exclusion=.09*bit_period,voltage_atol=4e-6,performance=performance)


def main():
    period=1/115200
    cases=[case('sparse-status-messages',.1,period,[(.001003716+i*.01001723,(i*61+165)%256,(-.02 if i%2 else .02),True) for i in range(10)],[(.000303713,.2*period)],performance=True),
           case('framing-reset-recovery',.005,period,[(.000203716,165,0,False),(.001003716,60,.02,True),(.002003716,231,0,True),(.003003716,113,-.02,True)],resets=[(.002003716+3.3*period,2*period)]),
           case('other-baud-and-false-start',.008,1/57600,[(.001003716,90,.02,True),(.005003716,195,-.02,True)],glitches=[(.000303713,.2/57600),(.003503717,.3/57600)])]
    (Path(__file__).parent/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')

if __name__=='__main__':main()
