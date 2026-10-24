"""Verilog-A capability nodes.

Compared scores are transcribed from evas/docs/COMPARISON.md sections 1–5.
Waiting rows are the written gaps in evas/validation/paper/COVERAGE.md
(“还缺哪些测试和验收”) plus above / last_crossing from PROTOCOL.md.
Their review status is pending. Issues and old README ideas are not imported.
"""

CHAPTERS = (
    "语言",
    "静态电压传递",
    "参考与供电",
    "阈值、迟滞、启动",
    "采样、保持、复位",
    "延迟、边沿、周期",
    "连续动态与相位",
    "组合、反馈、实例",
)

BACKENDS = ("spectre", "ngspice", "gnucap", "evas")


def compared(id, title, chapter, label, spectre, ngspice, gnucap, evas, depends=()):
    return {
        "id": id,
        "title": title,
        "chapter": chapter,
        "label": label,
        "status": "compared",
        "depends_on": list(depends),
        "review": "recorded",
        "evidence": "evas/docs/COMPARISON.md#支持矩阵",
        "results": {
            "spectre": spectre,
            "ngspice": ngspice,
            "gnucap": gnucap,
            "evas": evas,
        },
    }


def waiting(id, title, chapter, gap, depends=()):
    return {
        "id": id,
        "title": title,
        "chapter": chapter,
        "label": title,
        "status": "waiting",
        "depends_on": list(depends),
        "review": "pending",
        "evidence": "evas/validation/paper/COVERAGE.md#remaining-coverage",
        "gap": gap,
    }


Q3 = "✓ Q3"

