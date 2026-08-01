import json
import os
import re
from functools import lru_cache
from typing import List, Dict, Optional, Any

# Get API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")

@lru_cache(maxsize=4)
def get_genai_module():
    import google.generativeai as genai
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    return genai

@lru_cache(maxsize=4)
def get_gemini_model(model_name: str):
    genai = get_genai_module()
    return genai.GenerativeModel(model_name)

@lru_cache(maxsize=1)
def get_groq_client():
    if not GROQ_API_KEY:
        return None
    from groq import AsyncGroq
    return AsyncGroq(api_key=GROQ_API_KEY)

_httpx_client: Optional[Any] = None

# ─── Career-specific simulation contexts ─────────────────────────────────────
# Each entry has:
#   theme       – CSS theme class applied to the UI
#   metric      – name of the dashboard metric shown on the right panel
#   scenario    – the main Phase 1 storyline / challenge for this career
#   phase2      – brief description of the Phase 2 workspace task
#   task        – short name of the workspace task
#   mcq_topic   – topic hint used when generating AI MCQs
#   options     – 4 choices the student can pick for scenaroo-type phases
#   future_questions – 3 personalised Phase 3 reflection questions

CAREER_CONTEXTS: Dict[str, Dict] = {
    "software": {
        "theme": "tech-neon",
        "metric": "Build Health",
        "scenario": (
            "You are a junior Software Developer. Your team is about to release a new feature, "
            "but a bug has just been reported that could break the app for some users. "
            "Your manager wants to ship on time. What do you do first?"
        ),
        "phase2": (
            "You are in the engineering workspace. You have the bug report, the timeline, "
            "and your teammates available. Choose your next action."
        ),
        "task": "Fix the bug before the release",
        "mcq_topic": "software development, debugging, code reviews, team communication, and professional responsibility",
        "options": [
            ("Stop the release, fix the bug first, then tell your manager clearly.", "best"),
            ("Ship the feature now and quietly create a ticket to fix the bug later.", "weak"),
            ("Ask a teammate to handle it without telling your manager.", "mixed"),
            ("Remove only the broken feature so the rest of the app ships safely.", "mixed"),
        ],
        "future_questions": [
            "It is five years from now and you are a senior Software Developer. "
            "Describe one real problem you enjoy solving every day in your work.",
            "What kind of software project would make you feel proud to have built, and why?",
            "What skill are you still improving so that your code and your career keep growing?",
        ],
    },
    "medical": {
        "theme": "medical-clean",
        "metric": "Patient Safety Score",
        "scenario": (
            "You are a medical intern in a busy hospital. A patient tells you about symptoms "
            "that seem minor, but one detail makes you worry it could be serious. "
            "The waiting room is full and everyone is rushing. What do you do first?"
        ),
        "phase2": (
            "You are at the patient desk with the case notes and a triage checklist. "
            "A senior doctor is available nearby. Choose the safest next step."
        ),
        "task": "Protect the patient and act on the warning sign",
        "mcq_topic": "clinical decision making, patient communication, medical ethics, triage, and teamwork in healthcare",
        "options": [
            ("Escalate to the senior doctor immediately, document the warning sign, and monitor the patient.", "best"),
            ("Ask the patient to wait because others arrived earlier.", "weak"),
            ("Give the patient general advice without checking their vital signs.", "weak"),
            ("Ask a colleague for a quick second opinion while you prepare full notes.", "mixed"),
        ],
        "future_questions": [
            "Five years from now, you are a working doctor or medical professional. "
            "What does a meaningful patient interaction look like to you?",
            "Describe a medical challenge you would feel proud to have helped solve.",
            "What knowledge or skill are you still developing to become a better clinician?",
        ],
    },
    "finance": {
        "theme": "finance-sapphire",
        "metric": "Risk Exposure Level",
        "scenario": (
            "You are a junior financial analyst. A client wants to put all their savings "
            "into a high-risk investment for fast returns. Based on their profile, they cannot "
            "afford to lose that money. How do you handle this?"
        ),
        "phase2": (
            "You are reviewing the client's portfolio, risk score, and financial goals. "
            "Choose the best recommendation to give your client."
        ),
        "task": "Recommend a plan that balances growth and safety",
        "mcq_topic": "financial analysis, investment advising, client communication, risk management, and financial ethics",
        "options": [
            ("Explain the risk mismatch clearly, show safer alternatives, and document your advice.", "best"),
            ("Approve the risky investment because the client asked for it.", "weak"),
            ("Avoid the conversation and let the client decide on their own.", "weak"),
            ("Offer a smaller allocation to the risky option with clear written warnings.", "mixed"),
        ],
        "future_questions": [
            "Five years from now, you are an experienced finance professional. "
            "What does a good day solving a client's real financial challenge look like?",
            "Describe a financial problem you would feel proud to have helped solve.",
            "What skill or knowledge are you still building to grow in this field?",
        ],
    },
    "law": {
        "theme": "default",
        "metric": "Case Confidence Index",
        "scenario": (
            "You are a trainee lawyer. Your senior asks you to research a case where the "
            "client's request is legal but feels ethically wrong to you. "
            "What do you do first?"
        ),
        "phase2": (
            "You are in the law office with the case file, legal precedents, and your senior "
            "available by phone. Choose your next professional action."
        ),
        "task": "Prepare an honest and professional legal brief",
        "mcq_topic": "legal research, courtroom ethics, client representation, professional conduct, and conflict resolution",
        "options": [
            ("Research the law objectively, flag your ethical concern to your senior, and document your findings.", "best"),
            ("Refuse to work on the case without telling your senior.", "weak"),
            ("Do the work without raising any concerns and let your senior decide.", "mixed"),
            ("Look for legal arguments that also address the ethical issue you noticed.", "mixed"),
        ],
        "future_questions": [
            "Five years into your legal career, what type of case would you feel proud to argue?",
            "Describe a moment where your legal work made a real difference for someone.",
            "What area of law are you still studying to become sharper in your practice?",
        ],
    },
    "creative": {
        "theme": "creative-vibrant",
        "metric": "Client Alignment Score",
        "scenario": (
            "You are a designer or creative professional. A client rejects your first design "
            "even though it matches the brief they gave you. They are upset and the deadline "
            "is in two days. What do you do first?"
        ),
        "phase2": (
            "You are in your creative workspace with the original brief, the client's feedback, "
            "and two draft directions ready. Choose how to move forward."
        ),
        "task": "Recover the project with a focused creative direction",
        "mcq_topic": "creative problem solving, client feedback, design iteration, project management, and professional communication",
        "options": [
            ("Clarify what the client actually wants, then propose a focused revision plan.", "best"),
            ("Defend your original design and ask the client to give it more time.", "mixed"),
            ("Start over from scratch without confirming what should change.", "weak"),
            ("Copy a style the client liked before to satisfy them quickly.", "weak"),
        ],
        "future_questions": [
            "Five years from now, you work as a creative professional. "
            "What kind of project brings you pure creative satisfaction?",
            "Describe a creative challenge you would be proud to have solved.",
            "What creative skill are you still practicing to reach the next level?",
        ],
    },
    "education": {
        "theme": "default",
        "metric": "Student Engagement Score",
        "scenario": (
            "You are a new teacher. One student in your class is clearly smart but refuses "
            "to participate or do homework. The other students are noticing. "
            "What is your first step?"
        ),
        "phase2": (
            "You have the student's academic records, a quiet classroom after hours, and "
            "the support of the school counsellor. Choose your best next action."
        ),
        "task": "Re-engage the student without embarrassing them",
        "mcq_topic": "classroom management, student motivation, educational psychology, lesson planning, and inclusive teaching",
        "options": [
            ("Have a private, kind one-on-one conversation to understand what is going on.", "best"),
            ("Publicly praise other students so the struggling student feels motivated to join.", "weak"),
            ("Involve the parents immediately before fully understanding the situation.", "mixed"),
            ("Assign a small group activity where the student naturally takes a role.", "mixed"),
        ],
        "future_questions": [
            "Five years from now, you are an experienced teacher or educator. "
            "What does a great day in the classroom look like for you?",
            "Describe the type of student breakthrough that would make your work feel most meaningful.",
            "What teaching skill or knowledge are you still working to improve?",
        ],
    },
    "engineering": {
        "theme": "tech-neon",
        "metric": "System Reliability Index",
        "scenario": (
            "You are a junior engineer on site. A machine has stopped working in the middle "
            "of production, and the team is waiting for you to diagnose the problem. "
            "You have limited tools and a tight deadline. What do you do first?"
        ),
        "phase2": (
            "You are at the engineering workstation with the equipment's manual, diagnostic "
            "logs, and a senior engineer on the phone. Choose your next action."
        ),
        "task": "Diagnose and restore the production system",
        "mcq_topic": "engineering problem-solving, safety protocols, equipment failure, team coordination, and technical documentation",
        "options": [
            ("Run a systematic check from the last known working state and document each step.", "best"),
            ("Try random fixes quickly to meet the deadline without documenting anything.", "weak"),
            ("Call the manufacturer support line first before examining the equipment.", "mixed"),
            ("Isolate the affected section to keep other machinery running while you investigate.", "mixed"),
        ],
        "future_questions": [
            "Five years from now, you are a working engineer. "
            "Describe a technical problem you enjoy solving in your everyday work.",
            "What kind of engineering project would you feel most proud to have designed or built?",
            "What technical skill are you still learning to become a stronger engineer?",
        ],
    },
    "data": {
        "theme": "tech-neon",
        "metric": "Model Accuracy Score",
        "scenario": (
            "You are a data analyst. Your manager shares a dataset and asks you to "
            "present insights to a client by tomorrow. But you notice the data has "
            "several missing values and possible errors. What do you do first?"
        ),
        "phase2": (
            "You have the dataset, a cleaning script, and access to the original data source. "
            "Choose the best action to get accurate insights ready in time."
        ),
        "task": "Deliver clean and reliable data insights",
        "mcq_topic": "data analysis, data cleaning, visualization, ethical data use, and communicating findings clearly",
        "options": [
            ("Clean the data first, note the issues clearly, then build honest charts and insights.", "best"),
            ("Present the data as-is and mention errors only if the client asks.", "weak"),
            ("Ask to delay the presentation until you get a perfect dataset.", "mixed"),
            ("Highlight only the clean parts of the data and flag the problematic sections to the manager.", "mixed"),
        ],
        "future_questions": [
            "Five years from now, you work as a data scientist or analyst. "
            "What type of data problem makes your work feel genuinely interesting?",
            "Describe an insight or model you would be proud to have built for a real project.",
            "What data skill or tool are you still learning to advance your career?",
        ],
    },
    "default": {
        "theme": "default",
        "metric": "Decision Quality Score",
        "scenario": (
            "You are starting a new job. Your manager gives you an important task, "
            "but the instructions are unclear and your deadline is tight. "
            "Other team members are busy. What is your first move?"
        ),
        "phase2": (
            "You are at your desk with a task brief, a notepad to plan steps, "
            "and your manager available for one quick question. Choose the best next action."
        ),
        "task": "Complete the task professionally under pressure",
        "mcq_topic": "professional decision-making, communication, time management, teamwork, and handling ambiguity",
        "options": [
            ("Clarify the top priority with your manager, break the task into clear steps, then start.", "best"),
            ("Start working immediately without asking questions so you look proactive.", "weak"),
            ("Wait for someone else to give you clearer instructions.", "weak"),
            ("Do the easiest parts first and check in with the manager later.", "mixed"),
        ],
        "future_questions": [
            "Five years from now, describe a typical satisfying day in your career.",
            "What kind of challenge would you be proud to solve in your professional life?",
            "What skill or habit are you still building to keep growing in your work?",
        ],
    },
}


