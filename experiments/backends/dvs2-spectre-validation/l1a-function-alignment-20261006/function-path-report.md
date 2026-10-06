# PR85 函数路径实际对照（有限范围）

修正后的同一 VA 模型在 Spectre 21.1.0.509.isr12、EVAS 4e9051df 和最终 0425728a 上符合独立答案。原始 `logic` 端口被 Spectre VACOMP-2259 拒绝的失败仍保留：共实际执行两个分别获授权的 Spectre 配置，一次语法失败、一次修正后成功，无自动重试。042 只新执行 EVAS，复用修正配置的实际 Spectre 波形。

模型覆盖七层函数链（原12叶参数表达式被结果常数1舍弃）、比较/条件纯函数，以及两个14层 twice sibling 相加。输入为0到1秒的线性PWL，u从−2^-16到+2^-16 V；独立答案为 discarded=1、gain=32768u=t−.5、ydecision=(t>.5)。端口重命名之外物理模型、刺激、求解设置和预算未变。原冻结contract仍记4e，042执行身份另列，不倒写原收据。

单端预算1µV、两端2µV、离散差0、转换括区±1e-7秒。Spectre1034个真实导出点独立答案最大gain误差5.55e-17V；两个EVAS版本的7个请求点独立误差及pair误差均≤2.78e-17V。pair只比较7个共同真实导出点，不插值；全部临界请求点存在。两端在t=.5值0，在t=.50000005值1；Spectre全轨迹仅一处转换，括区[.5,.50000005]，满足时间预算。原预检漏掉保留关键字，原语法失败不归因于EVAS函数语义。

042执行前工作树clean，94个受版本管理的Python/Rust目录文件与固定Git提交逐字节核对，再执行独立snapshot。Rust源码与实际4e build完全相同，kernel SHA179315e5b00cbce61ed42ebd0ce8d17dbf100444655c27d8b22503c9f69124fd，实际旧build收据与日志SHA在capsule保留。两个版本源码/内核执行后未变。校准接受正确答案、拒绝10µV gain偏差和错误精确半点离散值、缺失半点判inconclusive。

`function-path-results.json`包含可公开输入、派生结果和真实raw/receipt SHA。精确机器路径/argv、PSF/source snapshots/build日志只在local-only原收据；逻辑archive ID不是公开下载地址，可移植命令模板不是实际精确命令。这个有界对照不能推出全部函数支持、内部执行次数一致或全面模拟器一致；不替换原24例或D7六配置。
