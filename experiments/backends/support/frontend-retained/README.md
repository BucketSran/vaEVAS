# 标准数学头与未引用私有节点的有限对照

显式标准头现在提供十四个数学常量；从未引用的私有 electrical 声明不再制造电压未知量。实现固定于 `e9429435e85bd997e18359f5791fc948cc00a3d6`，基线为 `ff5d0fd9bc4dbeafe7fc91e233ad97880155a233`。标准头环境为 `evas-voltage-vams-v2`，EVAS 仍为 0.15.0、IR19。行为边界见[编译准入契约](../../../../evas/docs/reference/frontend-admission.md)。

## 什么通过，什么仍缺证

| 条件 | 保留结论 |
| --- | --- |
| fourteen constants | 同 VA 的实际 Spectre 16 行、224 值及四个精确 query、56 值满足原 1e-14 V 门槛；候选重新编译为 IR19 的 56 值最大 Decimal 误差 2.449340730629116e-16 V。复用已有实际运行，未新增远端运行。 |
| unused_scalar | 候选静态 u=0/0.5 与 Spectre PWL 两个端点均满足 y=u、1e-9 V；是相同代数关系的有限对照，双方不是相同请求协议。 |
| zero_forcing_filter v1 | 原七个 query 只记录五个精确时刻；已有点恒零通过 1e-9 V，缺两个。 |
| input_filter_product v1 | 只记录六个精确时刻；候选与解析值通过 2e-9 V，但 Spectre 与候选最大差 2.0968347974603674e-8 V，超原门槛，另缺一个精确时刻。 |
| 两个 filter v2 | 收紧 Spectre 配置后仍各缺五个原 exact query，只命中 0 和 5e-7 s。全原生诊断中 product 最大保守误差约 2.30626081726e-10 V；这项全行诊断保留于收据，完整大 PSF 仍 local-only。 |
| 两个 filter 附加有限近点对照 | 对原七个 query 分别保留实际最近原生点，直接比较样本与该 query 的独立解析值。十四项均通过原预算；product 最大保守界 2.3530753494034573e-10 V。不能认证未记录的 Spectre(q)。 |
| referenced_singular | EVAS 基线与候选均拒绝 singular_system；Spectre 安装 gmin 后完成。其浮置节点值不是 EVAS 应接受或应输出零的答案。 |

v1/v2 原严格 exact 判定保存在 [v1 ANALYSIS](spectre-v1/ANALYSIS.json) 与 [v2 ANALYSIS](spectre-v2/ANALYSIS.json)，没有回写。附加判据拥有独立身份 [near-sample/AUDIT.json](near-sample/AUDIT.json)，不授予 Q 资格，不代表整条轨迹或完整原任务通过。原 PWL、query、2e-9 V 门槛均未变。

## 附加有限对照约束的是实际样本

固定模型满足 `tau*f'+f=u`、f(0)=0、tau=0.5e-6，输出 y=u*f。PWL 连续且 |u|≤1，指数权重保证 |f|≤1，因此 `|y'|≤U+2/tau`。在准确 binary64 参数上，U 约为 2000000.000000000514 V/s，所需界约为 6000000.000000000695 V/s。采用严格更大的 **6000001 V/s**；zero forcing 采用 L=0。折点连续，分段积分给出全域解析变化界。

对原 query q、最近真实原生时刻 s 和该点电压 v，固定检查

`Bq = |v-y(q)| + L*(|s-q|+εt) + εv + εa ≤ 原电压预算`。

q 不变；不生成插值电压。εt、εv 分别采用读值半 ULP，εa 为有限解析表达式的保守 1e-60 V 运算界。独立 oracle 用 100 位 Decimal 分段求解。这约束实际样本与请求时刻的解析值，不能给未保存的 Spectre 数值轨迹加上导数界。两个端点样本都为零仍不能排除未记录中点的数值尖峰；该范围反例保存在 AUDIT。

[有限对照复核脚本](verify_finite_samples.py) 重算十四项、五个接受/拒绝校准、准确有理斜率界与范围反例，并核对所有留存文件哈希。它使用 v2 的逐字原生行摘录，不重新宣称完整 PSF 的 exact 缺失或全行最大值。

```sh
python3 -B experiments/backends/support/frontend-retained/verify_finite_samples.py
```

## 源码、设置与可获取性

[INVENTORY.json](INVENTORY.json) 给出每个留存文件的原位置、原哈希及摘录方法。本目录的控件 VA、原请求、候选响应、原生小 PSF 和收据为 repository-contained；原 bulk 输出与完整 v2 PSF 为 local-only，没有公共下载地址。v2 每个 query 最近点的原 HEADER 与 VALUE 行逐字摘录，保留原整文件 SHA、总行数和原行索引，不把七行摘录冒充完整运行。旧收据中 absolute path 与 local-only 标签描述取证时位置，当前可获取性以本清单为准。

Spectre 21.1.0.509.isr12，二进制 SHA `72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f`，运行前后身份一致。v1 请求 reltol=1e-10、实际 reltol=1e-11、vabstol=1e-12；v2 请求 reltol=1e-12、实际 reltol=1e-13、vabstol=1e-14、maxstep=5e-11，traponly/conservative。完整有效设置、命令、退出与诊断在各 ANALYSIS 和 EXECUTION。候选核 SHA `642cc6079d39a07fc54870f1d1b2d495dec0a0dbea5dae5a80af06f1ce8c6f1d`，build_revision=null；身份来自冻结源码/构建材料，没有另行独立重建。

constants/reference 保留实际小 PSF 与执行收据，VA SHA `4999a6c71fec89ac2d3943264ef6c2be6d652721b9a0fc415572e42571d0d556` 与 constants/dut.va 相同；复用只覆盖常量输出。旧 IR21 不用作候选前端执行。

## 开发回归与原请求边界

[local/FINAL-IDENTITY.json](local/FINAL-IDENTITY.json) 保存 main 基线与候选源哈希。N20a 基线 v2 测试有十五个缺宏错误和一个环境身份失败，候选 29 项通过；较早 v1 身份期望记录也保留。N10a 基线七方法有两失败和一奇异系统错误；候选 155 项及额外消费者 103 项通过。这些是选定开发回归，没有运行全库或 Rust tests。早期宽选择误写不存在模块产生的导入错误、首次候选失败也保留，未删失败记录。

原 affine 负控仅声明 floating，裁剪后是有效 y=u；新负控明确引用 V(floating)，仍拒绝奇异系统。原 laplace 两个仅声明 unused z 的负控现在作为正控，原 PWL、时刻、2e-9 V 和独立 Decimal ODE 答案保留。固定 main 原测试位于 local/baseline-tests；四个控件的原 VA、两阶段请求、响应和独立合同在 controls。真正引用而欠约束的系统仍拒绝；零乘项、未选中分支、零循环和整组向量不裁剪。独立去掉 unused z 的 main 实验与候选响应一致，简短结果在 local/masking-result.json。

原请求证据在 original-requests，CLI 和输入哈希在 local/REPLAY.json。v4-299 从 M_TWO_PI 未定义推进到 ANSI 端口 line9:5 解析拒绝；两条 core-boundary 的 CLI 在 iabstol options 拒绝，直接编译同源模型仍在 && line49:31 拒绝。没有编辑原输入、checker 或 denominator；不能计为原 70 新增成功。REPLAY 的 working_head 是记录时尚未提交 N10a 的 head，内容哈希与 FINAL-IDENTITY 的最终 e942 身份提供实际绑定。