def _career_context(career_title: str) -> Dict:
    """Pick the most relevant career context based on keywords in the career title."""
    title = (career_title or "").lower()
    if any(t in title for t in ("software", "developer", "programmer", "coder", "web", "app", "full stack", "front")):
        return {**CAREER_CONTEXTS["software"], "_career": career_title}
    if any(t in title for t in ("data scientist", "data analyst", "machine learning", "ml", "ai engineer", "deep learning")):
        return {**CAREER_CONTEXTS["data"], "_career": career_title}
    if any(t in title for t in ("data", "analytics", "statistician")):
        return {**CAREER_CONTEXTS["data"], "_career": career_title}
    if any(t in title for t in ("doctor", "physician", "surgeon", "medical", "nurse", "clinical", "health", "mbbs", "dentist", "pharmacist")):
        return {**CAREER_CONTEXTS["medical"], "_career": career_title}
    if any(t in title for t in ("finance", "financial", "banker", "investment", "accountant", "ca", "cfa", "chartered")):
        return {**CAREER_CONTEXTS["finance"], "_career": career_title}
    if any(t in title for t in ("lawyer", "attorney", "legal", "advocate", "law", "judge")):
        return {**CAREER_CONTEXTS["law"], "_career": career_title}
    if any(t in title for t in ("design", "designer", "artist", "creative", "illustrat", "animator", "ux", "ui", "graphic")):
        return {**CAREER_CONTEXTS["creative"], "_career": career_title}
    if any(t in title for t in ("teacher", "educator", "professor", "lecturer", "instructor", "tutor", "teaching")):
        return {**CAREER_CONTEXTS["education"], "_career": career_title}
    if any(t in title for t in ("engineer", "engineering", "mechanical", "civil", "electrical", "chemical", "structural")):
        return {**CAREER_CONTEXTS["engineering"], "_career": career_title}
    return {**CAREER_CONTEXTS["default"], "_career": career_title}


