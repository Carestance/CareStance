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


def _career_focus_skill(career_title: str) -> str:
    """Choose a practical starter skill that matches the selected career."""
    title = career_title.lower()
    mappings = (
        (("engineer", "hardware", "architect"), "Systems design"),
        (("software", "computer", "developer", "data", "cyber"), "Technical problem solving"),
        (("doctor", "health", "psycholog", "nurs"), "Empathetic communication"),
        (("design", "writer", "media", "content"), "Creative communication"),
        (("business", "manager", "consult", "market", "finance"), "Strategic decision making"),
        (("teacher", "policy", "social", "counsellor"), "People-centred problem solving"),
    )
    for keywords, skill in mappings:
        if any(keyword in title for keyword in keywords):
            return skill
    return "Career exploration"


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


def _career_weeks(career_title: str, focus_skill: str) -> list[dict[str, Any]]:
    """Return different practice work for each career family—not a relabelled generic plan."""
    career = career_title.lower()
    if any(word in career for word in ("backend", "software", "developer", "data", "cyber")):
        content = [
            ("Map the role", "Study one real {career} job description and identify the tools and skills it asks for.", "A one-page role and skill map.", ["List three responsibilities from the job description.", "Choose one technical concept used in the role and explain it simply.", "Plan one 30-minute practice session for that concept."]),
            ("Build a technical foundation", "Complete a small hands-on exercise relevant to {career}.", "A working code sample, query, workflow, or documented solution.", ["Choose a beginner exercise that matches the role.", "Build the first working version.", "Write down one bug or gap and how you solved it."]),
            ("Solve a role scenario", "Work through a realistic {career} problem.", "A short technical case study with your reasoning.", ["Pick a realistic user or system problem.", "Describe your solution step by step.", "Ask someone or an AI reviewer for one improvement."]),
            ("Show your evidence", "Package what you learned as a portfolio-ready proof of work.", "A shareable README, screenshot set, or project note.", ["Improve your solution using feedback.", "Document what you built and why.", "Reflect on whether this career work energized you."]),
        ]
    elif any(word in career for word in ("engineer", "hardware", "architect")):
        content = [
            ("Understand the system", "Break down a real {career} product or system into its main parts.", "A labelled system sketch.", ["Choose a device, product, or process to study.", "Map its inputs, components, and outputs.", "Identify one design trade-off it makes."]),
            ("Prototype an idea", "Create a low-fidelity solution for a {career} challenge.", "A sketch, circuit concept, CAD idea, or process prototype.", ["Define one practical problem to solve.", "Create a first design or workflow.", "Test the design against one constraint such as cost, safety, or reliability."]),
            ("Improve the design", "Use evidence to refine your {career} solution.", "A revised design with a clear rationale.", ["Identify one failure point in the first version.", "Make one measurable improvement.", "Explain the trade-off behind your final decision."]),
            ("Present like an engineer", "Communicate the design so another person can understand it.", "A concise design brief or presentation.", ["Summarise the problem and solution.", "Add a diagram or photo of the design.", "Reflect on what you enjoyed about this type of work."]),
        ]
    elif any(word in career for word in ("doctor", "health", "psycholog", "nurs")):
        content = [
            ("Explore the role", "Learn how a {career} professional supports people in a real setting.", "A role observation note.", ["Read or watch one day-in-the-life resource.", "List three responsibilities requiring empathy or accuracy.", "Write one question you would ask a professional."]),
            ("Practice communication", "Use a realistic scenario to practise listening and clear explanation.", "A written response to a patient or client scenario.", ["Choose an ethical care scenario.", "Write how you would listen before responding.", "Explain a next step in plain, supportive language."]),
            ("Use evidence carefully", "Explore how a {career} professional makes an informed decision.", "A short evidence-and-decision note.", ["Find two reliable facts about a health or wellbeing topic.", "Compare what each fact suggests.", "Write a safe, evidence-based conclusion."]),
            ("Reflect on fit", "Review the demands and impact of {career} work.", "A career-fit reflection.", ["List what felt meaningful.", "List one challenge you would need to prepare for.", "Decide one next learning action."]),
        ]
    elif any(word in career for word in ("design", "writer", "media", "content")):
        content = [
            ("Observe the audience", "Study how a {career} professional solves a communication or experience problem.", "An audience insight note.", ["Choose one app, campaign, article, or visual experience.", "Identify the intended audience and their need.", "List three choices that make the work effective."]),
            ("Create a first draft", "Make an original piece of work for a clear audience.", "A draft design, story, campaign, or content piece.", ["Write a one-sentence brief.", "Create a first version.", "Ask for feedback from one potential audience member."]),
            ("Iterate with feedback", "Improve your work based on what the audience understood.", "A revised piece with an iteration note.", ["Choose the most useful feedback.", "Make one purposeful revision.", "Explain how the revision improved clarity or impact."]),
            ("Build a mini portfolio", "Present your process and final work.", "A shareable case study or portfolio card.", ["Show the brief, draft, and final version.", "Write a short process summary.", "Reflect on the kind of creative work you want to explore next."]),
        ]
    else:
        return [
            {"week": week, "title": title, "goal": goal.format(career=career_title), "outcome": outcome, "tasks": [{"id": f"week-{week}-task-{index}", "text": task, "prompt": _task_prompt(week, index, focus_skill)} for index, task in enumerate(tasks, 1)]}
            for week, (title, goal, outcome, tasks) in enumerate([
                ("Understand your starting point", "Spend 30 minutes identifying one situation where {career} work would use your strengths.", "A short note describing the situation and one first action.", ["Describe one real situation where this skill would help you.", "Reserve one focused 20-minute practice slot.", "Choose and write down your first small action."]),
                ("Practice in a small way", "Complete one guided exercise connected to {career}.", "One completed practice exercise and a brief reflection.", ["Complete one guided practice exercise.", "Write one thing that felt difficult.", "Ask for or use one piece of feedback."]),
                ("Apply it to a real example", "Use {career} thinking in a mini project or scenario.", "A tangible example you can describe or share.", ["Use the skill in a mini project, scenario, or school task.", "Save one piece of proof of your work.", "Write what you would improve next time."]),
                ("Review and improve", "Review what you learned about {career}.", "A short reflection to inform your next step.", ["Review the work you completed this month.", "Identify your strongest improvement.", "Write a reflection for next month's path."]),
            ], 1)
        ]
    return [
        {"week": week, "title": title, "goal": goal.format(career=career_title), "outcome": outcome, "tasks": [{"id": f"week-{week}-task-{index}", "text": task, "prompt": _task_prompt(week, index, focus_skill)} for index, task in enumerate(tasks, 1)]}
        for week, (title, goal, outcome, tasks) in enumerate(content, 1)
    ]


