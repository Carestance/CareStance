"""Create deterministic monthly growth paths from a student's growth profile."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _month_label(month_key: str) -> str:
    return datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")


def _resource_suggestions(skill: str) -> list[dict[str, str]]:
    skill_lower = skill.lower()
    if "communicat" in skill_lower:
        return [
            {"title": "CareerBuddy practice prompt", "detail": "Ask CareerBuddy to role-play a short professional conversation."},
            {"title": "Reflection notes", "detail": "Write one clear message and improve it after feedback."},
        ]
    if "problem" in skill_lower or "decision" in skill_lower:
        return [
            {"title": "CareerBuddy practice prompt", "detail": "Ask for one role-relevant mini case study to solve."},
            {"title": "Decision journal", "detail": "Record your options, reasoning, and what you learned."},
        ]
    return [
        {"title": "CareerBuddy practice prompt", "detail": f"Ask for a beginner exercise to practice {skill.lower()}."},
        {"title": "Learning reflection", "detail": "Keep a short weekly note on what became easier and what still needs practice."},
    ]


def _week_tasks(week_number: int, focus_skill: str) -> list[dict[str, str]]:
    task_sets = {
        1: [
            "Describe one real situation where this skill would help you.",
            "Reserve one focused 20-minute practice slot.",
            "Choose and write down your first small action.",
        ],
        2: [
            "Complete one guided practice exercise.",
            "Write one thing that felt difficult.",
            "Ask for or use one piece of feedback.",
        ],
        3: [
            "Use the skill in a mini project, scenario, or school task.",
            "Save one piece of proof of your work.",
            "Write what you would improve next time.",
        ],
        4: [
            "Review the work you completed this month.",
            "Identify your strongest improvement.",
            "Write a reflection for next month’s path.",
        ],
    }
    return [
        {
            "id": f"week-{week_number}-task-{index}",
            "text": text.replace("this skill", focus_skill.lower()),
            "prompt": _task_prompt(week_number, index, focus_skill),
        }
        for index, text in enumerate(task_sets[week_number], start=1)
    ]


def _task_prompt(week_number: int, task_number: int, focus_skill: str) -> str:
    prompts = {
        (1, 1): "Describe the situation and why this skill matters there.",
        (1, 2): "Write the day, time, and place you will practice.",
        (1, 3): "Write one action you can finish in your planned practice slot.",
        (2, 1): "What exercise did you complete and what did you produce?",
        (2, 2): "Describe the specific point where you got stuck.",
        (2, 3): "What feedback did you use, and what will you change?",
        (3, 1): "Describe where you applied the skill and what happened.",
        (3, 2): "Describe the proof you saved, such as a note, screenshot, document, or link.",
        (3, 3): "Name one specific improvement for your next attempt.",
        (4, 1): "List the most meaningful work you completed this month.",
        (4, 2): "What improved most, and what evidence supports that?",
        (4, 3): "What should next month focus on, and why?",
    }
    return prompts[(week_number, task_number)].replace("this skill", focus_skill.lower())


def build_monthly_plan(
    growth_profile: dict[str, Any], month_key: str, previous_month_summary: str | None = None
) -> dict[str, Any]:
    """Build a four-week, practical path without depending on an external AI API."""
    if not growth_profile.get("is_ready"):
        raise ValueError("A completed growth profile is required before creating a monthly plan.")

    development_skills = growth_profile.get("skills_to_develop") or []
    strengths = growth_profile.get("strengths") or []
    focus_skill = development_skills[0] if development_skills else "Reflective career exploration"
    strength = strengths[0] if strengths else "your assessment insights"
    focus = growth_profile.get("focus") or "your preferred career direction"
    activity_count = growth_profile.get("activity_count", 0) or 0
    if activity_count:
        progress_summary = f"Your completed simulation activity is being used to keep this path focused on {focus_skill.lower()}."
    else:
        progress_summary = "This first path uses your completed assessment as the baseline. Your weekly activity will refine the next one."

    return {
        "month_key": month_key,
        "month_label": _month_label(month_key),
        "title": f"Build {focus_skill}",
        "milestone": f"By the end of {_month_label(month_key)}, complete one small practice task that demonstrates {focus_skill.lower()}.",
        "why_this_path": f"This path builds on {strength} and supports your current direction: {focus}.",
        "progress_summary": progress_summary,
        "previous_month_summary": previous_month_summary,
        "focus_skill": focus_skill,
        "completed_week_numbers": [],
        "completed_task_ids": [],
        "task_responses": {},
        "weeks": [
            {
                "week": 1,
                "title": "Understand your starting point",
                "goal": f"Spend 30 minutes identifying one situation where {focus_skill.lower()} would help you.",
                "outcome": "A short note describing the situation and one first action.",
                "tasks": _week_tasks(1, focus_skill),
            },
            {
                "week": 2,
                "title": "Practice in a small way",
                "goal": f"Complete one guided exercise that uses {focus_skill.lower()}.",
                "outcome": "One completed practice exercise and a brief reflection.",
                "tasks": _week_tasks(2, focus_skill),
            },
            {
                "week": 3,
                "title": "Apply it to a real example",
                "goal": f"Use {focus_skill.lower()} in a mini project, scenario, or school task.",
                "outcome": "A tangible example you can describe or share.",
                "tasks": _week_tasks(3, focus_skill),
            },
            {
                "week": 4,
                "title": "Review and improve",
                "goal": "Review your work, identify one improvement, and prepare your next focus.",
                "outcome": "A short reflection to inform next month's path.",
                "tasks": _week_tasks(4, focus_skill),
            },
        ],
        "resources": _resource_suggestions(focus_skill),
    }


def get_monthly_plan_progress(plan: dict[str, Any] | None) -> dict[str, int | list[int]]:
    """Calculate completion for the saved four-week plan."""
    plan = plan if isinstance(plan, dict) else {}
    completed = set()
    task_responses = plan.get("task_responses") if isinstance(plan.get("task_responses"), dict) else {}
    for week in plan.get("weeks", []):
        tasks = week.get("tasks", []) if isinstance(week, dict) else []
        task_ids = {task.get("id") for task in tasks if isinstance(task, dict)}
        if task_ids and task_ids.issubset(task_responses):
            completed.add(week.get("week"))
    completed = sorted(week for week in completed if isinstance(week, int) and 1 <= week <= 4)
    current_week = next((week for week in range(1, 5) if week not in completed), None)
    return {
        "completed_weeks": len(completed),
        "total_weeks": 4,
        "percent": round(len(completed) / 4 * 100),
        "completed_week_numbers": completed,
        "current_week": current_week,
    }


def get_week_states(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Expose only the next incomplete week; later weeks are deliberately locked."""
    plan = plan if isinstance(plan, dict) else {}
    progress = get_monthly_plan_progress(plan)
    completed_weeks = set(progress["completed_week_numbers"])
    current_week = progress["current_week"]
    return [
        {
            **week,
            "is_complete": week.get("week") in completed_weeks,
            "is_unlocked": week.get("week") == current_week,
            "is_locked": week.get("week") not in completed_weeks and week.get("week") != current_week,
        }
        for week in plan.get("weeks", [])
        if isinstance(week, dict)
    ]


