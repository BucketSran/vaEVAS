# v4  BBPD 鉴相模块

原题 v4-001，单个 `bbpd_ref` module，来源组 `v4-family-001`。数据边沿决定 UP/DOWN，下一时钟边沿清除，原题定位于 CDR 行为模型。

来源追到旧 slug001 及旧 spec-to-va 的 bbpd 任务路径，尚未据此确认配套实际电路。拟用于单模块规格建模，原协议与 Alexander 的对应关系尚未证实；用户随后选定完整 Alexander 内部采样方案，见[设计卡](../cases/spec-modeling/pll/case-0012-bbpd/README.md)。

来源、固定快照和读取范围见[共用来源卡](../sources/v4-single-module-migration.md)。仅作内部材料引用，未将旧源码复制到新题。未运行编译或仿真，未把旧认证转为当前准入证据。

已有派生任务 [spec-cdr-phase-detector](../../tasks/spec-cdr-phase-detector/SOURCE.md)明确需求参考 v4-001，并使用旧来源组 cdr-phase-original。实现独立编写不消除需求来源关联。case-0012 的 r2 移除外部 retimed_data，重新定义内部三点采样和输出保持。此卡继续记录旧资产；新方向依据独立主源，旧代码和旧成绩不自动继承。详见[本轮题卡](../cases/spec-modeling/pll/case-0012-bbpd/README.md)。
