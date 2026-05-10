"""Tests for data_engine prompt builders."""

from __future__ import annotations

from pathlib import Path

import pytest

from ares_agent.prompts.data_engine_prompts import (
    DataEngineStep1PromptBuilder,
    DataEngineStep2PromptBuilder,
)

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "data_engine"


@pytest.fixture()
def step1_builder() -> DataEngineStep1PromptBuilder:
    return DataEngineStep1PromptBuilder.from_files(
        registry_path=CONFIG_DIR / "stage1_registry.yaml",
        system_template_path=CONFIG_DIR / "stage1_system_core.txt",
        user_template_path=CONFIG_DIR / "stage1_user_prompt.txt",
    )


@pytest.fixture()
def step2_builder() -> DataEngineStep2PromptBuilder:
    return DataEngineStep2PromptBuilder.from_files(
        registry_path=CONFIG_DIR / "stage2_rule_registry.yaml",
        system_template_path=CONFIG_DIR / "stage2_system_core.txt",
        user_template_path=CONFIG_DIR / "stage2_user_prompt.txt",
    )


def test_step1_build_messages_has_system_and_user(step1_builder: DataEngineStep1PromptBuilder) -> None:
    messages = step1_builder.build_messages("http://example.com/img.jpg", image_hint="front")
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_step1_system_prompt_contains_anchors(step1_builder: DataEngineStep1PromptBuilder) -> None:
    messages = step1_builder.build_messages("http://example.com/img.jpg")
    system = messages[0]["content"]
    assert "pedestrian_walkway" in system
    assert "shop_boundary" in system
    assert "touching" in system


def test_step1_system_prompt_no_unfilled_placeholders(step1_builder: DataEngineStep1PromptBuilder) -> None:
    messages = step1_builder.build_messages("http://example.com/img.jpg")
    system = messages[0]["content"]
    assert "{{" not in system
    assert "}}" not in system


def test_step1_user_prompt_contains_image_hint(step1_builder: DataEngineStep1PromptBuilder) -> None:
    messages = step1_builder.build_messages("http://example.com/img.jpg", image_hint="test-hint")
    user_content = messages[1]["content"]
    assert isinstance(user_content, list)
    text_parts = [p for p in user_content if p.get("type") == "text"]
    assert any("test-hint" in p["text"] for p in text_parts)


def test_step1_user_prompt_contains_image_url(step1_builder: DataEngineStep1PromptBuilder) -> None:
    messages = step1_builder.build_messages("http://example.com/img.jpg")
    user_content = messages[1]["content"]
    assert isinstance(user_content, list)
    image_parts = [p for p in user_content if p.get("type") == "image_url"]
    assert len(image_parts) == 1
    assert image_parts[0]["image_url"]["url"] == "http://example.com/img.jpg"


def test_step2_build_messages_has_system_and_user(step2_builder: DataEngineStep2PromptBuilder) -> None:
    messages = step2_builder.build_messages(
        image_uri="http://example.com/img.jpg",
        stage1_json='{"environment_analysis":"test","scene_elements":[],"key_anchors":[],"key_relations":[]}',
        sample_id="evt_123",
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_step2_system_prompt_no_unfilled_placeholders(step2_builder: DataEngineStep2PromptBuilder) -> None:
    messages = step2_builder.build_messages(
        image_uri="http://example.com/img.jpg",
        stage1_json="{}",
        sample_id="evt_123",
    )
    system = messages[0]["content"]
    assert "{{" not in system
    assert "}}" not in system


def test_step2_user_prompt_contains_stage1_json(step2_builder: DataEngineStep2PromptBuilder) -> None:
    stage1_json = '{"environment_analysis":"test scene"}'
    messages = step2_builder.build_messages(
        image_uri="http://example.com/img.jpg",
        stage1_json=stage1_json,
        sample_id="evt_456",
    )
    user_content = messages[1]["content"]
    assert isinstance(user_content, list)
    text_parts = [p for p in user_content if p.get("type") == "text"]
    assert any(stage1_json in p["text"] for p in text_parts)
    assert any("evt_456" in p["text"] for p in text_parts)