def _fallback_mcqs(career_title: str, context: Dict) -> List[Dict]:
    """Reliable 5-question fallback MCQ set, tailored to the career context."""
    return [
        {
            "question": context["scenario"],
            "options": [o[0] for o in context["options"]],
            "correct_index": 0,
            "explanation": "The best professionals protect people, communicate clearly, and act on the most important risk first."
        },
        {
            "question": f"As a {career_title}, a colleague gives you critical feedback about your work. What is your best first response?",
            "options": [
                "Thank them, review the feedback carefully, and discuss the next steps together.",
                "Defend your work immediately and explain why you made those decisions.",
                "Ignore the feedback until you finish your current task.",
                "Ask your manager to settle the disagreement for you."
            ],
            "correct_index": 0,
            "explanation": "Staying open to feedback builds trust and helps you grow faster in any career."
        },
        {
            "question": f"You are a {career_title} and you realise halfway through a project that the plan will not work. What do you do?",
            "options": [
                "Flag the issue honestly, propose an adjusted plan, and keep your team informed.",
                "Carry on with the original plan and hope the problem sorts itself out.",
                "Start the whole project over without telling anyone first.",
                "Quietly hand the difficult part to a colleague without explaining why."
            ],
            "correct_index": 0,
            "explanation": "Recognising a problem early and communicating it clearly is a sign of professional maturity."
        },
        {
            "question": f"As a {career_title}, you are asked to do something that feels ethically wrong. What is your best move?",
            "options": [
                "Raise your concern professionally with the right person and ask for clarification.",
                "Do it anyway because you do not want to cause trouble.",
                "Refuse without saying anything and let someone else handle it.",
                "Agree but later do something different from what was asked."
            ],
            "correct_index": 0,
            "explanation": "Speaking up about ethical concerns professionally is a responsibility, not a risk."
        },
        {
            "question": f"What is the most effective way to grow your skills as a {career_title}?",
            "options": [
                "Practise regularly, seek honest feedback, and focus on improving one skill at a time.",
                "Only repeat the tasks you already do well so you stay confident.",
                "Watch what others do but avoid trying new things in case you fail.",
                "Wait until your employer sends you for formal training."
            ],
            "correct_index": 0,
            "explanation": "Deliberate practice and honest feedback create the fastest and most lasting growth."
        },
    ]


