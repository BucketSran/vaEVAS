# v4 边沿采样保持模块

原题 v4-024，单个 `sample_hold` module，来源组 `v4-family-024`。参考在上升沿采样相对 VSS 的输入，输出通过 transition 平滑到保持值。它是理想行为资产，尚未找到配套晶体管采样级或真实表征记录。

旧来源指向 slug026 与 sample_hold_smoke 的提升记录；不据此声明实际工程电路来源。用户已确认用于基础规格建模；[r2 规格草案](../cases/spec-modeling/adc/case-0011-clocked-sample-hold/instruction.md)已明确局部轨、初态和固定供电，运行校准仍待完成。

来源、固定快照和读取范围见[共用来源卡](../sources/v4-single-module-migration.md)。仅作内部材料引用，未将旧源码复制到新题。未运行编译或仿真，未把旧认证转为当前准入证据。
