# 开源电路仿真器 Verilog-A 模拟事件语义 + Spectre SCS 网表联合支持调研

日期：2026-10-17
背景：vaEVAS（GitHub BucketSran/vaEVAS issue #181）评估自研 Verilog-A 内核经原生 C++ 插件接入 Xyce，遇到 transition/cross 与默认 LTE 步长控制衔接失败。闭源 Spectre 同时支持 (a) Verilog-A 模拟事件语义（cross/above/timer/transition/initial_step/final_step/discontinuity，含混合事件/连续求解）与 (b) 原生读取 SCS 网表。本报告调查开源生态是否存在同等"联合方案"。

证据等级标注：
- 【官方】= 官方文档/官方仓库明确声明
- 【源码】= 源码中存在实现但无官方声明
- 【社区】= 社区报告，未证实

---

## 一、结论摘要（先给答案）

**现状没有任何单一开源方案同时满足 (a) Verilog-A 模拟事件语义 和 (b) 直接读 Spectre SCS 网表。**

- (a) 缺口是硬缺口：两大开源 VA 编译路径（Xyce/ADMS、OpenVAF/OSDI）官方文档均明确不支持 cross/timer/transition 等模拟事件构造，目标是紧凑器件模型而非行为级建模。
- (b) 有可用的开源转换/读取路径：Sandia 的 XDM 转换器（Spectre→Xyce，官方）和 ChipFlow 的 VAJAX（Spectre↔ngspice 转换，开源）；另有实验性 Rust 仿真器 Melange 和 JAX 仿真器 VAJAX 声称能解析 Spectre 网格子集，但均早期阶段且不含事件语义。
- vaEVAS 在 Xyce 上遇到的 transition/cross 衔接失败不是实现 bug，而是 Xyce/ADMS 官方声明的功能边界——事件语义必须由自研内核自带，并自己解决与求解器步长控制的衔接（breakpoint/中断步长机制）。

可行组合路径（详见第四节）：
1. **Xyce + XDM（SCS→Xyce 转换）+ 自研 VA 内核插件**：缺口 = 事件与 Xyce 时间步进控制的接口要自建。
2. **ngspice + VAJAX 转换（SCS→ngspice）+ 自研 VA 内核**：同上，且 ngspice 无原生插件接口（OSDI 不支持事件）。
3. **关注 OpenVAF-Reloaded / VACASK 生态**（卢布尔雅那大学，2024–2026 活跃）：仍无 cross/timer 支持，但有社区分支声称在加。

---

## 二、逐项调查详情

### 1. Xyce（Sandia）

**(a) Verilog-A 支持方式与事件构造支持【官方】**

