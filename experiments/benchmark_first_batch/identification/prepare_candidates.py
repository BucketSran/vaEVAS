"""Generate reference and semantic negative VA only from public observations."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
VARIANTS={
    "identify-sh-acquisition":["no-droop","no-hold-step","wrong-polarity-step","fast-acquisition"],
    "identify-sc-clocked-filter":["single-pole","wrong-clock-edge","no-history","wrong-gain","low-phase-reset"],
    "identify-adc-driver-settling":["no-slew","wrong-bandwidth","no-rails","restart-on-input"],
    "identify-comparator-overdrive":["constant-delay","symmetric-delay","late-after-reset","wrong-dispersion"],
    "identify-pll-hop-dynamics":["wrong-damping","no-integral","wrong-loop-rate","wrong-clock-phase","grid-alias-ripple","early-tune-ripple"],
}


def prepare(output=None):
    output=output or ROOT/"runs/identification-candidates"
    for task,variants in VARIANTS.items():
        directory=ROOT/"benchmark/tasks"/task
        path=directory/"solution/fit.py"
        spec=importlib.util.spec_from_file_location(task,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        parameters=m.fit(directory/"environment/public")
        for variant in ["reference"]+variants:
            candidate=output/task/variant/"dut.va";candidate.parent.mkdir(parents=True,exist_ok=True)
            candidate.write_text(m.model(parameters,variant))
        print(json.dumps(dict(task=task,prepared_variants=["reference"]+variants,source="public observations",output=str(output/task))))


if __name__=="__main__":prepare()
