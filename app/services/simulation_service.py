import json
import os
import re
from functools import lru_cache
from typing import List, Dict, Optional, Any

# Get API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")  # Placeholder for Grok

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

CAREER_CONTEXTS = {
    "software": {
        "theme": "tech-neon",
        "metric": "Build Health",
        "phase1": "A feature you own is due today, but a teammate finds a bug that could affect real users. The product lead wants to ship anyway. What do you do first?",
        "phase2": "You are in the team workspace after the bug report. Your task is to choose the best next action while keeping the release moving responsibly.",
        "task": "Stabilize the release plan",
        "options": [
            ("Pause the release, reproduce the bug, share impact, and propose a fixed ETA.", "best"),
            ("Ship now and create a ticket to fix the bug later.", "weak"),
            ("Ask the teammate to handle it without updating the product lead.", "mixed"),
            ("Remove the affected feature quietly and continue the release.", "mixed"),
        ],
    },
    "medical": {
        "theme": "medical-clean",
        "metric": "Patient Safety",
        "phase1": "A patient describes symptoms that seem minor, but one detail suggests a possible emergency. The waiting room is full and everyone is rushing. What do you do first?",
        "phase2": "You are at the care desk with patient notes, a triage checklist, and a senior doctor available. Choose the safest next action.",
        "task": "Prioritize patient safety",
        "options": [
            ("Escalate immediately, document the warning sign, and keep monitoring the patient.", "best"),
            ("Tell the patient to wait because others arrived earlier.", "weak"),
            ("Give general advice without checking vitals.", "weak"),
            ("Ask a colleague for a quick second look while you prepare notes.", "mixed"),
        ],
    },
    "finance": {
        "theme": "finance-sapphire",
        "metric": "Risk Exposure",
        "phase1": "A client wants a high-return option, but the risk profile you collected shows they cannot afford a major loss. How do you respond?",
        "phase2": "You are reviewing a portfolio workspace with risk score, investment horizon, and client goals. Pick the next recommendation step.",
        "task": "Balance growth with suitability",
        "options": [
            ("Explain the mismatch, show safer alternatives, and document the recommendation.", "best"),
            ("Approve the high-risk option because the client requested it.", "weak"),
            ("Avoid the topic and suggest they decide alone.", "weak"),
            ("Offer a smaller allocation with clear risk warnings and confirmation.", "mixed"),
        ],
    },
    "creative": {
        "theme": "creative-vibrant",
        "metric": "Client Alignment",
        "phase1": "A client rejects your first concept even though it matches the brief. They are upset and the deadline is close. What do you do first?",
        "phase2": "You are in the project workspace with the brief, feedback notes, and two draft directions. Choose how to move forward.",
        "task": "Recover the creative direction",
        "options": [
            ("Clarify the feedback, restate the goal, and propose a focused revision plan.", "best"),
            ("Defend the original concept and ask them to reconsider.", "mixed"),
            ("Start over without confirming what changed.", "weak"),
            ("Copy a competitor's style to satisfy them quickly.", "weak"),
        ],
    },
    "default": {
        "theme": "default",
        "metric": "Decision Quality",
        "phase1": "You are given an important career task with limited time, unclear information, and people depending on your decision. What do you do first?",
        "phase2": "You are in a workspace with the task, possible actions, and a short deadline. Choose the most professional next step.",
        "task": "Make a clear professional decision",
        "options": [
            ("Clarify the goal, identify risks, communicate a plan, and act on the highest priority.", "best"),
            ("Choose quickly without asking questions.", "weak"),
            ("Wait until someone else decides.", "weak"),
            ("Do the easiest part first and update people later.", "mixed"),
        ],
    },
}


def _career_context(career_title: str) -> Dict:
    title = (career_title or "").lower()
    if any(token in title for token in ("software", "developer", "engineer", "data", "ai", "tech")):
        return CAREER_CONTEXTS["software"]
    if any(token in title for token in ("doctor", "medical", "nurse", "health", "clinical")):
        return CAREER_CONTEXTS["medical"]
    if any(token in title for token in ("finance", "account", "bank", "commerce", "business")):
        return CAREER_CONTEXTS["finance"]
    if any(token in title for token in ("design", "artist", "creative", "media", "writer")):
        return CAREER_CONTEXTS["creative"]
    return CAREER_CONTEXTS["default"]


