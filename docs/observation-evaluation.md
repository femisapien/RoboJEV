# 空间输入正式对照 / Spatial input comparison

实验日期：2026-09-27（UTC；北京时间 9 月 28 日完成）。本轮固定 40 个槽位已全部完成，40/40 离线回放核验通过，回放网络请求为 0。

**结论：本轮没有观察到完整几何提高任务成功率。单门框为原有输入 3/10、完整几何 2/10；错位双门框均为 0/10。** 每任务仅 10 对 seed，不能据此证明两种输入等效，或认定完整几何降低真实成功率。原有 `legacy` 仍是正常使用的默认输入；`full_geometry` 仅为现实中难以完整获取的仿真特权信息对照。

## 固定条件与统计口径

- 两任务 × seeds 0–9 × 两种输入，共 40 个独立运行槽位、20 对场景。两组初始物理状态哈希逐对一致；偶数 seed 原有输入先运行，奇数 seed 完整几何先运行。
- JEV `jev-1.13.0`、物理配置、动作接口、提示中的动作规则和成功阈值冻结。完整几何额外提供机器人碰撞部件、保守 OBB、关节/刚体位姿、门框几何及当前有符号距离；没有增加候选动作碰撞预测、规划器或规则回退。
- 单门框：40 mm 方块、70 mm 开口、120 mm 横梁、350 次决策上限；错位双门框：两道 90 mm 开口、100/120 mm 横梁、横向错位 90 mm、500 次决策上限。
- 全程机器人或物体对门框接触力总和 >0.05 N 即失败；过门底部净空 ≥5 mm，方块投影在开口内。双门框还要求正确过门顺序与抓持；最终在目标内释放、得到支撑并稳定 0.5 s。
- API 重试时物理仿真暂停，已收到的回答存档且不重采样。所有碰撞、决策预算耗尽和响应校验失败保留在每组 10 次的分母内。
- 此批不合并进原五任务 100 轮评测，也不合并 9 月 23 日历史对照、18 槽位重试及被排除的恢复调试批次。

冻结仿真/策略源码 SHA-256：`5925c8250ff703004a1e0e915bfdabc28e526849df3f77f0aafaeeb90a91ec33`。恢复、校验和重放细节见[本轮实验协议](observation-recomparison.md)。

## 结果

| 任务 | 输入 | 成功 / 10 | 碰撞 | 决策预算耗尽 | 响应校验失败 | 未解决 API 中断 | Wilson 95% |
|---|---|---:|---:|---:|---:|---:|---|
| 单门框 | 原有输入（默认） | 3/10 | 2 | 2 | 3 | 0 | 10.8%–60.3% |
| 单门框 | 完整几何（仅仿真） | 2/10 | 4 | 0 | 4 | 0 | 5.7%–51.0% |
| 错位双门框 | 原有输入（默认） | 0/10 | 10 | 0 | 0 | 0 | 0.0%–27.8% |
| 错位双门框 | 完整几何（仅仿真） | 0/10 | 7 | 0 | 3 | 0 | 0.0%–27.8% |

共 5 次成功、23 次碰撞、2 次预算耗尽、10 次响应校验失败。响应校验失败是已收到的模型输出不一致，不是 HTTP/网络传输中断；该次动作未执行，不能删除失败或重新请求直到有效。

## 同 seed 配对

| 任务 | 双方成功 | 仅完整几何成功 | 仅原有输入成功 | 双方失败 | 成功率差（完整−原有） | 精确 McNemar 双侧 p |
|---|---:|---:|---:|---:|---:|---:|
| 单门框 | 2 | 0 | 1 | 7 | -10 个百分点 | 1.00 |
| 错位双门框 | 0 | 0 | 0 | 10 | +0 个百分点 | 1.00 |

单门框双方均在 seed 2、8 成功；seed 3 只有原有输入成功。双门框没有成功试次，也没有不一致的成功对，p=1 是该精确检验在无不一致对时的约定，不能视为两种输入等效的证据。

| 任务 | Seed | 原有输入 | 完整几何 |
|---|---:|---|---|
| 单门框 | 0 | 预算耗尽 | 碰撞 |
| 单门框 | 1 | 预算耗尽 | 响应校验失败 |
| 单门框 | 2 | 成功 | 成功 |
| 单门框 | 3 | 成功 | 响应校验失败 |
| 单门框 | 4 | 碰撞 | 响应校验失败 |
| 单门框 | 5 | 响应校验失败 | 响应校验失败 |
| 单门框 | 6 | 响应校验失败 | 碰撞 |
| 单门框 | 7 | 响应校验失败 | 碰撞 |
| 单门框 | 8 | 成功 | 成功 |
| 单门框 | 9 | 碰撞 | 碰撞 |
| 错位双门框 | 0 | 碰撞 | 碰撞 |
| 错位双门框 | 1 | 碰撞 | 响应校验失败 |
| 错位双门框 | 2 | 碰撞 | 碰撞 |
| 错位双门框 | 3 | 碰撞 | 碰撞 |
| 错位双门框 | 4 | 碰撞 | 响应校验失败 |
| 错位双门框 | 5 | 碰撞 | 碰撞 |
| 错位双门框 | 6 | 碰撞 | 碰撞 |
| 错位双门框 | 7 | 碰撞 | 碰撞 |
| 错位双门框 | 8 | 碰撞 | 响应校验失败 |
| 错位双门框 | 9 | 碰撞 | 碰撞 |

