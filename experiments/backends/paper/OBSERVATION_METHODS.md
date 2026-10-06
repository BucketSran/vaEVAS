# 局部观察请求与资格准备

状态：本地静态准备；没有安装版工具 preflight、后端编译或实际运行。
协调者先冻结新 deck，再在已有授权计数内进行小型 preflight。未取得有效证据的
项目保持 unknown/I；不能把全部默认 I 的矩阵视为 A1 交付完成。

## 断点请求

ngspice/Gnucap deck 的 `Vpaper_observer` 只接独立 `paper_observer` 节点与 ground。
DUT VA、真实层级与输入源保持原样，辅助节点不进入 DUT 绑定或评分端口。
理想源在规定窗口点与中心安排角点，以触发求解时间请求；这是额外观察电路，
仍会影响共同积分步序列。不得声称对数值积分轨迹完全没有影响。
全局 200 ps 最大步长不变。局部网格额外细分一次，合并距离关键中心不到 3 fs
的普通网格点，优先保留明确中心。合并后逐窗口最大间隔仍须本地校验 <=20 ps。
每个请求有稳定 request_id；请求与实际 raw 行的关联要由后续证据建立。

[ngspice VSRCaccept 源码](https://raw.githubusercontent.com/ngspice/ngspice/master/src/spicelib/devices/vsrc/vsrcacct.c)
的 PWL 分支在接受步匹配当前源角点时，调用 CKTsetBreak 登记下一个角点。
这是机制依据，不能代替安装版本源码/构建映射与 raw 输出核验。
[官方控制语言教程](https://ngspice.sourceforge.io/ngspice-control-language-tutorial.html)
说明 wrdata 导出 plot 中的向量。此 deck 不调用 linearize；后续须证明 plot 保存
的是该版本接受步，而非默认重采样，并核验 time 与所有输出向量长度和来源。

[Gnucap 官方镜像 PWL 源码](https://raw.githubusercontent.com/gnucap/gnucap/develop/bm/bm_pwl.cc)
的 tr_review 使用下一个 PWL 表点的 min_event；检索时向前加 2*dtmin，
deck 请求 dtmin=1fs，普通点距关键中心不到 3fs 时合并。
安装版的 dtmin 生效读回、时间量化和紧邻点合并规则仍必须实际核验。
[官方 transient 文档](https://gnucap.org/dokuwiki/doku.php/gnucap:manual:commands:transient)
描述 trace alltime 显示所有接受的内部步。deck 明确请求该选项；语法与版本对应
仍需安装版日志、源码映射和 raw 输出检查。禁止把 rejected steps 用作原生值。
以上网页在 2026-10-07 核对；网页分支不是安装版本身份证明。

## 预算与 preflight 闸门

规划行数为 2*(全局 200ps 区间数 + 局部断点数 + 1)，每列按 32 byte 估计。
估算须低于文件上限的 80%，并在 condition 的 256 MiB 内。
这是规划余量；无法约束自适应步数、编译产物或日志。实际进程文件上限仍为
32 MiB，90 s、4 GiB、CPU1、零自动重试均不变。真实 size/间隔/中心缺口失败
须保留，不能在看到结果后放宽判据。协调者须先核验每条件总目录 256 MiB。

优先用已冻结事件条件与 wrap 条件做小型 preflight。保存完整 tool/version/image
身份、source/deck/request manifest、命令、日志与 raw 波形。核验辅助节点的独立
拓扑、所有规定窗口的实际最大间隔、每个中心的请求到 raw 行映射、t=0 settled
初始来源、实际文件/目录大小。未满足以上项目，不进入完整 12 条件 lane。
不能重复运行已占用条件来隐藏失败或绕过启动分母。

## 资格证据方法

实际后端资格由独立审查入口给出；适配器不自动签发资格。每个 role 的 method
必须指向带推导与原始证据的报告，报告另绑定本次 source/deck/tool/raw 身份。
artifact hash 只确认内容未变，不证明报告科学结论正确。不存在通用“任意文件
哈希即证书”的实际执行路径；runner 初始 origins 全为 unknown，不提供误差界。

- time/export voltage：核对安装版内部浮点与导出格式，保留原始数值/字节及实际
  导出设置。推导十进制序列化舍入界、单位换算界；插值另给覆盖整个括定区间的
  独立余项界。导出设置、密集网格或 solver tolerance 本身都不是误差界。
- inputs：单独绑定真实输入源与刺激字节，给出输入方程/插值/序列化和时刻误差
  的保守推导，必要时保存原生输入节点证据。输出 50uV 界不能代替输入 10uV 界。
- native_initial/counters/phase：用安装版事件、接受步与导出顺序证明 t=0 在
  initial_step settled 后，以及后续保存原生状态。实际接受日志/内部 raw 与导出
  逐行对应；不能以解析 DUT 答案或 counter 数值吻合代替来源证明。
- boundary_cohort：给出请求 ID、卡片名义时间、raw 行号与证明的 serialization_error_s。
  仅这一界内的已证请求行可成为中心诊断，普通邻近点和人工插值不可冒充。
- EVAS：保存 raw-response.json 与 IR/runtime/kernel 身份，核验 response times 与
  requests 的真实关系。stateless working-point 分支与 transient 接受步分支分别
  说明来源；accepted_steps=0 本身不证明插值，也不证明 native_initial settled。

A0 负责实际误差方法与 checker 资格审查。此文与静态 fixture 不构成任何后端
证书；安装语义、真实误差界和原始接受记录尚未取证。
