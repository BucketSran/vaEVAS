"""P1 public CLI/build and real host startup/batch/calendar validation."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

from clock_cases import CASES, FILES, SOURCES, configuration, answers
from clock_reference import score_wave, ng_trace, pair, shape
from check import read_ng
from prepare_reference import prepare_reference
from trace_files import retained_traces, open_trace
from validate import ROOT, run, sha
from pilot_identity import write_identity


def rollback(directory, tag, highbit=False):
    with open_trace(directory / ("trace-" + tag + ".csv")) as f:
        rows = [r for r in csv.DictReader(f) if r["analysis"] == "1"]
    inj = next((i for i, r in enumerate(rows) if r["injected"] == "1"), None)
    retry = next((r for r in rows[(inj + 1):] if r["rollback"] == "1"), None) if inj is not None else None
    if retry is None:
        return {"passed": False, "activated": False, "kind_matches": False, "errors": ["missing actual injected batch retry"]}
    mask = int(rows[inj]["event_mask"])
    same = {k: retry[k] == retry["trial_" + k[5:]] for k in retry
            if k.startswith(("prev_s", "prev_tick", "prev_q", "prev_end"))}
    restored = (all(same.values()) and retry["prev_armed"] == retry["trial_armed"]
                and int(retry["event_mask"]) == 0 and retry["restored"] == "1"
                and retry["trial_hash"] == retry["prev_hash"])
    kind = mask.bit_length() > 32 if highbit else mask.bit_count() >= 2
    return {"passed": restored and kind, "activated": True, "first_retry_invariants": same, "event_mask": mask,
            "first_retry_time": float(retry["time"]), "injection_time": float(rows[inj]["time"]),
            "restored": restored, "kind_matches": kind}


def negative_verdict(mode, execution, complete_wave, trace, rb):
    if mode == "dc-leak":
        activated = trace.get("dc_injected") is True and trace.get("dc_calls", 0) >= 2
        detected = trace.get("dc_state_invariants") is False
        passed = activated and detected
        category = "DC candidate leak; nonconvergence may leave no waveform"
    else:
        activated = bool(rb and rb.get("activated") and rb.get("kind_matches"))
        detected = bool(rb and rb.get("restored") is False)
        passed = activated and detected and execution["exit_code"] == 0 and complete_wave
        category = "completed transient with actual batch rollback and leaked Frame"
    return {"passed": bool(passed), "activated": activated, "detected": detected,
            "complete_waveform": complete_wave, "category": category}


def analyze_run(d, cfg, mode, normal):
    receipt=json.loads((d/"execution.json").read_text())
    negative=mode in ("dc-leak","batch-leak")
    wave=read_ng(d/"wave.raw") if (d/"wave.raw").exists() else None
    physical=score_wave(wave,cfg) if wave else {"passed":False,"errors":["no complete waveform"]}
    traces={tag:ng_trace(d/("trace-"+tag+".csv"),cfg,tag,o["state_names"],o["triggers"],mode=="dc-retry")
            for tag,o in cfg["observations"].items()}
    rb=rollback(d,"a",mode=="highbit-retry") if mode in ("batch-retry","batch-leak","highbit-retry") else None
    paired=pair(wave,read_ng(normal/"wave.raw"),cfg,cfg["budgets"]["retry_V"] if mode!="dense" else None) if wave and mode in ("dc-retry","batch-retry","highbit-retry","dense") else None
    names=[n for a in answers(cfg).values() for n in a["outputs"]]
    control=negative_verdict(mode,receipt,bool(wave and shape(wave,names,cfg["stop"])),traces["a"],rb) if negative else None
    passed=control["passed"] if negative else receipt["exit_code"]==0 and physical["passed"] and all(t["passed"] for t in traces.values()) and (rb is None or rb["passed"]) and (paired is None or paired["passed"])
    return {"passed":passed,"negative_control":negative,"control":control,"physical":physical,"traces":traces,"rollback":rb,"pair":paired}


def reanalyze(source, output):
    source,output=Path(source).resolve(),Path(output).resolve();output.mkdir(exist_ok=False)
    rows={}
    for d in sorted(source.iterdir()):
        if not (d/"contract.json").is_file():continue
        cfg=json.loads((d/"contract.json").read_text());mode=d.name[len(cfg["case"])+1:]
        rows[d.name]=analyze_run(d,cfg,mode,source/(cfg["case"]+"-normal"))
        (output/(d.name+".json")).write_text(json.dumps(rows[d.name],indent=2,allow_nan=False)+'\n')
        print(d.name,rows[d.name]["passed"],flush=True)
    result={"passed":bool(rows) and all(r["passed"] for r in rows.values()),"runs":rows,"new_simulator_runs":0,
            "checker_sha256":{n:sha(Path(__file__).parent/n) for n in ('clock_cases.py','clock_reference.py','validate_clock.py')}}
    (output/"analysis.json").write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


def deck(cfg, models, mode):
    text = "P1 fixed parameterized clock and startup\n"
    nodes = []
    for m in cfg["models"]:
        tag = m["tag"]; built = models[tag]
        opts = 'evas_trace="trace-' + tag + '.csv" evas_trace_dc=true'
        if tag == "a":
            if mode in ("dc-retry", "dc-leak"): opts += " evas_inject_dc=true"
            if mode in ("batch-retry", "batch-leak"): opts += " evas_inject=true evas_inject_time=19n"
            if mode == "highbit-retry": opts += " evas_inject=true evas_inject_time=1871n"
            if mode in ("dc-leak", "batch-leak"): opts += " evas_bad_state=true"
        text += f".model m{tag} {built['metadata']['model_name']}({opts})\n"
        pins = [p.lower() + tag for p in built["metadata"]["ports"]]
        nodes.extend(pins)
        text += "a" + tag + " " + " ".join(pins) + " m" + tag + "\n"
        text += "".join("r" + p + " " + p + " 0 1k\n" for p in pins)
    step = cfg["maxstep_s"] / (2 if mode == "dense" else 1)
    return (text + ".options method=gear maxord=2 reltol=1e-10 vntol=1e-13 abstol=1e-16\n.save "
            + " ".join("v(" + n + ")" for n in nodes)
            + f"\n.tran {step:.17g} {cfg['stop']:.17g} 0 {step:.17g}\n.control\nset filetype=ascii\nset numdgt=17\nrun\nwrite wave.raw all\nquit\n.endc\n.end\n")


def validate(output, sdk, cases):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    write_identity(output)
    cache, results = {}, {}
    recipes = {c: configuration(c) for c in cases}
    (output / "recipes.json").write_text(json.dumps(recipes, indent=2) + "\n")
    for case, cfg in recipes.items():
        models = {}
        for m in cfg["models"]:
            key = hashlib.sha256(json.dumps([m["kind"], m["parameters"]], sort_keys=True).encode()).hexdigest()[:12]
            if key not in cache:
                artifact = output / ("model-" + key)
                command = [sys.executable, "-B", "-m", "evas", "xspice", "compile", SOURCES / FILES[m["kind"]],
                           "-o", artifact, "--model-name", "p1_" + key, "--test-hooks"]
                for name, value in m["parameters"].items(): command.extend(("--parameter", name + "=" + repr(value)))
                for command, label, timeout in [(command, "compile", 30),
                        ([sys.executable,"-B","-m","evas","xspice","build",artifact,"--sdk",str(Path(sdk).resolve())],"build",120)]:
                    receipt = run(command, ROOT, output / (key + "-" + label + ".log"), timeout)
                    if receipt["exit_code"]: raise RuntimeError(receipt)
                cache[key] = {"artifact": str(artifact), "metadata": json.loads((artifact / "metadata.json").read_text()),
                              "ir": json.loads((artifact / "ir.json").read_text()), "build": json.loads((artifact / "native/build.json").read_text())}
            models[m["tag"]] = cache[key]
        cfg["observations"] = {tag: {"state_names": m["metadata"]["state_names"], "triggers": [e["trigger"] for e in m["ir"]["events"]]} for tag,m in models.items()}
        (output / (case + "-answer.json")).write_text(json.dumps(answers(cfg), indent=2) + "\n")
        modes = ["normal"]
        if case == "zero": modes += ["dc-retry", "dc-leak"]
        if case == "default32": modes += ["batch-retry", "batch-leak", "dense"]
        if case == "variant42": modes += ["highbit-retry"]
        for mode in modes:
            d = output / (case + "-" + mode);d.mkdir()
            for tag, m in models.items():
                (d / ("model-" + tag + ".cm")).symlink_to(m["build"]["library"])
            (d / ".spiceinit").write_text("".join("codemodel model-" + tag + ".cm\n" for tag in models))
            (d / "tb.cir").write_text(deck(cfg, models, mode))
            (d / "contract.json").write_text(json.dumps(cfg, indent=2) + "\n")
            if mode == "normal":
                reference = prepare_reference(d, [m["artifact"] for m in models.values()])
                native = output / "spectre" / case;shutil.copytree(reference,native)
                text = (native / "tb.scs").read_text().replace("iabstol=1e-16", 'iabstol=1e-16 precision="%.17g" saveahdlvars=all')
                text += "save " + " ".join("x" + tag + ":" + n for tag,m in models.items() for n in m["metadata"]["state_names"]) + "\n"
                (native / "tb.scs").write_text(text);shutil.copy2(d / "contract.json",native / "contract.json")
            with retained_traces(d):
                receipt = run([next(iter(models.values()))["build"]["ngspice"],"-b","tb.cir"],d,d/"stdout.log",120)
                (d/"execution.json").write_text(json.dumps({**receipt,"deck_sha256":sha(d/"tb.cir")},indent=2)+'\n')
                row=analyze_run(d,cfg,mode,output/(case+"-normal"))
                results[case+"-"+mode]=row;(d/"analysis.json").write_text(json.dumps(row,indent=2,allow_nan=False)+'\n')
                print(case,mode,row["passed"],row["physical"]["errors"],{t:v["errors"] for t,v in row["traces"].items()},flush=True)
        (output/"analysis.json").write_text(json.dumps({"passed":all(r["passed"] for r in results.values()),"runs":results},indent=2,allow_nan=False)+'\n')
    final={"passed":all(r["passed"] for r in results.values()),"runs":results,"new_ngspice_circuit_runs":len(results),"new_build_probes":len(cache),"new_spectre_runs":0}
    (output/"analysis.json").write_text(json.dumps(final,indent=2,allow_nan=False)+'\n');return final


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);p.add_argument("--sdk");p.add_argument("--reanalyze");p.add_argument("--cases",default=",".join(CASES));a=p.parse_args()
    result=reanalyze(a.reanalyze,a.output) if a.reanalyze else validate(a.output,a.sdk,a.cases.split(","))
    raise SystemExit(0 if result["passed"] else 1)
