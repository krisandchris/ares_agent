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


def test_scene_activation_supports_front_left_right_across_two_locations() -> None:
    config = SceneActivationPolicyConfig(
        camera_defaults={
            "front": SceneActivationRule(
                enabled_categories=[
                    "road_occupying_vendor",
                    "goods_blocking_road",
                    "unauthorized_electrical_wiring",
                    "motor_vehicle_illegal_parking",
                    "nonmotor_vehicle_illegal_parking",
                    "vagrants_blocking_roadway",
                    "begging_blocking_roadway",
                    "off_leash_dog_nuisance",
                ],
                priority_categories=[
                    "motor_vehicle_illegal_parking",
                    "nonmotor_vehicle_illegal_parking",
                    "goods_blocking_road",
                ],
                scene_hint="road-facing camera",
            ),
            "left": SceneActivationRule(
                enabled_categories=[
                    "road_occupying_vendor",
                    "goods_blocking_road",
                    "unauthorized_electrical_wiring",
                    "staff_not_wear_mask",
                ],
                priority_categories=[
                    "staff_not_wear_mask",
                    "goods_blocking_road",
                    "unauthorized_electrical_wiring",
                ],
                scene_hint="storefront-facing camera",
            ),
            "right": SceneActivationRule(
                enabled_categories=[
                    "road_occupying_vendor",
                    "goods_blocking_road",
                    "unauthorized_electrical_wiring",
                    "staff_not_wear_mask",
                ],
                priority_categories=[
                    "staff_not_wear_mask",
                    "goods_blocking_road",
                    "unauthorized_electrical_wiring",
                ],
                scene_hint="storefront-facing camera",
            ),
        },
        location_defaults={
            "南山路": SceneActivationRule(
                location_constraints=[
                    "focus on roadside, sidewalk, storefront frontage, and pedestrian passage"
                ]
            ),
            "水坊街": SceneActivationRule(
                location_constraints=[
                    "focus on storefront frontage, sidewalk occupation, and outdoor charging behavior"
                ]
            ),
        },
        overrides={
            "南山路": {
                "front": SceneActivationRule(
                    enabled_categories=[
                        "road_occupying_vendor",
                        "goods_blocking_road",
                        "unauthorized_electrical_wiring",
                        "motor_vehicle_illegal_parking",
                        "nonmotor_vehicle_illegal_parking",
                        "vagrants_blocking_roadway",
                        "begging_blocking_roadway",
                        "off_leash_dog_nuisance",
                    ],
                    disabled_categories=["staff_not_wear_mask"],
                    priority_categories=[
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
                    priority_categories=[
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
                    priority_categories=[
                        "staff_not_wear_mask",
                        "goods_blocking_road",
                        "unauthorized_electrical_wiring",
                    ],
                ),
            },
            "水坊街": {
                "front": SceneActivationRule(
                    enabled_categories=[
                        "road_occupying_vendor",
                        "goods_blocking_road",
                        "unauthorized_electrical_wiring",
                        "motor_vehicle_illegal_parking",
                        "nonmotor_vehicle_illegal_parking",
                        "off_leash_dog_nuisance",
                    ],
                    priority_categories=[
                        "road_occupying_vendor",
                        "goods_blocking_road",
                        "off_leash_dog_nuisance",
                    ],
                    scene_hint="road-facing camera near mixed storefront block",
                ),
                "left": SceneActivationRule(
                    enabled_categories=[
                        "road_occupying_vendor",
                        "goods_blocking_road",
                        "unauthorized_electrical_wiring",
                        "staff_not_wear_mask",
                    ],
                    priority_categories=[
                        "road_occupying_vendor",
                        "staff_not_wear_mask",
                        "goods_blocking_road",
                    ],
                    scene_hint="storefront-facing camera in dense storefront block",
                ),
                "right": SceneActivationRule(
                    enabled_categories=[
                        "road_occupying_vendor",
                        "goods_blocking_road",
                        "unauthorized_electrical_wiring",
                        "staff_not_wear_mask",
                    ],
                    priority_categories=[
                        "road_occupying_vendor",
                        "staff_not_wear_mask",
                        "unauthorized_electrical_wiring",
                    ],
                    scene_hint="storefront-facing camera in dense storefront block",
                ),
            },
        },
    )

    front_nanshan = resolve_scene_activation_context(config, camera_id="front", location="南山路")
    left_nanshan = resolve_scene_activation_context(config, camera_id="left", location="南山路")
    right_shuifang = resolve_scene_activation_context(config, camera_id="right", location="水坊街")

    assert front_nanshan.priority_categories == [
        "motor_vehicle_illegal_parking",
        "nonmotor_vehicle_illegal_parking",
        "goods_blocking_road",
    ]
    assert front_nanshan.scene_hint == "road-facing camera"
    assert front_nanshan.location_constraints == [
        "focus on roadside, sidewalk, storefront frontage, and pedestrian passage"
    ]

    assert left_nanshan.priority_categories == [
        "staff_not_wear_mask",
        "goods_blocking_road",
        "unauthorized_electrical_wiring",
    ]
    assert left_nanshan.enabled_categories == [
        "staff_not_wear_mask",
        "goods_blocking_road",
        "unauthorized_electrical_wiring",
    ]
    assert left_nanshan.scene_hint == "storefront-facing camera"

    assert right_shuifang.priority_categories == [
        "road_occupying_vendor",
        "staff_not_wear_mask",
        "unauthorized_electrical_wiring",
    ]
    assert right_shuifang.scene_hint == "storefront-facing camera in dense storefront block"
    assert right_shuifang.location_constraints == [
        "focus on storefront frontage, sidewalk occupation, and outdoor charging behavior"
    ]
