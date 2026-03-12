from textwrap import dedent

from ares_agent.infra.config import CategoryRegistryRule
from ares_agent.prompts.preliminary_prompt import CategoryDefinitionRenderer, PreliminaryPromptAssembler
from ares_agent.prompts.scene_activation import SceneActivationContext


def test_category_definition_renderer_only_renders_prioritized_categories() -> None:
    renderer = CategoryDefinitionRenderer(
        {
            "goods_blocking_road": CategoryRegistryRule(
                definition="goods on sidewalk",
                common_objects=["goods", "sidewalk"],
                relation_focus=["obstruct_pedestrian_passage"],
                exceptions=[],
            ),
            "staff_not_wear_mask": CategoryRegistryRule(
                definition="catering staff missing mask",
                common_objects=["staff", "mask", "counter"],
                relation_focus=["staff_without_mask"],
                exceptions=[],
            ),
            "motor_vehicle_illegal_parking": CategoryRegistryRule(
                definition="vehicle occupies prohibited area",
                common_objects=["motor_vehicle", "sidewalk"],
                relation_focus=["vehicle_occupies_prohibited_area"],
                exceptions=[],
            ),
        }
    )

    rendered = renderer.render(["staff_not_wear_mask", "goods_blocking_road"])

    assert rendered == dedent(
        """\
        - staff_not_wear_mask
          definition: catering staff missing mask
          common_objects: staff, mask, counter
          relation_focus: staff_without_mask
          exceptions: none
        - goods_blocking_road
          definition: goods on sidewalk
          common_objects: goods, sidewalk
          relation_focus: obstruct_pedestrian_passage
          exceptions: none"""
    )


def test_preliminary_prompt_assembler_builds_system_prompt_from_blocks() -> None:
    assembler = PreliminaryPromptAssembler()
    context = SceneActivationContext(
        camera_id="left",
        location="南山路",
        priority_categories=["staff_not_wear_mask", "goods_blocking_road"],
        scene_hint="storefront-facing camera",
        open_risk_guidance="If obvious risk exists outside prioritized categories, output open_risk.",
    )

    system_prompt = assembler.assemble(
        role_block="ROLE BLOCK",
        scene_activation_block_template=(
            "scene_hint={scene_hint}\npriority_categories={priority_categories}\nopen_risk_guidance={open_risk_guidance}"
        ),
        category_focus_block_template="CATEGORY FOCUS\n{category_definitions}",
        reasoning_block="REASONING BLOCK",
        output_contract_block="OUTPUT BLOCK",
        scene_activation_context=context,
        category_definitions=dedent(
            """\
            - staff_not_wear_mask
              definition: catering staff missing mask
              common_objects: staff, mask, counter
              relation_focus: staff_without_mask
              exceptions: none"""
        ),
    )

    assert system_prompt == dedent(
        """\
        ROLE BLOCK

        scene_hint=storefront-facing camera
        priority_categories=staff_not_wear_mask, goods_blocking_road
        open_risk_guidance=If obvious risk exists outside prioritized categories, output open_risk.

        CATEGORY FOCUS
        - staff_not_wear_mask
          definition: catering staff missing mask
          common_objects: staff, mask, counter
          relation_focus: staff_without_mask
          exceptions: none

        REASONING BLOCK

        OUTPUT BLOCK"""
    )
