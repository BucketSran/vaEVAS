#!/usr/bin/env python3
"""Generate docs/TRACEABILITY.md from test GUARDS tags and validation contracts.

The matrix is a generated artifact: never hand-edit docs/TRACEABILITY.md.
Run from the repository root:

    python3 scripts/traceability.py            # write docs/TRACEABILITY.md
    python3 scripts/traceability.py --check    # exit 1 on untagged test files

It also reports gaps: contract keys with no guarding tests, and pure-DEV
tests with no contract linkage. Those gaps are the input for the test
backlog, not an error by themselves.
"""
import argparse
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "evas/tests"
OUT = ROOT / "evas/docs/TRACEABILITY.md"

# Contract keys -> validation anchor. Keys are the IDs used in test GUARDS.
CONTRACTS = {
    "ANALOG": ("普通 analog 条件", "../validation/ANALOG_CONDITIONS_CONTRACT.md"),
    "LANG": ("语言/绑定/IR 契约", "../README.md#实现范围"),
    "LIN": ("线性电压关系", "math/solving.md"),
    "NONLINEAR-TRANSIENT": ("非线性瞬态契约", "../validation/NONLINEAR_TRANSIENT_CONTRACT.md"),
    "SPARSE": ("稀疏线性代数", "math/solving.md#稀疏分支与性能边界"),
    "CROSS": ("阈值事件", "math/events.md"),
    "TIMED-OPERATOR": ("定时与波形算子契约", "../validation/TIMED_OPERATOR_CONTRACTS.md"),
    "EVENT-CONDITIONS": ("事件条件与采样复位契约", "../validation/EVENT_CONDITIONS_CONTRACT.md"),
    "DYNAMICS": ("积分与共同生命周期契约", "../validation/DYNAMICS_CONTRACTS.md"),
    "LAPLACE": ("滤波契约", "../validation/LAPLACE_CONTRACTS.md"),
    "COMPOSE": ("实例与组合义务", "math/continuous.md"),
    "QUALIFICATION": ("独立验收矩阵", "../validation/README.md"),
}
CAPABILITIES = {"LANG", "LIN", "NONLINEAR", "SPARSE", "CROSS", "TIMER", "EVENT-ORDER",
                "TRANSITION", "ABSDELAY", "SLEW", "DYNAMICS", "COMPOSE", "QUALIFICATION",
                "PERFORMANCE"}


def collect():
    rows, untagged = {}, []
    for f in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(f.read_text())
        guards = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "GUARDS" for t in node.targets):
                guards = ast.literal_eval(node.value)
                break
        if guards is None:
            untagged.append(f.name)
            continue
        rows[f.name] = guards
    return rows, untagged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if any test file lacks a GUARDS tag")
    args = ap.parse_args()

    rows, untagged = collect()
    if args.check:
        if untagged:
            print("UNTAGGED:", ", ".join(untagged))
            return 1
        print("all test files tagged")
        return 0

    guarded = {}
    for name, guards in rows.items():
        for g in guards:
            guarded.setdefault(g, []).append(name)

    lines = [
        "# 追溯矩阵（自动生成，勿手编）",
        "",
        f"由 `scripts/traceability.py` 扫描 `evas/tests/*.py` 的 `GUARDS` 标签生成。",
        f"流程与标签语义见 [PROCESS.md](PROCESS.md)。共 {len(rows)} 个测试文件。",
        "",
        "## 契约 / 能力 → 守护测试",
        "",
        "| 契约/能力 ID | 判据锚点 | 守护测试 |",
        "| --- | --- | --- |",
    ]
    for key, (label, anchor) in CONTRACTS.items():
        tests = guarded.get(key, [])
        cell = " ".join(f"[{t.replace('.py','')}]" f"(../tests/{t})" for t in tests) or "**无守护测试（缺口）**"
        lines.append(f"| {key}：{label} | [锚点]({anchor}) | {cell} |")
    case_ids = sorted(g for g in guarded if g.startswith("case:"))
    if case_ids:
        lines.append("")
        lines.append("### 具体条件 DUT（case:*）")
        lines.append("")
        lines.append("| 条件 | 守护测试 |")
        lines.append("| --- | --- |")
        for c in case_ids:
            lines.append(f"| {c} | {' '.join('`'+t+'`' for t in guarded[c])} |")
    dev = sorted(g for g in guarded if g.startswith("DEV:"))
    if dev:
        lines.append("")
        lines.append("### 纯开发回归（DEV:*，无契约对应，诚实标注）")
        lines.append("")
        lines.append("| 主题 | 测试 |")
        lines.append("| --- | --- |")
        for d in dev:
            lines.append(f"| {d} | {' '.join('`'+t+'`' for t in guarded[d])} |")
    gaps = [k for k in CONTRACTS if k not in guarded and k != "QUALIFICATION"]
    lines += [
        "",
        "## 缺口报告",
        "",
    ]
    if gaps:
        lines.append("无守护测试的契约：" + "、".join(gaps) + "。")
    if untagged:
        lines.append("未挂标签的测试文件：" + "、".join(untagged) + "。")
    if not gaps and not untagged:
        lines.append("当前无契约缺口；QUALIFICATION 按设计无单元测试守护（资格只来自矩阵执行收据）；DEV 主题为开发护栏，不要求契约对应。")
    lines.append("收据与执行身份见 [CAPABILITIES](CAPABILITIES.md#检查点身份)与"
                 "[实验目录](../../experiments/README.md)。")
    lines.append("")
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} files, gaps: {gaps or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
