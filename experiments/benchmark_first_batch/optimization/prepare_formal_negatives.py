"""Prepare all 24 formal optimization negatives with the coordinator runtime.

Preparation only. No call to execute, SSH, Spectre or the harness remote transport.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

CHECKPOINT='8e4a7a186f4d171d4042b1e2105c8d0a569050b1'
CLASSIFICATION={
 'optimize-vco-step':{
  'unchanged_bound':('performance_only','Baseline-equivalent function; performance condition must fail the admitted steps ratio.'),
  'frozen_low_band':('semantic','Constant low-band output may pass low-band; slew/clamps and high-band must expose frozen frequency.'),
  'reduced_resolution':('semantic_accuracy','32 points/cycle violates the public 64-point phase-advance contract on constant-frequency cases.'),
  'undersample':('semantic_accuracy','Two points/cycle violates public resolution and waveform reconstruction.'),
  'wrong_amplitude':('semantic','0.9 amplitude changes the prescribed output voltage.'),
  'wrong_phase':('semantic','frequency*time is wrong under changing control; constant-frequency conditions may pass.')},
 'optimize-power-monitor':{
  'unchanged_poll':('performance_only','Corrected legal 1ns polling baseline; function passes, admitted steps ratio must fail.'),
  'coarse_poll':('semantic_timing','100ns polling cannot preserve the public 2ns edge timing; reduced cost cannot excuse that error.'),
  'no_hysteresis':('semantic','Disables at on threshold instead of off threshold.'),
  'no_qualification':('semantic','Does not maintain the required continuous high-supply qualification interval.'),
  'stale_qualification':('semantic','Does not cancel qualification after a below-on interruption.'),
  'no_transition':('semantic_edge','Removes the required finite 0.5ns linear output transition.')},
 'optimize-sar-calendar':{
  'unchanged_poll':('performance_only','Legal held-input/bit-calendar baseline; admitted steps ratio must fail.'),
  'coarse_poll':('semantic_timing','10ns polling violates 2ns conversion/trial/control edge timing.'),
  'early_bit_calendar':('semantic_timing','Changes prescribed bit intervals and completion deadlines.'),
  'no_input_hold':('semantic','Reads the changing input during bit decisions instead of holding accepted-start input.'),
  'restart_while_busy':('semantic','Accepts a start during an active conversion and overwrites conversion state.'),
  'no_transition':('semantic_edge','Removes required finite transitions from observable control/trial/code signals.')},
 'optimize-uart-calendar':{
  'unchanged_oversampling':('performance_only','Legal 16x receiver baseline; admitted steps ratio must fail.'),
  'eight_times_baud':('performance_and_possible_semantic','8x polling still cannot meet a 0.1 steps ratio; up-to-0.125bit phase quantization may also violate the public 0.08bit deadline tolerance. Actual evidence decides which rejection occurs.'),
  'msb_first':('semantic','Wrong serial bit weights change public data and shift history.'),
  'no_start_validation':('semantic','Short false starts must abort at half-bit validation; some no-false-start conditions may pass.'),
  'no_stop_check':('semantic','Bad stop bit must set framing error rather than valid; clean-frame cases may pass.'),
  'no_transition':('semantic_edge','Removes required finite 10ns output transitions.')},
}


def sha(data):return hashlib.sha256(data).hexdigest()


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def prepare(repo,harness,output):
    repo=repo.resolve();output=output.resolve()
    if output.exists():raise FileExistsError('never overwrite existing preparation/evidence directory')
    runtime=load(repo/'experiments/benchmark_first_batch/runtime.py','optimization_coordinator_prepare')
    guard=load(repo/'benchmark/checkers/first_batch_optimization.py','optimization_formal_source_guard')
    core=load(repo/'benchmark/checkers/circuit_task.py','optimization_actual_core_guard')
    checkpoint_source=subprocess.check_output(['git','show',CHECKPOINT+':benchmark/checkers/first_batch_optimization.py'],cwd=repo)
    checker_sha=sha((repo/'benchmark/checkers/first_batch_optimization.py').read_bytes())
    if checker_sha!=sha(checkpoint_source):raise ValueError('main checker differs from specified reviewed checkpoint')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    items=[]
    # Validate whole inventory/guards before creating any frozen packet.
    for task_id,negatives in CLASSIFICATION.items():
        task=repo/'benchmark/tasks'/task_id
        files={p.stem:p for p in (task/'tests/negatives').glob('*.va')}
        if set(files)!=set(negatives):raise ValueError('formal negatives changed: '+task_id)
        if sha((task/'tests/first_batch_optimization.py').read_bytes())!=checker_sha:raise ValueError('task/shared checker drift')
        cases=json.loads((task/'tests/cases.json').read_text())
        if len(cases)!=3 or sum(bool(c.get('performance')) for c in cases)!=1:raise ValueError('complete three-condition task required')
        for name,(category,reason) in negatives.items():
            candidate=files[name];data=candidate.read_bytes()
            identity=guard.validate_performance_source(data)
            _,relocation=core.prepare_source(data,['dut.va'],[],output/'validation-only')
            baseline=(task/'tests/baseline.va').read_bytes()
            tokens=core._legacy_module().source_tokens
            token_equivalent=[(k,v) for k,v,_,_ in tokens(data)]==[(k,v) for k,v,_,_ in tokens(baseline)]
            if category=='performance_only' and not token_equivalent:raise ValueError('unchanged negative active tokens differ from current legal baseline')
            items.append(dict(task_id=task_id,negative=name,category=category,reason=reason,
                              candidate=candidate,task=task,cases=cases,source_sha256=identity['source_sha256'],
                              legal_baseline_sha256=sha(baseline),baseline_token_equivalent=token_equivalent,
                              sourceguard='passed_without_execution',core_sourceguard='passed_without_execution',
                              compiler_status='unknown_until_actual_execution',output_translation=relocation))
    output.mkdir(parents=True,mode=0o700)
    plan=[];conditions=[]
    for item in items:
        target=output/item['task_id']/item['negative']
        result=runtime.prepare(item['task'],item['candidate'],target,harness)
        if result['source_identity']['first_batch_optimization.py']!=checker_sha:raise ValueError('frozen checker differs')
        if len(result['cases'])!=3:raise ValueError('condition lost during preparation')
        row={k:v for k,v in item.items() if k not in ('candidate','task','cases')}
        row.update(prepared=str(target),candidate_path=str(item['candidate']),criteria_sha256=result['criteria_sha256'],
                   frozen_candidate_sha256=result['candidate']['candidate_sha256'],
                   source_identity=result['source_identity'],status='prepared_only',simulator_executed=False,
                   expected_task_reward=0,expectation_scope='at least one of all three conditions rejects; not necessarily three zero scores')
        plan.append(row)
        for case in result['cases']:
            conditions.append(dict(task_id=item['task_id'],negative=item['negative'],category=item['category'],
                                   prepared=str(target),condition_id=case['condition_id'],package_sha256=case['sha256'],
                                   criteria_sha256=result['criteria_sha256'],source_sha256=item['source_sha256'],
                                   performance=next(c for c in item['cases'] if c['name']==case['condition_id']).get('performance',False),
                                   simulator_executed=False,status='prepared_only'))
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (output/'manifest.json').write_text(json.dumps(dict(kind='formal_optimization_negative_preparation_only',
        benchmark_revision=revision,reviewed_checker_checkpoint=CHECKPOINT,checker_sha256=checker_sha,
        coordinator_runtime_sha256=sha((repo/'experiments/benchmark_first_batch/runtime.py').read_bytes()),
        tasks=4,submissions=24,conditions=72,simulator_executed=False,records=conditions),indent=2)+'\n')
    (output/'prepare.py').write_bytes(Path(__file__).read_bytes())
    return plan


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--harness-checkout',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plan=prepare(args.repo,args.harness_checkout,args.output)
    print(json.dumps(dict(status='prepared_only',submissions=len(plan),conditions=72,simulator_executed=False)))
