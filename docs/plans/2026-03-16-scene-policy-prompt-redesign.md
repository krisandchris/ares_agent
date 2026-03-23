# Scene Policy and Prompt Injection Redesign

## Goal
把当前 VLM-1 的场景策略从“弱提示”改成“检测空间约束”。重设计 `scene_policies`、`SceneActivationContext` 和 prompt 注入流程，使相机与位置共同决定最终可检测类别集合，并把 `location_constraints` 正式注入 VLM-1 prompt。

## Current Problems
- `enabled_categories` 当前采用覆盖/合并去重，不是相机与位置共同约束。
- `location_constraints` 虽被解析，但未进入 prompt。
- `priority_categories` 当前既承担“排序”又间接决定注入类别定义，语义混乱。
- `scene_hint` 只提供弱提示，不构成有效检测约束。
- `category_registry` 当前只按 `priority_categories` 渲染，和真实检测空间不一致。

## Design Principles
- 只保留一个最终类别集合：`effective_enabled_categories`
- `effective_enabled_categories` 永远由 `camera.enabled_categories ∩ location.enabled_categories` 计算
- `override` 不允许直接改类别集合
- `location_constraints` 进入 prompt，参与空间关系判断
- `category_registry` 只为最终允许类别集合提供定义
- 删除无效场景元信息：`priority_categories`、`scene_hint`

## Proposed `scene_policies` Structure

### Keep
- `enabled_categories`
- `disabled_categories`
- `location_constraints`

### Remove
- `priority_categories`
- `scene_hint`

### Proposed YAML shape
```yaml
scene_policies:
  camera_defaults:
    front:
      enabled_categories:
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
        - goods_blocking_road
    left:
      enabled_categories:
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
    right:
      enabled_categories:
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask

  location_defaults:
    南山路:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - motor_vehicle_illegal_parking
        - nonmotor_vehicle_illegal_parking
      location_constraints:
        - focus on roadside, sidewalk, storefront frontage, and pedestrian passage
    水坊街:
      enabled_categories:
        - road_occupying_vendor
        - goods_blocking_road
        - unauthorized_electrical_wiring
        - staff_not_wear_mask
      location_constraints:
        - focus on storefront frontage, sidewalk occupation, and outdoor charging behavior

  overrides:
    南山路:
      front:
        location_constraints:
          - pay extra attention to mixed curbside occupation near crosswalk entrance
      left:
        location_constraints:
          - focus on dense storefront frontage and outdoor charging corners
```

## Resolution Flow

### Inputs
- `camera_rule`
- `location_rule`
- `override_rule`

### Effective enabled categories
1. Compute:
   - `effective_enabled_categories = camera.enabled_categories ∩ location.enabled_categories`
2. Merge disabled categories from camera/location.
3. Remove disabled categories from `effective_enabled_categories`.
4. `override` must not participate in category selection.

### Effective location constraints
1. If `override.location_constraints` is non-empty, use it directly.
2. Otherwise merge:
   - `camera.location_constraints + location.location_constraints`
3. De-duplicate while keeping order.

### Open risk guidance
- Keep current `open_risk_guidance_default` / override mechanism.

## New `SceneActivationContext`
Recommended fields:
- `camera_id`
- `location`
- `effective_enabled_categories`
- `disabled_categories`
- `location_constraints`
- `open_risk_guidance`

Remove:
- `priority_categories`
- `scene_hint`

## Prompt Injection

### `scene_activation_block_template`
Inject only:
- `enabled_categories`
- `location_constraints`
- `open_risk_guidance`

Recommended form:
```yaml
scene_activation_block_template: |
  Current detection scope:
  - enabled_categories: {enabled_categories}
  - location_constraints: {location_constraints}
  - open_risk_guidance: {open_risk_guidance}

  Use rules:
  - only classify within enabled_categories unless strong evidence supports open_risk
  - use location_constraints when judging spatial relations, occupation, obstruction, and storefront boundaries
```

### `category_focus_block_template`
Render category definitions for `effective_enabled_categories`:
```yaml
category_focus_block_template: |
  Allowed category references:
  {category_definitions}
```

## Category Registry Injection
- `CategoryDefinitionRenderer.render(...)` should accept `effective_enabled_categories`
- No longer render by `priority_categories`
- Inject full definition bundle for each allowed category:
  - `definition`
  - `common_objects`
  - `relation_focus`
  - `exceptions`

## Behavioral Effect
After redesign, VLM-1 prompt semantics become:
- These are the only standard categories you are allowed to classify.
- These are the spatial constraints for the current location.
- These are the formal definitions of the allowed categories.
- If evidence does not fit allowed standard categories but still indicates real risk, output `open_risk`.

This aligns prompt behavior with the actual scene policy instead of relying on weak hints.

## Implementation Impact

### Files to update
- `src/ares_agent/infra/config.py`
- `src/ares_agent/prompts/scene_activation.py`
- `src/ares_agent/prompts/preliminary_prompt.py`
- `src/ares_agent/prompts/builders.py`
- `config/prompt_config.example.yaml`
- `config/agent_config.example.yaml`
- prompt-related tests and snapshots

### Main code changes
- Remove `priority_categories` and `scene_hint` from config models and context model
- Make category selection strictly intersection-based
- Remove `override.enabled_categories` support
- Add `location_constraints` prompt injection
- Change category definition rendering source from priority list to effective enabled list

## Validation Focus
- `front + 南山路` should produce only the intersection categories
- `left/right + 水坊街` should exclude road-only categories
- `location_constraints` must appear in the final system prompt
- `category_definitions` must match `effective_enabled_categories`
- `disabled_categories` must successfully remove categories from the final set
- `override` must not be able to add or replace enabled categories