async def generate_simulation_mcqs(career_title: str, context: Dict) -> List[Dict]:
    """Generate exactly 5 career-specific MCQs using AI, with fallback."""
    topic = context.get("mcq_topic", f"the role of a {career_title}")
    prompt = f"""You are designing a career simulation for a student exploring the role of: {career_title}.

Create exactly 5 multiple-choice questions that test real judgement a {career_title} needs.
Topics to cover: {topic}

RULES:
- Each question must describe a realistic situation this professional could actually face.
- Write in simple, clear language that any student can understand immediately.
- Each question must have exactly 4 options and exactly 1 correct answer.
- The correct answer should always reflect the most professional and responsible choice.
- Do NOT use technical jargon the student might not know.

Return ONLY valid JSON in this exact format:
{{"mcqs":[{{"question":"...","options":["...","...","...","..."],"correct_index":0,"explanation":"..."}}]}}"""

    try:
        response = await generate_ai_content(prompt, use_grok=False)
        parsed = json.loads(extra_json(response))
        mcqs = parsed.get("mcqs", []) if isinstance(parsed, dict) else []
        valid = [
            q for q in mcqs
            if isinstance(q, dict)
            and isinstance(q.get("question"), str)
            and isinstance(q.get("options"), list)
            and len(q["options"]) == 4
            and isinstance(q.get("correct_index"), int)
            and 0 <= q["correct_index"] < 4
        ]
        if len(valid) >= 5:
            return valid[:5]
    except Exception as exc:
        print(f"Simulation MCQ generation fallback triggered: {exc}")
    return _fallback_mcqs(career_title, context)


