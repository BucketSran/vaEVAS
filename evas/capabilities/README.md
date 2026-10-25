# Verilog-A 规范与能力登记

本目录分别记录语言配置、规范来源、EVAS 目标范围、验证资格和历史比较结果。
规范选入不表示实现支持，运行通过也不自动授予能力资格。

| 入口 | 维护内容 |
| --- | --- |
| [data/language-profile.json](data/language-profile.json) | LRM 2.4 基础及明确选入的 7780、7920 原子变化；未选变化继续用 2.4 |
| [data/target-scope.json](data/target-scope.json) | 电压域目标及目标外能力；与 Verilog-A 适用性分开 |
| [data/source-inventory.json](data/source-inventory.json) | 独立于测试和要求的规范源索引、正文及抽取边界 |
| [data/dispositions.json](data/dispositions.json) | 各来源项的纳入、排除或待判定及依据 |
| [data/registry.json](data/registry.json) | 对象的稳定 ID、版本、内容绑定及依赖；待补证保留原状态 |
| [registry.py](registry.py) | 登记校验、版本选择及资格失效传播 |
| [generated/normative.md](generated/normative.md) | 从登记生成的规范处置与资格缺口视图 |
| [data/historical-comparison.json](data/historical-comparison.json) | 固定 `f210ebd5` 的旧成绩转录，保留历史范围，不授予当前 main 资格 |
| [catalog.py](catalog.py) | 读取历史登记的兼容接口，不再维护 Python 成绩常量 |
| [generated/comparison.md](generated/comparison.md) 与 [generated/paper.md](generated/paper.md) | 历史比较视图 |

规范索引的分母来自官方文件，不从已有能力或通过测试反推。条款、表项、语法和附录的
来源处置与语义要求审核分开；待判定项必须可枚举，不能当作已经排除或已经验证。
目录检查不能证明全部规范要求已取得答案。完整迁移的批次与验收见
[实施计划](../docs/development/validation-restructure-plan.md)。

2023 的 Table 4-14 同时含已选与未选变化。只选 `ln1p`、`$ln1p`、`expm1`、`$expm1`
及其定义、域和必要语法/上下文依赖，不能整表覆盖。`log1p` 是表中的 C 等价名。
7920 只扩展 `$rtoi`、`$itor` 的模拟上下文；转换定义仍依赖被引用的 IEEE 1364。
未取得引用正文和边界答案的要求继续待补证，Spectre 继续待跑。

对象依赖固定 `id`、`version` 和内容 SHA-256。checker、预算、模型、解释或后端身份变化时，
按[重验规则](../../.agents/skills/evas-validate/SKILL.md#revalidation-triggers)重新校准、重分析或执行。
共享依赖改版、撤销或源码字节变化后，所有消费者均失去当前资格。旧版本查询只解释旧身份，
显式撤销仍然生效。授予资格还须绑定同一案例的执行、分析及独立审核，不能拼接不相干的通过记录。

`checker-definition` 固定源码、适用域及预算，校准执行直接绑定这份定义，避免资格记录与校准互相依赖。
校准必须有可读取且哈希匹配的原始 JSON 收据、正负控实际结果及审核收据，不能只登记控制名称和
`approved` 标签。审核收据固定受校准定义、执行、范围和审核者；校准不得转授给另一判据。
案例与分析必须引用相同 checker 完整身份。资格中的范围、要求及后端身份须与案例、实际执行和
审核结论精确对应；程序不从自然语言描述推断更大的适用范围。收据可用仓库文件或带内容哈希的
内嵌 JSON，缺失或无法读取继续待补证。

科学输入由 `case-inputs` 单独固定模型、参数、刺激、初态与观察要求，执行绑定该输入及原始收据。
案例绑定具体 checker，分析和审核再绑定具体案例。仅 checker 改版且原始观测足够时，可以保留
同一个原执行身份，建立新的校准、案例用法、分析和审核；输入或观察要求变化后，旧执行不能
冒充新输入的执行结果。该规则不要求为了重分析重复运行未改变的 DUT。
`qualified()` 仅对完整 checker 校准或 `qualification`
记录授予资格；其余对象的缺口为就绪性导航，不把单独的来源、案例或执行成功当作资格。

登记中的正控、负控、未支持扩展和内部合同是贯通样例。历史结果仍待当前范围审核，
没有因本次登记自动取得后端资格。规范相关对象和内部合同分别保留来源。
冻结收据与历史波形仍在 `experiments/backends/`，本目录不回写它们。

更新登记后运行现有 CI 的相同入口：

```sh
python3 -B evas/capabilities/registry.py
python3 -B evas/capabilities/render.py
python3 -B evas/capabilities/render.py --check
python3 -B -m unittest discover -s evas/capabilities -p 'test_registry.py' -v
```
