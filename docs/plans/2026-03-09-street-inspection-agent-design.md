# 城市街道视觉巡检后端 Agent 设计

## 1. 目标

设计一个服务城市街道巡检机器狗的视觉巡检后端 Agent。系统接收机器狗上传的街景图片与元数据，基于现有微调 VLM 和 SAM3 模型完成违规初判、证据提取、二次审证、事件归档，并将结果回传后台管理服务。

当前目标不是训练新模型，而是设计一套可运行、可审计、可扩展的后端编排架构。

## 2. 设计原则

- 采用分层编排式 Agent 后端，而不是单体识别服务
- 同时支持同步快反馈和异步精反馈
- 同一帧图片的同步链路和异步链路共享同一个 `event_id`
- `SAM3` 负责提取违规判定依据，不直接做最终归档判决
- 第二次 `VLM` 负责按类目规则审证
- 标准类目和开放风险并存，但开放风险不污染标准执法类目
- 回传层插件化，但插件职责仅限于适配后台管理服务

## 3. 违规类别范围

首期标准类目如下：

- `road_occupying_vendor`
- `goods_blocking_road`
- `unauthorized_electrical_wiring`
- `motor_vehicle_illegal_parking`
- `nonmotor_vehicle_illegal_parking`
- `vagrants_blocking_roadway`
- `begging_blocking_roadway`
- `off_leash_dog_nuisance`
- `staff_not_wear_mask`

同时支持 `open_risk` 输出，用于记录不属于上述标准类目但具有风险提示价值的异常线索。

## 4. 总体架构

系统建议拆为 5 层：

### 4.1 Ingestion Gateway

负责：

- 接收图片、设备 ID、任务 ID、时间、位置、相机信息
- 生成 `frame_id`
- 生成稳定的 `event_id`
- 做幂等去重、图片质量检查、原图存储、任务入队

### 4.2 Orchestrator Agent Core

主编排内核，负责：

- 管理事件生命周期
- 驱动同步初判链路和异步精检链路
- 根据配置决定是否启用异步证据强化
- 根据类目策略决定是否需要人工复核
- 控制结果何时可归档和何时可回传

### 4.3 Model Capability Layer

封装模型能力：

- `VLM-1`：同步初判
- `SAM3`：违规判定依据分割
- `VLM-2`：对分割可视化结果做规则复判

### 4.4 Evidence & Event Layer

负责统一构建：

- `violation_event`
- `evidence_package`

并把同步阶段和异步阶段的结果更新到同一个事件对象中。

### 4.5 Sink Plugin Layer

负责把结果回传后台管理服务。插件层不介入识别和业务决策，只做：

- 协议适配
- 字段映射
- 鉴权签名
- 重试与超时处理

支持同步反馈和异步反馈两种回传。

## 5. 双链路工作流

### 5.1 同步链路

目标是快速输出 `preliminary_event_feedback`，用于上层系统快速感知风险。

流程：

1. 接收原图和元数据
2. 创建 `event_id`
3. 调用 `VLM-1` 进行快速初判
4. 生成同步阶段结果
5. 通过 `SinkPlugin` 回传后台管理服务

同步输出建议包含：

- `event_id`
- `frame_id`
- `stage=preliminary`
- 疑似违规类别及 Top-K
- 风险等级
- 初判置信度
- 是否建议补拍/复拍
- 是否需要进入异步精检
- 开放风险提示

### 5.2 异步链路

目标是完成证据强化、规则审证和正式归档。

流程：

1. 读取同一 `event_id` 的原图和同步初判结果
2. 根据初判类别和目标提示调用 `SAM3`
3. 生成 `mask`、裁剪图、叠图、边界框、面积比等候选证据材料
4. 调用 `VLM-2`，输入原图、裁剪图、叠图、初判类别、类目规则模板
5. 生成规则复判结论
6. 更新 `violation_event`
7. 构建 `evidence_package`
8. 通过 `SinkPlugin` 回传后台管理服务

异步结果不是新事件，而是对同一 `event_id` 的补充更新。

## 6. 模型职责划分

### 6.1 第一次 VLM：同步初判

负责：

- 标准类目初判
- 开放风险描述
- 风险等级输出
- 补拍/复拍建议
- 为异步链路提供候选目标提示

建议输出：

- `closed_set_topk`
- `open_risk_hints`
- `risk_level`
- `need_retake`
- `evidence_targets`

### 6.2 SAM3：违规依据提取

`SAM3` 的职责不是分割“违规主体”，而是分割“违规判定依据要素”。

例如：

- `road_occupying_vendor`
  分割摊位、棚具、货物、店门边界、人行道、车道
- `goods_blocking_road`
  分割货物、材料、宣传牌、垃圾、人行道区域
- `unauthorized_electrical_wiring`
  分割电线、充电器、电动车、可疑电源延伸区域
- `motor_vehicle_illegal_parking`
  分割车辆、人行道、公交站台、非划线区域
- `nonmotor_vehicle_illegal_parking`
  分割非机动车、人行道、车道，并辅助判断无人使用状态
- `vagrants_blocking_roadway`
  分割人物与道路位置关系要素
