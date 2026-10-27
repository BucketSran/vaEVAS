#!/usr/bin/env python3
"""Write historical capability views and the current requirement view.

    python3 evas/capabilities/render.py
    python3 evas/capabilities/render.py --check

The default write and --check emit the historical pages together with
generated/support.md and generated/support-facts.json. Both current files
come from one registry projection.
"""
import argparse
import json
from pathlib import Path
from collections import Counter

from registry import load

from catalog import BACKENDS, CAMPAIGNS, CHAPTERS, NODES

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "registry.json"
COMPARISON = HERE / "generated" / "comparison.md"
PAPER = HERE / "generated" / "paper.md"
SUPPORT = HERE / "generated" / "support.md"
SUPPORT_FACTS = HERE / "generated" / "support-facts.json"
BACKEND_HEADINGS = {
    "spectre": "Spectre",
    "ngspice": "ngspice + OpenVAF-R",
    "gnucap": "Gnucap + modelgen-verilog",
    "evas": "EVAS",
}


def historical_view():
    from support_view import load_historical_import
    raw = load_historical_import()
    return {
        "identity": raw["identity"],
        "source": raw["source"],
        "scope": raw["scope"],
        "role": "historical-index",
        "in_current_requirement_denominator": False,
    }


def registry(reg=None):
    normative = load() if reg is None else reg
    return {
        "language_profile": normative.data["language_profile"]["id"],
        "target_scope": normative.data["target_scope"]["id"],
        "normative_index": {"items": len(normative.data["inventory"]),
                            "dispositions": dict(sorted(Counter(
                                x["decision"] for x in normative.data["dispositions"]).items()))},
        "chapters": list(CHAPTERS),
        "campaigns": CAMPAIGNS,
        "historical_view": historical_view(),
        "nodes": NODES,
    }


def paper_sentence(node):
    cells = "；".join(
        f"{BACKEND_HEADINGS[name]}：{node['results'][name]}" for name in BACKENDS
    )
    return f"{node['title']}。{cells}。"


def evidence_scope():
    # All generated views are one directory below capabilities/.
    return [
        "成绩沿用[原支持矩阵](../../docs/COMPARISON.md#支持矩阵)的固定模型和配置，",
        "只适用于各行的容差、停止时间及来源版本，不覆盖所有合法写法。",
        "结果来自不同历史版本，不代表当前 main 或 IR33 的一次全量验收。",
        "逐行范围见[验证覆盖](../../validation/paper/COVERAGE.md)，",
        "执行版本与收据见[来源和补充证据](../../docs/development/COMPARISON.md#table-evidence)。",
        "",
    ]


def historical_lines(data, view_link, facts_link):
    view = data.get("historical_view") or {}
    identity = view.get("identity") or "unknown"
    source = view.get("source") or "unknown"
    scope = view.get("scope") or "unknown"
    return [
        f"历史视图身份：`{identity}`。",
        f"原输入：`{source}`。",
        f"原判据范围：{scope}。",
        "这些成绩留在该历史身份下。当前要求分母只计登记中的当前要求。",
        f"当前逐要求四后端事实见 [support.md]({view_link}) 与 [support-facts.json]({facts_link})。",
        "",
    ]