## API 中断如何与任务结果分离

- 实际 HTTP 尝试共 12,631 次：12,480 次收到 HTTP 200、113 次传输错误、38 次 HTTP 402 账户拒绝。113 次传输错误包括 64 次 ConnectError、46 次 RemoteProtocolError、2 次 ReadTimeout、1 次 ConnectTimeout。
- 38 次 402 发生于充值前的中断阶段，作为账户阻塞留档；充值后从同一批次继续。它们不代表 38 个失败或额外样本，也不是自动重试成功的 38 次临时 HTTP 故障。最终未解决槽位为 0。
- 每个未收到回答的请求最多 20 次传输/临时服务重试，每次超时 60 s，退避 5、10…30 s。等待不推进物理时间、不消耗物理动作；账户 401/402/403 停止后需恢复服务再续跑。
- 离线验证仅使用保存的回答，逐步核对请求对应的机器人/障碍物状态、动作、物理转移和最终结果。40/40 通过，0 次网络请求，新增独立试次为 0。连续量容差 1e-9，离散量精确一致。
- 回放不要求重新计算的网格距离相等：曾观察到约 1e-15 的姿态差异导致距离从 0.109045 m 跳为 0。原回答仍基于原始观测，其他物理量独立核验。这是距离特征可重算性的限制。
- 本协议消除了已记录传输中断作为终止失败和物理时间扰动的影响，但远端推理仍可能随机；同 seed 并不固定模型回答。未收到的回答也可能在服务端已计算或计费。

## 失败证据与边界

碰撞部件与力由原始终止 qpos/qvel/mocap 状态重建，并核对与当时总接触力一致。下表列出全部 35 次失败。阶段描述是直接观测，不能单独证明根本因果。

| 任务 | 输入 | Seed | 决策 | 终止原因与证据 |
|---|---|---:|---:|---|
| 单门框 | 原有输入（默认） | 0 | 350 | 350 次预算耗尽；157 次动作被拒绝，最长连续 157 次；未满足过门、释放与稳定条件 |
| 单门框 | 完整几何（仅仿真） | 0 | 136 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate ↔ link5 73.862 N >0.05 N |
| 单门框 | 完整几何（仅仿真） | 1 | 190 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 单门框 | 原有输入（默认） | 1 | 350 | 350 次预算耗尽；276 次动作被拒绝，最长连续 276 次；未满足过门、释放与稳定条件 |
| 单门框 | 完整几何（仅仿真） | 3 | 221 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 单门框 | 原有输入（默认） | 4 | 174 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate ↔ link5 25.267 N >0.05 N |
| 单门框 | 完整几何（仅仿真） | 4 | 142 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 单门框 | 完整几何（仅仿真） | 5 | 117 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 单门框 | 原有输入（默认） | 5 | 112 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 单门框 | 原有输入（默认） | 6 | 109 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 单门框 | 完整几何（仅仿真） | 6 | 140 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate ↔ link5 14.246 N >0.05 N |
| 单门框 | 完整几何（仅仿真） | 7 | 153 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate ↔ link5 25.537 N >0.05 N |
| 单门框 | 原有输入（默认） | 7 | 163 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 单门框 | 完整几何（仅仿真） | 9 | 161 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate ↔ link5 14.694 N >0.05 N |
| 单门框 | 原有输入（默认） | 9 | 120 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate ↔ link5 25.666 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 0 | 143 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link5 51.556 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真） | 0 | 145 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link5 16.369 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真） | 1 | 220 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 错位双门框 | 原有输入（默认） | 1 | 58 | 碰撞；lift；x=positive, y=zero, z=positive, gripper=hold；gate_1 ↔ link7 3.990 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 2 | 64 | 碰撞；lift；x=positive, y=zero, z=positive, gripper=hold；gate_1 ↔ link7 15.012 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真） | 2 | 130 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link7 7.454 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真） | 3 | 223 | 碰撞；lift；x=zero, y=zero, z=positive, gripper=hold；gate_2 ↔ link7 35.911 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 3 | 62 | 碰撞；lift；x=positive, y=zero, z=zero, gripper=hold；gate_1 ↔ link7 47.947 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 4 | 59 | 碰撞；lift；x=positive, y=zero, z=positive, gripper=hold；gate_1 ↔ link7 5.500 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真） | 4 | 294 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 错位双门框 | 完整几何（仅仿真） | 5 | 138 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link5 9.773 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 5 | 59 | 碰撞；lift；x=positive, y=zero, z=positive, gripper=hold；gate_1 ↔ link7 3.959 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 6 | 143 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link5 29.695 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真） | 6 | 228 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link5 38.192 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真） | 7 | 165 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link7 56.767 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 7 | 145 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link5 40.942 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 8 | 144 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link5 50.316 N >0.05 N |
| 错位双门框 | 完整几何（仅仿真） | 8 | 132 | 响应校验失败；intent intent=lift，所选 0.49 < 最大 0.50；该次动作未执行 |
| 错位双门框 | 完整几何（仅仿真） | 9 | 141 | 碰撞；lower；x=zero, y=zero, z=negative, gripper=hold；gate_2 ↔ link5 10.679 N >0.05 N |
| 错位双门框 | 原有输入（默认） | 9 | 62 | 碰撞；lift；x=positive, y=zero, z=positive, gripper=hold；gate_1 ↔ link7 16.732 N >0.05 N |