Xyce 通过 ADMS 编译器 + Xyce 提供的 XML 模板（"Xyce/ADMS"）支持 Verilog-A。官方文档 [Xyce/ADMS Users Guide](https://xyce.sandia.gov/documentation-tutorials/xyce-adms-users-guide) 明确：

- 支持的：`ddt`（仅限 contribution 语句）、`ddx`（有限制）、`limexp`、`$limit`（非标准的 Xyce 特有方式）、噪声源（仅 contribution）、analog functions、`@(initial_step)`（仅无分析参数形式，且每个 DC Newton 迭代都执行，不能用于一次性初始化）、ADMS 扩展块 `@(initial_model)`/`@(initial_instance)`。
- **明确不支持**：
  - "Monitored events (LRM 5.10.3) and named events (LRM 5.10.4) are not supported" —— 即 **cross()、timer()、above() 等被监视事件全部不支持**；事件的 OR 运算符也不支持；带分析参数的 `@(initial_step("type"))` 会使 ADMS 直接报错退出。
  - **transition() 明确列为不支持**，同列表还包括 `idt`、`absdelay`、`idtmod`、`slew`、`last_crossing`。
  - `discontinuity()`：指南中完全未提及（指南声明"只实现了前节列出的函数"，故视为不支持）。
- 其他重要限制：不支持数组、`genvar`、向量 branch、switch branch、间接 contribution、层次化模块例化、`paramset`、electrical/thermal 之外的 discipline；端口电流 `I(<port>)` 生成错误代码导致不收敛；`final_step` 未列为支持。

补充【官方】：MOS-AK 2022 报告 [Verley_Xyce_MOS-AK_Q1_2022.pdf](https://mos-ak.org/panel_Q1_2022/presentations/Verley_Xyce_MOS-AK_Q1_2022.pdf) 指出 Xyce/ADMS 需要特殊构建、多数模型需手工修改、表达式支持受限、"缺失模拟行为"。Xyce 用户邮件列表（[Google Groups](https://groups.google.com/g/xyce-users/c/iDW-mihHIGI)）确认它"只能处理实现 SPICE 原语的 Verilog-A，不支持子电路等层次结构"。

**(b) 网表格式【官方】**

Xyce 主程序读取 SPICE3 格式网表；无内置 Spectre reader。SCS 路径靠独立的 **XDM 网表转换器**：
- [Xyce/XDM GitHub 仓库](https://github.com/Xyce/XDM)（Perl）：官方描述"convert PSPICE and HSPICE netlists into Xyce format"；仓库实际包含 Spectre 翻译模块。
- [XDM Netlist Translator User Guide 2.6 (PDF)](https://xyce.sandia.gov/files/xyce/XDM_User_Guide_2.6.pdf)【官方】："XDM currently supports translation from PSpice, HSPICE, and **Spectre** netlists into Xyce netlists"，并注明 PSpice 翻译最成熟（暗示 Spectre 方向成熟度较低）。更新版 v2.7 见 [OSTI](https://www.osti.gov/biblio/2430544)。
- Keiter MOS-AK 2022 报告（[PDF](https://www.mos-ak.org/silicon_valley_2022/presentations/Keiter_Xyce_AWG_MOS-AK_Dec_7_2022.pdf)）：XDM 为支持 GF 12/14nm PDK 用现代解析器重写过，可转换 HSPICE/Spectre 格式。

**结论：Xyce 满足 (b)（经 XDM 离线转换，非原生 reader），不满足 (a)（官方明确不支持事件语义）。**

### 2. ngspice + OSDI/OpenVAF

**(a) OpenVAF 事件语义支持【官方】**

- [OpenVAF Verilog-A Standard Compliance](https://openvaf.semimod.de/docs/details/verilog-a-standard)（官方文档，页面标注"not yet fully complete"）：明确 "OpenVAF currently supports the **initial_step and final_step** events for initialization of code"，且这两个事件在每个迭代都执行；**其余所有事件（cross/timer/above/命名事件等）无法解析**。
- [OpenVAF Language Support（man.sr.ht）](https://man.sr.ht/~dspom/openvaf_doc/language_support.md)【官方】："OpenVAF follows the Verilog-AMS LRM 2.4.0... The current goal is to support only the analog (Verilog-A) subset"，且以紧凑器件模型（HiSIM-HV、PSP、BSIM 系列等，见 [GitHub README](https://github.com/pascalkuthe/OpenVAF) 测试列表）为目标。
- transition()/above() 这类滤波器：官方合规页未见声明支持；因依赖事件驱动的步长控制（OSDI API 无此机制），实际编译报错不支持。【社区】多个使用报告确认 transition/cross 报错；未见任何官方反例。
- 时效性：原 OpenVAF 自 2023 年底停止维护（最后 release 23.5.0），由社区分支 [OpenVAF/OpenVAF-Reloaded](https://github.com/OpenVAF/OpenVAF-Reloaded)（Árpád Bűrmen，2024 起，[官方下载页](https://openvaf.semimod.de/download/) 已指明迁移）继续开发，输出 OSDI 0.3 动态库。截至调查日（2026-10）**未发现 Reloaded 增加事件/cross/timer 支持的官方声明**。【社区】有 LinkedIn 帖（Shivaram Mysore，2025 末）提及某衍生分支"修复 Reloaded bug 并新增完整 cross 与 laplace 支持"——未证实，需跟踪。

**(b) ngspice 网表格式【官方】**

ngspice 只读 SPICE 系列网表，无 SCS reader。官方 OSDI 页面：[ngspice Verilog-A with OSDI/OpenVAF](https://ngspice.sourceforge.io/osdi.html)（`pre_osdi` 加载、`N` 前缀实例化）。

**结论：ngspice+OpenVAF 满足"读 VA 模型"但不满足 (a) 事件语义（官方明确），也不满足 (b)（SPICE-only）。**

### 3. ADMS 本体

ADMS 是"编译器生成器"：用 XML 模板定义目标后端，为各仿真器生成 C 代码。它解析 VA 源码，但**事件语义能否落地完全取决于后端模板**——Xyce 模板不支持（见第 1 项）【官方】。ADMS 项目本身长期低维护，无任何后端声明支持 cross/timer/transition 的混合事件/连续求解。【社区】

### 4. Verilog-Ae（OpenVAF 同团队）

**不是仿真器**。Verilog-AE 是面向**紧凑模型参数提取**的 VA 编译器：把 VA 方程编译为 Python 可调用函数，供 DMT（[Device Modeling Toolkit](https://dmt.semimod.de)）拟合参数用。论文：[VerilogAE: An Open Source Verilog-A Compiler for Compact Model Parameter Extraction](https://www.researchgate.net/publication/344819581_VerilogAE_An_Open_Source_Verilog-A_Compiler_for_Compact_Model_Parameter_Extraction)（Kuthe & Müller, IEEE JEDS）【官方】。与电路仿真无关，不适用。

### 5. Qucs-S 及其他 ngspice 前端

Qucs-S 使用的仿真内核是 ngspice，VA 支持即 OSDI 路径（见 [qucs_s issue #197](https://github.com/ra3xdh/qucs_s/issues/197)【源码/官方 issue】），继承 OpenVAF 的全部事件语义缺口；网表是 SPICE 系，不读 SCS。

### 6. 其他候选

- **VAJAX（ChipFlow）**：[github.com/ChipFlow/vajax](https://github.com/ChipFlow/vajax)【官方 README】——基于 JAX 的 GPU 加速开源模拟仿真器，设备模型用 OpenVAF 编译；提供 `vajax convert input.scs ...` 在 ngspice/HSPICE/LTspice/Spectre 格式间转换（[for_spectre_users.md](https://github.com/ChipFlow/vajax/blob/main/docs/for_spectre_users.md)）。因模型走 OpenVAF，**事件语义同 OpenVAF 缺口**；项目早期，分析类型覆盖有限（文档中有 Status 表）。
- **Melange**：[github.com/pascalkuthe/melange](https://github.com/pascalkuthe/melange)【官方 README】——OpenVAF 作者的实验性 Rust 仿真器，README 明言 "can parse a subset of the **spectre netlist format**"。这是开源界少见的"直接解析 SCS"的实现，但明确 experimental、子集、无事件语义、基本停更。
- **VACASK**：[codeberg.org/arpadbuermen/VACASK](https://codeberg.org/arpadbuermen/VACASK)【官方】——卢布尔雅那大学 Bűrmen 团队的 "Verilog-A Circuit Analysis Kernel"（模拟仿真器+VA 器件库），用 OpenVAF-Reloaded 经 OSDI 编译模型。其文档自述某些所需特性"OpenVAF-Reloaded 甚至 Verilog-A 标准本身不可用"，说明事件语义仍是缺口；网表为自有格式，非 SCS。值得跟踪。
- **OpenModelica / CppSim**：无 Verilog-A 前端（OpenModelica 是 Modelica；CppSim 无 VA/SCS 支持）。未发现任何声明同时支持 SCS 与 VA 事件语义的项目。【社区/排除性检索】

### 7. SCS→SPICE 网表转换路径

| 工具 | 方向 | 性质 | 可靠性边界 |
|---|---|---|---|
| [XDM](https://github.com/Xyce/XDM) | Spectre/HSPICE/PSpice → Xyce | 开源、Sandia 官方 | 官方称 PSpice 最成熟；Spectre 方向成熟度次之，分析语句映射见 [User Guide 2.6](https://xyce.sandia.gov/files/xyce/XDM_User_Guide_2.6.pdf)【官方】 |
| [VAJAX convert](https://github.com/ChipFlow/vajax/blob/main/docs/for_spectre_users.md) | Spectre↔ngspice/HSPICE/LTspice | 开源 | 新项目、覆盖有限，边界未系统文档化【官方 README，细节缺】 |
| Cadence `spp` | SPICE↔Spectre | **闭源**（随 Spectre 发货） | 不属于开源路径【官方用户手册，[Spectre User Guide PDF](https://web.eecs.utk.edu/~dbouldin/protected/spectreuser.pdf)】 |

通用风险：SCS 中的分析语句（tran 参数如 strobecount、参数扫描、MDL/PSF 输出、analogLib 行为源、CDL 差异等）在转换中往往丢失或需手改；两转换器均无完整的逐构造保真承诺。所谓 "ngsconvert" 未找到可靠开源实现【社区，未证实其存在】。

---

## 三、证据等级总表

| 结论 | 等级 |
|---|---|
| Xyce/ADMS 不支持 cross/timer/transition/monitored+named events | 官方（Users Guide） |
| Xyce 主程序无 SCS reader，XDM 提供 Spectre→Xyce 转换 | 官方 |
| OpenVAF 仅支持 initial_step/final_step，其余事件不可解析 | 官方 |
| ngspice 无 SCS reader | 官方（文档仅 SPICE 格式） |
| VAJAX 可转换/读取 Spectre 网表 | 官方 README（覆盖面细节缺） |
| Melange 解析 Spectre 网格子集、实验性 | 官方 README |
| OpenVAF 衍生分支加 cross/laplace | 社区（未证实） |
| XDM Spectre 方向转换保真度低于 PSpice 方向 | 官方暗示 + 社区经验 |

---

## 四、对 vaEVAS #181 的含义（值得试验的路径）

1. **transition/cross 失败是结构性缺口，不是调参问题。** Xyce/ADMS 官方即不支持这些构造；自研内核走原生 C++ 插件是唯一在 Xyce 上获得事件语义的路。关键是自研内核必须自带事件状态机，并主动向 Xyce 求解器注册时间断点（breakpoint / 步长截断）——即复刻 Spectre 中 cross/timer 与 LTE 控制的联动。可在 Xyce 源码 DevicePKG 中查找现有离散设备（如 SW/PWL 源）如何上报 breakpoint（【源码】级工作，本次未逐行核验）。
2. **(b) 用 XDM 补齐即可**：SCS→Xyce 离线转换是官方路径，不必自研 SCS reader；先用 XDM 跑通自家 SCS 测试集，统计丢失的构造，得到明确缺口清单。
3. **备选：VAJAX convert（SCS→ngspice）+ 自研内核接 ngspice**——但 ngspice 缺少像 Xyce 原生插件那样的设备接口（OSDI 无事件 API），改造成本可能更高，仅作对照。
4. **跟踪项**：OpenVAF-Reloaded / VACASK（fides.fe.uni-lj.si/openvaf）与传闻中的 cross/laplace 分支；若其事件支持落地，可评估把自研内核的事件层对齐其语义而非自造。
5. Melange 的 Spectre 解析子集可作为自研 SCS reader 的语法参考（Rust，代码量小）。

---

## 五、关键来源清单

1. Xyce/ADMS Users Guide — https://xyce.sandia.gov/documentation-tutorials/xyce-adms-users-guide
2. XDM Netlist Translator User Guide 2.6 — https://xyce.sandia.gov/files/xyce/XDM_User_Guide_2.6.pdf ；代码 https://github.com/Xyce/XDM
3. OpenVAF Standard Compliance — https://openvaf.semimod.de/docs/details/verilog-a-standard ；Language Support — https://man.sr.ht/~dspom/openvaf_doc/language_support.md
4. OpenVAF-Reloaded — https://github.com/OpenVAF/OpenVAF-Reloaded ；VACASK — https://codeberg.org/arpadbuermen/VACASK
5. VAJAX — https://github.com/ChipFlow/vajax ；Melange — https://github.com/pascalkuthe/melange
6. ngspice OSDI — https://ngspice.sourceforge.io/osdi.html ；Verley MOS-AK 2022 — https://mos-ak.org/panel_Q1_2022/presentations/Verley_Xyce_MOS-AK_Q1_2022.pdf
