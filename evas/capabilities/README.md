# Verilog-A 能力目录

这里按仿真能力给测试分类。一个目录是一个能力节点。比较表和给审稿人的表都从 [catalog.py](catalog.py) 生成，不另维护一套名字。

| 文件 | 作用 |
| --- | --- |
| [catalog.py](catalog.py) | 节点、章节、依赖、成绩或待补说明 |
| [registry.json](registry.json) | 同一登记的 JSON |
| [generated/comparison.md](generated/comparison.md) | 全部节点。有四后端成绩的填成绩，没有的标等待跑 |
| [generated/paper.md](generated/paper.md) | 只含已比较的节点，供使用者和审稿人看 |

章节写在节点上，不作为上级目录。七组行为加上「语言」是章节字段。组合节点用 `depends_on` 指向基本节点；组合通过不使基本节点自动合格。

已比较的成绩转录自 [四后端支持表前五节](../docs/COMPARISON.md#支持矩阵)。该文的历史说明、第六节进度和收据路径仍留在原处。等待跑来自 [COVERAGE 的待补清单](../validation/paper/COVERAGE.md#remaining-coverage)，以及 PROTOCOL 里点名的 `above` 和 `last_crossing`。这些行的审核状态是待审核。Issue 和旧 README 里的想法还没有收进来。

冻结收据、历史波形和被哈希锁住的源码仍在 `experiments/backends/`。本目录不搬那些文件。31 条件的逐条映射还没有审核，campaign `dvs-31` 只指向原目录。

更新登记后运行：

```sh
python3 evas/capabilities/render.py
python3 -m unittest discover -s evas/capabilities -p 'test_registry.py'
```
