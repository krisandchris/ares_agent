"""Inspection taxonomy and rule anchors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryRule:
    code: str
    label: str
    anchors: tuple[str, ...]


CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule(
        code="road_occupying_vendor",
        label="占道经营",
        anchors=("stall", "goods", "storefront_boundary", "sidewalk_or_roadway"),
    ),
    CategoryRule(
        code="goods_blocking_road",
        label="货物阻道",
        anchors=("goods_or_materials", "sidewalk", "passage_obstruction"),
    ),
    CategoryRule(
        code="unauthorized_electrical_wiring",
        label="私拉电线",
        anchors=("wire", "charger", "electric_vehicle", "outdoor_connection"),
    ),
    CategoryRule(
        code="motor_vehicle_illegal_parking",
        label="机动车违停",
        anchors=("motor_vehicle", "sidewalk_or_bus_stop_or_unmarked_area"),
    ),
    CategoryRule(
        code="nonmotor_vehicle_illegal_parking",
        label="非机动车违停",
        anchors=("nonmotor_vehicle", "sidewalk_or_roadway", "unattended_state"),
    ),
    CategoryRule(
        code="vagrants_blocking_roadway",
        label="流浪人员占道",
        anchors=("disheveled_person", "sitting_or_lying", "roadside_or_roadway"),
    ),
    CategoryRule(
        code="begging_blocking_roadway",
        label="乞讨人员占道",
        anchors=("disheveled_person", "begging_tools", "roadside_or_roadway"),
    ),
    CategoryRule(
        code="off_leash_dog_nuisance",
        label="不文明遛狗",
        anchors=("pedestrian", "pet_dog", "missing_leash"),
    ),
    CategoryRule(
        code="staff_not_wear_mask",
        label="商户未佩戴口罩",
        anchors=("catering_staff", "face", "missing_mask"),
    ),
)

