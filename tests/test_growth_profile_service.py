from types import SimpleNamespace

from app.services.growth_profile_service import build_growth_profile


def test_build_growth_profile_uses_assessment_and_simulation_signals():
    assessment = SimpleNamespace(
        assessment_report={
            "personality_archetype": "Strategic Builder",
            "dashboard": {
                "dominant_riasec": "Investigative",
                "strengths": ["Analytical Curiosity", "Leadership"],
                "weaknesses": ["Stress Management"],
            },
        },
        simulation_evaluation={
            "strengths": ["Leadership", "Clear communication"],
            "improvement_areas": ["Decision making"],
        },
        stream_cons=["Problem Solving", "Communication"],
        phase_2_category="Strategic Builder",
        recommended_stream="Science",
    )

    profile = build_growth_profile(assessment)

    assert profile["is_ready"] is True
    assert profile["strengths"] == ["Analytical Curiosity", "Leadership", "Clear communication"]
    assert profile["skills_possessed"] == ["Problem solving", "Professional communication", "Team leadership"]
    assert profile["skills_to_develop"] == ["Stress management", "Decision making"]
    assert profile["focus"] == "Science"
    assert profile["growth_stage"] == "Applying your skills"


def test_build_growth_profile_handles_missing_assessment():
    profile = build_growth_profile(None)

    assert profile["is_ready"] is False
    assert profile["growth_stage"] == "Assessment pending"