def _fallback_mcqs(career_title: str, context: Dict) -> List[Dict]:
    """A reliable five-question fallback when an AI provider is unavailable."""
    best = context["options"][0][0]
    mixed = context["options"][2][0]
    weak = context["options"][1][0]
    return [
        {"question": context["phase1"], "options": [best, mixed, weak, context["options"][3][0]], "correct_index": 0,
         "explanation": "The strongest professional response protects people, communicates clearly, and acts on the risk."},
        {"question": f"Which skill matters most when beginning work as a {career_title}?", "options": ["Clarifying the goal before acting", "Avoiding feedback", "Waiting for every detail", "Working alone by default"], "correct_index": 0,
         "explanation": "Clear goals make good decisions and collaboration possible."},
        {"question": "A teammate spots a possible issue in your work. What is the best first response?", "options": ["Thank them, check the evidence, and agree on a next step", "Ignore it until the deadline passes", "Defend your work immediately", "Ask them not to mention it"], "correct_index": 0,
         "explanation": "Professional growth depends on being open to evidence and shared problem solving."},
        {"question": "When a decision could affect someone else, what should guide you?", "options": ["Safety, ethics, and the likely impact", "What is quickest for you", "What avoids all responsibility", "What sounds most impressive"], "correct_index": 0,
         "explanation": "Good role decisions balance results with responsibility."},
        {"question": f"What is the most useful way to grow in the {career_title} role?", "options": ["Practice, seek feedback, and improve one skill at a time", "Only repeat familiar tasks", "Hide mistakes", "Compare yourself to everyone else"], "correct_index": 0,
         "explanation": "Deliberate practice and feedback create sustainable progress."},
    ]


async def generate_simulation_mcqs(career_title: str, context: Dict) -> List[Dict]:
    """Generate exactly five role-specific MCQs and validate the response before use."""
    prompt = f"""
You design career simulations for students. Create exactly 5 clear, realistic multiple-choice questions for a learner exploring the role: {career_title}.
Each question must test role judgement, communication, ethics, collaboration, or problem solving. It must have exactly four concise options and exactly one best answer.
Return ONLY JSON in this exact shape:
{{"mcqs":[{{"question":"...","options":["...","...","...","..."],"correct_index":0,"explanation":"..."}}]}}
"""
    try:
        response = await generate_ai_content(prompt, use_grok=True)
        parsed = json.loads(extra_json(response))
        mcqs = parsed.get("mcqs", []) if isinstance(parsed, dict) else []
        valid = [q for q in mcqs if isinstance(q, dict) and isinstance(q.get("question"), str)
                 and isinstance(q.get("options"), list) and len(q["options"]) == 4
                 and isinstance(q.get("correct_index"), int) and 0 <= q["correct_index"] < 4]
        if len(valid) == 5:
            return valid
    except Exception as exc:
        print(f"Simulation MCQ generation fallback: {exc}")
    return _fallback_mcqs(career_title, context)