- `begging_blocking_roadway`
  分割人物、乞讨工具、道路位置关系要素
- `off_leash_dog_nuisance`
  分割人、狗、可能的 leash 区域
- `staff_not_wear_mask`
  分割工作人员面部区域和口罩相关区域

### 6.3 第二次 VLM：规则审证

`VLM-2` 不判断“分割是否命中主体”，而判断“这些依据要素是否足以支撑违规类别成立”。

建议输出 4 个核心结论：

- `evidence_basis_match`
- `violation_relation_confirmed`
- `exception_excluded`
- `archive_readiness`

其中：

- `evidence_basis_match`
  判断分割依据是否符合该类目定义
- `violation_relation_confirmed`
  判断依据要素之间是否构成违规关系
- `exception_excluded`
  判断该类目的正常例外是否已排除
- `archive_readiness`
  判断证据是否足够用于归档、回传、或进入人工复核

## 7. 类目规则与证据锚点

### 7.1 `road_occupying_vendor`

关注：

- 商户或流动摊贩摆摊、设棚、堆放物品
- 是否超出店门口经营边界
- 是否占用人行道或车道

例外检查：

- 景观类物品
- 书报亭附近合理摆放

### 7.2 `goods_blocking_road`

关注：

- 货物、材料、宣传牌、垃圾是否位于人行道
- 是否形成通行阻碍

### 7.3 `unauthorized_electrical_wiring`

关注：

- 是否存在从室内或商铺延伸到户外的电线
- 是否用于给电动车充电

### 7.4 `motor_vehicle_illegal_parking`

关注：

- 机动车是否占用人行道
- 是否占用公交站台
- 是否停放在非划线区域

### 7.5 `nonmotor_vehicle_illegal_parking`

关注：

- 非机动车是否占用人行道或车道
- 是否处于无人使用状态

### 7.6 `vagrants_blocking_roadway`

关注：

- 衣衫褴褛、头发凌乱的人
- 是否倚坐或躺在路旁或路中央
- 是否影响市容

### 7.7 `begging_blocking_roadway`

关注：

- 衣衫褴褛、头发凌乱的人
- 是否携带乞讨工具
- 是否在路边或路中央形成占道

### 7.8 `off_leash_dog_nuisance`

关注：

- 行人与宠物狗是否存在同行关系
- 狗是否未被 leash 约束

### 7.9 `staff_not_wear_mask`

关注：

- 是否为餐饮商户工作人员
- 是否未佩戴口罩

## 8. 输出对象设计

### 8.1 violation_event

作为系统联动主对象，建议字段包括：

- `event_id`
- `frame_id`
- `device_id`
- `task_id`
- `occur_time`
- `location`
- `stage`
- `category_code`
- `category_name`
- `risk_level`
- `prelim_confidence`
- `final_confidence`
- `need_retake`
- `review_required`
- `open_risk_flag`
- `open_risk_text`
- `event_status`
- `event_version`

### 8.2 evidence_package

作为审证与留档对象，建议字段包括：

- `event_id`
- `source_image_uri`
- `crop_image_uris`
- `overlay_image_uris`
- `mask_uri`
- `bbox_list`
- `area_ratio`
- `evidence_basis_summary`
- `violation_relation_summary`
- `exception_check_result`
- `archive_readiness`
- `rejection_reason`
- `model_trace`

### 8.3 双阶段回传对象

#### preliminary_event_feedback

建议字段：

- `event_id`
- `frame_id`
- `stage=preliminary`
- `suspected_categories`
- `risk_level`
- `prelim_confidence`
- `need_retake`
- `open_risk_hints`
- `async_enqueued`

#### refined_event_feedback

建议字段：

- `event_id`
- `frame_id`
- `stage=refined`
- `final_category`
- `final_confidence`
- `evidence_package`
- `archive_readiness`
- `review_required`
- `rejection_reason`
- `event_version`

## 9. Sink Plugin 设计

### 9.1 职责边界

`SinkPlugin` 只负责把结果回传后台管理服务，不负责业务规则判断。

其职责包括：

- 支持同步链路回传
- 支持异步链路回传
- 保证同一帧同步和异步结果共享一个 `event_id`
- 把异步结果作为同一逻辑事件的补充更新进行回传

### 9.2 插件接口建议

统一输入：

- `event_payload`
- `runtime_config`

统一输出：

- `success`
- `status_code`
- `backend_trace_id`
- `retryable`
- `error_message`

### 9.3 可支持的回传方式

- `http_callback`
- `message_queue`
- `grpc`

## 10. 状态机设计

建议事件状态机如下：

- `received`
- `prelim_analyzing`
- `prelim_ready`
- `prelim_callback_sent`
- `async_queued`
- `evidence_segmenting`
- `evidence_judging`
- `refined_ready`
- `manual_review_required`
- `archived`
- `refined_callback_sent`
- `closed`
- `failed`

建议流转：

