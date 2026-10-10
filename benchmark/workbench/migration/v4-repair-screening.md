# 旧 v4 单模块修复资产筛选

2026-10-10。供 Issue107 的同行讨论，建议在已有 PFD case-0008 外，先讨论 **v4-1005 去抖资格计时**，其次讨论 **v4-1272 电源与偏置资格下的复位释放序列**。这是材料方向推荐，具体规格、题目质量和允许整体重写后的难度均未确定。五类任务用独立 checker 定义正确性的方向已定；本报告只筛诊断与修复，不纳入优化、收敛或异常耗时题，多 module 留待后续。

原资产身份见[资料入口](../../reference/README.md)，迁入来源快照 `7b5616dc52195ec275ec6d21c71d7763613702cd`；本轮读取 vaEVAS `c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9` 保存的字节。reference 仅供内部使用，保持原字节，不在本报告复制源码或外发。旧后端约束、认证结果和 scored 标签不转成当前准入条件。

## 数量及阅读边界

逐个读取 [r53 tasks](../../reference/v4/release/benchmarkv4-r53/tasks/) 的 `task_record.json`，1200 个包分为 dut、testbench、bugfix 各400个。对400个 bugfix 的 `public/buggy_bundle/*.va` 先将行注释、块注释和双引号字符串替换为空白，再用词法模式 `\bmodule\s+[A-Za-z_][A-Za-z0-9_$]*` 扫描声明，包含同行声明。1/2/3/4/5 module 分别为355/3/18/14/10包，即355个单module、45个多module包，共521个 VA文件。本次修正方法后数量不变。这是静态声明数，未展开实例层级，也不是355道已经合格的单模块题。

按名称先筛状态、复位、保持、边沿与计时方向，再细读下表六个包的题面、公开合同、actual starter、reference、score deck、checker profile、task record及各自 provenance 的 manifest/catalog。逐个计算 starter SHA-256，并比对实际 mutation 文件和 catalog 哈希；仅六个包做此身份核验。复用[已有修复调查](../../research/diagnosis-repair.md)的042/281线索和[PFD来源卡](../sources/v4-pfd-reset.md)，不重复建case。未普查其余394个故障，也未证明候选有真实用户工程bug记录，六项均按人工注错素材讨论。

| family / 修复ID | actual starter违反的行为 | manifest seed / 实际mutation | 讨论位置 |
| --- | --- | --- | --- |
| 005 / [1005][t005] | 上升沿立即置高，绕过12ns稳定资格计时；短毛刺也会产生高输出 | immediate_set_on_rise / 同名，字节一致 | 首选，资格计时与取消，3端口1module |
| 272 / [1272][t272] | 时钟上升更新时忽略rst，已有阶段不能按复位清零 | wrong_progress_scale / no_reset_clear，不一致 | 次选，顺序与重新资格，8端口1module |
| 064 / [1064][t064] | reset/disable时驱动vdd；合法高输出仅0.3V；边沿逆转会替换pending而非按reference拒绝 | neg_001 / neg_005，不一致 | 保留备选，6端口1module，合同需先理清 |
| 042 / [1042][t042] | 采样置零且decay默认0.900，合同为捕获vin及0.985 | neg_001 / 同名，字节一致 | 简单保持/下垂素材，已有研究 |
| 249 / [1249][t249] | 完全忽略rstb，缺公开tr参数 | metric_scale_low / ignore_reset，不一致 | 已有case-0008，复核后不新增 |
| 281 / [1281][t281] | 算出valid后不用，非法供电或en关闭时仍计数 | wrong_scale / ignore_enable，不一致 | 暂缓，14端口中四路未影响主要计数 |

这些错误能从实际赋值与公开合同推出反例，不依赖标签，也不是靠编译失败成立。本轮未编译，因此不宣称当前任何后端已经接受其语法。

## 两个优先讨论方向

1005的[starter][s005]、[reference][r005]和[provenance][p005]身份清楚。输入高持续短于stable时，starter在上升沿便置高，违反公开资格要求。可对应控制输入抗毛刺，但不能把行为锁存器称为真实模拟前端。保留低有效复位、资格期间回落取消、输出保持及有限平滑；独立checker从sig/rst_n阈值交点建立带取消标记的deadline，验收短脉冲、持续高、复位插入、再次上升和释放后的行为。专家需确定起始sig已高时是否资格、reset释放时sig仍高如何处理，以及stable=0和同时事件规则。现reference只在sig上升沿启动，不能默认为释放即启动。单module代码短、故障明显，允许整体重写后可能是简单题；尚无解题数据支持难度结论。其取消计时机制与已有UVLO有重叠，适合补单模块基础覆盖，不按新独立工程来源夸大多样性。

1272的[starter][s272]、[reference][r272]和[provenance][p272]提供同步阶段递推。保持supply_ok/bias_ok有效，先达到ready，再让rst在时钟上升时为高，starter继续保持ready，合同要求清零。它与PFD的异步挂起状态取消不同，可讨论电源、偏置满足后按拍释放下游使能的工程用途。checker只按外部clock上升计数、清零和饱和，检查stage1/stage2/ready/progress一致性。须明确这是同步复位；停钟期间rst高不能偷偷要求立即清零。旧参数只写finite，final_stage=0有除零问题，负值或小于2的阶段意义也需重设。优先考虑保留默认三级行为，其他参数范围由同行决定。实际starter只缺一项条件，整体重写难度同样未知。

