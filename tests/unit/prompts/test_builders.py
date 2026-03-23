from textwrap import dedent

from ares_agent.domain.events import EventSeed
from ares_agent.infra.config import SceneActivationPolicyConfig, SceneActivationRule
from ares_agent.prompts.builders import ConfigurableInspectionPromptBuilder, DefaultInspectionPromptBuilder
from ares_agent.prompts.scene_activation import SceneActivationContext, ScenePolicyResolver
from type_helpers import image_url_part, make_candidate, make_preliminary_result, message_parts, text_part


def test_default_prompt_builder_builds_preliminary_messages_from_event_seed() -> None:
    builder = DefaultInspectionPromptBuilder()
    seed = EventSeed(
        image_uri="s3://street/frame-010.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-30",
        task_id="patrol-sh-010",
        occur_time="2026-03-09T11:00:00Z",
    )

    messages = builder.build_preliminary_messages(seed)

    assert messages[0]["role"] == "system"
    assert "preliminary inspection" in str(messages[0]["content"]).lower()
    user_content = message_parts(messages[1])
    assert text_part(user_content[0]) == "Analyze inspection image for violations."
    assert image_url_part(user_content[1]) == "s3://street/frame-010.jpg"


def test_default_prompt_builder_builds_judge_messages_with_preliminary_context() -> None:
    builder = DefaultInspectionPromptBuilder()
    preliminary = make_preliminary_result(
        environment_analysis="street storefront scene",
        scene_elements=["storefront", "stall", "sidewalk"],
        candidates=[
            make_candidate(
                violation_category="road_occupying_vendor",
                confidence=0.91,
                evidence_reasoning="stall extends into sidewalk",
                segmentation_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
                relation_hint="stall overlaps sidewalk outside storefront boundary",
            )
        ],
    )

    messages = builder.build_judge_messages(
        category_code="road_occupying_vendor",
        overlay_image="s3://mock/overlay.png",
        mask_labels=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        relation_hint="stall overlaps sidewalk outside storefront boundary",
        evidence_basis_summary="stall overlaps sidewalk boundary",
    )

    assert messages[0]["role"] == "system"
    assert "evidence judge" in str(messages[0]["content"]).lower()
    user_content = message_parts(messages[1])
    user_text = text_part(user_content[0])
    assert "category_code=road_occupying_vendor" in user_text
    assert "mask_labels=stall, storefront_boundary, sidewalk_or_roadway" in user_text
    assert "relation_hint=stall overlaps sidewalk outside storefront boundary" in user_text
    assert "evidence_basis_summary=stall overlaps sidewalk boundary" in user_text
    assert image_url_part(user_content[1]) == "s3://mock/overlay.png"
    assert "event_id=" not in user_text
    assert "segmentation_status=" not in user_text
    assert "risk_level=" not in user_text
    assert "prelim_confidence=" not in user_text
    assert "need_retake=" not in user_text


def test_configurable_prompt_builder_uses_resolver_when_scene_context_not_provided() -> None:
    class FakeResolver:
        def resolve(self, *, camera_id: str, location: str) -> SceneActivationContext:
            assert camera_id == "front"
            assert location == "南山路"
            return SceneActivationContext(
                camera_id=camera_id,
                location=location,
                enabled_categories=["goods_blocking_road"],
                location_constraints=["focus on roadside occupation"],
                open_risk_guidance="If strong evidence suggests uncategorized risk, output open_risk.",
            )

    builder = ConfigurableInspectionPromptBuilder(
        preliminary_role_block="ROLE BLOCK",
        preliminary_scene_activation_block_template=(
            "enabled_categories={enabled_categories}; location_constraints={location_constraints}; "
            "open_risk_guidance={open_risk_guidance}"
        ),
        preliminary_category_focus_block_template="CATEGORY FOCUS\n{category_definitions}",
        preliminary_reasoning_block="REASONING BLOCK",
        preliminary_output_contract_block="OUTPUT BLOCK",
        preliminary_user_template="Analyze inspection image for violations.",
        judge_system_template="JUDGE SYSTEM",
        judge_user_template="JUDGE USER {category_code}",
        scene_activation_resolver=FakeResolver(),
        category_registry={
            "goods_blocking_road": {
                "definition": "goods on sidewalk",
                "common_objects": ["goods", "sidewalk"],
                "relation_focus": ["obstruct_pedestrian_passage"],
                "exceptions": [],
            }
        },
        open_risk_guidance_default="Default open risk guidance.",
    )

    messages = builder.build_preliminary_messages(
        EventSeed(
            image_uri="s3://street/frame-010.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-30",
            task_id="patrol-sh-010",
            occur_time="2026-03-09T11:00:00Z",
        )
    )

    system_text = messages[0]["content"]
    assert "enabled_categories=goods_blocking_road" in system_text
    assert "location_constraints=focus on roadside occupation" in system_text
    assert "open_risk_guidance=If strong evidence suggests uncategorized risk, output open_risk." in system_text
    assert "CATEGORY FOCUS" in system_text
    assert "definition: goods on sidewalk" in system_text