async def build_live_simulation(career_title: str, difficulty: str = "Foundation") -> List[Dict]:
    """Build the three-phase career simulation: 5 MCQs, activity, then future-role scenario."""
    context = _career_context(career_title)
    mcqs = await generate_simulation_mcqs(career_title, context)
    return [
        {
            "phase": 1,
            "type": "mcq_quiz",
            "scenario": "Phase 1: Role readiness check. Answer all five AI-generated questions.",
            "objective": "Show your professional judgement",
            "theme_hint": context["theme"],
            "visual_cue": "pulse-green",
            "emergency_alert": "Phase 1 of 3 • Five quick career MCQs",
            "visual_dashboard": {"metric_name": context["metric"], "value": "45%"},
            "workspace": None,
            "mcqs": mcqs,
        },
        {
            "phase": 2,
            "type": "workspace_activity",
            "scenario": context["phase2"],
            "objective": "Complete the role workspace activity",
            "theme_hint": context["theme"],
            "visual_cue": "shake",
            "emergency_alert": "Phase 2 of 3 • Build your action sequence",
            "visual_dashboard": {"metric_name": context["metric"], "value": "68%"},
            "workspace": {
                "task": context["task"],
                "brief": f"Role: {career_title}. Use the workspace to create and connect the resources, people, and actions needed to complete this task.",
                "panels": [
                    {"label": "Task", "value": context["task"]},
                    {"label": "Constraint", "value": "Limited time and visible consequences"},
                    {"label": "Expected", "value": "Clear reasoning, ownership, and ethical judgment"},
                ],
            },
        },
        {
            "phase": 3,
            "type": "future_role",
            "scenario": "Phase 3: Five years from now — chat with your future self.",
            "objective": "Picture your life and choices in the role",
            "theme_hint": context["theme"],
            "visual_cue": "pulse-green",
            "emergency_alert": "Phase 3 of 3 • Step into your future role",
            "visual_dashboard": {"metric_name": "Future-role confidence", "value": "82%"},
            "chat_questions": [
                f"It is five years from now and you are a {career_title}. What does a satisfying ordinary workday look like for you?",
                "What kind of challenge would you be proud to solve, and who would you work with to solve it?",
                "What would you keep learning or improving so that your work and life stay meaningful?",
            ],
            "workspace": {"task": "A day in your future role", "brief": "Answer the future-self chat questions honestly and specifically.", "panels": [{"label": "Your role", "value": career_title}, {"label": "Focus", "value": "Impact, growth, and balance"}, {"label": "Timeline", "value": "Five years from today"}]},
            "options": None,
        },
    ]