def ensure_monthly_plan_structure(plan: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Upgrade existing saved plans with task data without replacing their progress."""
    updated = dict(plan or {})
    changed = False
    focus_skill = updated.get("focus_skill", "your focus skill")
    weeks = []
    for week in updated.get("weeks", []):
        item = dict(week)
        if not item.get("tasks") and item.get("week") in range(1, 5):
            item["tasks"] = _week_tasks(item["week"], focus_skill)
            changed = True
        weeks.append(item)
    if weeks != updated.get("weeks", []):
        updated["weeks"] = weeks
    if not isinstance(updated.get("completed_task_ids"), list):
        updated["completed_task_ids"] = []
        changed = True
    if not isinstance(updated.get("task_responses"), dict):
        updated["task_responses"] = {}
        changed = True
    return updated, changed


def get_week_task_states(plan: dict[str, Any], week_number: int) -> list[dict[str, Any]]:
    """Only one unfinished response task is open at a time within a week."""
    responses = plan.get("task_responses") if isinstance(plan.get("task_responses"), dict) else {}
    week = next((item for item in plan.get("weeks", []) if item.get("week") == week_number), None)
    if not week:
        return []
    next_task_id = next((task["id"] for task in week.get("tasks", []) if task["id"] not in responses), None)
    return [
        {
            **task,
            "response": responses.get(task["id"]),
            "is_complete": task["id"] in responses,
            "is_open": task["id"] == next_task_id,
            "is_locked": task["id"] not in responses and task["id"] != next_task_id,
        }
        for task in week.get("tasks", [])
    ]


def _days_since(value: str | None, today: date) -> int | None:
    if not value:
        return None
    try:
        return (today - date.fromisoformat(value)).days
    except ValueError:
        return None


def get_monthly_cycle_status(
    plan: dict[str, Any] | None, today: date | None = None, week_number: int | None = None
) -> dict[str, Any]:
    """Return due states for one weekly cycle, keeping support actions tied to that week."""
    today = today or date.today()
    plan = plan or {}
    checkins = plan.get("weekly_checkins", [])
    quizzes = plan.get("weekend_quizzes", [])
    conversations = plan.get("weekly_conversations", [])
    progress = get_monthly_plan_progress(plan)
    active_week = week_number or progress["current_week"] or 4
    week_checkins = [entry for entry in checkins if entry.get("week") == active_week]
    week_quizzes = [entry for entry in quizzes if entry.get("week") == active_week]
    week_conversations = [entry for entry in conversations if entry.get("week") == active_week]
    completed_conversation = next(
        (entry for entry in reversed(week_conversations) if entry.get("completed_at")), None
    )
    last_checkin = week_checkins[-1].get("date") if week_checkins else None
    last_quiz = week_quizzes[-1].get("date") if week_quizzes else None
    encouragement_seen = plan.get("last_encouragement_seen_on")
    return {
        "today": today.isoformat(),
        "week_number": active_week,
        "weekly_conversation_due": completed_conversation is None,
        "weekly_conversation": completed_conversation,
        "weekly_checkin_due": _days_since(last_checkin, today) is None or _days_since(last_checkin, today) >= 7,
        "weekend_quiz_due": today.weekday() >= 5 and (
            _days_since(last_quiz, today) is None or _days_since(last_quiz, today) >= 7
        ),
        "encouragement_due": _days_since(encouragement_seen, today) is None or _days_since(encouragement_seen, today) >= 2,
        "latest_checkins": week_checkins[-2:],
        "latest_quiz": week_quizzes[-1] if week_quizzes else None,
        "month_end_review": plan.get("month_end_review"),
    }


def build_weekly_reflection_response(plan: dict[str, Any], message: str) -> str:
    progress = get_monthly_plan_progress(plan)
    focus_skill = plan.get("focus_skill", "your focus skill")
    return (
        f"Thanks for the update. You are {progress['percent']}% through this month’s path. "
        f"For {focus_skill.lower()}, keep your next action small and visible: finish one concrete piece of work, "
        "note one blocker, and return next week with what changed."
    )


def get_encouragement_message(plan: dict[str, Any]) -> str:
    progress = get_monthly_plan_progress(plan)
    focus_skill = plan.get("focus_skill", "your monthly focus")
    if progress["percent"] == 100:
        return f"Excellent work—you completed this month’s path. Take a moment to reflect on how {focus_skill.lower()} improved."
    return f"Small progress counts. You are {progress['percent']}% through your path; choose one 20-minute action for {focus_skill.lower()} today."


def build_weekend_quiz(plan: dict[str, Any]) -> list[dict[str, Any]]:
    skill = plan.get("focus_skill", "your focus skill")
    return [
        {"question": f"What is the best first step when practising {skill.lower()}?", "options": ["Choose one small, clear action", "Wait until everything is perfect", "Avoid feedback", "Skip planning"], "correct_index": 0},
        {"question": "What makes a weekly goal useful?", "options": ["It is specific and achievable", "It has no deadline", "It is copied from someone else", "It changes every day"], "correct_index": 0},
        {"question": "When you hit a blocker, what should you do first?", "options": ["Identify the blocker and ask for targeted help", "Stop the plan completely", "Ignore it", "Start several unrelated tasks"], "correct_index": 0},
        {"question": "Which is the strongest proof of progress?", "options": ["A completed practice task and reflection", "Only saying you will start", "Comparing yourself with others", "Waiting for motivation"], "correct_index": 0},
        {"question": "What should inform your next monthly path?", "options": ["What you completed and what you learned", "A random new goal", "Only the hardest task", "Nothing from this month"], "correct_index": 0},
    ]


def build_month_end_summary(plan: dict[str, Any], reflection: str) -> str:
    progress = get_monthly_plan_progress(plan)
    skill = plan.get("focus_skill", "your focus skill")
    return (
        f"You completed {progress['completed_weeks']} of {progress['total_weeks']} weekly actions while building {skill.lower()}. "
        f"Your reflection: {reflection.strip()}"
    )
