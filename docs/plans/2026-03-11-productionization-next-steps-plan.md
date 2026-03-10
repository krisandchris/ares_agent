# 生产化下一步规划文档

## 1. 文档目的

本文档基于当前 `ares_agent` 的 MVP 收口状态，规划从 `mocked closed-loop demo` 走向“可外部联调的后端 MVP / 生产前版本”的下一步工作安排。

当前规划聚焦以下 4 条主线：

1. 真实生产级持久化
2. 真实外部模型服务稳定联调
3. 人工复核闭环
4. 生产级可观测性与审计

## 2. 规划原则

下一阶段必须坚持以下原则：

- 先稳协议，再接真实服务
- 先补基础设施，再加运营能力
- 不再继续扩张 mock feature
- 尽量让每个阶段都形成可独立验收的交付物

## 3. 总体阶段划分

建议将下一步拆成 4 个阶段：

### Phase 1：持久化与状态落库

目标：

- 把当前内存态事件结果提升为可持久化状态

交付：

- 数据库 schema
- repository 层
- event store 持久化实现
- callback / workflow 结果落库

完成标志：

- 服务重启后仍可查询事件
- preliminary / refined / failed 都能稳定落库

### Phase 2：真实模型服务联调

目标：

- 将 `VLM-1 / SAM3 / VLM-2` 从 stub/mock 切换到真实外部服务

交付：

- 真实 `SGLang/vLLM` preliminary/judge 联调
- 真实 `SAM3 FastAPI` 联调
- 真实错误码、超时、异常响应处理

完成标志：

- 在真实模型环境下跑通最小链路
- 形成稳定的接口契约记录

### Phase 3：人工复核闭环

目标：

- 将当前“review_required”结果从标记字段升级为可操作流程

交付：

- review task 数据模型
- review queue / review status
- 审核结果回写机制

完成标志：

- 审核事件能够形成闭环状态迁移

### Phase 4：可观测性与审计

目标：

- 为生产运行补齐日志、指标、审计证据和回溯能力

交付：

- 结构化日志
- metrics
- request / model / callback trace
- evidence / decision audit record

完成标志：

- 线上问题能够基于日志和审计记录快速回溯

## 4. 主线一：真实生产级持久化

### 4.1 目标

将：

- `InMemoryEventStore`

替换为：

- 数据库持久化存储

### 4.2 推荐范围

首期至少落以下实体：

- `inspection_event`
- `preliminary_result`
- `segmentation_result`
- `evidence_judgment_result`
- `callback_delivery`

### 4.3 必要字段

至少应保存：

- `event_id`
- `frame_id`
- `device_id`
- `task_id`
- `occur_time`
- 当前 `stage`
- preliminary 输出摘要
- segmentation 输出摘要
- refined judgment 输出摘要
- callback 投递状态

### 4.4 建议安排

建议顺序：

1. 设计 schema
2. 实现 repository 层
3. 替换 event store
4. 在 workflow 成功/失败分支统一落库

### 4.5 验收标准

- 任意阶段结果都能查询
- 服务重启不丢事件
- failed 事件也可回放

## 5. 主线二：真实外部模型服务稳定联调

### 5.1 目标

从：

- local HTTP stub

切换到：

- 真实 `SGLang/vLLM`
- 真实 `SAM3 FastAPI`

### 5.2 重点工作

#### VLM-1

- 验证 OpenAI-compatible chat completion 返回是否稳定
- 验证 JSON content 是否始终满足 `PreliminaryResult`
- 记录 bad case：
  - 非 JSON
  - 字段缺失
  - 错误类别

#### SAM3

- 验证 `image_uri + targets` 协议
- 验证 `overlay_image / mask_labels / segmentation_status / evidence_basis_summary`
- 明确真实服务返回空结果时的标准化策略

#### VLM-2

- 验证 `overlay_image + configured prompt` 路径
- 验证 evidence judgment 字段稳定性

### 5.3 联调产出

每个模型服务都应形成：

- 请求样例
- 成功响应样例
- 失败响应样例
- 异常处理策略

### 5.4 验收标准

- 使用真实外部模型服务跑通完整链路
- 对关键错误场景形成确定处理方式

## 6. 主线三：人工复核闭环

### 6.1 目标

把当前的：

- `review_required`

从一个布尔结果，升级成可执行的人工复核闭环。

### 6.2 需要新增的对象

- `review_task`
- `review_status`
- `review_decision`
- `review_operator`
- `review_time`

### 6.3 建议流程

1. `VLM-2` 输出 `review_required=true`
2. 创建 `review_task`
3. 后台管理服务或审核端领取任务
4. 人工给出：
   - confirm
   - reject
   - modify_category
5. 审核结果回写原事件

### 6.4 验收标准

- review-required 事件不再只是静态字段
- 审核意见可以改变事件最终状态

## 7. 主线四：生产级可观测性与审计

### 7.1 目标

让系统在真实环境里具备：

- 可定位问题
- 可追踪决策
- 可回放证据

### 7.2 日志

至少补：

- `event_id`
- `frame_id`
- `device_id`
- `stage`
- `category_code`
- `callback_status`
- `error_type`

### 7.3 指标

至少补：

- preliminary 成功率
- segmentation 成功率
- VLM-2 judgment 成功率
- callback 成功率
- 各阶段平均耗时

### 7.4 审计

至少保存：

- 原始输入元数据
- VLM-1 输出
- SAM3 输出摘要
- VLM-2 输出
- callback 历史
- review 历史

### 7.5 验收标准

- 能基于 `event_id` 回溯整条链路
- 能定位失败点与耗时瓶颈

## 8. 建议执行顺序

建议顺序如下：

1. 持久化
2. 真实模型联调
3. 人工复核闭环
4. 可观测性与审计

原因：

- 没有持久化，真实联调结果难以沉淀
- 没有真实联调，人工复核和审计都只是空架子
- 审计和可观测性应建立在相对稳定的真实运行链路之上

## 9. 每阶段输出物

### 阶段 1 输出

- 数据库 schema 文档
- repository 实现
- 持久化 event store 替换方案

### 阶段 2 输出

- 三个真实模型服务联调记录
- 真实错误样例库
- 契约对齐文档

### 阶段 3 输出

- review task 状态机
- review API / callback 设计
- 审核回写策略

### 阶段 4 输出

- logging 规范
- metrics 清单
- audit record schema

## 10. 最终目标

这 4 条主线完成后，项目应从：

- `MVP 闭环 demo`

进入：

- `可外部联调的后端 MVP`

再进一步，才适合进入真正的生产试运行阶段。