def comparison_markdown(data):
    lines = [
        "# 能力比较表",
        "",
        *historical_lines(data, "support.md", "support-facts.json"),
        "由 `evas/capabilities/data/` 生成。已比较的成绩转录自",
        "[四后端支持表前五节](../../docs/COMPARISON.md#支持矩阵)，不改写该文的历史说明。",
        "没有四后端成绩的节点标为等待跑，不填通过或失败。",
        "",
        *evidence_scope(),
        "| 能力 | 章节 | 状态 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for node in data["nodes"]:
        if node["status"] == "compared":
            cells = [node["results"][name] for name in BACKENDS]
            status = "已比较"
        else:
            cells = ["等待跑"] * len(BACKENDS)
            status = "等待跑"
        chapter = node["chapter"]
        lines.append(
            f"| [{node['title']}](../{node['id']}/README.md) | {chapter} | {status} | "
            + " | ".join(cells)
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def paper_markdown(data):
    lines = [
        "# 给使用者和审稿人的能力比较",
        "",
        *historical_lines(data, "support.md", "support-facts.json"),
        "由 `evas/capabilities/data/` 生成。只包含已经有四后端成绩的能力节点。",
        "这一页不是实验开发的登记簿。落后和未验收留在格子里。",
        "",
        *evidence_scope(),
        "| 能力 | 与其他仿真器的比较 |",
        "| --- | --- |",
    ]
    for node in data["nodes"]:
        if node["status"] != "compared":
            continue
        lines.append(f"| {node['title']} | {paper_sentence(node)} |")
    lines.append("")
    return "\n".join(lines)


def node_page(node, data=None):
    lines = [
        f"# {node['title']}",
        "",
        *historical_lines(data or {}, "../generated/support.md", "../generated/support-facts.json"),
        f"章节：{node['chapter']}。",
        f"状态：{'已比较' if node['status'] == 'compared' else '等待跑'}。",
        f"审核：{'成绩已转录' if node['review'] == 'recorded' else '待审核'}。",
        "",
    ]
    if node["depends_on"]:
        deps = "、".join(f"`{item}`" for item in node["depends_on"])
        lines.append(f"依赖的基本节点：{deps}。组合通过不使这些节点自动合格。")
        lines.append("")
    if node["status"] == "compared":
        lines.extend(evidence_scope())
        lines.append(paper_sentence(node))
        lines.append("")
        lines.append(f"成绩来源：[{node['evidence']}](../../../{node['evidence']})。")
    else:
        lines.append(node["gap"])
        lines.append("")
        lines.append(f"待补来源：[{node['evidence']}](../../../{node['evidence']})。")
    lines.append("")
    lines.append("当前合同若仍在旧路径，是因为那一路径或字节已被冻结收据引用。本目录不搬那些文件。")
    lines.append("")
    return "\n".join(lines)


def normative_markdown(reg):
    profile = reg.data['language_profile']
    counts = Counter(x['decision'] for x in reg.data['dispositions'])
    target = reg.data['target_scope']
    lines = ['# 规范登记状态', '',
             '由 `evas/capabilities/data/` 生成。规范索引、目标范围、资格和历史成绩分别记录。',
             '当前逐要求四后端事实见 [support.md](support.md) 与 [support-facts.json](support-facts.json)。',
             '',
             f"语言配置：`{profile['id']}`。基础为 LRM {profile['base']}，选入变化为 "
             + ', '.join(profile['selected_changes']) + '。', '',
             '未选入的变化继续采用基础版本；规范选入不表示后端已支持。Spectre 待跑。', '',
             f"EVAS 目标配置：`{target['id']}`，目标域 {len(target['included'])} 项，明确目标外 {len(target['excluded'])} 项，待细分 {len(target['pending'])} 项。",
             '这些是产品范围组，不是规范覆盖率或实现支持数。', '',
             '| 来源处置 | 条目数 |', '| --- | ---: |']
    lines.extend(f'| {key} | {value} |' for key, value in sorted(counts.items()))
    lines += ['', '处置数是源索引的分母，不是要求数、测试方法数或规范覆盖率。',
              '待判定条目及抽取边界保留在登记中；完整语义审核不能由目录自检代替。', '',
              '| 当前对象 | 类型 | 资格缺口数 |', '| --- | --- | ---: |']
    for name, version in sorted(reg.data['current'].items()):
        obj = reg.objects[(name, version)]
        if obj['kind'] in {'source', 'asset', 'method', 'entrypoint',
                           'historical-audit-record', 'historical-finding'}:
            continue
        lines.append(f"| `{name}@{version}` | {obj['kind']} | {len(reg.qualification_gaps(name))} |")
    lines += ['', '资格缺口来自固定版本的依赖、审核和来源检查，不把历史运行通过转授为当前支持。', '']
    return '\n'.join(lines)


def support_pair(reg, historical=None):
    from support_view import projection_texts
    return projection_texts(reg, historical)


def outputs(data, reg=None):
    reg = load() if reg is None else reg
    facts, support = support_pair(reg)
    files = {
        REGISTRY: json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        COMPARISON: comparison_markdown(data),
        PAPER: paper_markdown(data),
        HERE / "generated" / "normative.md": normative_markdown(reg),
        SUPPORT_FACTS: facts,
        SUPPORT: support,
    }
    for node in data["nodes"]:
        files[HERE / node["id"] / "README.md"] = node_page(node, data)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--support-preview", metavar="DIR",
                        help="write the same requirement projection into DIR; does not replace --check")
    args = parser.parse_args(argv)
    if args.support_preview:
        if args.check:
            raise SystemExit("support preview does not replace --check")
        from support_view import SupportViewError, write_preview
        try:
            written = write_preview(load(), args.support_preview)
        except SupportViewError as error:
            raise SystemExit(str(error))
        print(f"wrote {len(written)} support preview files")
        return
    from support_view import SupportViewError
    try:
        reg = load()
        files = outputs(registry(reg), reg)
    except SupportViewError as error:
        raise SystemExit(str(error))
    if args.check:
        stale = [path.relative_to(ROOT).as_posix() for path, text in files.items()
                 if not path.is_file() or path.read_text() != text]
        if stale:
            raise SystemExit("stale capability views:\n" + "\n".join(stale))
        print(f"checked {len(files)} capability files")
        return
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    print(f"wrote {len(files)} capability files")


if __name__ == "__main__":
    main()
