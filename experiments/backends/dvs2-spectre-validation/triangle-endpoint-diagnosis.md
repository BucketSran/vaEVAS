# VA07 有向 half-speed 的原 stop 端点诊断

原 stop=3 s 的 half-speed 模型在基线内核返回 `event_resolution`，没有完整波形。
本地候选仅在现有变号包围内保留可证明的精确点根；相同模型、设置与固定 601/607 格
现在均完整执行，未修改的独立任务 checker 均明确判错。该结果是一个开发条件的数值修复，
尚待固定提交的 Standards/Spec 审查与集成；不代表 #70 或一般动态 cross 已解决。

[紧凑收据](triangle-endpoint-results.json)保存输入、内核、adapter、checker 哈希、逐次执行账本
及各格结果。原始输出、源快照、二进制、探针补丁与测试日志保留在本工作区 `runs/d7/`，
可用性为 **local-only**；校验和不是公开下载入口。模型、回归测试与此摘要保存在仓库。

## 固定条件和预算

基线为 `1006c3d59e404cf307ee83c21e93178151257f40`，不依赖 F2 索引改动。
原 benchmark reference 的唯一变换是将 `sign*V(ctl,r)` 改成 `0.5*sign*V(ctl,r)`，
与保存的 wrong-speed 候选逐字节相同。ctl=1、上下限 ±0.5、初值 0、方向 +1；
stop=3、max_step=0.005、ttol=vtol=1e-10，EVAS vabstol=1e-8、reltol=0。
任务 checker 的 wave_atol=1e-6、time_atol=2e-7 保持不动。请求经保存的 CLI/runtime
转发；没有后端独立回显 effective tolerance。Spectre iabstol/method 仍未映射。

原 601 格及预定补充 607 格均由原 adapter 生成，补充格来自独立参考根附近的固定时间，
不由 EVAS 事件时刻生成。共实际启动 11/12 次 bounded candidate/grid 执行，
每次 60 s、16 MiB；内部聚焦单元测试另列，不启动远端或改变任务截止点。
原 harness 的保存工作区只读使用，实际 adapter 源哈希记录在收据中，未修改 harness。

## 证据和原因

先使用真实编译/CLI/kernel/harness 路径建立红反馈：reference 两格可完成；wrong-speed
原 601 格返回 `cannot determine dynamic cross sign at interval end`，607 格明确未运行。
去掉计数累加的缩减模型仍拒绝；删除下限 guard 的单事件对照可完成。
该对照曾计划将 upper 默认值设为 1.5，使首次到达位于 stop；实际 manifest 覆盖为 upper=0.5，
保存的唯一事件约在 t=1。因此这条运行没有检验“无先前翻转、首次在 stop 到达”，不能排除该假设。
这是缩减复现与一个诊断对照，不宣称已经找到全局最小 VA 程序。

| 假设 | 可证伪检查 | 结果 |
| --- | --- | --- |
| 首次根的可消除宽度进入重启历史，令终点跨零 | 记录首根和 stop guard；仅改善首根证书 | 支持：首根精确收缩后原模型两格完成 |
| 无先前事件的普通 stop 到达本身被拒绝 | 原计划单次到达 stop，但 manifest 覆盖导致事件在 t≈1 | 未检验；仅证实删除下限 guard 后该请求完成，任务评分仍 fail |
| 计数或 checker 引发此 backend 拒绝 | 去除计数累加；检查拒绝发生在根隔离器 | 排除：缩减模型在同一数值步骤拒绝 |

首根的二分窗口为 `[0.9999999999990905, 1.0000000000004547]`，
两端 guard 为精确点值 `-4.547473508864641e-13`、`2.2737367544323206e-13`，
整个窗口导数精确为 `[0.5,0.5]`。二分窗口已满足 ttol/64，旧代码直接返回。
历史保留了这段事件时间宽度；随后的区间为
`[1.0000000000004547,3]`，终点 lower guard 为
`[-9.094947017729282e-13,4.547473508864641e-13]`，导数 `[-0.5,-0.5]`。
这个跨零终点不能被当作精确零：原拒绝符合现有保守语义。

