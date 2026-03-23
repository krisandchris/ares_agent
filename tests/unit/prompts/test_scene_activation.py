from ares_agent.infra.config import SceneActivationPolicyConfig
from ares_agent.prompts.scene_activation import resolve_scene_activation_context


def test_scene_activation_reads_location_camera_rule_directly() -> None:
    config = SceneActivationPolicyConfig.model_validate(
        {
            "南山路": {
                "front": {
                    "enabled_categories": [
                        "road_occupying_vendor",
                        "goods_blocking_road",
                    ],
                    "location_constraints": [
                        "focus on roadside and sidewalk occupation",
                    ],
                },
                "left": {
                    "enabled_categories": [
                        "unauthorized_electrical_wiring",
                    ],
                    "location_constraints": [
                        "focus on storefront frontage and near-entrance obstruction",
                    ],
                },
                "right": {},
            }
        }
    )

    context = resolve_scene_activation_context(config, camera_id="left", location="南山路")

    assert context.enabled_categories == ["unauthorized_electrical_wiring"]
    assert context.location_constraints == [
        "focus on storefront frontage and near-entrance obstruction",
    ]
    assert context.open_risk_guidance == ""


def test_scene_activation_allows_empty_camera_rule() -> None:
    config = SceneActivationPolicyConfig.model_validate(
        {
            "南山路": {
                "front": {
                    "enabled_categories": ["goods_blocking_road"],
                    "location_constraints": ["focus on roadside occupation"],
                },
                "left": {},
                "right": {},
            }
        }
    )

    context = resolve_scene_activation_context(config, camera_id="right", location="南山路")

    assert context.enabled_categories == []
    assert context.location_constraints == []


def test_scene_activation_supports_front_left_right_across_two_locations() -> None:
    config = SceneActivationPolicyConfig.model_validate(
        {
            "南山路": {
                "front": {
                    "enabled_categories": [
                        "road_occupying_vendor",
                        "goods_blocking_road",
                        "unauthorized_electrical_wiring",
                        "motor_vehicle_illegal_parking",
                        "nonmotor_vehicle_illegal_parking",
                        "vagrants_blocking_roadway",
                        "begging_blocking_roadway",
                        "off_leash_dog_nuisance",
                    ],
                    "location_constraints": [
                        "focus on roadside space, sidewalk occupation, storefront frontage, and pedestrian passage",
                    ],
                },
                "left": {
                    "enabled_categories": [
                        "unauthorized_electrical_wiring",
                    ],
                    "location_constraints": [
                        "focus on storefront frontage, sidewalk blockage, and near-entrance obstruction",
                    ],
                },
                "right": {
                    "enabled_categories": [
                        "unauthorized_electrical_wiring",
                    ],
                    "location_constraints": [
                        "focus on storefront frontage, sidewalk blockage, and near-entrance obstruction",
                    ],
                },
            },
            "水坊街": {
                "front": {},
                "left": {
                    "enabled_categories": [
                        "unauthorized_electrical_wiring",
                        "staff_not_wear_mask",
                    ],
                    "location_constraints": [
                        "focus on storefront frontage, sidewalk blockage, and outdoor charging behavior",
                    ],
                },
                "right": {
                    "enabled_categories": [
                        "unauthorized_electrical_wiring",
                        "staff_not_wear_mask",
                    ],
                    "location_constraints": [
                        "focus on storefront frontage, sidewalk blockage, and outdoor charging behavior",
                    ],
                },
            },
        }
    )

    front_nanshan = resolve_scene_activation_context(config, camera_id="front", location="南山路")
    left_nanshan = resolve_scene_activation_context(config, camera_id="left", location="南山路")
    right_shuifang = resolve_scene_activation_context(config, camera_id="right", location="水坊街")
    front_shuifang = resolve_scene_activation_context(config, camera_id="front", location="水坊街")

    assert front_nanshan.enabled_categories == [
        "road_occupying_vendor",
        "goods_blocking_road",
        "unauthorized_electrical_wiring",
        "motor_vehicle_illegal_parking",
        "nonmotor_vehicle_illegal_parking",
        "vagrants_blocking_roadway",
        "begging_blocking_roadway",
        "off_leash_dog_nuisance",
    ]
    assert front_nanshan.location_constraints == [
        "focus on roadside space, sidewalk occupation, storefront frontage, and pedestrian passage",
    ]

    assert left_nanshan.enabled_categories == ["unauthorized_electrical_wiring"]
    assert left_nanshan.location_constraints == [
        "focus on storefront frontage, sidewalk blockage, and near-entrance obstruction",
    ]

    assert right_shuifang.enabled_categories == [
        "unauthorized_electrical_wiring",
        "staff_not_wear_mask",
    ]
    assert right_shuifang.location_constraints == [
        "focus on storefront frontage, sidewalk blockage, and outdoor charging behavior",
    ]

    assert front_shuifang.enabled_categories == []
    assert front_shuifang.location_constraints == []