async def build_live_simulation(career_title: str, difficulty: str = "Foundation") -> List[Dict]:
    """
    Build the three-phase career simulation:
      Phase 1 – 5 career-specific MCQs (role readiness check)
      Phase 2 – Practical workspace activity
      Phase 3 – Future-self reflection chat (3 open questions)
    """
    context = _career_context(career_title)
    mcqs = await generate_simulation_mcqs(career_title, context)

    # Build career-specific chat questions for Phase 3
    future_qs = context.get("future_questions", [
        f"It is five years from now and you are a {career_title}. What does a satisfying ordinary workday look like for you?",
        "What kind of challenge would you be proud to solve, and who would you work with to solve it?",
        "What would you keep learning or improving so that your work and life stay meaningful?",
    ])

    return [
        {
            "phase": 1,
            "type": "mcq_quiz",
            "scenario": (
                f"Phase 1 — Role Readiness Check\n\n"
                f"{context['scenario']}\n\n"
                f"Answer the 5 questions below to show how you think in this role."
            ),
            "objective": "Answer 5 career-specific questions to show your professional judgement",
            "theme_hint": context["theme"],
            "visual_cue": "pulse-green",
            "emergency_alert": f"Phase 1 of 3  •  5 Questions  •  {career_title}",
            "visual_dashboard": {"metric_name": context["metric"], "value": "40%"},
            "workspace": None,
            "mcqs": mcqs,
        },
        {
            "phase": 2,
            "type": "workspace_activity",
            "scenario": (
                f"Phase 2 — Practical Workspace\n\n"
                f"{context['phase2']}"
            ),
            "objective": "Build a step-by-step action plan in the workspace",
            "theme_hint": context["theme"],
            "visual_cue": "shake",
            "emergency_alert": f"Phase 2 of 3  •  Practical Task  •  {career_title}",
            "visual_dashboard": {"metric_name": context["metric"], "value": "65%"},
            "workspace": {
                "task": context["task"],
                "brief": (
                    f"You are working as a {career_title}. "
                    f"Use the workspace below to drag in resources, connect the steps, "
                    f"and build a clear action plan. Click Export when you are ready."
                ),
                "panels": [
                    {"label": "Your Role", "value": career_title},
                    {"label": "Task", "value": context["task"]},
                    {"label": "What is expected", "value": "Clear thinking, ownership, and good judgement"},
                ],
            },
        },
        {
            "phase": 3,
            "type": "future_role",
            "scenario": (
                f"Phase 3 — Your Future Self\n\n"
                f"Imagine it is five years from now and you are an experienced {career_title}. "
                f"Answer three honest questions about what your life and work look like."
            ),
            "objective": "Reflect on your future in this career with honesty and detail",
            "theme_hint": context["theme"],
            "visual_cue": "pulse-green",
            "emergency_alert": f"Phase 3 of 3  •  Future-Self Chat  •  {career_title}",
            "visual_dashboard": {"metric_name": "Future-Role Confidence", "value": "85%"},
            "chat_questions": future_qs,
            "workspace": {
                "task": "A day in your future role",
                "brief": "Answer each question honestly. The more specific you are, the more useful your reflection will be.",
                "panels": [
                    {"label": "Your Role", "value": career_title},
                    {"label": "Timeline", "value": "Five years from today"},
                    {"label": "Focus", "value": "Impact, growth, and everyday satisfaction"},
                ],
            },
            "options": None,
        },
    ]