def analyze_live_simulation_move(user_input: str, scenario: Dict, response_time: float = 0) -> Dict:
    """Scores one simulation move locally for reliable product behavior."""
    if scenario.get("type") == "mcq_quiz":
        try:
            answers = json.loads(user_input)
            mcqs = scenario.get("mcqs", [])
            correct = sum(1 for index, answer in enumerate(answers)
                          if index < len(mcqs) and answer == mcqs[index].get("correct_index"))
            total = max(1, len(mcqs))
            ratio = correct / total
            return {
                "eq_impact": round((ratio - 0.5) * 0.18, 2),
                "problem_solving_score": round(0.35 + ratio * 0.6, 2),
                "clarity_score": round(0.4 + ratio * 0.55, 2),
                "feedback": f"You answered {correct} of {total} role-readiness questions correctly. " + ("Excellent professional judgement." if ratio >= .8 else "Use the explanations to strengthen your role judgement."),
            }
        except (json.JSONDecodeError, TypeError):
            return {"eq_impact": 0, "problem_solving_score": .3, "clarity_score": .3, "feedback": "Your quiz response could not be read. Please try again."}

    if scenario.get("type") == "workspace_activity":
        try:
            workspace = json.loads(user_input)
        except (json.JSONDecodeError, TypeError):
            workspace = {}
        items = workspace.get("items", []) if isinstance(workspace, dict) else []
        connections = workspace.get("connections", []) if isinstance(workspace, dict) else []
        has_practical_plan = len(items) >= 3 and len(connections) >= 1
        return {
            "eq_impact": 0.08 if has_practical_plan else 0.02,
            "problem_solving_score": 0.92 if has_practical_plan else 0.45,
            "clarity_score": 0.88 if has_practical_plan else 0.48,
            "feedback": "Strong practical workflow: you created a connected plan with multiple role resources." if has_practical_plan else "Add at least three workspace elements and link them before exporting your practical workflow.",
        }

    if scenario.get("type") == "future_role":
        try:
            future_answers = json.loads(user_input)
            if isinstance(future_answers, list):
                user_input = " ".join(str(answer) for answer in future_answers)
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
        clarity = 0.9
        problem = 0.92
        eq = 0.18
        feedback = "Strong move: you balanced action, communication, and responsibility."
    elif quality == "mixed":
        clarity = 0.62
        problem = 0.58
        eq = 0.04
        feedback = "Partial move: it shows intent, but needs clearer ownership and risk handling."
    elif quality == "weak":
        clarity = 0.32
        problem = 0.28
        eq = -0.16
        feedback = "Risky move: it misses the core responsibility in this situation."
    else:
        depth = min(len(words) / 35, 1)
        responsibility_words = {"explain", "communicate", "ask", "clarify", "document", "help", "check", "review", "priority", "risk", "plan"}
        responsibility = len(responsibility_words.intersection(words)) / 5
        clarity = max(0.25, min(0.95, 0.35 + depth * 0.35 + responsibility * 0.2))
        problem = max(0.25, min(0.95, 0.30 + depth * 0.30 + responsibility * 0.25))
        eq = max(-0.12, min(0.16, (clarity + problem - 1.0) / 3))
        feedback = "Good start. Add the exact first action, who you would inform, and how you would reduce risk." if len(words) < 25 else "Thoughtful answer: you gave enough context to show how you reason under pressure."

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
        avg = sum((a.get("problem_solving_score", 0.5) + a.get("clarity_score", 0.5)) / 2 for a in analyses) / len(analyses)
        eq_score = 0.5 + sum(a.get("eq_impact", 0) for a in analyses)
        score = max(18, min(98, round(((avg * 0.75) + (eq_score * 0.25)) * 100)))
    else:
        score = 35

    strengths = []
    improvements = []
    if score >= 75:
        strengths = ["Responsible decision making", "Clear professional communication", "Good pressure handling"]
        improvements = ["Add measurable next steps", "Mention how you would follow up"]
        persona = "Ready Practitioner"
    elif score >= 50:
        strengths = ["Engagement with the scenario", "Developing problem-solving instincts"]
        improvements = ["Be more specific about your first action", "Show how you would communicate risks"]
        persona = "Developing Explorer"
    else:
        strengths = ["Willingness to attempt the simulation"]
        improvements = ["Avoid vague or rushed answers", "Focus on ethics, clarity, and action"]
        persona = "Needs Guided Practice"

    return {
        "match_score": f"{score}%",
        "overall_score": f"{score}%",
        "summary": f"Your {career_title} simulation shows a {score}% readiness signal across judgment, clarity, and response quality.",
        "persona": persona,
        "strengths": strengths,
        "weaknesses": improvements,
        "improvement_areas": improvements,
        "career_readiness": "You are strongest when you slow the situation down, name the risk, and choose a professional next step. Keep practicing with more specific actions and follow-up plans.",
    }

def get_shared_async_client():
    global _httpx_client
    if _httpx_client is None:
        import httpx
        _httpx_client = httpx.AsyncClient(timeout=30.0)
    return _httpx_client

async def generate_ai_content(prompt: str, use_grok: bool = False) -> str:
    """
    Unified AI generation helper with fallbacks.
    Priority: xAI Grok (if requested & key exists) -> Gemini -> Groq.
    """
    # 1. Try Grok if requested and key exists
    if use_grok and XAI_API_KEY:
        try:
            # Assuming OpenAI compatibility for Grok
            client = get_shared_async_client()
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {XAI_API_KEY}"},
                json={
                    "model": "grok-beta",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                },
            )
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            print(f"Grok Error: {e}")
            # Fallback to Groq if Grok fails
            pass

    if GEMINI_API_KEY:
        try:
            model = get_gemini_model("gemini-2.5-flash")
            response = await model.generate_content_async(prompt)
            content = (response.text or "").strip()
            if content:
                return content
        except Exception as e:
            print(f"Gemini Error: {e}")

    gclient = get_groq_client()
    if gclient:
        try:
            chat_completion = await gclient.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq Error: {e}")
            raise Exception("All AI systems failed.")

    raise Exception("No AI API keys configured.")

