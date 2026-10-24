# 给使用者和审稿人的能力比较

由 `evas/capabilities/catalog.py` 生成。只包含已经有四后端成绩的能力节点。
这一页不是实验开发的登记簿。落后和未验收留在格子里。

| 能力 | 与其他仿真器的比较 |
| --- | --- |
| 宏与 include | 宏与 include。Spectre：✓ Q3；ngspice + OpenVAF-R：层次语法编译失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 参数 | 参数。Spectre：✓ Q3；ngspice + OpenVAF-R：层次语法编译失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 条件与逻辑表达式 | 条件与逻辑表达式。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| case 分支 | case 分支。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 顺序赋值 | 顺序赋值。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 用户函数 | 用户函数。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 静态循环 | 静态循环。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：编译失败；EVAS：✓ Q3。 |
| 变量数组：静态下标 | 变量数组：静态下标。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：编译失败；EVAS：✓ Q3。 |
| 电气向量 | 电气向量。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：编译失败；EVAS：✓ Q3。 |
| 模块层次 | 模块层次。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| sin | sin。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| cos | cos。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| exp | exp。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| ln | ln。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| sqrt | sqrt。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| pow：三次幂 | pow：三次幂。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| pow：半次幂 | pow：半次幂。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 电压访问与贡献 | 电压访问与贡献。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 静态电压反馈 | 静态电压反馈。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| initial_step | initial_step。Spectre：✓ Q3；ngspice + OpenVAF-R：编译或初始化失败；Gnucap + modelgen-verilog：编译失败；EVAS：✓ Q3。 |
| cross：斜坡穿越 | cross：斜坡穿越。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：漏事件；EVAS：✓ Q3。 |
| 固定 timer | 固定 timer。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 事件 OR：采样与复位 | 事件 OR：采样与复位。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：漏事件；EVAS：✓ Q3。 |
| transition：定时非对称沿 | transition：定时非对称沿。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 固定 absdelay | 固定 absdelay。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 固定 slew | 固定 slew。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| idt：非零初值与正负面积 | idt：非零初值与正负面积。Spectre：✓ Q2；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| idtmod：原始相位与环回 | idtmod：原始相位与环回。Spectre：环回边界未验收；ngspice + OpenVAF-R：环回边界未验收；Gnucap + modelgen-verilog：编译失败；EVAS：✓ Q3。 |
| ddt：二次时间表达式 | ddt：二次时间表达式。Spectre：Q1 误差超限；ngspice + OpenVAF-R：误差超限；Gnucap + modelgen-verilog：✓ Q2；EVAS：✓ Q3。 |
| ddt：电压斜坡平方 | ddt：电压斜坡平方。Spectre：✓ Q2；ngspice + OpenVAF-R：误差超限；Gnucap + modelgen-verilog：✓ Q2；EVAS：✓ Q3。 |
| 一阶 laplace_nd | 一阶 laplace_nd。Spectre：✓ Q3；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：非零初态错误；EVAS：✓ Q3。 |
| 一阶 laplace_np | 一阶 laplace_np。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。 |
| 二阶滤波（内部微分） | 二阶滤波（内部微分）。Spectre：✓ Q3；ngspice + OpenVAF-R：Q1 误差超限；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。 |
| 采样保持：定时 | 采样保持：定时。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 采样保持：阈值 | 采样保持：阈值。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：漏事件；EVAS：✓ Q3。 |
| 采样、复位与输出边沿 | 采样、复位与输出边沿。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：漏事件；EVAS：✓ Q3。 |
| 迟滞比较器与边沿 | 迟滞比较器与边沿。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。 |
| 定时采样→积分：原模型 | 定时采样→积分：原模型。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：漏定时事件；EVAS：✓ Q3。 |
| 采样→积分：停止边界与非线性 | 采样→积分：停止边界与非线性。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：停止边界未达标；EVAS：✓ Q3。 |
| 积分级联与复位 | 积分级联与复位。Spectre：复位误差超限；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。 |
| 非线性输入与滤波直通项 | 非线性输入与滤波直通项。Spectre：Q2 误差超限；ngspice + OpenVAF-R：Q1/Q2 误差超限；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。 |
| 滤波与微分：DC 直通项 | 滤波与微分：DC 直通项。Spectre：Q3 启动误差超限；ngspice + OpenVAF-R：✓ Q3；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。 |
| 两个固定延迟的历史 | 两个固定延迟的历史。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 两级 slew 与反向追赶 | 两级 slew 与反向追赶。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 中断边沿→积分 | 中断边沿→积分。Spectre：✓ Q3；ngspice + OpenVAF-R：新版验收未跑；Gnucap + modelgen-verilog：新版验收未跑；EVAS：✓ Q3。 |
| 数组的事件状态更新 | 数组的事件状态更新。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：编译失败；EVAS：✓ Q3。 |
| 采样→保持→边沿→滤波 | 采样→保持→边沿→滤波。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：事件与输出错误；EVAS：✓ Q3。 |
| 滤波→采样保持 | 滤波→采样保持。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：采样历史错误；EVAS：✓ Q3。 |
| 电压求解→延迟→采样 | 电压求解→延迟→采样。Spectre：✓ Q3；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| VCO：扫频与原始相位 | VCO：扫频与原始相位。Spectre：环回边界未验收；ngspice + OpenVAF-R：扫频误差超限；Gnucap + modelgen-verilog：编译失败；EVAS：✓ Q3。 |
| 实例隔离：双积分器复位 | 实例隔离：双积分器复位。Spectre：复位误差超限；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。 |
| 实例隔离：双相位历史 | 实例隔离：双相位历史。Spectre：环回边界未验收；ngspice + OpenVAF-R：编译失败；Gnucap + modelgen-verilog：编译失败；EVAS：✓ Q3。 |
| 非线性积分与滤波联合反馈 | 非线性积分与滤波联合反馈。Spectre：✓ Q3；ngspice + OpenVAF-R：误差超限；Gnucap + modelgen-verilog：✓ Q3；EVAS：✓ Q3。 |
| 事件改变动态：线性反馈 | 事件改变动态：线性反馈。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：Q1 误差超限；EVAS：✓ Q3。 |
| 事件改变动态：Riccati 滤波 | 事件改变动态：Riccati 滤波。Spectre：✓ Q3；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：误差超限；EVAS：✓ Q3。 |
| 近邻定时事件：原整链 | 近邻定时事件：原整链。Spectre：✓ 1 µV；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：✓ 1µV；EVAS：✓ Q3。 |
| 近邻定时事件：相邻浮点采样积分 | 近邻定时事件：相邻浮点采样积分。Spectre：回调同刻；ngspice + OpenVAF-R：初始化失败；Gnucap + modelgen-verilog：回调同刻；EVAS：✓ Q3。 |
