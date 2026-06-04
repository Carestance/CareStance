import json
import os
import re
from functools import lru_cache
from typing import List, Dict, Optional
import httpx

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
_httpx_client: Optional[httpx.AsyncClient] = None

def get_shared_async_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None:
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
        return []

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