def extra_json(text: str) -> str:
    """Extracts JSON block from AI response."""
    text = re.sub(r'```json\s*|\s*```', '', text).strip()
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        return text[start_idx:end_idx + 1]
    return text

async def generate_simulation_questions(career_title: str) -> List[str]:
    """Generates 7 specific scenario-based questions for a career simulation."""
    prompt = f"""
    You are an expert Career Simulation Architect. Design a immersive "Simulation Phase" for a user tracking a career as a "{career_title}".
    
    TASK:
    Generate exactly 7 scenario-based, open-ended questions. Each question must place the user in a realistic, challenging situation specific to being a {career_title}.
    
    TONE:
    - Natural, conversational storytelling style.
    - Slightly challenging, reflective, and engaging.
    - Avoid robotic or academic language.
    
    DIVERSITY REQUIREMENTS (Exactly 7 Questions):
    1. 1 Ethical Dilemma (Testing integrity and values)
    2. 1 High-Pressure Situation (Testing reaction under stress/deadlines)
    3. 1 Teamwork/Conflict Scenario (Testing interpersonal skills and EQ)
    4. 1 Failure/Recovery Situation (Testing resilience)
    5. 1 Long-term Decision-making Scenario (Testing strategic thinking)
    6. 2 General Real-world Challenges specific to being a {career_title}
    
    OUTPUT FORMAT:
    Respond STRICTLY with a JSON array of 7 strings.
    Example: ["You are facing...", "A client asks...", ...]
    """
    
    try:
        raw_response = await generate_ai_content(prompt, use_grok=True)
        json_str = extra_json(raw_response)
        questions = json.loads(json_str)
        if isinstance(questions, list) and len(questions) == 7:
            return questions
        # Fallback if list size is wrong
        return questions[:7] if isinstance(questions, list) else []
    except Exception as e:
        print(f"Question Generation Error: {e}")
        return [state["scenario"] for state in await build_live_simulation(career_title)]

async def evaluate_simulation(career_title: str, questions: List[str], answers: List[str]) -> Dict:
    """Evaluates the user's responses to the simulation questions."""
    
    # Combine questions and answers for analysis
    qa_pairs = []
    for q, a in zip(questions, answers):
        qa_pairs.append(f"Q: {q}\nA: {a}")
    
    qa_text = "\n\n".join(qa_pairs)
    
    prompt = f"""
    You are an AI Career Psychologist evaluating a user's performance in a real-world simulation for the role of "{career_title}".
    
    INPUT DATA:
    {qa_text}
    
    TASK:
    Analyze the responses and provide a final evaluation. 
    
    STRICT EVALUATION CRITERIA:
    - DEPTH & RELEVANCE: If answers are one-word, generic (e.g., "idk", "yes", "nice"), or completely nonsense, provide a FAIL score below 30%.
    - LOGICAL CONSISTENCY: Every scenario has a specific challenge. If the user ignores the core challenge or provides an off-topic response, penalize heavily.
    - PROFESSIONALISM: Check for reasoning that matches the maturity of a {career_title}.
    
    SCORING GUIDE:
    - 85-100: Exceptional depth, clear logic, high empathy/strategic thinking.
    - 60-84: Good effort, logical but could use more detail.
    - 40-59: Shallow or inconsistent responses.
    - 0-39: Nonsense, irrelevant, or intentionally disruptive answers.
    
    OUTPUT FORMAT:
    Respond STRICTLY in JSON:
    {{
      "match_score": "XX%", (provide a highly specific, non-rounded percentage)
      "summary": "3-5 lines justifying the score. Be honest and CRITICAL if the user provided poor input.",
      "strengths": ["list of 2-3 specific observed strengths, or leave empty if none"],
      "improvement_areas": ["list of 2-3 specific areas for growth or a critique of answer quality"]
    }}
    
    TONE:
    Engaging, reflective, and professional.
    """
    
    try:
        raw_response = await generate_ai_content(prompt, use_grok=True)
        json_str = extra_json(raw_response)
        evaluation = json.loads(json_str)
        return evaluation
    except Exception as e:
        print(f"Evaluation Error: {e}")
        return {
            "match_score": "70%",
            "summary": "We encountered an error during analysis, but your responses show promising alignment with the role.",
            "strengths": ["Resilience", "Engagement"],
            "improvement_areas": ["Clarity in high-pressure scenarios"]
        }