1. 图片接入后进入 `received`
2. 调用 `VLM-1` 时进入 `prelim_analyzing`
3. 初判完成进入 `prelim_ready`
4. 同步结果回传成功进入 `prelim_callback_sent`
5. 需要异步精检则进入 `async_queued`
6. 调用 `SAM3` 进入 `evidence_segmenting`
7. 调用 `VLM-2` 进入 `evidence_judging`
8. 审证通过进入 `refined_ready`
9. 若证据不足但需人工介入则进入 `manual_review_required`
10. 归档完成进入 `archived`
11. 异步结果回传成功进入 `refined_callback_sent`
12. 生命周期结束进入 `closed`

失败则根据阶段进入：

- `prelim_failed`
- `segmentation_failed`
- `evidence_judge_failed`
- `callback_failed`

也可以统一映射到 `failed`，但建议保留阶段化失败原因。

## 11. 配置文件设计

建议使用一个启动配置文件控制运行策略，例如 `agent_config.yaml`。

```yaml
agent:
  service_name: street-inspection-agent
  region: default

ingestion:
  image_storage: local
  dedup_window_seconds: 30
  min_image_width: 640
  min_image_height: 480

orchestrator:
  enable_async_refine: true
  preliminary_timeout_ms: 2500
  refined_timeout_ms: 15000
  max_retry: 3
  force_manual_review_categories:
    - vagrants_blocking_roadway
    - begging_blocking_roadway
    - staff_not_wear_mask

models:
  vlm_prelim:
    provider: local
    model_name: ft-vlm-inspection
    timeout_ms: 2500
  sam3:
    provider: local
    model_name: sam3-evidence
    timeout_ms: 8000
  vlm_judge:
    provider: local
    model_name: ft-vlm-inspection
    timeout_ms: 5000

taxonomy:
  closed_set_categories:
    - road_occupying_vendor
    - goods_blocking_road
    - unauthorized_electrical_wiring
    - motor_vehicle_illegal_parking
    - nonmotor_vehicle_illegal_parking
    - vagrants_blocking_roadway
    - begging_blocking_roadway
    - off_leash_dog_nuisance
    - staff_not_wear_mask
  enable_open_risk: true

callback:
  plugin: http_callback
  endpoint: https://backend.example/api/v1/events/callback
  auth_type: bearer
  auth_token_env: BACKEND_CALLBACK_TOKEN
  timeout_ms: 3000
  retry:
    max_attempts: 5
    backoff_ms: 1000
  send_preliminary: true
  send_refined: true

review:
  enable_manual_review: true
  archive_without_review: false
```

配置设计原则：

- 模型、链路、类目、回传、复核策略都应配置化
- 同一部署实例可通过配置切换回传协议与回传开关
- 强制人工复核类目应显式配置

## 12. 异常处理设计

### 12.1 接入阶段异常

场景：

- 图片损坏
- 元数据缺失
- 重复帧
- 图片尺寸过小

处理：

- 拒绝入队并记录原因
- 若可回传则回传 `invalid_input`
- 为重复帧复用既有 `event_id`

### 12.2 同步初判异常

场景：

- `VLM-1` 超时
- 模型不可用
- 初判结果为空

处理：

- 重试有限次数
- 超过阈值后进入降级状态
- 可回传 `preliminary_unavailable`
- 若系统允许，仍保留原图供后续异步补算

### 12.3 SAM3 分割异常

场景：

- 无法找到候选依据区域
- 掩码异常
- 分割超时

处理：

- 对该事件标记 `segmentation_failed`
- 进入人工复核或弱信号丢弃
- 不直接生成正式归档结论

### 12.4 第二次 VLM 审证异常

场景：

- 无法确认证据依据
- 规则关系不成立
- 例外无法排除
- 模型响应异常

处理：

- 输出 `archive_readiness=false`
- 标记 `review_required=true`
- 记录 `rejection_reason`
- 不把该结果当作正式闭环事件

### 12.5 回传异常

场景：

- 后台管理服务超时
- 鉴权失败
- 字段校验失败
- 服务端幂等冲突

处理：

- 由 `SinkPlugin` 按策略重试
- 保留本地待回传状态
- 成功后更新事件版本
- 多次失败后进入 `callback_failed`

## 13. 人工复核建议

以下情况建议强制人工复核：

- `vagrants_blocking_roadway`
- `begging_blocking_roadway`
- `staff_not_wear_mask`
- `archive_readiness=false`
- `exception_excluded` 无法确认
- 同步和异步结论明显冲突

## 14. 测试建议

### 14.1 单元测试

- 事件状态机流转
- `event_id` 生成与幂等复用
- 配置加载
- 回传插件输入输出校验

### 14.2 集成测试

- 同步链路回传
- 异步链路回传
- 同一帧共享 `event_id`
- 异步链路对同一事件做更新而非新建

### 14.3 回归测试

- 每个标准类目至少准备正样本和混淆样本
- 重点覆盖例外场景
- 覆盖开放风险不误入标准执法类目

## 15. 当前未决项

以下内容仍需后续结合真实部署条件细化：

- 每台机器狗的上传频率与峰值吞吐
- 同步初判允许的最大时延
- 后台管理服务的具体接口协议
- 人工复核平台是否由同一后台承载
- 开放风险的展示与闭环策略