def build_monthly_plan(
    growth_profile: dict[str, Any], month_key: str, previous_month_summary: str | None = None,
    career_title: str | None = None,
) -> dict[str, Any]:
    """Build a four-week, practical path without depending on an external AI API."""
    if not growth_profile.get("is_ready"):
        raise ValueError("A completed growth profile is required before creating a monthly plan.")

    development_skills = growth_profile.get("skills_to_develop") or []
    strengths = growth_profile.get("strengths") or []
    focus_skill = _career_focus_skill(career_title) if career_title else (development_skills[0] if development_skills else "Reflective career exploration")
    strength = strengths[0] if strengths else "your assessment insights"
    focus = career_title or growth_profile.get("focus") or "your preferred career direction"
    activity_count = growth_profile.get("activity_count", 0) or 0
    if activity_count:
        progress_summary = f"Your completed simulation activity is being used to keep this path focused on {focus_skill.lower()}."
    else:
        progress_summary = "This first path uses your completed assessment as the baseline. Your weekly activity will refine the next one."

    return {
        "template_version": 2,
        "month_key": month_key,
        "month_label": _month_label(month_key),
        "career_title": career_title,
        "title": f"Explore {focus}" if career_title else f"Build {focus_skill}",
        "milestone": f"By the end of {_month_label(month_key)}, complete one small practice task that helps you explore {focus} through {focus_skill.lower()}.",
        "why_this_path": f"This path builds on {strength} and is tailored to your selected career: {focus}.",
        "progress_summary": progress_summary,
        "previous_month_summary": previous_month_summary,
        "focus_skill": focus_skill,
        "completed_week_numbers": [],
        "completed_task_ids": [],
        "task_responses": {},
        "weeks": _career_weeks(career_title, focus_skill) if career_title else [
            {"week": week, "title": title, "goal": goal, "outcome": outcome, "tasks": _week_tasks(week, focus_skill)}
            for week, title, goal, outcome in [
                (1, "Understand your starting point", f"Spend 30 minutes identifying one situation where {focus_skill.lower()} would help you.", "A short note describing the situation and one first action."),
                (2, "Practice in a small way", f"Complete one guided exercise that uses {focus_skill.lower()}.", "One completed practice exercise and a brief reflection."),
                (3, "Apply it to a real example", f"Use {focus_skill.lower()} in a mini project, scenario, or school task.", "A tangible example you can describe or share."),
                (4, "Review and improve", "Review your work, identify one improvement, and prepare your next focus.", "A short reflection to inform next month's path."),
            ]
        ],
        "resources": _resource_suggestions(focus_skill),
        "evidence_locker": [],
        "career_experiments": _career_experiments(focus),
        "decision_checkpoint": None,
    }


