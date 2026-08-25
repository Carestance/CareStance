"""Build the student-growth foundation from existing assessment data.

Monthly plans, weekly goals, and support messages will use this single profile
in later PRs. Keeping the transformation here prevents each feature from
interpreting assessment results differently.
"""

from __future__ import annotations

from typing import Any


def _unique_strings(*groups: Any, limit: int | None = None) -> list[str]:
    """Return non-empty strings once, preserving their original order."""
    values: list[str] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for value in group:
            if not isinstance(value, str):
                continue
            value = value.strip()
            if value and value not in values:
                values.append(value)
                if limit is not None and len(values) >= limit:
                    return values
    return values


def _skill_from_signal(signal: str) -> str | None:
    """Translate observed behaviour into a skill label without copying it."""
    signal_lower = signal.lower()
    mappings = (
        ("problem sol", "Problem solving"),
        ("communicat", "Professional communication"),
        ("scenario", "Scenario analysis"),
        ("engagement", "Active participation"),
        ("decision", "Decision making"),
        ("research", "Research skills"),
        ("leadership", "Team leadership"),
        ("planning", "Planning and organisation"),
    )
    return next((skill for keyword, skill in mappings if keyword in signal_lower), None)


def _development_skill_from_area(area: str) -> str:
    """Turn assessment feedback into an actionable skill focus."""
    area_lower = area.lower()
    mappings = (
        ("specific", "Action planning"),
        ("communicat", "Clear communication"),
        ("decision", "Decision making"),
        ("stress", "Stress management"),
        ("detail", "Attention to detail"),
        ("research", "Research skills"),
        ("feedback", "Using feedback"),
    )
    return next((skill for keyword, skill in mappings if keyword in area_lower), area)


def build_growth_profile(assessment: Any) -> dict[str, Any]:
    """Create a display-ready, private growth profile for a student.

    The function accepts an AssessmentResult or a lightweight test object and
    deliberately tolerates unfinished assessments.
    """
    if assessment is None:
        return {
            "is_ready": False,
            "message": "Complete your career assessment to generate your growth profile.",
            "capabilities": [],
            "strengths": [],
            "growth_areas": [],
            "skills_possessed": [],
            "skills_to_develop": [],
            "growth_stage": "Assessment pending",
            "focus": None,
        }

    report = getattr(assessment, "assessment_report", None)
    report = report if isinstance(report, dict) else {}
    dashboard = report.get("dashboard") if isinstance(report.get("dashboard"), dict) else {}
    simulation = getattr(assessment, "simulation_evaluation", None)
    simulation = simulation if isinstance(simulation, dict) else {}

    strengths = _unique_strings(dashboard.get("strengths"), simulation.get("strengths"), limit=4)
    growth_areas = _unique_strings(
        dashboard.get("weaknesses"),
        simulation.get("improvement_areas"),
        limit=4,
    )
    observed_skill_signals = _unique_strings(
        getattr(assessment, "stream_cons", None),
        simulation.get("strengths"),
    )
    skills_possessed = _unique_strings(
        [_skill_from_signal(signal) for signal in observed_skill_signals if _skill_from_signal(signal)],
        limit=4,
    )
    skills_to_develop = _unique_strings(
        [_development_skill_from_area(area) for area in growth_areas],
        limit=3,
    )

    archetype = report.get("personality_archetype") or getattr(assessment, "phase_2_category", None)
    focus = getattr(assessment, "recommended_stream", None) or dashboard.get("dominant_riasec")
    # The result page supports both the current report format and legacy
    # stream_pros recommendations.  Use the same sources here so every
    # visible career's Growth Map link is valid.
    final_recommendations = report.get("final_recommendations") if isinstance(report.get("final_recommendations"), list) else []
    top_careers = report.get("top_careers") if isinstance(report.get("top_careers"), list) else []
    legacy_recommendations = getattr(assessment, "stream_pros", None)
    legacy_recommendations = legacy_recommendations if isinstance(legacy_recommendations, list) else []
    career_candidates = final_recommendations + top_careers + legacy_recommendations
    career_directions: list[dict[str, Any]] = []
    for index, career in enumerate(career_candidates):
        if not isinstance(career, dict):
            continue
        title = career.get("title") or career.get("career")
        if not isinstance(title, str) or not title.strip():
            continue
        title = title.strip()
        if any(item["title"].casefold() == title.casefold() for item in career_directions):
            continue
        raw_score = career.get("match_percent", career.get("match_score", 0))
        try:
            score = float(raw_score)
            score = round(score * 100) if score <= 1 else round(score)
        except (TypeError, ValueError):
            score = max(55, 82 - (index * 9))
        career_directions.append({
            "title": title,
            "confidence": max(1, min(99, int(score))),
            "next_signal": "Complete a real-world experiment and save what you learned.",
        })
    if not career_directions and isinstance(focus, str) and focus.strip():
        career_directions.append({
            "title": focus.strip(),
            "confidence": 72,
            "next_signal": "Complete this month's path to build stronger evidence for this direction.",
        })
    capability_candidates = _unique_strings(
        [archetype] if isinstance(archetype, str) else [],
        [focus] if isinstance(focus, str) else [],
        limit=4,
    )
    is_ready = bool(report or archetype or focus or strengths or growth_areas)
    simulations_completed = getattr(assessment, "simulations_completed", 0) or 0
    if simulation or simulations_completed:
        growth_stage = "Applying your skills"
        growth_stage_detail = "You have started testing your strengths in practical career activities."
    elif is_ready:
        growth_stage = "Building your foundation"
        growth_stage_detail = "Your assessment is complete; the next step is to turn its insights into practice."
    else:
        growth_stage = "Assessment pending"
        growth_stage_detail = "Complete the assessment to identify your current starting point."

    return {
        "is_ready": is_ready,
        "message": "Your profile will become more specific when you complete the assessment." if not is_ready else None,
        "capabilities": capability_candidates,
        "strengths": strengths,
        "growth_areas": growth_areas,
        "skills_possessed": skills_possessed,
        "skills_to_develop": skills_to_develop,
        "growth_stage": growth_stage,
        "growth_stage_detail": growth_stage_detail,
        "activity_count": simulations_completed,
        "focus": focus,
        "career_directions": career_directions,
    }
