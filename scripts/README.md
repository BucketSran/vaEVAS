# Scripts

此工作区按实际需要增加仓库维护工具，例如任务静态检查、发布清单生成和结果整理。

任务的验收入口归对应任务维护，EVAS 的内部实现归 [`evas/`](../evas/README.md) 维护，
实验分析归 [`experiments/`](../experiments/README.md) 维护。
Harbor 承担评测执行和 Agent 接入。

[verify_validation_version.py](verify_validation_version.py) 只读核验独立仿真器验证集版本的
Git 文件、版本描述文件及原运行输入哈希，不调用仿真器。当前默认版本为
[v1](../evas/validation/versions/v1/README.md)。
