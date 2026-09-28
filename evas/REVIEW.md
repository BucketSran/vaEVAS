# EVAS 重构 review 记录

## 检查点 2：参数契约与结构化支路身份

2026-09-28，基于 `f530c8d`（PR #2），本批实现已完成并停在人工 review 点。
当前版本 `evas-affine-0.2.0` / IR v2。下面的检查点 1 保留当时的结果与限制；
其中 LOW 和 WATCH 在本批当前支持范围内已落实，不再列为本阶段待实现项。

本批阅读顺序与设计决策：

1. [参数契约](DESIGN.md#参数绑定契约)与[边界测试](tests/test_contracts.py)：
   默认表达式始终检查结构，但只求覆盖后的有效依赖图。无覆盖时的除零、溢出、循环，
   与被覆盖后的有效值分开验证；声明顺序和实例缓存不能改变结果。
   超大整数覆盖值原先会泄漏 `OverflowError`，现统一返回 `CompileError`。
2. [Python IR](src/evas/ir.py)与[Rust IR](rust_core/src/ir.rs)：
   支路身份显式包含实例、本地正负端点和贡献种类。实例来源与身份必须一致；
   当前只有电压贡献，未来命名支路、电流贡献、层次实例仍需另行设计。
3. [Rust 组装](rust_core/src/assembly.rs)：独立检查规范方向、地绑定、同一本地节点的
   一致绑定，以及不同本地支路不能因端口连接而被合并的现有约束。
4. [v1 → v2 迁移](DESIGN.md#v1--v2-迁移)：版本在贡献解码前检查；旧格式需要重新编译，
   不能只修改版本号。版本预检不允许重复 JSON 字段绕过完整解码。

### 本阶段验证

- **33 项 unittest 方法全部通过**（原 19 项 + 新增 14 项，1.032 秒）。
  新测试覆盖有效依赖、被覆盖的算术/循环、始终非法的结构、无效覆盖值、实例隔离、
  手写 IR 的贡献累加、反向贡献、隐式/显式地、身份冲突、别名与协议版本拒绝。
- 锁定依赖的离线 Rust 构建、warnings-as-errors 的 all-targets 检查和格式检查通过。
- 重新执行 31 条件中的静态支持部分：**9 条件 × 两档 = 18 组，396,018 个点**，
  全部满足原独立判据；另 22 个条件仍在编译阶段明确拒绝。
- 18 份波形 CSV 与检查点 1 的归档逐字节相同；全部分析记录和 22 条拒绝诊断相同。
  回放所引用的 20 个验证源码/独立判据文件 SHA-256 与原报告一致。
- 求解器、线性代数和语法解析文件未修改；本轮没有开展 thu-sui 四后端重测。

复现仍使用 [README 的构建、测试和回放命令](README.md#当前切片的运行和检查)，
回放输出必须选一个新目录。

| 本地证据 | 身份 |
| --- | --- |
| 新回放目录（Git 忽略） | `runs/evas-static-contracts-v2/static-1/` |
| `report.json` SHA-256 | `f8985b6f7c1f3b2eb95c5d4e26c2c0f110a74fb782a701b203b32da0bb359c71` |
| 内核 SHA-256 | `8797d352567a0e5a3b63e46611b7d877953a706d0d4eebfdd62f933e0e8c29cb` |
| 对照归档 | `runs/evas-refactor-checkpoint-1/static-1/` |

本批完成实现者自查与上述验证，未重新进行检查点 1 的两路独立 agent review。
待人工 review 的重点是参数覆盖契约、支路身份字段和显式版本迁移边界。
时间推进、事件状态及动态算子留在下一阶段；正式 DVS 资格仍为 I。

## 历史：检查点 1

2026-09-28。功能开发已停在“原始 VA → 贡献 IR → Rust 静态线性求解”的完整切片。
独立代码和架构 review 已完成，综合结论为 **COMMENT**：当前切片没有发现阻断项，
保留一项参数契约说明问题与一项后续架构扩展提醒。初次 review 后功能开发停在此处。

随后按讨论完成语法/绑定、组装/求解的文件拆分，并通过下述小范围 smoke。
拆分前内核保存在 `cf221b1`；本次只调整模块职责，不扩展语言或改变参数契约。

## 本批交付与 review 阅读顺序

1. [设计与支持范围](DESIGN.md)：本批做什么、拒绝什么、后续哪些约束尚未实现。
2. [Python IR](src/evas/ir.py) / [Rust IR](rust_core/src/ir.rs)：贡献身份、方向、来源、版本与结果格式。
3. [方程组装](rust_core/src/assembly.rs) / [工作点与残差](rust_core/src/solver.rs) / [线性代数](rust_core/src/linear.rs)：校验、贡献累加、求解与验收的边界。
4. [语法解析](src/evas/syntax.py) / [语义绑定](src/evas/frontend.py)：语法树与参数绑定、节点隔离、仿射 lowering 的边界。
5. [行为回归](tests/test_affine.py)和[原测试回放器](tests/run_static_regression.py)：从接口验证，不调用旧 EVAS。

这是新内核的第一个可运行切片，尚未替换旧 EVAS，也没有修改旧部署镜像或旧仓库。
初次 review 时尚未提交；现在按用户要求保存 Git 检查点并提交草案 PR。

## 文件拆分后的 smoke（2026-09-28）

- `frontend.py` 从 332 行变为 144 行，解析逻辑移至 197 行的 `syntax.py`。
- `solver.rs` 从 241 行变为 123 行，校验和组装移至 148 行的 `assembly.rs`。
- Python 原有 12 项顶层定义/赋值的 AST 对照一致；Rust `solve` 函数及其注释逐字节一致。
- 锁定依赖的离线 Rust 构建通过；**19 项 unittest 方法通过**（0.800 秒）。
- 31 个现有条件仅做编译对照：9 个支持条件的完整 IR、22 个拒绝条件的诊断文本均与拆分前一致。
- `static_sum.json` 的 CLI `compile` / `solve` 输出逐字节一致，三个输出电压为
  `0.225`、`1.825`、`-0.325` V（浮点表示允许末位舍入）。
- `RUSTFLAGS='-D warnings' cargo check --locked --offline --all-targets` 和 `cargo fmt -- --check` 通过。

拆分前后对照保存在 Git 忽略的 `runs/evas-module-split-smoke/`。
`before.json` 与 `after.json` 的 SHA-256 相同：
`2d2982d6f8b6e302e40d21986b1eb4f6f49af69994ed0ce8325e8d137eb42d98`。
本轮没有重跑下面的 396,018 点回放或 thu-sui 四后端实验；下面的全量静态回放与独立 review
均属于拆分前检查点，不能解释为拆分后的再次全量认证。

## 已取得的验证证据

- **19 项 unittest 方法通过**，包含贡献顺序的全部六种排列、合并形式、反向支路、
  参数覆盖、非零参考、自反馈、跨实例反馈、实例次序、私有内部节点、并联约束、
  奇异/冲突方程、30 个固定种子的解析反馈对照及明确拒绝的错误输入。
- Rust 构建通过；`RUSTFLAGS='-D warnings' cargo check --all-targets` 通过；格式检查通过。
- Clippy 在当前 Rust 工具链未安装，本轮未取得 Clippy 检查结果。
- 对已有 86 个验证/实验文件核对 SHA-256，全部保持不变。

从原 31 个条件读取原 VA、原输入和原独立数学判据。当前 9 个条件属于已实现范围，
每个按 1 ns / 0.1 ns 两个网格独立求解，共 **18 组、396,018 个静态点**。

| 原条件类别 | 条件数 | 两档组合 | 最大解析输出误差 | 最大支路残差 |
| --- | ---: | ---: | ---: | ---: |
| V2 差分/共模/参考/供电 | 4 | 8/8 满足原判据 | 4.44e-16 V | 3.33e-16 V |
| V7 线性反馈/实例次序/输入缩放 | 3 | 6/6 满足原判据 | 1.11e-16 V | 5.55e-17 V |
| S1 多贡献/参数覆盖 | 2 | 4/4 满足原判据 | 1.11e-16 V | 0 V |

其余 **22 个条件编译时明确拒绝**，没有伪造输出或回退到旧实现。
这是静态关系回归，不能与旧完整执行器的 31 条总分直接排名，也不是瞬态仿真达标率。
动态积分、事件历史和非线性反馈尚未实现，正式 DVS 资格仍为 I。

## 本地复现身份

本轮在本机运行，未在 thu-sui 部署新内核。
环境：Python 3.14.6，rustc 1.95.0，Apple Silicon；使用锁定的 Cargo 依赖。

- 执行器：`evas-affine-0.1.0`。
- 原始回放目录：`runs/evas-refactor-checkpoint-1/static-1/`（Git 忽略）。
- `report.json` SHA-256：`5187188d7cf9b1c30022b5bb7121c971c891ab2337788c7fcbaedcae36baf487`。
- 内核二进制 SHA-256：`3a2221e90b7b82c35ba6c640e6c5945eb369fc76807f9d0ed50c63798b0ae7bb`。
- 报告记录逐文件源代码/独立判据/VA 的 SHA-256；`SHA256.json` 校验每份 IR、条件、波形和报告。
- 运行命令见 [README](README.md#当前切片的运行和检查)。

## Review 结果

两路独立 agent 只读评审，代码保持冻结。代码 review 覆盖 22 个文件，
返回 **COMMENT**，CRITICAL/HIGH/MEDIUM 均为 0，LOW 为 1；
架构 review 返回 **WATCH**，没有当前范围内的架构阻断项。
按两路意见综合，本检查点为 **COMMENT**，不标记为完整仿真器的发布验收。

### LOW：参数覆盖与默认表达式检查的契约需要明确

历史位置：[参数求值](https://github.com/BucketSran/vaEVAS/blob/f530c8d/evas/src/evas/frontend.py#L97)、[默认表达式检查](https://github.com/BucketSran/vaEVAS/blob/f530c8d/evas/src/evas/frontend.py#L117)。
当前实现检查所有默认表达式中的未知名字和电压引用；求值时，实例覆盖值优先。
因此 `parameter real a=1/0;` 在实例提供 `a=2` 时能够编译；全部被覆盖的默认循环也可被接收。
现有注释“即使覆盖也验证默认值”没有说明这种区别，测试也未固定这一边界。

**这不是已证实的 Verilog-A 语义错误。** review 初稿曾建议忽略覆盖先求值所有默认值，
经追问后已撤回该建议并将发现降为 LOW：例如 `a=0; b=1/a;`，实例覆盖 `a=2` 后，
当前有效绑定得到 `b=0.5`；强制先求所有原始默认值会错误拒绝这种有效绑定。

下一步应明确“覆盖后的有效参数依赖图必须有限且无环”等实际契约，
补充依赖覆盖、无效默认值被覆盖、循环被覆盖的对照测试，再对齐注释。
本次没有为关闭 review 而改变参数语义，也没有据此宣布符合完整 LRM。

### WATCH：下一类语义扩展前，应结构化支路身份

历史位置：[IR](https://github.com/BucketSran/vaEVAS/blob/f530c8d/evas/src/evas/ir.py)、[前端绑定](https://github.com/BucketSran/vaEVAS/blob/f530c8d/evas/src/evas/frontend.py#L133)、
[Rust 汇总](https://github.com/BucketSran/vaEVAS/blob/f530c8d/evas/rust_core/src/assembly.rs#L78)。
v1 用本地节点对生成字符串，Rust 通过 `(实例, 支路字符串)` 归并贡献。
当前语法限制和回归能保护这一约定，评审认为它不阻断本批静态仿射切片。
加入命名支路、电流贡献或层次结构前，应把本地端点、贡献种类与身份改为结构化字段，
明确 IR 版本迁移，避免后续语义依赖字符串格式。

### 停止点与后续范围

当前完整通路、失败行为和测试已可独立复现，适合在此讨论接口与支持范围。
本轮不继续迁移事件、动态算子和非线性求解，不启动全量重写或性能优化。
下一批开始前，先处理上述参数契约及 IR 身份的具体设计决策。