严格变号已证明唯一根存在，严格常导数 `d` 给出均值定理根包围
`r ∈ lo - g(lo)/d`。只有向外舍入算术返回位于原包围内的单点时，候选才接受该点。
本例得到 `[1,1]`，不是取代表时刻或清零已有误差。非点结果仍走原二分；
含历史误差的 stop 跨零仍拒绝，非可表示的 1/3 根仍保留宽度。
未改 scheduler、direction、事件身份/次序、历史重启、stop、容差或 checker。

## 原条件结果

| 模型/内核 | 原 601 格 | 预定 607 格 | 两格共同电压差 |
| --- | --- | --- | --- |
| reference / 基线 | 完整；波形/计数通过，采样计时 fail（0.005 s） | 完整；开发判据 pass（计时误差约 1e-7 s） | 0 |
| wrong-speed / 基线 | backend refusal；评分未执行 | 未运行 | 不适用 |
| reference / 候选 | 完整；原 checker pass，计时误差 0 | 完整；原 checker pass，计时误差 0 | 0 |
| wrong-speed / 候选 | 完整；原 checker fail：incorrect count outside event windows | 同样明确 fail | 0 |

reference 原历史计时失败记录保留；候选精确事件使新原格计时通过，没有改写旧记录。
wrong-speed checker 先在计数条件短路，独立任务波形/计时子检查未分别返回结果；
不能将这两项声称为 checker pass。额外手算物理核对给出
`z=0.5t (0≤t≤1)`、`z=1-0.5t (1≤t≤3)`，事件恰为 `t=1,3`，
到达 stop 后 count=2。两格全部样本符合该半速物理答案，电压误差 0。
这些事件与 reference 要求的 `0.5,1.5,2.5` 不同，故真实模型行为应判错。
`t=3` 的到达来自物理推导，不使用会排除 stop 根的 checker.roots 来决定事件数。
两格一致仅支持这两个固定请求，不是一般查询不变性或连续时间资格。

## 验证和身份边界

新增公共路径回归读取原 reference 并进行原 half-speed 变换，使用原 601 格和全部固定设置。
它在保存的基线内核上得到原 `event_resolution` 红结果，在验收内核上通过；
同时核对解析电压、逐样本计数、两个 trigger 身份、顺序及 stop 提交。
Rust 的精确常导数非二分点根测试先红后绿；另一个测试确保非点算术/历史误差没有被清除。
完整 Rust 检查 149 passed、1 既有 ignored。既有动态/历史重定位/事件/采样/生命周期
113 测试通过，初始事件/精度/OR/事件条件/horizon 55 测试通过，新增公共路径 1 通过。
保存的 #70 双向自换向拒绝、初始零离开、终点到达与 Rust 真实 rollback 测试均通过。
显式指定保存 harness 后 checker 11/11，通过含“确定 fail 不能被 inconclusive 覆盖”的校准。
首次 Python 命令错误包含不存在的模块名：113 个实际测试通过，另有 1 个导入错误；
修正后的完整命令 113/113，通过日志另存，原错误没有删除。

四个候选验收 grid 绑定同一个 `d3abc8612956f75ae329ba10ac4ad0b13df1ebfc5313e02cba10cde157c7f329`
内核和保存源码。之后仅增加一个 `cfg(test)` 测试并格式化测试行，最终重建 debug 内核
SHA 为 `48ad82b0948efc9e03a6d7e5cba11c94fa43a233169affbe1ce8b9f2e3329ac5`。
验收快照与最终 `dynamic_roots.rs` 的全部 production 字节相同，SHA 为
`0be767ecb02a0c248e9d1403599bd66d1bc5f59d5847721c5a29194cb9aa91a6`；其他 production 文件相同。
最终二进制没有重新执行四个格，不能将验收二进制哈希替换成最终哈希。
两个构建及源快照都保留供审查。无性能测量或速度声明。

相关能力、更新记录和 benchmark 候选已链接此报告；CMP 的独立冻结快照另行保留其原始版本身份。
本报告保留局部候选证据；双模型审查与集成完成前，D7 状态仍为待审候选。