def analyze_live_simulation_move(user_input: str, scenario: Dict, response_time: float = 0) -> Dict:
    """Score one simulation move locally for reliable product behaviour."""
    if scenario.get("type") == "mcq_quiz":
        try:
            answers = json.loads(user_input)
            mcqs = scenario.get("mcqs", [])
            correct = sum(
                1 for idx, ans in enumerate(answers)
                if idx < len(mcqs) and ans == mcqs[idx].get("correct_index")
            )
            total = max(1, len(mcqs))
            ratio = correct / total
            return {
                "eq_impact": round((ratio - 0.5) * 0.18, 2),
                "problem_solving_score": round(0.35 + ratio * 0.6, 2),
                "clarity_score": round(0.4 + ratio * 0.55, 2),
                "feedback": (
                    f"You answered {correct} of {total} role-readiness questions correctly. "
                    + ("Excellent professional judgement!" if ratio >= 0.8
                       else "Review the explanations — they will sharpen your role judgement.")
                ),
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "eq_impact": 0,
                "problem_solving_score": 0.3,
                "clarity_score": 0.3,
                "feedback": "We could not read your quiz response. Please try again.",
            }

    if scenario.get("type") == "workspace_activity":
        try:
            workspace = json.loads(user_input)
        except (json.JSONDecodeError, TypeError):
            workspace = {}
        items = workspace.get("items", []) if isinstance(workspace, dict) else []
        connections = workspace.get("connections", []) if isinstance(workspace, dict) else []
        has_plan = len(items) >= 3 and len(connections) >= 1
        return {
            "eq_impact": 0.08 if has_plan else 0.02,
            "problem_solving_score": 0.92 if has_plan else 0.45,
            "clarity_score": 0.88 if has_plan else 0.48,
            "feedback": (
                "Strong practical workflow — you created a connected plan with multiple steps."
                if has_plan else
                "Add at least three workspace elements and link them before exporting your workflow."
            ),
        }

    if scenario.get("type") == "future_role":
        try:
            future_answers = json.loads(user_input)
            if isinstance(future_answers, list):
                user_input = " ".join(str(a) for a in future_answers)
        except (json.JSONDecodeError, TypeError):
            pass

    text = (user_input or "").strip().lower()
    words = [w for w in re.split(r"\W+", text) if w]
    quality = None
    for option in scenario.get("options") or []:
        if option.get("text") == user_input:
            quality = option.get("quality")
            break

    if quality == "best":
        clarity, problem, eq = 0.9, 0.92, 0.18
        feedback = "Strong move — you balanced action, communication, and responsibility."
    elif quality == "mixed":
        clarity, problem, eq = 0.62, 0.58, 0.04
        feedback = "Partial move — it shows good intent, but needs clearer ownership and risk handling."
    elif quality == "weak":
        clarity, problem, eq = 0.32, 0.28, -0.16
        feedback = "Risky move — it misses the core professional responsibility in this situation."
    else:
        depth = min(len(words) / 35, 1)
        responsibility_words = {
            "explain", "communicate", "ask", "clarify", "document", "help",
            "check", "review", "priority", "risk", "plan", "honest", "safe",
        }
        responsibility = len(responsibility_words.intersection(words)) / 5
        clarity = max(0.25, min(0.95, 0.35 + depth * 0.35 + responsibility * 0.2))
        problem = max(0.25, min(0.95, 0.30 + depth * 0.30 + responsibility * 0.25))
        eq = max(-0.12, min(0.16, (clarity + problem - 1.0) / 3))
        feedback = (
            "Good start — try to name your exact first action, who you would tell, and how you would reduce the risk."
            if len(words) < 25 else
            "Thoughtful answer — you gave enough detail to show how you reason under pressure."
        )

    if response_time and response_time > 25:
        clarity = max(0.2, clarity - 0.05)
        feedback += " Try to decide a little faster in timed situations."

    return {
        "eq_impact": round(eq, 2),
        "problem_solving_score": round(problem, 2),
        "clarity_score": round(clarity, 2),
        "feedback": feedback,
    }