064虽包含资格、延迟、拒绝及有效脉冲，更有事件交互，当前却不是干净的单故障版本。[reference][r064]递减qualification与delay后要再一次tick才发布，题面没有明确定义这些tick的计数边界；pending在delay期间逆转也会被拒绝，超过“资格完成前逆转”文字范围。应先讨论重叠边沿是取消、替换还是排队、脉冲有界的具体时长，再决定收题，不能直接照reference内部算法判分。042则适合明确递推答案，但采样恒零太直观，且reset只在采样或leak更新生效；281需先解释冗余端口及工程用途。两者保留现有研究即可。

## checker、迁移与待判断项

六份profile均写`private_checker_backend`及`checker_source_public=false`。本轮查阅迁入v4的runners/scripts并搜索六个checker身份，发现[feedback oracle](../../reference/v4/runners/feedback_oracle.py)调用外部`simulate_evas.evaluate_behavior`，[批量验证入口](../../reference/v4/scripts/validate_v4_checker_batch.py)导入`runners.checkers.v4.registry`。未在本次读取及文件路径搜索范围取得六个实际checker实现，不能宣称全库不存在checker。profile、刺激和认证不是独立评分代码已审计的证据。249的profile另称旧checker已静态审计并登记v3别名，本轮没有取得该别名实现或重做审计，保留为历史声明。

六个task record都声明公开visible与trusted replay同字节，实读两份deck也一致。旧刺激可用来解释现象，不能充当新隐藏泛化验收。应保留来源身份、接口意图和能解释的状态故障；重设清晰题面、同时事件与参数边界、独立checker、负例及后端校准。原reference留在资料库，不原地修改。历史认证的Rust EVAS2限定不沿用。Spectre、EVAS、ngspice根据实际支持与评分校准另定；ngspice可独立评分，无需默认把旧Spectre deck格式当后端准入条件。

同行需判断两项基础单module是否值得补充、064是否值得先清合同，以及允许重写后怎样仍衡量故障修复而非重复规格建模。本轮完成文件读取、全量record/声明统计、六包SHA/负例字节核对、deck身份比较和受限checker定位。未运行编译、仿真、评分、模型解题或历史认证重判；未改原始资产、索引或任务。

## 起始字节核验

下列哈希既匹配catalog实际mutation项，也匹配provenance中相应`evaluator/mutation_bundles/<id>/<artifact>.va`的真实字节；manifest指定不同项的四包均不能沿用旧seed标签。差异如何形成仍未知。005的manifest、catalog和负例文件三者一致，适合先做来源清楚的基础方向；272虽标签错误，实际遗漏rst能由公开递推直接解释，仍可保留。064的实际负例同时包含复位高电平、输出幅值与pending处理差异，不能把它描述成仅漏延迟。

| ID | starter SHA-256 |
| --- | --- |
| 1005 | `62450f5aaee354ec7d3996a5547c13c8f120655821c7ee3c219fe454c0759874` |
| 1272 | `1f7df42b4bae031dd03c5fba26c68efc5849611cf2c171a5e6d1539e6bebc23f` |
| 1064 | `2fd15e26b53bd9418b154e5cddef1cc6a90bc3e148db91c85a924dfce0700fcb` |
| 1042 | `0d8198c96dbe64c02e6e9edbe4e914619de02d709b7d8a3684cad347297908aa` |
| 1249 | `41023069a21d873c92ddd874ec7600edf1417db35f8a0cda642a0aa046b6415c` |
| 1281 | `b50490447ef19eb1a62cfebbc126c9f5033524077e2c013fc112518eb45a872e` |

[t005]: ../../reference/v4/release/benchmarkv4-r53/tasks/1005-debounce-latch-bugfix/public/instruction.md
[t272]: ../../reference/v4/release/benchmarkv4-r53/tasks/1272-reset-release-sequencer-bugfix/public/instruction.md
[t064]: ../../reference/v4/release/benchmarkv4-r53/tasks/1064-edge-delay-line-with-deglitch-bugfix/public/instruction.md
[t042]: ../../reference/v4/release/benchmarkv4-r53/tasks/1042-sample-and-hold-with-droop-leakage-bugfix/public/instruction.md
[t249]: ../../reference/v4/release/benchmarkv4-r53/tasks/1249-pfd-active-low-reset-bugfix/public/instruction.md
[t281]: ../../reference/v4/release/benchmarkv4-r53/tasks/1281-async-reset-event-counter-bugfix/public/instruction.md
[s005]: ../../reference/v4/release/benchmarkv4-r53/tasks/1005-debounce-latch-bugfix/public/buggy_bundle/debounce_latch.va
[r005]: ../../reference/v4/release/benchmarkv4-r53/tasks/1005-debounce-latch-bugfix/evaluator/solution/debounce_latch.va
[p005]: ../../reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/005-debounce-latch/evaluator/derivation_manifest.json
[s272]: ../../reference/v4/release/benchmarkv4-r53/tasks/1272-reset-release-sequencer-bugfix/public/buggy_bundle/reset_release_sequencer.va
[r272]: ../../reference/v4/release/benchmarkv4-r53/tasks/1272-reset-release-sequencer-bugfix/evaluator/solution/reset_release_sequencer.va
[p272]: ../../reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/272-reset-release-sequencer/evaluator/derivation_manifest.json
[r064]: ../../reference/v4/release/benchmarkv4-r53/tasks/1064-edge-delay-line-with-deglitch-bugfix/evaluator/solution/edge_delay_line_deglitch.va