def _career_experiments(focus: str) -> list[dict[str, str]]:
    """Give every student a small, practical way to test—not just read about—a direction."""
    label = focus if isinstance(focus, str) and focus.strip() else "your career direction"
    return [
        {"id": "role-play", "title": "Try a career scenario", "detail": f"Complete a short {label} scenario and note what you enjoyed or found difficult."},
        {"id": "career-story", "title": "Learn from a real professional", "detail": "Watch or read one day-in-the-life story and record one insight that surprised you."},
        {"id": "mini-project", "title": "Create a mini project", "detail": "Make one small piece of work that lets you use a skill from this direction."},
    ]


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
    if not isinstance(updated.get("evidence_locker"), list):
        updated["evidence_locker"] = []
        changed = True
    if not isinstance(updated.get("career_experiments"), list):
        updated["career_experiments"] = _career_experiments(updated.get("focus") or updated.get("title") or "your career direction")
        changed = True
    if "decision_checkpoint" not in updated:
        updated["decision_checkpoint"] = None
        changed = True
    return updated, changed


def get_growth_momentum(plan: dict[str, Any] | None) -> dict[str, Any]:
    """A small, meaningful progress signal—not a generic game score."""
    plan = plan or {}
    progress = get_monthly_plan_progress(plan)
    evidence_count = len(plan.get("evidence_locker") or []) + len(plan.get("task_responses") or {})
    completed = progress["completed_weeks"]
    message = (
        "Your consistency is turning practice into evidence."
        if completed >= 3 else
        "Each completed week makes your career direction clearer."
        if completed else
        "Your first small action will create the evidence your future choices need."
    )
    return {"weeks": completed, "evidence_count": evidence_count, "message": message}


def build_monthly_growth_report(plan: dict[str, Any]) -> dict[str, Any]:
    """Create a simple student/parent-ready snapshot from the student's actual work."""
    progress = get_monthly_plan_progress(plan)
    task_responses = plan.get("task_responses") if isinstance(plan.get("task_responses"), dict) else {}
    decision = plan.get("decision_checkpoint") if isinstance(plan.get("decision_checkpoint"), dict) else None
    return {
        "month_label": plan.get("month_label", "This month"),
        "focus_skill": plan.get("focus_skill", "Growth exploration"),
        "completed_weeks": progress["completed_weeks"],
        "total_weeks": progress["total_weeks"],
        "evidence_count": len(plan.get("evidence_locker") or []) + len(task_responses),
        "strongest_habit": "Showing up for small, focused practice" if progress["completed_weeks"] else "Choosing a clear first action",
        "next_focus": (plan.get("month_end_review") or {}).get("reflection") or "Continue with one small, visible action next week.",
        "decision": decision,
    }


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
