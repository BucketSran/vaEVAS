#!/usr/bin/env python3
"""Write the capability registry and the two views derived from it.

    python3 evas/capabilities/render.py          # write registry, views, node pages
    python3 evas/capabilities/render.py --check  # fail if those files drift
"""
import argparse
import json
from pathlib import Path

from catalog import BACKENDS, CAMPAIGNS, CHAPTERS, NODES

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "registry.json"
COMPARISON = HERE / "generated" / "comparison.md"
PAPER = HERE / "generated" / "paper.md"
BACKEND_HEADINGS = {
    "spectre": "Spectre",
    "ngspice": "ngspice + OpenVAF-R",
    "gnucap": "Gnucap + modelgen-verilog",
    "evas": "EVAS",
}


def registry():
    return {
        "chapters": list(CHAPTERS),
        "campaigns": CAMPAIGNS,
        "nodes": NODES,
    }


def paper_sentence(node):
    cells = "；".join(
        f"{BACKEND_HEADINGS[name]}：{node['results'][name]}" for name in BACKENDS
    )
    return f"{node['title']}。{cells}。"


def comparison_markdown(data):
    lines = [
        "# 能力比较表",
        "",
        "由 `evas/capabilities/catalog.py` 生成。已比较的成绩转录自",
        "[四后端支持表前五节](../../docs/COMPARISON.md#支持矩阵)，不改写该文的历史说明。",
        "没有四后端成绩的节点标为等待跑，不填通过或失败。",
        "",
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
        "由 `evas/capabilities/catalog.py` 生成。只包含已经有四后端成绩的能力节点。",
        "这一页不是实验开发的登记簿。落后和未验收留在格子里。",
        "",
        "| 能力 | 与其他仿真器的比较 |",
        "| --- | --- |",
    ]
    for node in data["nodes"]:
        if node["status"] != "compared":
            continue
        lines.append(f"| {node['title']} | {paper_sentence(node)} |")
    lines.append("")
    return "\n".join(lines)


def node_page(node):
    lines = [
        f"# {node['title']}",
        "",
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


def outputs(data):
    files = {
        REGISTRY: json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        COMPARISON: comparison_markdown(data),
        PAPER: paper_markdown(data),
    }
    for node in data["nodes"]:
        files[HERE / node["id"] / "README.md"] = node_page(node)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = outputs(registry())
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
