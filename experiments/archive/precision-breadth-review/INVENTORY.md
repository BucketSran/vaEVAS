# 新增精度检查范围

以下为本轮冻结的44组。通过数需要实际四后端结果；这份清单不宣称通过。

| 组 | 测试内容 | 变体数 |
| --- | --- | --- |
| F01 | Macro and instance parameters | 1 |
| F02 | Sequential locals and contribution snapshots | 1 |
| F03 | Comparisons, logic and ternary DC boundaries | 12 |
| F04 | Scalar case first match and default | 5 |
| F05 | Pure function branches and locals | 4 |
| F06 | Static loop and local array | 1 |
| F07 | Non-idempotent persistent array events | 1 |
| F08 | Static electrical vector | 1 |
| F09 | Two-level hierarchy parameters | 2 |
| F10 | Reference and additive contributions | 3 |
| F11 | Unique affine implicit relation | 1 |
| F12 | Monotone cubic implicit relation | 4 |
| F13 | Integral with nonzero initial state | 1 |
| F14 | PWL derivative one-sided values | 1 |
| F15 | Dyadic laplace_nd DC initialization | 1 |
| F16 | Dyadic laplace_np equivalent encoding | 1 |
| F17 | Fixed delay startup history | 1 |
| F18 | Asymmetric slew reverse catch-up | 1 |
| F19 | Timer and complete asymmetric transition | 1 |
| F20 | Half-open wrapped phase and sine | 1 |
| EC01 | Sample/reset priority and transition | 1 |
| EC02 | Hysteresis, asymmetric edges and short-pulse reversal | 1 |
| EC03 | Sampled integral nonzero IC including stop callback | 1 |
| EC04 | Ordered sampled assignment into nonlinear integral | 1 |
| EC05 | Interrupted transition into integral support probe | 1 |
| EC06 | Two integrals with one reset and independent IC | 2 |
| EC07 | Reset upstream integral preserves downstream accumulated area | 1 |
| EC08 | Held-input linear feedback retains other state | 1 |
| EC09 | Joint nonlinear integral and filter feedback | 1 |
| EC10 | Event activates Riccati filter without new DC initialization | 1 |
| EC11 | Second-order filter with internal derivative | 2 |
| EC12 | Polynomial filter direct term with nonzero DC | 2 |
| EC13 | Algebraic projection into delay and sampling | 1 |
| EC14 | Two fixed delays and independent parallel history | 1 |
| EC15 | Two asymmetric slew stages and reversal catch-up | 1 |
| EC16 | DC derivative phase into filter direct term | 1 |
| EC17 | Positive chirp VCO coherent phase and sine | 1 |
| EC18 | Negative frequency with nonzero modulo offset | 1 |
| EC19 | Independent phase histories with different frequency and IC | 1 |
| EC20 | Binary64 nearby clocks and sampled integral area | 1 |
| EC21 | Advanced held calendar bounds nonlinear propagation | 1 |
| EC22 | Same-time reset and clock semantic probe | 1 |
| EC23 | Bidirectional self-commutation support probe | 1 |
| EC24 | Index-one implicit DAE with reset support probe | 1 |
