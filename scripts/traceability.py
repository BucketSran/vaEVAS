#!/usr/bin/env python3
"""Generate docs/TRACEABILITY.md from test GUARDS tags and validation contracts.

The matrix is a generated artifact: never hand-edit docs/TRACEABILITY.md.
Run from the repository root:

    python3 scripts/traceability.py            # write docs/TRACEABILITY.md
    python3 scripts/traceability.py --check    # validate tags and matrix freshness

Tags are reviewed file-level declarations, not proof of coverage or execution.
Read source with AST; never import test modules. Invalid tags fail both modes.
"""
import argparse
import ast
import pathlib
import re
import sys
from urllib.parse import unquote, urlsplit

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
EVIDENCE_ONLY = {"QUALIFICATION", "PERFORMANCE"}


def check_links(markdown):
    """Check local files and anchors referenced by the generated registry rows."""
    for link in re.findall(r"\]\(([^\s)]+)\)", markdown):
        url = urlsplit(link)
        if url.scheme:
            continue
        path = (OUT.parent / unquote(url.path)).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f"missing local target: {link}")
        if url.fragment:
            text = path.read_text()
            anchors = set(re.findall(r'id=[\"\']([^\"\']+)[\"\']', text))
            used = {}
            for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.M):
                slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
                count = used.get(slug, 0)
                anchors.add(f"{slug}-{count}" if count else slug)
                used[slug] = count + 1
            if unquote(url.fragment) not in anchors:
                raise ValueError(f"missing local anchor: {link}")


def capabilities():
    """The capability table owns IDs, math links and evidence navigation."""
    rows = {}
    text = (OUT.parent / "CAPABILITIES.md").read_text()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not re.fullmatch(r"[A-Z][A-Z-]*", cells[0]):
            continue
        if len(cells) != 5 or cells[0] in rows or not cells[4]:
            raise ValueError(f"invalid capability row: {line}")
        check_links(cells[2] + " " + cells[4])
        rows[cells[0]] = (cells[2], cells[4])
    if not rows:
        raise ValueError("no capability rows found")
    return rows


def collect(known, cases):
    rows = {}
    for f in sorted(TESTS.rglob("test_*.py")):
        tree = ast.parse(f.read_text())
        declarations = []
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, ast.AnnAssign) else [])
            if any(isinstance(t, ast.Name) and t.id == "GUARDS" for t in targets):
                declarations.append(node.value)
        if len(declarations) != 1:
            raise ValueError(f"{f.name}: expected one GUARDS declaration")
        guards = ast.literal_eval(declarations[0])
        if not isinstance(guards, list) or not guards or any(not isinstance(g, str) for g in guards):
            raise ValueError(f"{f.name}: GUARDS must be a nonempty list of strings")
        if len(set(guards)) != len(guards):
            raise ValueError(f"{f.name}: duplicate GUARDS IDs")
        for guard in guards:
            if guard not in known and guard not in cases and not re.fullmatch(r"DEV:[a-z0-9]+(?:-[a-z0-9]+)*", guard):
                raise ValueError(f"{f.name}: unknown GUARDS ID {guard!r}")
        rows[f.relative_to(TESTS).as_posix()] = guards
    if not rows:
        raise ValueError("no test files found")
    return rows


def render(rows, caps, cases):
    guarded = {}
    for name, guards in rows.items():
        for g in guards:
            guarded.setdefault(g, []).append(name)

    lines = [
        "# 追溯矩阵（自动生成，勿手编）",
        "",
        "由 `scripts/traceability.py` 读取测试 `GUARDS`、能力表及 DUT 目录生成。",
        f"流程与标签语义见 [PROCESS.md](PROCESS.md)。共 {len(rows)} 个测试文件。",
        "标签是人工审查的文件级关联，不证明完整覆盖、测试通过或先红后绿。",
        "证据链接沿用能力表中的检查点，不自动认证当前代码；实现入口见数学章节的代码地图。",
        "",
        "## 契约 / 能力 → 守护测试",
        "",
        "| 契约/能力 ID | 契约或数学入口 | 已声明的守护测试 | 证据入口 |",
        "| --- | --- | --- | --- |",
    ]
    keys = list(dict.fromkeys([*caps, *CONTRACTS]))
    for key in keys:
        _, anchor = CONTRACTS.get(key, (key, "CAPABILITIES.md#能力矩阵"))
        entry, evidence = caps.get(key, (f"[契约]({anchor})", "按所属能力查阅；此行不绑定执行"))
        if key in CONTRACTS and key in caps:
            entry = f"[契约/数学]({anchor})"
        tests = guarded.get(key, [])
        cell = test_links(tests) or ("以执行证据为准" if key in EVIDENCE_ONLY else "未声明关联")
        lines.append(f"| {key} | {entry} | {cell} | {evidence} |")
    if cases:
        lines.append("")
        lines.append("### 直接使用的 DUT 模型（case:*）")
        lines.append("")
        lines.append("列出当前 DUT 目录；模型 ID 不等于运行条件 ID，未声明关联也不代表未被矩阵执行。")
        lines.append("")
        lines.append("| 模型 | 已声明的守护测试 |")
        lines.append("| --- | --- |")
        for c in sorted(cases):
            lines.append(f"| [{c}](../validation/cases/{c[5:]}/dut.va) | {test_links(guarded.get(c, [])) or '未声明关联'} |")
    dev = sorted(g for g in guarded if g.startswith("DEV:"))
    if dev:
        lines.append("")
        lines.append("### 开发主题（DEV:*，可与契约标签并存）")
        lines.append("")
        lines.append("| 主题 | 测试 |")
        lines.append("| --- | --- |")
        for d in dev:
            lines.append(f"| {d} | {test_links(guarded[d])} |")
    gaps = [k for k in keys if k not in guarded and k not in EVIDENCE_ONLY]
    lines += [
        "",
        "## 关联缺口",
        "",
    ]
    if gaps:
        lines.append("尚未声明测试关联的能力/契约：" + "、".join(gaps) + "。")
    else:
        lines.append("登记的能力/契约已有文件级关联（QUALIFICATION、PERFORMANCE 以执行证据为准）。")
    lines.append("本表不枚举所有语义组合或逐条测试方法，不能据此声称没有测试或实现缺口。")
    lines.append("收据与执行身份见 [CAPABILITIES](CAPABILITIES.md#检查点身份)与"
                 "[实验目录](../../experiments/README.md)。")
    lines.append("")
    return "\n".join(lines)


def test_links(names):
    return " ".join(f"[{name.removesuffix('.py')}](../tests/{name})" for name in names)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate without writing; reject stale matrix")
    args = ap.parse_args()
    try:
        caps = capabilities()
        for _, anchor in CONTRACTS.values():
            check_links(f"[contract]({anchor})")
        cases = {f"case:{p.parent.name}" for p in (ROOT / "evas/validation/cases").glob("*/dut.va")}
        rows = collect(set(CONTRACTS) | set(caps), cases)
        result = render(rows, caps, cases)
        if args.check:
            if not OUT.exists() or OUT.read_text() != result:
                raise ValueError("TRACEABILITY.md is missing or stale; run python3 scripts/traceability.py")
            print(f"validated tags, targets and matrix freshness ({len(rows)} test files)")
        else:
            OUT.write_text(result)
            print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} test files)")
    except (OSError, ValueError, SyntaxError) as error:
        print(f"Traceability check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
