# smoke admission v1 successors

显式开发/演示 successor，原 validation/smoke 源、manifest 和历史收据保留。
manifest 字节与原文件相同，只在本目录读取同名 successor VA。三个 VA 均显式增加
`include "disciplines.vams"`；cross_counter 另将 `.5/.1/.01` 改为 `0.5/0.1/0.01`。
事件时间、刺激、查询、参数和数值预期不改。这不重新认证原历史结果。

| 原冻结案例 | 原 VA SHA256 | 原 manifest SHA256 |
| --- | --- | --- |
| absdelay | `6e71eedc36f895aa377278569fb670355ef1c7fe8f10f965f024313569cd7a72` | `8954098f85bdb889bc807a1be23da54e3685c8e6595b194144e622698f3596ac` |
| cross_counter | `9bdd89f5db64631c1c28b9a64b5c0b1327f960335f4ff232b8ba2ca4ba2906b1` | `cee72b20f2ff3581062e267b7b392d8e0f440f07e589e58c873d8afbb8e8f93f` |
| timer_counter | `99ff50acde19b4d20f3b8d4f504b8d94a7cc7a35f77c3308a6cc0d373e48c44c` | `eca6b63a749b12db16a7bc7cf391705fbeb341bb358e8ff28d44ef968a88de8c` |
