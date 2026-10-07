# 来源和校准边界

本题是仓库作者根据 对齐 pipeline ADC 的级间数据 的工程需求原创的小工程。`source_group=original-pipeline-adc`。旧v4 096的pipeline ADC方向只用于选题方向，没有复制其代码、参数、注释或文件结构，不继承旧资产许可或成绩。

上下文层次为 `bounded_small_project`。本工程没有伪造工业版本史；题面明确说明是原创教学和研究工程。起点保留现有模块，只故意遗漏或错接新功能。独立验收依据为 instruction 中公开公式、事件配对和时间窗，参考解不定义真值。

终评有 3 组独立实验。语义负例见 experiments/benchmark_first_batch/integration/mutants/integrate-pipeline-adc-alignment/。每个负例仍是可编译的 VA，针对不同条款；实际 Spectre 编译及拒绝情况待校准。行级合成测试只验证 checker 自身，不证明 VA 参考解通过。

发布身份为 Spectre 扩展集候选。Spectre 校准、Harbor oracle、Agentic 主评及开源重评都需分别取得真实证据；当前不宣称已完成这些阶段。