def finalize_live_simulation(career_title: str, moves: List[Dict]) -> Dict:
    analyses = [m.get("analysis", {}) for m in moves]
    if analyses:
        avg = sum(
            (a.get("problem_solving_score", 0.5) + a.get("clarity_score", 0.5)) / 2
            for a in analyses
        ) / len(analyses)
        eq_score = 0.5 + sum(a.get("eq_impact", 0) for a in analyses)
        score = max(18, min(98, round(((avg * 0.75) + (eq_score * 0.25)) * 100)))
    else:
        score = 35

    if score >= 75:
        strengths = ["Responsible decision making", "Clear professional communication", "Strong performance under pressure"]
        improvements = ["Add specific next steps after each decision", "Show how you would follow up to confirm things went well"]
        persona = "Ready Practitioner"
    elif score >= 50:
        strengths = ["Good engagement with realistic scenarios", "Developing problem-solving instincts"]
        improvements = ["Be more specific about your first action in each situation", "Practise explaining risks clearly to others"]
        persona = "Developing Explorer"
    else:
        strengths = ["Willingness to attempt the full simulation"]
        improvements = ["Focus on the most responsible option in each scenario", "Practise explaining your thinking clearly"]
        persona = "Needs Guided Practice"

    return {
        "match_score": f"{score}%",
        "overall_score": f"{score}%",
        "summary": (
            f"Your {career_title} simulation shows a {score}% readiness signal across professional "
            f"judgement, clarity, and response quality."
        ),
        "persona": persona,
        "strengths": strengths,
        "weaknesses": improvements,
        "improvement_areas": improvements,
        "career_readiness": (
            f"You perform best when you slow down the situation, identify the key risk, and choose "
            f"the most professional next step. Keep practising with specific, well-communicated "
            f"actions and clear follow-up plans. Working through more real {career_title} scenarios "
            f"will sharpen your instincts quickly."
        ),
    }


# ─── Shared HTTP client for xAI Grok ─────────────────────────────────────────

def get_shared_async_client():
    global _httpx_client
    if _httpx_client is None:
        import httpx
        _httpx_client = httpx.AsyncClient(timeout=30.0)
    return _httpx_client


async def generate_ai_content(prompt: str, use_grok: bool = False) -> str:
    """
    Unified AI generation helper.
    Priority: xAI Grok (if use_grok=True and key set) → Gemini → Groq.
    """
    if use_grok and XAI_API_KEY:
        try:
            client = get_shared_async_client()
            res = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {XAI_API_KEY}"},
                json={
                    "model": "grok-beta",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                },
            )
            return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Grok error: {e}")

    if GEMINI_API_KEY:
        try:
            model = get_gemini_model("gemini-2.5-flash")
            response = await model.generate_content_async(prompt)
            content = (response.text or "").strip()
            if content:
                return content
        except Exception as e:
            print(f"Gemini error in simulation_service: {e}")

    gclient = get_groq_client()
    if gclient:
        try:
            completion = await gclient.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Groq error in simulation_service: {e}")
            raise Exception("All AI systems failed.")

    raise Exception("No AI API key is configured.")


