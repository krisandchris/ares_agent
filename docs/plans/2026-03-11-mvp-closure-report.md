# MVP 收口报告

## 1. 文档目的

本文档用于对当前 `ares_agent` 仓库进行一次面向交付的 MVP 收口评估，重点回答两个问题：

1. 当前最小链路是否完整
2. 当前流程是否真正联通

评估对象是当前仓库内已经实现并通过测试验证的最小闭环，而不是未来的生产版目标系统。

## 2. 当前 MVP 定位

当前仓库定位是：

- `mocked closed-loop demo`

它已经具备完整的最小处理链路，但仍不是生产版城市街道视觉巡检后端。  
其主要价值是验证：

- 编排链路是否完整
- 模型接口契约是否稳定
- prompt/config/model client/callback/event store 是否能形成可测试闭环

## 3. 最小链路范围

当前确认已经成立的最小链路如下：

1. `POST /v1/inspection-items`
2. 请求体校验为 `EventSeed`
3. 调用 `VLM-1` 输出 `PreliminaryResult`
4. 调用 `SAM3` 输出 `SegmentationResult`
5. 调用 `VLM-2` 输出 `EvidenceJudgeResult`
6. 发送 preliminary/refined 阶段 callback
7. 将结果保存到 `event_store`
8. 通过 `GET /v1/events/{event_id}` 查询结果

主链路实现位置：

- `src/ares_agent/api/app.py`
- `src/ares_agent/workflows/inspection_event_workflow.py`
- `src/ares_agent/model_clients/http_clients.py`
- `src/ares_agent/plugins/http_callback.py`
- `src/ares_agent/infra/event_store.py`

## 4. 完整性评估

### 4.1 接入层

完整性结论：`通过`

当前已经具备：

- `FastAPI` 应用入口
- 健康检查接口
- 巡检输入接口
- 事件查询接口
- 本地 stub 模型接口

说明：

- API 层已经不是单纯 demo handler，而是能承载完整最小链路的接入层
- 请求失败和工作流失败会返回结构化失败结果

### 4.2 编排层

完整性结论：`通过`

当前 workflow 已经具备：

- preliminary
- segmentation
- evidence_judge

并已覆盖：

- 正常 refined 分支
- callback failure 分支
- fixture / 文件缺失分支
- `segmentation_status=failed` 提前终止分支

说明：

- 当前 workflow 已经具备最小闭环需要的分支控制能力
- 至少在 MVP 层面，不再是“只有 happy path”

### 4.3 模型接入层

完整性结论：`通过（MVP 级）`

当前支持两种形态：

- fixture-backed mock clients
- local HTTP stub-backed clients

这意味着：

- 本地单元测试可以覆盖契约
- 本地集成测试可以模拟真实 `SGLang/vLLM` 与 `FastAPI SAM3` 的协议形态

但该层仍未完成：

- 真实外部模型服务稳定联调
- 真实异常码、慢响应、非标准返回的全量验证

### 4.4 callback 与事件结果层

完整性结论：`基本通过`

当前已具备：

- preliminary/refined 同一 `event_id`
- callback 开关控制
- callback retry/backoff/timeout
- 结果入库
- 结果查询

当前限制：

- 事件存储仍然是内存级
- callback 尚未具备幂等和失败审计链

## 5. 流程联通性评估

### 5.1 VLM-1 -> SAM3

联通结论：`通过`

已联通字段：

- `violation_category`
- `segmentation_targets`
- `relation_hint`

`SAM3` 输入已收敛为：

- `image_uri`
- `targets`

### 5.2 SAM3 -> VLM-2

联通结论：`通过`

已联通字段：

- `overlay_image`
- `mask_labels`
- `relation_hint`
- `evidence_basis_summary`

并且当前约束已经落实：

- `overlay_image` 是主视觉输入
- `VLM-2` 不再依赖继续传原图链接

### 5.3 callback / store / query

联通结论：`通过`

已联通能力：

- 同一事件的阶段结果可发送 callback
- 最终结果可入 `event_store`
- 结果可按 `event_id` 查询

说明：

- 这条链使得“输入图像 -> 结果事件 -> 查询回放”已经成为真实闭环

## 6. 验证状态

当前验证方式包括：

- 单元测试
- 近集成级 HTTP roundtrip 测试
- mock fixture 驱动
- local stub service 驱动

当前测试结果：

- `uv run pytest tests/unit`
- 结果：`72 passed`

这说明当前 MVP 的最小链路在代码层和测试层是一致的。

## 7. 当前未完成项

当前没有阻断最小链路的“断点型缺陷”，但仍存在明显生产化缺口：

- 无持久化数据库
- 无对象存储
- 无真实模型服务稳定联调结论
- 无人工复核闭环
- 无生产级可观测性与审计体系
- `enable_async_refine` 与 `enable_manual_review` 尚未真正驱动 workflow 分支

## 8. 收口结论

最终结论如下：

- 最小链路完整性：`通过`
- 流程联通性：`通过`
- 配置/契约一致性：`基本通过`
- 生产可交付性：`未通过`

因此，当前项目可以被定义为：

- 一个结构清晰、链路完整、测试充分的 `MVP 闭环 demo`

但不能被定义为：

- 一个可直接外部稳定交付的生产后端

## 9. 下一步建议

接下来的工作不应再以“补更多 demo 功能”为主，而应聚焦以下生产化主线：

1. 真实生产级持久化
2. 真实外部模型服务稳定联调
3. 人工复核闭环
4. 生产级可观测性与审计

这些内容的规划见下一份文档：

- `docs/plans/2026-03-11-productionization-next-steps-plan.md`
