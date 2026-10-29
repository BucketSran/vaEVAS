# 来源与验收状态

## Behavior basis

来源为仓库保存的 v4 396-quadrature-lo-generator-divided-clock。原始材料保持原身份，本任务不继承旧验收结果。规格归口为 [#133](https://github.com/BucketSran/vaEVAS/issues/133)，本任务对应唯一 P1 来源 396。

迁移前公开合同固定在 [HEAD c485de86 instruction](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-396-quadrature-lo-generator-divided-clock/instruction.md)（blob `6d799fb70f1dbae3e7ed54ec54b6f75be0ee0ce4`），原来源页为 [HEAD c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v2-01/tasks/v2-spec-396-quadrature-lo-generator-divided-clock/SOURCE.md)。公开激励仍是 [visible_test.scs](environment/public/visible_test.scs)。

参考源码和激励经过原合同核对后保存。独立 checker 只读取实际输入输出，未读取参考源码。历史 Spectre 作者校准的固定身份与完整分母见 [作者校准最终报告](../../../../../../../experiments/benchmark_v2/author-calibration-final.md)，run `final-a5-cb789-equivalent-20261010T2140Z`。该结论绑定旧 `/work` 题包身份，不认证本次 `/app` Harbor 包。EVAS 行为不是本题验收真值。

同源关系：首批 v2-spec-001 BBPD 等时钟题职责不同；R01 两题无同源；规划池 C320 为“保留组件或变体”，没有候选。

## Modeling choices

原题面英文段与“本轮冻结的数值合同”合并写入 Spec：初态所有输出 vss；每次 reset/disable 异步清相位；释放控制不推进，首次新 clk 输出 10；合格上升沿指 rst 低且 enable 高时的 clk_in 上升沿；重新使能后从第 1 个合格沿重新计数，quad_ok 在第 1 至第 7 沿保持 vss、第 8 沿更新为 vdd，不另等第 9 沿；资格输出也用 tr 过渡。没有改数。

原题面写 helper 模块可选、公开合同不要求 helper；交付仍是单文件 `/app/circuit.va`，Deliverable 写明 helper 放在同一文件。端口方向按原题面角色写入 starter：`clk_in`、`rst`、`enable` 为输入，四个输出为输出。

Harbor 包装把 `environment/public` 放到 `/app/testbench`，`visible_test.scs` 的 include 由 `/work/dut.va` 改为 `/app/circuit.va`。公开用例取原私有 `tests/cases.json` 的第一个用例 `contract-base`。

题面评分句改为现行政策：已执行的失败尝试记 0，失败原因单独记录；环境或基础设施导致的 0 分不证明 VA 语义错误。

### 用户已确认（2026-10-28）：F01 选 A

2026-10-28 约 02:40Z 用户经总协调答复“全部按推荐”，评分起点问题（F01）选 A：题面写明 checker 实际的观察起点，checker 不动；每题加迟到负例与窗内对照。本题按此处理如下（第二批 f01-r1，所有记录写明“未仿真”）。

- 题面：评分段原句 “After a `tr` transition finishes, every point in the following hold interval is checked.” 改为 “Each output reaches its new value within `tr` after the event that changes it. Every saved point is scored, for all four outputs, except points less than `1.15*tr` after t = 0 or after an event that changes an output target: a qualified rising `clk_in` edge, or a clear by a rising `rst` or a falling `enable`.”
  - 对应 checker：`tests/v2_spec.py:188`：一行的时刻早于最近一次期望值改变时刻加 `1.15*tr` 时，该行全部输出跳过；期望值改变时刻来自 `tests/v2_spec.py:151` 的事件历史，起点含 t = 0（`:183`）。目标改变的事件见 `:105-108`（有效 `clk_in` 上升、`rst` 或 `enable` 清零）；`tr` 取默认 200 ps（`:11`）。
  - 余量：到达期限仍是 `tr`；在 `tr` 与 `1.15*tr` 之间到达的不区分，这是用户已接受的余量。
  - 题面其余合同和末尾执行段落未改；`environment/starter/testbench/README.md` 不含评分规则，未改。
- checker 不动：`tests/v2_spec.py` 与公开副本 `environment/starter/testbench/v2_spec.py`、`cases.json`、参考解、starter 模型、公开激励和其余共用文件都逐字节不变，改前改后哈希见 disposition.json。
- 负例与对照：`tests/calibration/` 三件（生成器 `mutants.py`、被拒矩阵 `expected.json`、中文说明 `README.md`），候选只改输出过渡时间。应被拒：`late_transition_1p3tr`；应通过（窗内对照）：`inwindow_transition_1p1tr`。
  - 合成控制（未仿真）：底波形为 fix-a-r1 的旧版参考波形（各用例的网表、支撑文件与交付文件都核对为现行字节），在内存中推迟输出列后直接调用本题 checker。`late-shift-60ps` 3 个私有用例都被拒；`inwindow-shift-20ps` 3 个私有用例都通过；未平移的底波形 3/3 通过。共 9/9 符合预期。
  - 旧版 EVAS 0.8.7：`late_transition_1p3tr` 3 个私有用例都被拒；`inwindow_transition_1p1tr` 3 个私有用例都通过。有预期的 6 例中 6 例符合 `expected.json`；只用网格行复判，判决都不变。参考解抽查 2 例（private/contract-base、public/contract-base）都通过，与此前记录一致。以上为旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。
- 证据目录：runs/t3-batch2-20261027/f01-r1/disposition.md（`runs/t3-batch2-20261027/f01-r1/disposition.md`）。

## Open items

本次 `/app` 包的参考运行、公开与私有一致性、以及包校准都尚未验证。**未仿真**：没有运行 Spectre。EVAS 02dee32b 与旧版 EVAS 0.8.7 的阶段结果只是开发证据（待 Spectre 复跑），记录在本地运行目录 `runs/t3-batch2-20261027/migration/v2-spec-396-quadrature-lo-generator-divided-clock/checks.json`（不入库）。阶段结果：EVAS 02dee32b 在 stage c 报 `kernel.unsupported_history_input`（同 308 的消息），没有提交步，私有 2 个用例与公开台架相同；旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2/2、公开 1/1 个用例通过各自 checker，只用规则网格行复判无判决变化。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

私有 checker 在目标变化后跳过 `1.15*tr`。迁移时（2026-10-27）公开合同是 `tr` 结束后检查保持区间，当时不采用 1.15。2026-10-28 起按本文件建模选择中的“用户已确认（2026-10-28）：F01 选 A”一段处理：题面已写明 `1.15*tr` 评分起点，到达期限仍是 `tr`。

迁移时两例的 rst 只在开头为高（同时 enable 低），工作中的清除只靠 enable 下降，无法区分真正响应 rst 的实现。2026-10-28 修正（fix-a-r1，F11）新增私有用例 `running-reset-reassert`：enable 自 3.25 ns 起一直为高；第 10 个合格沿后（quad_ok 已置位、状态 11）在约 53.05 ns 断言 rst、约 55.05 ns 释放，两沿离最近 clk 边沿至少 975 ps，rst 高期间没有 clk 上升沿；之后检验从 `10` 重新开始、第 8 个新合格沿再置 quad_ok。旧版 EVAS 0.8.7 上参考解私有 3/3、公开 1/1 通过，只用网格行复判无变化；删去 rst 异步清相位路径的错误模型原两例都通过、在新用例被拒。**未仿真**：没有运行 Spectre，旧版结果待 Spectre 复跑。

## 2026-10-29 触碰门限（v2spec-touch-r1，决定单第 4 项）

- 依据：决定单第 4 项（P0 清单第 38 项），用户 2026-10-29 定 A 收窄版；样板 r2.37 第 2 节“触碰门限”：题面写明，外部驱动的逻辑输入与独立比较器测试的输入差，到达门限时必定穿过，不触碰后返回，不停在门限上；被测模块内部产生的信号不受此限，按题面的相等规则判。本题照 P0 六题的英文写法补写同一句。
- 受约束的信号与门限：`clk_in`、`rst`、`enable`，门限 `vth`（缺省 0.45 V，用例不覆盖）。
- 激励核对（未仿真）：题包全部 6 份网表（`tests/cases.json` 3 份、公开 `cases.json` 1 份、`environment/public/visible_test.scs`、`environment/starter/testbench/visible_test.scs`）。每个受约束信号减去门限（相对参考节点的按差值），在有关源的折点并集上精确求值，十进制数按有理数读入：停在门限上 0 处、触碰后返回 0 处、t = 0 恰在门限上 0 处；另查 stop 时恰在门限上，0 处。不穿过门限的局部极值离门限最近 0.45 V（如 `environment/public/visible_test.scs` 的 clk_in，只作记录）。脚本 touch_scan.py（`runs/t3-harbor30-20261027/v2spec-touch-r1/scripts/touch_scan.py`）（`ba3e87af…`，自测合成停在门限、触碰、正常穿越等 9 条波形，各报对）→ touch-scan.json（`runs/t3-harbor30-20261027/v2spec-touch-r1/touch-scan.json`）（`a9c256da…`）。
- 题面：合法输入段原句 “A control does not stop exactly on its threshold.” 改为 “`clk_in`, `rst`, and `enable` never rest at `vth`. Each of them that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.” 原句即“不停在门限上”，与新句前半同义；合并时点名本题受约束的信号，原意不变；后半是本轮补的触碰一句。
- 不改：checker 与公开副本、`tests/cases.json` 与公开 `cases.json`、全部 `.scs`、参考解、starter、校准三件、`task.toml` 都逐字节不变，只改 `instruction.md` 与本页。网表、checker、参考解都没变，不需要新的 Spectre 作业。
- 记录：v2spec-touch-r1 交付（`runs/t3-harbor30-20261027/v2spec-touch-r1/disposition.md`）。