def extra_json(text: str) -> str:
    """Extract a JSON object from an AI response that may contain markdown fences."""
    text = re.sub(r"```json\s*|\s*```", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return text[start : end + 1]
    return text


# ─── Legacy helpers (kept for backward compatibility) ────────────────────────

async def generate_simulation_questions(career_title: str) -> List[str]:
    """Generates 7 scenario-based questions for a career simulation (legacy flow)."""
    prompt = f"""You are a Career Simulation Architect. Create exactly 7 realistic,
scenario-based open-ended questions for a student exploring the role of: {career_title}.

Write in simple, clear language that any student can understand immediately.
Cover: one ethical dilemma, one high-pressure decision, one teamwork challenge,
one failure/recovery, one long-term decision, and two general real-world challenges.

Return ONLY a JSON array of 7 strings.
Example: ["You are facing...", "A client asks...", ...]"""

    try:
        raw = await generate_ai_content(prompt, use_grok=True)
        questions = json.loads(extra_json(raw))
        if isinstance(questions, list) and len(questions) >= 5:
            return questions[:7]
    except Exception as e:
        print(f"Question generation error: {e}")
    # Fallback: use scenario descriptions from the 3-phase simulation
    phases = await build_live_simulation(career_title)
    return [p["scenario"] for p in phases]


async def evaluate_simulation(career_title: str, questions: List[str], answers: List[str]) -> Dict:
    """Evaluates the student's responses to simulation questions (legacy flow)."""
    qa_pairs = [f"Q: {q}\nA: {a}" for q, a in zip(questions, answers)]
    qa_text = "\n\n".join(qa_pairs)

    prompt = f"""You are an AI Career Psychologist evaluating a student's performance in a
real-world simulation for the role of "{career_title}".

INPUT DATA:
{qa_text}

TASK:
Analyse the responses and give an honest evaluation.

SCORING:
- 85-100: Excellent depth, clear logic, high professional thinking.
- 60-84: Good effort, logical but could be more detailed.
- 40-59: Shallow or inconsistent responses.
- 0-39: Nonsense, irrelevant, or very poor quality answers.

Return ONLY valid JSON:
{{
  "match_score": "XX%",
  "summary": "3-5 honest sentences justifying the score.",
  "strengths": ["2-3 specific strengths you observed"],
  "improvement_areas": ["2-3 specific areas to work on"]
}}"""

    try:
        raw = await generate_ai_content(prompt, use_grok=True)
        return json.loads(extra_json(raw))
    except Exception as e:
        print(f"Evaluation error: {e}")
        return {
            "match_score": "70%",
            "summary": "We encountered an error during analysis, but your responses show good engagement with the role.",
            "strengths": ["Resilience", "Engagement"],
            "improvement_areas": ["Clarity in high-pressure scenarios"],
        }


async def generate_academic_simulation_questions(stream_name: str) -> List[str]:
    """Generates 5 easy academic/conceptual questions for a stream simulation (Class 10)."""
    prompt = f"""You are an Educational Consultant. Create 5 easy, interesting conceptual questions
for a 10th-grade student who is exploring the {stream_name} stream.

Each question should show the student what kind of thinking this stream requires.
Write in simple, encouraging language — not like a formal exam.

Return ONLY a JSON array of 5 strings."""

    try:
        raw = await generate_ai_content(prompt)
        questions = json.loads(extra_json(raw))
        if isinstance(questions, list):
            return questions[:5]
    except Exception as e:
        print(f"Academic question generation error: {e}")
    return [
        "If you could design a new gadget to solve a daily problem, what would it be?",
        "How do you think a large company manages its daily expenses?",
        "Why do you think some events from history seem to repeat themselves?",
        "What interests you more: solving a maths puzzle or writing a story? Why?",
        "How would you explain the importance of nature to a young child?",
    ]


async def evaluate_academic_simulation(stream_name: str, questions: List[str], answers: List[str]) -> Dict:
    """Evaluates academic conceptual responses for Class 10 students."""
    qa_pairs = [f"Q: {q}\nA: {a}" for q, a in zip(questions, answers)]
    qa_text = "\n\n".join(qa_pairs)

    prompt = f"""You are an AI Academic Advisor. Evaluate a 10th-grade student's responses in
an academic simulation for the "{stream_name}" stream.

INPUT DATA:
{qa_text}

Be encouraging but honest. Give a low score if answers are very short, random, or show no effort.

Return ONLY valid JSON:
{{
  "match_score": "XX/100",
  "summary": "2-3 lines of direct feedback.",
  "strengths": ["2 specific conceptual strengths"],
  "improvement_areas": ["2 areas to read more about"]
}}"""

    try:
        raw = await generate_ai_content(prompt)
        return json.loads(extra_json(raw))
    except Exception:
        return {
            "match_score": "80/100",
            "summary": "You have a good intuitive feel for this stream's core ideas!",
            "strengths": ["Curiosity", "Logical thinking"],
            "improvement_areas": ["Deeper theoretical reading", "More specific examples"],
        }
