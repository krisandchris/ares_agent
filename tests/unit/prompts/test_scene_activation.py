from ares_agent.infra.config import SceneActivationPolicyConfig, SceneActivationRule
from ares_agent.prompts.scene_activation import resolve_scene_activation_context


def test_scene_activation_prefers_location_camera_override() -> None:
    config = SceneActivationPolicyConfig(
        camera_defaults={
            "front": SceneActivationRule(
                enabled_categories=["motor_vehicle_illegal_parking", "goods_blocking_road"],
                priority_categories=["motor_vehicle_illegal_parking"],
                scene_hint="road-facing camera",
            ),
            "left": SceneActivationRule(
                enabled_categories=["road_occupying_vendor", "goods_blocking_road"],
                priority_categories=["goods_blocking_road"],
                scene_hint="storefront-facing camera",
            ),
        },
        location_defaults={
            "南山路": SceneActivationRule(
                enabled_categories=[
                    "goods_blocking_road",
                    "unauthorized_electrical_wiring",
                    "motor_vehicle_illegal_parking",
                ],
                location_constraints=["focus on roadside and storefront frontage"],
            )
        },
        overrides={
            "南山路": {
                "left": SceneActivationRule(
                    enabled_categories=[
                        "staff_not_wear_mask",
                        "goods_blocking_road",
                        "unauthorized_electrical_wiring",
                    ],
                    priority_categories=["staff_not_wear_mask"],
                )
            }
        },
    )

    context = resolve_scene_activation_context(config, camera_id="left", location="南山路")

    assert context.enabled_categories == [
        "staff_not_wear_mask",
        "goods_blocking_road",
        "unauthorized_electrical_wiring",
    ]
    assert context.priority_categories == ["staff_not_wear_mask"]
    assert context.location_constraints == ["focus on roadside and storefront frontage"]
    assert context.scene_hint == "storefront-facing camera"
    assert context.open_risk_guidance == ""


def test_scene_activation_falls_back_to_defaults_without_override() -> None:
    config = SceneActivationPolicyConfig(
        camera_defaults={
            "front": SceneActivationRule(
                enabled_categories=["motor_vehicle_illegal_parking", "off_leash_dog_nuisance"],
                priority_categories=["motor_vehicle_illegal_parking"],
                scene_hint="road-facing camera",
            )
        },
        location_defaults={
            "南山路": SceneActivationRule(
                enabled_categories=["goods_blocking_road", "motor_vehicle_illegal_parking"],
                location_constraints=["focus on roadside occupation"],
            )
        },
        overrides={},
    )

    context = resolve_scene_activation_context(config, camera_id="front", location="南山路")

    assert context.enabled_categories == [
        "motor_vehicle_illegal_parking",
        "off_leash_dog_nuisance",
        "goods_blocking_road",
    ]
    assert context.priority_categories == ["motor_vehicle_illegal_parking"]
    assert context.location_constraints == ["focus on roadside occupation"]
    assert context.scene_hint == "road-facing camera"
    assert context.open_risk_guidance == ""
