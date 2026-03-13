# 日志系统设计方案

## 1. 文档目的

本文档定义当前 `ares_agent` 项目的接口链路日志系统设计，目标是解决：

- 线上接口排障困难
- 联调时难以判断失败边界
- 外部依赖调用缺少过程证据

当前仓库已经有接口输入输出 JSON 存储，因此本方案不把日志设计成业务载荷归档系统，而是聚焦：

- 链路过程可观测性
- 阶段耗时与失败边界定位
- `event_id` 维度的全链路关联
- `request_id` 维度的 HTTP 入口兜底关联

## 2. 设计目标

本方案的主要目标如下：

1. 所有核心链路日志都能通过同一个 `event_id` 关联。
2. 在请求还未进入业务阶段时，仍可通过 `request_id` 排查入口问题。
3. 所有阶段边界都记录开始、成功、失败、耗时。
4. 外部 HTTP 调用和 callback 重试可清晰还原。
5. 不重复打印完整输入输出 JSON，避免日志噪音和敏感信息扩散。

## 3. 推荐技术栈

推荐采用以下组合：

- `structlog`
  - 负责结构化 JSON 日志输出
  - 支持 `contextvars` 绑定上下文字段
- `asgi-correlation-id`
  - 负责为 FastAPI 请求生成或透传 `request_id`
- 项目内轻量装饰器
  - 基于统一装饰器记录阶段开始、结束、异常、耗时

不推荐当前阶段直接以 OpenTelemetry 作为主方案。
原因不是它不好，而是它对当前项目“先解决线上排障与联调定位”的问题来说偏重，会增加接入与维护成本。

## 4. 关联键策略

### 4.1 `event_id` 作为主关联键

当前项目中的 `event_id` 是由以下字段稳定生成：

- `image_uri`
- `camera_id`
- `location`
- `device_id`
- `task_id`
- `occur_time`

这意味着同一个巡检事件在以下阶段中可以天然共享同一个键：

- `/v1/inspection-items`
- `preliminary`
- `segmentation`
- `evidence_judge`
- `callback`
- `event_store`

因此，日志检索和问题排查应以 `event_id` 为主。

### 4.2 `request_id` 作为辅助关联键

`request_id` 主要用于补足 HTTP 层问题，例如：

- 请求在生成 `event_id` 前就失败
- 参数校验失败
- 上游网关或调用方只认 `request_id`
- 同一 `event_id` 被重复提交时区分不同请求

## 5. 日志分层设计

### 5.1 入口层

在 FastAPI middleware 中完成：

- 生成或透传 `request_id`
- 记录接口入口日志
- 尽早从请求体推导 `event_id`
- 将 `request_id`、`event_id` 绑定到上下文

推荐日志事件：

- `inspection.request.received`
- `inspection.request.completed`
- `inspection.request.failed`

### 5.2 工作流阶段层

对以下边界使用装饰器：

- `ingest_inspection_item`
- `preliminary`
- `segmentation`
- `evidence_judge`
- `HttpCallbackPlugin.send`
- `MinioS3UriResolver.resolve`
- `InMemoryEventStore.save`
- `InMemoryEventStore.get`

模型客户端边界也应纳入：

- `SglangVlmPreliminaryClient.analyze`
- `Sam3FastApiClient.segment`
- `SglangVlmJudgeClient.judge`

每个装饰器统一记录：

- `*.started`
- `*.succeeded`
- `*.failed`
- `duration_ms`

### 5.3 基础设施层

通过统一日志初始化模块负责：

- `structlog` processor 配置
- JSON renderer
- 日志级别控制
- 公共字段注入
- 异常格式统一

建议新增模块：

- `src/ares_agent/infra/logging.py`
- `src/ares_agent/infra/log_context.py`
- `src/ares_agent/infra/log_decorators.py`

## 6. 字段规范

### 6.1 通用字段

所有日志统一包含：

- `timestamp`
- `level`
- `event`
- `service`
- `request_id`
- `event_id`
- `stage`
- `duration_ms`

### 6.2 调试字段

按需追加：

- `chain_mode`
- `camera_id`
- `location`
- `model_client`
- `endpoint_host`
- `callback_status_code`
- `retry_attempt`
- `failed_step`
- `send_preliminary`
- `send_refined`

### 6.3 错误字段

失败日志至少包含：

- `error_type`
- `error_message`
- `exception_class`
- `stage`
- `event_id`
- `request_id`

## 7. 装饰器设计

装饰器职责必须保持很薄，只做以下事情：

