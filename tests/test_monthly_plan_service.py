from app.services.monthly_plan_service import build_monthly_plan, get_monthly_plan_progress


def test_build_monthly_plan_creates_a_personalised_four_week_path():
    plan = build_monthly_plan({
        "is_ready": True,
        "skills_to_develop": ["Action planning"],
        "strengths": ["Curiosity"],
        "focus": "Technology",
    }, "2026-08")

    assert plan["title"] == "Build Action planning"
    assert plan["focus_skill"] == "Action planning"
    assert len(plan["weeks"]) == 4
    assert "Curiosity" in plan["why_this_path"]
    assert get_monthly_plan_progress(plan)["percent"] == 0


def test_career_plan_assigns_multiple_skills_and_concrete_career_tasks():
    plan = build_monthly_plan({"is_ready": True, "strengths": ["Curiosity"]}, "2026-08", career_title="Lawyer")

    assert plan["career_title"] == "Lawyer"
    assert plan["assigned_skills"] == ["Legal research", "Structured argument", "Professional communication"]
    assert plan["weeks"][0]["title"] == "Read the real work"
    assert "legal" in plan["weeks"][0]["tasks"][0]["text"].lower()
    assert "Lawyer" in plan["resources"][0]["title"]


def test_business_career_uses_business_specific_work_not_generic_questions():
    plan = build_monthly_plan({"is_ready": True}, "2026-08", career_title="Product Manager")

    assert plan["career_family"] == "business"
    assert plan["weeks"][0]["title"] == "Spot a real opportunity"
    assert "stakeholder" in plan["weeks"][0]["tasks"][1]["text"].lower()


def test_monthly_plan_progress_counts_only_valid_completed_weeks():
    progress = get_monthly_plan_progress({"completed_week_numbers": [1, 1, 3, 7, "4"]})

    assert progress == {
        "completed_weeks": 2,
        "total_weeks": 4,
        "percent": 50,
        "completed_week_numbers": [1, 3],
    }


def test_build_monthly_plan_requires_a_ready_growth_profile():
    try:
        build_monthly_plan({"is_ready": False}, "2026-08")
    except ValueError as error:
        assert "completed growth profile" in str(error)
    else:
        raise AssertionError("Expected a ValueError for an incomplete profile")
