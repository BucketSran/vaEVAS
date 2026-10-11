"""Copy maintained verifier modules into self-contained Harbor task tests."""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_START = "<!-- generated submission policy -->"
POLICY_END = "<!-- end generated submission policy -->"


def submission_policy(contract):
    files = contract.get("candidate_files", ["dut.va"])
    outputs = contract.get("output_files", [])
    includes = "、".join("`" + name + "`" for name in ["disciplines.vams", "constants.vams", *files])
    text = (POLICY_START + "\n\n## 源码与文件合同\n\n"
            "终评只接收题目列出的 Verilog-A 文件。允许 include 的文件为 " + includes + "。"
            "不支持预处理宏定义、条件编译或宏引用，包括标准头文件中的常量宏；"
            "需要常量时请使用数值字面量或 Verilog-A parameter。普通数学函数不受此限制。\n\n"
            "候选不能读取外部文件、环境变量或内存数据文件，也不能执行系统命令。")
    if outputs:
        text += ("文件输出仅允许以字面量路径和模式 \"w\" 调用 $fopen："
                 + "、".join("`/work/output/" + name + "`" for name in outputs)
                 + "。终评只重定位这些输出路径，保留其余源码。")
    else:
        text += "本题不允许打开文件。"
    return text + "无法编译、超时或不能产生完整规定波形的提交计零分。\n\n" + POLICY_END


def with_submission_policy(instruction, contract):
    policy = submission_policy(contract)
    if POLICY_START not in instruction:
        return instruction.rstrip() + "\n\n" + policy + "\n"
    before, rest = instruction.split(POLICY_START, 1)
    if POLICY_END not in rest:
        raise ValueError("unclosed generated submission policy")
    _, after = rest.split(POLICY_END, 1)
    return before + policy + after


def sync(check=False):
    stale = []
    count = 0
    for contract in sorted((ROOT / "benchmark/tasks").glob("*/tests/contract.json")):
        tests = contract.parent
        if tests.parent.name.startswith("va") and tests.parent.name != "va07-triangle-repair":
            continue
        tree = ast.parse((tests / "verify.py").read_text())
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        v2 = "v2_runtime" in modules
        if v2:
            names = {"adc_linearity", *[m for m in modules if m.startswith("v2_")]}
        else:
            names = {"circuit_task", "adc_linearity", *[m for m in modules if m.startswith("first_batch_")]}
        if "first_batch_triangle" in modules:
            names.add("triangle_oscillator")
        for name in sorted(names):
            source = ROOT / "benchmark/checkers" / (name + ".py")
            target = tests / source.name
            data = source.read_bytes()
            if not target.exists() or target.read_bytes() != data:
                stale.append(str(target.relative_to(ROOT)))
                if not check:
                    target.write_bytes(data)
        # V2 preserves the task's public requirements and executes candidate
        # bytes unchanged. Legacy language and zero-on-error rules do not apply.
        if not v2:
            instruction = tests.parent / "instruction.md"
            original = instruction.read_text()
            updated = with_submission_policy(original, json.loads(contract.read_text()))
            if updated != original:
                stale.append(str(instruction.relative_to(ROOT)))
                if not check:
                    instruction.write_text(updated)
        count += 1
    return count, stale


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count, stale = sync(args.check)
    print(f"{count} task runtimes; {len(stale)} {'stale' if args.check else 'updated'} files")
    if args.check and stale:
        print("\n".join(stale))
        raise SystemExit(1)