NODES = [
    compared("macro-include", "宏与 include", "语言", "宏与 include（含实例）", Q3, "层次语法编译失败", Q3, Q3),
    compared("parameters", "参数", "语言", "参数", Q3, "层次语法编译失败", Q3, Q3),
    compared("conditions", "条件与逻辑表达式", "语言", "条件与逻辑表达式", Q3, Q3, Q3, Q3),
    compared("case", "case 分支", "语言", "case 分支", Q3, Q3, Q3, Q3),
    compared("sequential-assign", "顺序赋值", "语言", "顺序赋值", Q3, Q3, Q3, Q3),
    compared("user-function", "用户函数", "语言", "用户函数", Q3, Q3, Q3, Q3),
    compared("static-loop", "静态循环", "语言", "静态循环", Q3, Q3, "编译失败", Q3),
    compared("array-static-index", "变量数组：静态下标", "语言", "变量数组：静态下标", Q3, Q3, "编译失败", Q3),
    compared("electrical-vector", "电气向量", "语言", "电气向量", Q3, Q3, "编译失败", Q3),
    compared("hierarchy", "模块层次", "语言", "模块层次", Q3, "编译失败", Q3, Q3),
    compared("sin", "sin", "语言", "sin", Q3, Q3, Q3, Q3),
    compared("cos", "cos", "语言", "cos", Q3, Q3, Q3, Q3),
    compared("exp", "exp", "语言", "exp", Q3, Q3, Q3, Q3),
    compared("ln", "ln", "语言", "ln", Q3, "初始化失败", Q3, Q3),
    compared("sqrt", "sqrt", "语言", "sqrt", Q3, "初始化失败", Q3, Q3),
    compared("pow-cube", "pow：三次幂", "语言", "pow：三次幂", Q3, Q3, Q3, Q3),
    compared("pow-half", "pow：半次幂", "语言", "pow：半次幂", Q3, Q3, Q3, Q3),
    compared("voltage-contribution", "电压访问与贡献", "静态电压传递", "电压访问与贡献", Q3, Q3, Q3, Q3),
    compared("static-voltage-feedback", "静态电压反馈", "静态电压传递", "静态电压反馈", Q3, Q3, Q3, Q3),
    compared("initial-step", "initial_step", "阈值、迟滞、启动", "initial_step：事件状态初始化", Q3, "编译或初始化失败", "编译失败", Q3),
    compared("cross", "cross：斜坡穿越", "阈值、迟滞、启动", "cross：斜坡穿越", Q3, "初始化失败", "漏事件", Q3),
    compared("timer", "固定 timer", "延迟、边沿、周期", "固定 timer", Q3, "初始化失败", Q3, Q3),
    compared("event-or", "事件 OR：采样与复位", "采样、保持、复位", "事件 OR：采样与复位", Q3, "编译失败", "漏事件", Q3),
    compared("transition", "transition：定时非对称沿", "延迟、边沿、周期", "transition：定时非对称沿", Q3, "初始化失败", Q3, Q3),
    compared("absdelay", "固定 absdelay", "延迟、边沿、周期", "固定 absdelay", Q3, "初始化失败", Q3, Q3),
    compared("slew", "固定 slew", "延迟、边沿、周期", "固定 slew", Q3, "编译失败", Q3, Q3),
    compared("idt", "idt：非零初值与正负面积", "连续动态与相位", "idt：非零初值与正负面积", "✓ Q2", Q3, Q3, Q3),
    compared("idtmod", "idtmod：原始相位与环回", "连续动态与相位", "idtmod：原始相位与环回", "环回边界未验收", "环回边界未验收", "编译失败", Q3),
    compared("ddt-time", "ddt：二次时间表达式", "连续动态与相位", "ddt：二次时间表达式", "Q1 误差超限", "误差超限", "✓ Q2", Q3),
    compared("ddt-input", "ddt：电压斜坡平方", "连续动态与相位", "ddt：电压斜坡平方", "✓ Q2", "误差超限", "✓ Q2", Q3),
    compared("laplace-nd", "一阶 laplace_nd", "连续动态与相位", "一阶 laplace_nd", Q3, Q3, "非零初态错误", Q3),
    compared("laplace-np", "一阶 laplace_np", "连续动态与相位", "一阶 laplace_np", Q3, "编译失败", "误差超限", Q3),
    compared("filter-second-order", "二阶滤波（内部微分）", "连续动态与相位", "二阶滤波（内部微分）", Q3, "Q1 误差超限", "误差超限", Q3),
    compared("sample-hold-timer", "采样保持：定时", "采样、保持、复位", "采样保持：定时", Q3, "初始化失败", Q3, Q3, ("timer",)),
    compared("sample-hold-cross", "采样保持：阈值", "采样、保持、复位", "采样保持：阈值", Q3, "初始化失败", "漏事件", Q3, ("cross",)),
    compared("sample-reset-edge", "采样、复位与输出边沿", "采样、保持、复位", "采样、复位与输出边沿", Q3, "编译失败", "漏事件", Q3, ("transition",)),
    compared("hysteresis-edge", "迟滞比较器与边沿", "阈值、迟滞、启动", "迟滞比较器与边沿", Q3, "初始化失败", "误差超限", Q3, ("cross", "transition")),
    compared("sample-integrate-timer", "定时采样→积分：原模型", "组合、反馈、实例", "定时采样→积分：原模型", Q3, "初始化失败", "漏定时事件", Q3, ("timer", "idt")),
    compared("sample-integrate-ordered", "采样→积分：停止边界与非线性", "组合、反馈、实例", "采样→积分：停止边界与非线性", Q3, "初始化失败", "停止边界未达标", Q3, ("idt",)),
    compared("integrator-cascade-reset", "积分级联与复位", "组合、反馈、实例", "积分级联与复位", "复位误差超限", "初始化失败", "误差超限", Q3, ("idt",)),
    compared("nonlinear-filter-feedthrough", "非线性输入与滤波直通项", "连续动态与相位", "非线性输入与滤波直通项", "Q2 误差超限", "Q1/Q2 误差超限", "误差超限", Q3, ("laplace-nd",)),
    compared("filter-ddt-dc", "滤波与微分：DC 直通项", "连续动态与相位", "滤波与微分：DC 直通项", "Q3 启动误差超限", Q3, "误差超限", Q3, ("laplace-nd", "ddt-input")),
    compared("two-absdelay", "两个固定延迟的历史", "延迟、边沿、周期", "两个固定延迟的历史", Q3, "编译失败", Q3, Q3, ("absdelay",)),
    compared("two-slew", "两级 slew 与反向追赶", "延迟、边沿、周期", "两级 slew 与反向追赶", Q3, "编译失败", Q3, Q3, ("slew",)),
    compared("interrupted-edge-integrate", "中断边沿→积分", "组合、反馈、实例", "中断边沿→积分", Q3, "新版验收未跑", "新版验收未跑", Q3, ("idt",)),
    compared("array-event-update", "数组的事件状态更新", "语言", "数组的事件状态更新", Q3, "初始化失败", "编译失败", Q3, ("array-static-index",)),
    compared("chain-sample-hold-edge-filter", "采样→保持→边沿→滤波", "组合、反馈、实例", "采样→保持→边沿→滤波", Q3, "编译失败", "事件与输出错误", Q3, ("sample-hold-timer", "transition", "laplace-nd")),
    compared("filter-then-sample", "滤波→采样保持", "组合、反馈、实例", "滤波→采样保持", Q3, "编译失败", "采样历史错误", Q3, ("laplace-nd", "sample-hold-timer")),
    compared("solve-delay-sample", "电压求解→延迟→采样", "组合、反馈、实例", "电压求解→延迟→采样", Q3, "编译失败", Q3, Q3, ("absdelay",)),
    compared("vco", "VCO：扫频与原始相位", "连续动态与相位", "VCO：扫频与原始相位", "环回边界未验收", "扫频误差超限", "编译失败", Q3, ("idtmod",)),
    compared("instance-integrator-reset", "实例隔离：双积分器复位", "组合、反馈、实例", "实例隔离：双积分器复位", "复位误差超限", "编译失败", "误差超限", Q3, ("idt",)),
    compared("instance-phase", "实例隔离：双相位历史", "组合、反馈、实例", "实例隔离：双相位历史", "环回边界未验收", "编译失败", "编译失败", Q3, ("idtmod",)),
    compared("nonlinear-integral-filter-feedback", "非线性积分与滤波联合反馈", "组合、反馈、实例", "非线性积分与滤波联合反馈", Q3, "误差超限", Q3, Q3, ("idt", "laplace-nd")),
    compared("event-dynamics-linear", "事件改变动态：线性反馈", "组合、反馈、实例", "事件改变动态：线性反馈", Q3, "初始化失败", "Q1 误差超限", Q3),
    compared("event-dynamics-riccati", "事件改变动态：Riccati 滤波", "组合、反馈、实例", "事件改变动态：Riccati 滤波", Q3, "初始化失败", "误差超限", Q3, ("laplace-nd",)),
    compared("near-timer-chain", "近邻定时事件：原整链", "组合、反馈、实例", "近邻定时事件：原整链", "✓ 1 µV", "初始化失败", "✓ 1µV", Q3, ("timer",)),
    compared("near-timer-adjacent", "近邻定时事件：相邻浮点采样积分", "组合、反馈、实例", "近邻定时事件：相邻浮点采样积分", "回调同刻", "初始化失败", "回调同刻", Q3, ("timer", "idt")),
    waiting("include-guard", "include 保护", "语言", "include 保护、条件编译的独立验收尚未跑。"),
    waiting("parameter-range", "参数范围端点", "语言", "参数依赖与范围端点尚未跑。", ("parameters",)),
    waiting("loop-bounds", "零次、一次与参数化循环", "语言", "零次、一次与参数化次数的循环尚未跑。", ("static-loop",)),
    waiting("array-declaration-order", "数组声明方向", "语言", "相反声明方向的数组尚未跑。", ("array-static-index",)),
    waiting("supply-reference-precision", "供电与参考的统一精度", "参考与供电", "原 v2 四条件已测；统一精度流程中的供电依赖和对应观察尚未跑。"),
    waiting("initial-threshold", "初始阈值", "阈值、迟滞、启动", "初始阈值尚未逐项补齐。"),
    waiting("above", "above", "阈值、迟滞、启动", "PROTOCOL 仍将 above 列为待补，独立答案尚未写入本登记。"),
    waiting("last-crossing", "last_crossing", "阈值、迟滞、启动", "PROTOCOL 仍将 last_crossing 列为待补，独立答案尚未写入本登记。"),
    waiting("period-update", "周期修改", "延迟、边沿、周期", "周期修改尚未逐项补齐。", ("timer",)),
    waiting("schedule-cancel", "旧日程取消", "延迟、边沿、周期", "旧日程取消尚未逐项补齐。", ("timer",)),
    waiting("same-time-rules", "同刻规则", "阈值、迟滞、启动", "同刻规则尚未逐项补齐。"),
    waiting("vco-gated", "VCO 门控", "连续动态与相位", "门控 VCO 尚未跑。", ("vco",)),
    waiting("vco-long-phase", "VCO 长期相位", "连续动态与相位", "长期相位尚未跑。", ("vco",)),
    waiting("phase-cross", "读取相位的 cross", "阈值、迟滞、启动", "读取相位的 cross 尚未跑。", ("cross", "idtmod")),
    waiting("sine-response", "正弦幅相", "连续动态与相位", "正弦幅相尚未跑。", ("laplace-nd",)),
    waiting("conjugate-poles", "共轭极点", "连续动态与相位", "共轭极点尚未跑。", ("filter-second-order",)),
    waiting("smooth-derivative", "光滑曲线导数", "连续动态与相位", "光滑曲线导数尚未跑。", ("ddt-input",)),
    waiting("delay-then-slew", "延迟后限速", "延迟、边沿、周期", "延迟后限速尚未形成独立卡。", ("absdelay", "slew")),
    waiting("short-pulse", "短脉冲", "延迟、边沿、周期", "短脉冲尚未形成独立卡。", ("transition",)),
    waiting("deeper-slew-cascade", "更深 slew 级联", "延迟、边沿、周期", "更深 slew 级联尚未形成独立卡。", ("two-slew",)),
    waiting("adc-codes", "ADC 端码、阈值、饱和与读取时序", "采样、保持、复位", "固定端码、阈值、饱和及读取时序的仿真器用例尚未跑，不能用 benchmark 成绩代替。"),
]

CAMPAIGNS = [
    {
        "id": "four-backend-q",
        "title": "四后端支持表前五节",
        "evidence": "evas/docs/COMPARISON.md#支持矩阵",
        "node_ids": [node["id"] for node in NODES if node["status"] == "compared"],
        "note": "这些节点的成绩转录自该表。表内历史说明仍留在原文件。",
    },
    {
        "id": "dvs-31",
        "title": "原 31 条件",
        "evidence": "experiments/backends/dvs2-spectre-validation/README.md",
        "node_ids": [],
        "note": "冻结收据仍在 experiments/backends/dvs2-spectre-validation。逐条条件对应到能力节点尚未审核，这里不猜测映射。",
    },
]