def test_configurable_prompt_builder_renders_scene_specific_system_prompt_snapshots() -> None:
    builder = ConfigurableInspectionPromptBuilder(
        preliminary_role_block="ROLE BLOCK",
        preliminary_scene_activation_block_template=(
            "enabled_categories={enabled_categories}\nlocation_constraints={location_constraints}\nopen_risk_guidance={open_risk_guidance}"
        ),
        preliminary_category_focus_block_template="CATEGORY FOCUS\n{category_definitions}",
        preliminary_reasoning_block="REASONING BLOCK",
        preliminary_output_contract_block="OUTPUT BLOCK",
        preliminary_user_template="Analyze inspection image for violations.",
        judge_system_template="JUDGE SYSTEM",
        judge_user_template="JUDGE USER {category_code}",
        scene_activation_resolver=ScenePolicyResolver(
            SceneActivationPolicyConfig(
                camera_defaults={
                    "front": SceneActivationRule(
                        enabled_categories=[
                            "motor_vehicle_illegal_parking",
                            "nonmotor_vehicle_illegal_parking",
                            "goods_blocking_road",
                        ],
                    ),
                    "left": SceneActivationRule(
                        enabled_categories=[
                            "staff_not_wear_mask",
                            "goods_blocking_road",
                            "unauthorized_electrical_wiring",
                        ],
                    ),
                    "right": SceneActivationRule(
                        enabled_categories=[
                            "staff_not_wear_mask",
                            "goods_blocking_road",
                            "unauthorized_electrical_wiring",
                        ],
                    ),
                },
                location_defaults={
                    "南山路": SceneActivationRule(
                        enabled_categories=[
                            "motor_vehicle_illegal_parking",
                            "goods_blocking_road",
                            "staff_not_wear_mask",
                        ],
                        location_constraints=["focus on roadside occupation"],
                    ),
                    "水坊街": SceneActivationRule(
                        enabled_categories=[
                            "goods_blocking_road",
                            "unauthorized_electrical_wiring",
                            "staff_not_wear_mask",
                        ],
                        location_constraints=["focus on storefront frontage"],
                    ),
                },
            )
        ),
        category_registry={
            "motor_vehicle_illegal_parking": {
                "definition": "vehicle occupies prohibited area",
                "common_objects": ["motor_vehicle", "blind_path"],
                "relation_focus": ["vehicle_occupies_prohibited_area"],
                "exceptions": [],
            },
            "nonmotor_vehicle_illegal_parking": {
                "definition": "unattended nonmotor vehicle occupies walkway",
                "common_objects": ["e_bike", "sidewalk"],
                "relation_focus": ["unattended_vehicle_state"],
                "exceptions": [],
            },
            "goods_blocking_road": {
                "definition": "goods on sidewalk",
                "common_objects": ["goods", "sidewalk"],
                "relation_focus": ["obstruct_pedestrian_passage"],
                "exceptions": [],
            },
            "staff_not_wear_mask": {
                "definition": "catering staff missing mask",
                "common_objects": ["staff", "mask", "counter"],
                "relation_focus": ["staff_without_mask"],
                "exceptions": [],
            },
            "unauthorized_electrical_wiring": {
                "definition": "outdoor charging wire connected to electric vehicle",
                "common_objects": ["wire", "charger", "electric_vehicle"],
                "relation_focus": ["wire_connects_power_to_vehicle"],
                "exceptions": [],
            },
        },
        open_risk_guidance_default="If obvious risk exists outside prioritized categories, output open_risk.",
    )

    front_messages = builder.build_preliminary_messages(
        EventSeed(
            image_uri="s3://street/front.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-30",
            task_id="patrol-front",
            occur_time="2026-03-12T11:00:00Z",
        )
    )
    left_messages = builder.build_preliminary_messages(
        EventSeed(
            image_uri="s3://street/left.jpg",
            camera_id="left",
            location="南山路",
            device_id="dog-30",
            task_id="patrol-left",
            occur_time="2026-03-12T11:00:01Z",
        )
    )

    front_system = front_messages[0]["content"]
    left_system = left_messages[0]["content"]

    assert front_system == dedent(
        """\
        ROLE BLOCK

        enabled_categories=motor_vehicle_illegal_parking, goods_blocking_road
        location_constraints=focus on roadside occupation
        open_risk_guidance=If obvious risk exists outside prioritized categories, output open_risk.

        CATEGORY FOCUS
        - motor_vehicle_illegal_parking
          definition: vehicle occupies prohibited area
          common_objects: motor_vehicle, blind_path
          relation_focus: vehicle_occupies_prohibited_area
          exceptions: none
        - goods_blocking_road
          definition: goods on sidewalk
          common_objects: goods, sidewalk
          relation_focus: obstruct_pedestrian_passage
          exceptions: none

        REASONING BLOCK

        OUTPUT BLOCK"""
    )
    assert left_system == dedent(
        """\
        ROLE BLOCK

        enabled_categories=staff_not_wear_mask, goods_blocking_road
        location_constraints=focus on roadside occupation
        open_risk_guidance=If obvious risk exists outside prioritized categories, output open_risk.

        CATEGORY FOCUS
        - staff_not_wear_mask
          definition: catering staff missing mask
          common_objects: staff, mask, counter
          relation_focus: staff_without_mask
          exceptions: none
        - goods_blocking_road
          definition: goods on sidewalk
          common_objects: goods, sidewalk
          relation_focus: obstruct_pedestrian_passage
          exceptions: none

        REASONING BLOCK

        OUTPUT BLOCK"""
    )
    assert "camera_id=" not in front_system
    assert "location=南山路" not in left_system
