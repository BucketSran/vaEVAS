# Runner-host comparison fix successor construction

Successor of PR271 head dc8866d3; built on main ac1b6e8d. GitHub runner image 20261026.354.1 changed only the kernel release in platform.platform() and ImageVersion; every registered context was observed on 20261023.334.3. The trusted comparator now matches a run to exactly one registered context that differs only in those two runner-host fields and still compares every observation; the Rust listing applies the same kernel-release rule. Criteria, collector and language profile are unchanged. Scientific qualification is false.
