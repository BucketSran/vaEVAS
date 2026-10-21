"""Generate targeted VA candidates for later real simulator calibration."""
from pathlib import Path

def candidates():
    gold=(Path(__file__).resolve().parents[2]/'solution/circuit.va').read_text()
    release = """        @(cross(V(rst)-vth, -1)) begin
            if (V(track) <= vth) sample = vinit;
        end
"""
    return {
        'inclusive_threshold':gold.replace('> vth','>= vth').replace('<= vth','< vth'),
        'initial_input':gold.replace('@(initial_step) sample = vinit;', '@(initial_step) sample = V(vin);'),
        'sample_at_open':gold.replace('cross(V(track)-vth, -1)', 'cross(V(track)-vth, +1)'),
        'hold_feedthrough':gold.replace('else V(vout) <+ sample;', 'else V(vout) <+ V(vin);'),
        'stale_after_reset':gold.replace(release,''),
        'reset_to_zero':gold.replace('if (V(rst) > vth) V(vout) <+ vinit;', 'if (V(rst) > vth) V(vout) <+ 0;'),
        'track_priority':gold.replace(
            'if (V(rst) > vth) V(vout) <+ vinit;\n        else if (V(track) > vth) V(vout) <+ V(vin);',
            'if (V(track) > vth) V(vout) <+ V(vin);\n        else if (V(rst) > vth) V(vout) <+ vinit;'),
        'hold_droop':gold.replace('else V(vout) <+ sample;', 'else V(vout) <+ sample - 1e6*$abstime;'),
        'fixed_threshold':gold.replace('V(track)-vth','V(track)-0.9').replace('V(rst)-vth','V(rst)-0.9').replace('> vth','> 0.9').replace('<= vth','<= 0.9'),
        'fixed_initial':gold.replace('sample = vinit','sample = 0.9').replace('V(vout) <+ vinit','V(vout) <+ 0.9'),
        'finite_tracking':gold.replace('real sample;','real sample;\n    real filtered;').replace('analog begin','analog begin\n        filtered = laplace_nd(V(vin), {1}, {1, 1n});').replace('V(vout) <+ V(vin);','V(vout) <+ filtered;'),
    }

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for name,source in candidates().items(): (args.output/(name+'.va')).write_text(source)