可直接从轨迹确认的现象：

- 单门框的 6 次碰撞均为下降时 link5 碰门柱，力为 14.246–73.862 N。完整几何包含全臂当前空间信息，但仍未可靠转化为下降前的全臂避障动作。
- 双门框原有输入的 6 次失败为第一道门与 link7 碰撞（seeds 1、2、3、4、5、9），最后动作在 lift 意图下仍含 +X。其余 4 次为第二道门下降时 link5 碰撞。
- 双门框完整几何组没有记录到第一道门碰撞，7 次碰撞均在第二道门与 link5/link7，另 3 次响应校验失败。因此存在阶段行为变化，但最终成功率仍为 0/10；不能将“更晚失败”当作任务成功。
- 全部 10 次响应校验失败都是 intent 选择 lift 的概率 0.49 小于最大概率 0.50；校验器按冻结规则终止。它们不属于 API 传输故障，仍限制这轮端到端成功率，不能仅凭本轮单独估计移除输出校验后的纯几何效应。
- 原有输入单门框 seed 1 最后反复请求 +Y，而实测抓取方向为 −Y，最长连续 276 次 workspace_rejected，未抓到方块。seed 0 也经历长拒绝段，但末尾已持物过门且目标 XY 尚未对齐，不能把两次预算耗尽概括为同一失败轨迹。

## 输入体积

| 任务 | 原有输入平均请求字节 | 完整几何平均请求字节 | 比例 |
|---|---:|---:|---:|
| 单门框 | 9775 | 22545 | 2.31× |
| 错位双门框 | 9153 | 25843 | 2.82× |

请求字节先在各试次内平均，再对 10 次试次平均。恢复后的计时含缓存回答与实际等待，不能作为完整成功任务的纯推理时延或总成本对比，因此此处不据此比较速度；私有原始请求、回答、凭据和 token 使用记录不公开。

## 原始试次录像

以下六份录像直接渲染本轮保存的物理状态，没有再次调用 API、执行动作或积分物理。成功选最小成功 seed；为展示接触边界，失败选最小碰撞 seed（所以原有单门框为 seed 4，预算耗尽 seed 0、1 保留在上表和机器可读证据中）。双门框本轮两组均无成功录像，不借用历史成功试次。影片省略 API 等待，末尾有两秒结果静帧。

| 任务 | 输入 | 结果 | Seed | 录像 |
|---|---|---|---:|---|
| 单门框 | 原有输入（默认） | 成功 | 2 | [MP4](../site/media/observation/resilient-20260927/obstacle_pick_place-legacy-success.mp4) |
| 单门框 | 原有输入（默认） | 失败 | 4 | [MP4](../site/media/observation/resilient-20260927/obstacle_pick_place-legacy-failure.mp4) |
| 单门框 | 完整几何（仅仿真） | 成功 | 2 | [MP4](../site/media/observation/resilient-20260927/obstacle_pick_place-full_geometry-success.mp4) |
| 单门框 | 完整几何（仅仿真） | 失败 | 0 | [MP4](../site/media/observation/resilient-20260927/obstacle_pick_place-full_geometry-failure.mp4) |
| 错位双门框 | 原有输入（默认） | 失败 | 0 | [MP4](../site/media/observation/resilient-20260927/double_gate_pick_place-legacy-failure.mp4) |
| 错位双门框 | 完整几何（仅仿真） | 失败 | 0 | [MP4](../site/media/observation/resilient-20260927/double_gate_pick_place-full_geometry-failure.mp4) |

## 可审计文件与历史归档

- [本轮配对汇总与传输审计](../site/data/observation-resilient.json)
- [40 份零网络回放核验及原轨迹哈希](../site/data/observation-resilient-replay.json)
- [逐试次失败边界、末五次动作与接触证据](../site/data/observation-resilient-failures.json)
- [本轮录像来源与校验和](../site/data/observation-resilient-demonstrations.json)
- [9 月 23 日历史对照](observation-evaluation-20260923.md)及[历史 18 槽位重试状态](../site/data/observation-retry.json)独立归档，不与本轮合并。

English finding: after resolving transport interruptions, the fixed paired campaign found no success-rate improvement from full geometry (single gate 3/10 vs 2/10; double gate 0/10 vs 0/10). Both exact paired tests give p=1.00, with only ten pairs per task. All 40 traces passed offline verification without network requests. Model-response validation failures remain failures. The result is exploratory and does not establish equivalence or infer that additional geometry is inherently harmful.
