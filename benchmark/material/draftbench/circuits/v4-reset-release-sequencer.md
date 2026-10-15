# v4 电源与偏置就绪后的复位释放序列

原题 v4-1272，family272，单个 `reset_release_sequencer` module。时钟沿采样供电、偏置和复位，推进有限阶段，给出 stage1/stage2/ready/progress。

来源组 `v4-family-272`。actual starter 与 neg004 no_reset_clear 相同，而 manifest 指 neg005 wrong_progress_scale；按实际字节登记。参考和起始文件可读，参数范围、同步边界及独立 checker 需重建。

来源、固定快照和读取范围见[共用来源卡](../sources/v4-single-module-migration.md)。仅作内部材料引用，未将旧源码复制到新题。未运行编译或仿真，未把旧认证转为当前准入证据。
