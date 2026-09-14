"""Helpers for the day-3 onboarding milestone used in the CareStance student/counselor kickoff flow.

The service builds a stable payload that represents the third-day checklist slice:
1. profile_setup
2. upi_setup
3. verification_review

It deliberately keeps the contract simple and serializable, so it can be rendered by
HTML templates or returned through a JSON API endpoint without requiring a database model.
"""

from __future__ import annotations


def build_day3_onboarding_payload(
    completed_tasks: list[str] | None = None,
    user_name: str | None = None,
) -> dict:
    """Return a consistent Day 3 onboarding payload for any caller.

    Args:
        completed_tasks: IDs of tasks already completed in the first two onboarding steps.
        user_name: Friendly user name to personalize the payload.

    Returns:
        A serializable dictionary with day, user metadata, task objects, and progress.
    """
    completed = list(completed_tasks or [])
    tasks = [
        {
            "id": "profile_setup",
            "title": "Complete your profile",
            "description": "Add your contact details, preferences, and counselor/student basics.",
            "status": "completed" if "profile_setup" in completed else "pending",
        },
        {
            "id": "upi_setup",
            "title": "Link UPI or payout credentials",
            "description": "Connect the payout profile required for counselor onboarding.",
            "status": "completed" if "upi_setup" in completed else "pending",
        },
        {
            "id": "verification_review",
            "title": "Verification review",
            "description": "Align your setup and wait for a quick profile verification review.",
            "status": "pending",
        },
    ]

    total_tasks = len(tasks)
    completed_count = sum(1 for item in tasks if item["status"] == "completed")
    progress_percent = int(round((completed_count / total_tasks) * 100)) if total_tasks else 0

    return {
        "day": 3,
        "user_name": user_name or "there",
        "total_tasks": total_tasks,
        "completed_tasks": completed,
        "progress_percent": progress_percent,
        "tasks": tasks,
    }