1. 记录开始日志
2. 自动统计耗时
3. 记录成功日志
4. 记录失败日志并原样抛出异常

装饰器不应：

- 修改业务返回值语义
- 吞掉异常
- 写入完整业务载荷
- 持有业务判断逻辑

建议抽象两类装饰器：

- `@log_stage(stage_name, field_extractor=...)`
- `@log_external_call(target_name, field_extractor=...)`

其中 `field_extractor` 用于从参数中提取摘要字段，例如：

- `camera_id`
- `location`
- `category_code`
- `endpoint_host`

## 8. 日志内容边界

本方案强调“过程证据”，不强调“全量镜像”。

应该记录：

- 阶段名
- 成功/失败状态
- 耗时
- 重试次数
- 目标服务主机
- 配置开关摘要
- 分类结果摘要

不应该记录：

- 完整 prompt 文本
- 完整模型 message 内容
- 完整 callback body
- 完整 presigned URL
- 完整认证 token

## 9. 脱敏要求

必须从第一版开始执行以下规则：

- `Authorization` 仅记录是否存在，不记录值
- `image_uri` 仅记录 scheme、bucket、host 或摘要
- presigned URL 仅记录 `host` 和对象摘要，不记录签名串
- callback 仅记录 `event_id`、`stage`、`status_code`、`backend_trace_id`
- 模型请求只记录模型名、endpoint、耗时、结果摘要

## 10. 异常与失败日志

当前项目已使用 `WorkflowStageError` 包装阶段异常。
日志系统不改变该错误模型，只补足过程日志。

具体策略：

- 装饰器在函数抛异常时记录 `*.failed`
- API 层在返回失败响应前记录 `inspection.request.failed`
- callback 重试每次都记录一次 `callback.attempt`
- 最终失败时记录 `callback.failed`

这样排查时可以同时看到：

- 哪个阶段先失败
- 失败前是否有重试
- 接口最终返回了什么失败类型

## 11. 配置设计

建议在 `infra/config.py` 中新增：

```yaml
logging:
  enabled: true
  level: INFO
  json: true
  include_request_id: true
  include_event_id: true
  log_model_payload_summary: true
  log_callback_payload_summary: true
```

建议对应模型：

- `LoggingSettings`
- `AppConfig.logging`

目的：

- 控制日志级别
- 控制 JSON 输出开关
- 控制调试摘要字段是否开启
- 为后续接入日志平台保留兼容空间

## 12. 分期实施建议

### 第一阶段：最小可用链路日志

优先完成：

1. `structlog` 初始化
2. FastAPI middleware 绑定 `request_id`
3. API 入口绑定 `event_id`
4. workflow 三阶段装饰器
5. 模型 HTTP 调用日志
6. callback 重试日志

这一步完成后，已经能解决绝大多数线上排障与联调定位问题。

### 第二阶段：边缘能力补齐

继续补充：

1. `event_store` 日志
2. `image_uri_resolver` 日志
3. 启动配置摘要日志
4. 统一错误出口日志
5. 更细粒度的字段脱敏和采样策略

## 13. 测试建议

应新增以下测试：

### 13.1 单元测试

- 装饰器在成功路径输出 `started/succeeded`
- 装饰器在失败路径输出 `failed`
- 日志中包含 `event_id/request_id/stage/duration_ms`

### 13.2 集成测试

- 一次 `/v1/inspection-items` 请求中，所有阶段日志共享同一个 `event_id`
- callback 重试时能看到连续 `attempt` 记录
- `segmentation failed` 时能准确标识失败边界

### 13.3 回归测试

- mock 模式与 http 模式都能产生日志
- 参数校验失败时只有 `request_id` 也可排查
- `event_store` 读写后日志字段不丢失

## 14. 预期收益

完成本方案后，排障时可直接回答以下问题：

- 这次请求有没有进入业务层？
- 这条事件在哪个阶段失败？
- 外部模型调用是否发出？耗时多少？
- callback 是否重试？重试几次？
- 最终失败是业务失败、外部依赖失败，还是入口请求问题？

## 15. 结论

当前项目最合适的路线不是手写一套日志框架，也不是直接引入重型 tracing 体系，而是：

- 用 `structlog` 提供结构化日志
- 用 `asgi-correlation-id` 提供 HTTP 请求关联
- 用轻量装饰器覆盖工作流和依赖边界
- 用 `event_id` 作为主关联键，`request_id` 作为辅助关联键

这样可以在不重复造轮子的前提下，较低成本地补齐当前最缺的链路排障能力。
