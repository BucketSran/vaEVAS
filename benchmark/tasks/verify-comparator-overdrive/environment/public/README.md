公开器件为仓库原创的行为合成电路。public.scs 是一个正确器件的自测配置。需已配置的 licensed Spectre 后端；镜像本身不包含商业仿真器。

把提交 dut.va、device.va 和 public.scs 复制到新的工作目录，在该目录执行 `spectre -64 public.scs -format psfascii -raw psf`。查看 psf/tran.tran.tran 的原始观测，按 instruction.md 的公式和容差自检。该流程仅公开自测，不提供隐藏终评反馈。