async def generate_academic_simulation_questions(stream_name: str) -> List[str]:
    """Generates 5 easy academic/conceptual questions for a stream simulation (Class 10)."""
    prompt = f"""
    You are an expert Educational Consultant. Design an "Academic Discovery Simulation" for a 10th-grade student exploring the "{stream_name}" stream.
    
    TASK:
    Generate exactly 5 easy, conceptual, and engaging academic questions that define the core nature of {stream_name}. 
    Each question should show the student what kind of thinking/problem-solving is required in this stream.
    
    STREAM CONTEXT:
    - Science: Focus on observation, logic, and "how things work" (Physics/Bio/Chem concepts).
    - Commerce: Focus on decision making, organization, and value (Economics/Business concepts).
    - Arts: Focus on interpretation, society, and creativity (History/Psych/Literature concepts).
    
    TONE:
    - Encouraging, curious, and clear.
    - Not a formal exam; more like a "think about this" conceptual quiz.
    
    OUTPUT FORMAT:
    Respond STRICTLY with a JSON array of 5 strings.
    """
    
    try:
        raw_response = await generate_ai_content(prompt)
        json_str = extra_json(raw_response)
        questions = json.loads(json_str)
        return questions[:5] if isinstance(questions, list) else []
    except Exception as e:
        print(f"Academic Question Generation Error: {e}")
        return [
            f"If you could design a new gadget to solve a daily problem, what would it be?",
            f"How do you think a large company manages its daily expenses?",
            f"Why do you think history repeats itself in certain ways?",
            f"What interests you more: solving a math puzzle or writing a story?",
            f"How would you explain the importance of nature to a young child?"
        ]

async def evaluate_academic_simulation(stream_name: str, questions: List[str], answers: List[str]) -> Dict:
    """Evaluates academic conceptual responses."""
    qa_pairs = [f"Q: {q}\nA: {a}" for q, a in zip(questions, answers)]
    qa_text = "\n\n".join(qa_pairs)
    
    prompt = f"""
    You are an AI Academic Advisor. Evaluate a 10th-grade student's responses in an academic simulation for the "{stream_name}" stream.
    
    INPUT DATA:
    {qa_text}
    
    TASK:
    Analyze the student's conceptual depth and interest level. 
    
    STRICT EVALUATION CRITERIA:
    - CONCEPTUAL CLARITY: Does the user understand the core academic concept being tested?
    - EFFORT & DEPTH: If answers are nonsense (e.g. "asdf", "...", "idk") or extremely generic, assign a score below 30/100.
    - RELEVANCE: Ensure the user isn't just typing random text to pass the steps.
    
    SCORING GUIDE:
    - 85-100: Mastery of the stream's core concepts.
    - 50-84: Developing understanding, good intuition.
    - 0-49: Poor conceptual clarity, lack of effort, or nonsense input.

    OUTPUT FORMAT:
    Respond STRICTLY in JSON:
    {{
      "match_score": "XX/100", (provide a highly specific, non-rounded score out of 100)
      "summary": "2-3 lines of feedback. Be direct and critical if the user's responses lacked effort.",
      "strengths": ["list of 2 specific conceptual strengths or leave empty if none"],
      "improvement_areas": ["list of 2 areas to read up on or a critique of answer quality"]
    }}
    """
    
    try:
        raw_response = await generate_ai_content(prompt)
        json_str = extra_json(raw_response)
        evaluation = json.loads(json_str)
        return evaluation
    except Exception as e:
        return {
            "match_score": "80/100",
            "summary": "You have a great intuitive grasp of this stream's core concepts!",
            "strengths": ["Curiosity", "Logical Flow"],
            "improvement_areas": ["Theoretical Depth", "Nuance"]
        }
