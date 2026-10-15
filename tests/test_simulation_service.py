import asyncio
import re
from pathlib import Path

from app.services.simulation_service import (
    CAREER_CONTEXTS,
    analyze_live_simulation_move,
    build_live_simulation,
    get_workflow_resource_types,
)


def test_live_simulation_starts_with_a_written_situation():
    phases = asyncio.run(build_live_simulation("Software Developer"))

    assert [phase["phase"] for phase in phases] == [1, 2, 3]
    assert phases[0]["type"] == "situation_response"
    assert "What do you do first?" in phases[0]["scenario"]
    assert "write" in phases[0]["scenario"].lower()
    assert "mcqs" not in phases[0]
    assert phases[1]["type"] == "workspace_activity"


def test_situation_answer_scoring_does_not_penalize_elapsed_time():
    scenario = {"type": "situation_response", "options": []}
    answer = "I would check the risk, document what happened, and tell my manager."

    fast_result = analyze_live_simulation_move(answer, scenario, response_time=5)
    slow_result = analyze_live_simulation_move(answer, scenario, response_time=3240)

    assert slow_result == fast_result


def test_workflow_resources_are_filtered_for_the_selected_career():
    medical_resources = get_workflow_resource_types("Medical Intern")
    creative_resources = get_workflow_resource_types("Graphic Designer")
    template_path = Path(__file__).resolve().parents[1] / "frontend" / "templates" / "Phase 4 UI.html"
    template_resource_types = set(
        re.findall(r'class="palette-item[^"]*"[^>]*data-type="([^"]+)"', template_path.read_text(encoding="utf-8"))
    )

    assert "security" in medical_resources
    assert "ai_model" not in medical_resources
    assert "logo" in creative_resources
    assert "budget" not in creative_resources
    assert len(medical_resources) < 16
    assert len(creative_resources) < 16
    assert set(medical_resources).issubset(template_resource_types)
    assert set(creative_resources).issubset(template_resource_types)
    assert all(
        set(context["workflow_resources"]).issubset(template_resource_types)
        for context in CAREER_CONTEXTS.values()
    )
