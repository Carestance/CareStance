# ==========================================
# EXPANDED FEATURE DICTIONARY (38 FEATURES)
# Simple + student-friendly language
# ==========================================

FEATURE_RULES = {

# ========== INTERESTS (6) ==========

"IT_Artistic": {
    "creative": 1.0,
    "drawing": 1.0,
    "painting": 1.0,
    "design": 0.9,
    "art": 0.9,
    "music": 0.8,
    "dance": 0.8,
    "video editing": 0.7,
    "colors": 0.6,
    "imagination": 0.8,
    "sketching": 0.9,
    "doodling": 0.8,
    "crafts": 0.8,
    "photography": 0.8,
    "acting": 0.7,
    "writing stories": 0.8,
    "instruments": 0.8,
    "aesthetic": 0.7,
    "fashion": 0.7,
    "decorating": 0.7,
    "making videos": 0.8,
    "visuals": 0.7
},

"IT_Conventional": {
    "organized": 1.0,
    "plan": 1.0,
    "planning": 1.0,
    "notes": 0.8,
    "routine": 0.9,
    "step by step": 1.0,
    "structured": 1.0,
    "schedule": 0.9,
    "rules": 0.8,
    "lists": 0.9,
    "to-do list": 0.9,
    "sorting": 0.8,
    "filing": 0.8,
    "folders": 0.7,
    "organized desk": 0.8,
    "calendar": 0.9,
    "details": 0.8,
    "habits": 0.7,
    "clutter-free": 0.7,
    "systematic": 0.9
},

"IT_Enterprising": {
    "leader": 1.0,
    "lead": 1.0,
    "business": 0.9,
    "startup": 1.0,
    "sell": 0.8,
    "money": 0.6,
    "influence": 0.9,
    "convince": 0.8,
    "competition": 0.7,
    "selling": 0.8,
    "marketing": 0.8,
    "persuading": 0.9,
    "negotiating": 0.9,
    "starting a project": 0.8,
    "pitching": 0.9,
    "profit": 0.7,
    "trading": 0.7,
    "ambitious": 0.8,
    "managing people": 0.9,
    "promotions": 0.7
},

"IT_Investigative": {
    "curious": 1.0,
    "research": 1.0,
    "study": 0.8,
    "science": 0.9,
    "math": 0.9,
    "logic": 1.0,
    "problem": 0.9,
    "data": 0.8,
    "analysis": 1.0,
    "figuring out": 0.9,
    "investigating": 1.0,
    "exploring": 0.8,
    "experiments": 0.9,
    "searching": 0.7,
    "reading up": 0.8,
    "asking why": 0.9,
    "testing": 0.8,
    "clues": 0.7,
    "mysteries": 0.7
},

"IT_Realistic": {
    "coding": 1.0,
    "computer": 0.9,
    "machine": 0.8,
    "engineering": 1.0,
    "hardware": 1.0,
    "build": 0.8,
    "tools": 0.7,
    "fix": 0.7,
    "real world": 1.0,
    "hands-on": 0.9,
    "working with hands": 0.9,
    "fixing things": 0.8,
    "assembling": 0.8,
    "outdoor work": 0.7,
    "gardening": 0.6,
    "mechanics": 0.8,
    "repairs": 0.8,
    "tinkering": 0.9,
    "building blocks": 0.7,
    "manual work": 0.8
},

"IT_Social": {
    "help": 1.0,
    "friends": 0.8,
    "team": 1.0,
    "group": 1.0,
    "teach": 0.9,
    "support": 0.8,
    "volunteer": 1.0,
    "talk": 0.7,
    "helping out": 0.9,
    "caring": 0.8,
    "listening": 0.8,
    "mentoring": 0.9,
    "guiding": 0.8,
    "charity": 0.8,
    "advising": 0.8,
    "making friends": 0.8,
    "community": 0.8,
    "supporting others": 0.9
},

# ========== WORK STYLES (15) ==========

"WS_Intellectual Curiosity": {
    "curious": 1.0,
    "why": 0.8,
    "how": 0.8,
    "learn": 0.9,
    "understand": 1.0,
    "explore": 0.9,
    "wondering": 0.8,
    "asking questions": 0.9,
    "reading": 0.7,
    "seeking answers": 0.9,
    "learning new things": 1.0,
    "inquisitive": 0.8,
    "deep dive": 0.8
},

"WS_Initiative": {
    "start": 0.9,
    "self": 0.8,
    "independent": 1.0,
    "do myself": 1.0,
    "initiative": 1.0,
    "proactive": 0.9,
    "getting started": 0.9,
    "taking charge": 0.9,
    "self-starter": 1.0,
    "by myself": 0.8,
    "doing it first": 0.8,
    "no reminders": 0.8
},

"WS_Leadership Orientation": {
    "leader": 1.0,
    "lead": 1.0,
    "guide": 0.9,
    "manage": 0.8,
    "responsible": 0.7,
    "in charge": 0.9,
    "leading team": 1.0,
    "directing": 0.8,
    "taking responsibility": 0.9,
    "organizing people": 0.8,
    "motivating others": 0.9
},

"WS_Perseverance": {
    "try again": 1.0,
    "never give up": 1.0,
    "hard work": 0.8,
    "keep going": 0.9,
    "practice": 0.7,
    "pushing through": 0.9,
    "not giving up": 1.0,
    "staying with it": 0.9,
    "finishing what I start": 0.9,
    "determined": 0.9,
    "putting in effort": 0.8,
    "overcoming obstacles": 0.9
},

"WS_Attention to Detail": {
    "careful": 1.0,
    "mistake": 0.8,
    "check": 0.9,
    "detail": 1.0,
    "accurate": 1.0,
    "double check": 0.9,
    "spotting errors": 0.9,
    "perfectionist": 0.8,
    "precise": 0.9,
    "exact": 0.9,
    "noticing small things": 0.9,
    "thorough": 0.8
},

"WS_Adaptability": {
    "change": 1.0,
    "adjust": 1.0,
    "flexible": 1.0,
    "adapt": 1.0,
    "go with the flow": 0.8,
    "adjusting": 0.9,
    "open to change": 0.9,
    "pivoting": 0.8,
    "handling new situations": 0.9,
    "switching gears": 0.8
},

"WS_Innovation": {
    "new idea": 1.0,
    "creative": 0.9,
    "different": 0.8,
    "innovative": 1.0,
    "out of the box": 0.9,
    "brainstorming": 0.8,
    "new ways": 0.9,
    "original ideas": 1.0,
    "thinking differently": 0.9,
    "novelty": 0.7
},

"WS_Achievement Orientation": {
    "goal": 0.9,
    "success": 1.0,
    "win": 0.8,
    "achieve": 1.0,
    "doing my best": 0.8,
    "hitting targets": 0.9,
    "accomplishing": 0.9,
    "improving scores": 0.8,
    "high grades": 0.8,
    "results": 0.8,
    "driven": 0.9
},

"WS_Cooperation": {
    "team": 1.0,
    "together": 0.9,
    "help": 0.8,
    "group": 1.0,
    "teamwork": 1.0,
    "sharing the work": 0.8,
    "collaborating": 0.9,
    "working together": 1.0,
    "helping classmates": 0.8,
    "agreeable": 0.7,
    "supporting team": 0.9
},

"WS_Social Orientation": {
    "friends": 0.9,
    "talk": 0.7,
    "social": 1.0,
    "meet": 0.8,
    "hanging out": 0.8,
    "chatting": 0.7,
    "outgoing": 0.9,
    "meeting people": 0.9,
    "making connections": 0.8,
    "extroverted": 0.9,
    "socializing": 1.0
},

"WS_Stress Tolerance": {
    "pressure": 1.0,
    "stress": 1.0,
    "calm": 1.0,
    "deadline": 0.9,
    "keeping cool": 0.9,
    "not panicking": 0.9,
    "handling pressure": 1.0,
    "relaxing under pressure": 0.8,
    "managing stress": 0.9,
    "chill": 0.7
},

"WS_Self-Control": {
    "control": 1.0,
    "discipline": 1.0,
    "focus": 0.9,
    "avoid distraction": 0.9,
    "self-discipline": 1.0,
    "staying focused": 0.9,
    "resisting temptation": 0.8,
    "patience": 0.8,
    "holding back": 0.7,
    "staying on track": 0.9
},

"WS_Self-Confidence": {
    "confident": 1.0,
    "speak": 0.8,
    "present": 0.9,
    "sure": 0.7,
    "believing in myself": 1.0,
    "self-assured": 0.9,
    "speaking up": 0.8,
    "trusting myself": 0.9,
    "proud": 0.7,
    "standing tall": 0.7
},

"WS_Cautiousness": {
    "careful": 1.0,
    "think before": 1.0,
    "risk": 0.8,
    "slow": 0.7,
    "safe play": 0.8,
    "avoiding risks": 0.9,
    "double checking decisions": 0.9,
    "being safe": 0.8,
    "hesitant": 0.7,
    "thinking twice": 1.0
},

"WS_Tolerance for Ambiguity": {
    "uncertain": 1.0,
    "confusing": 0.8,
    "open": 0.7,
    "unknown": 1.0,
    "vague": 0.8,
    "not knowing": 0.8,
    "no clear rules": 0.9,
    "figuring it out as I go": 0.9,
    "unclear instructions": 0.8,
    "shades of gray": 0.7
},

# ========== ABILITIES (17) ==========

"AB_Deductive Reasoning": {
    "logic": 1.0,
    "step": 0.8,
    "because": 0.7,
    "therefore": 0.9,
    "rules to facts": 0.8,
    "logical steps": 0.9,
    "following a recipe": 0.7,
    "if-then": 0.9,
    "deduction": 1.0,
    "applying formulas": 0.8
},

"AB_Mathematical Reasoning": {
    "math": 1.0,
    "numbers": 1.0,
    "calculate": 0.9,
    "sum": 0.8,
    "word problems": 0.9,
    "equations": 0.9,
    "algebra": 0.8,
    "fractions": 0.7,
    "math puzzles": 0.8,
    "calculating costs": 0.8
},

"AB_Problem Sensitivity": {
    "problem": 1.0,
    "issue": 0.9,
    "mistake": 0.8,
    "noticing problems": 1.0,
    "something feels off": 0.8,
    "spotting trouble": 0.9,
    "identifying issues": 0.9,
    "troubleshooting": 0.8
},

"AB_Information Ordering": {
    "order": 1.0,
    "step by step": 1.0,
    "sequence": 0.9,
    "chronological": 0.8,
    "putting in order": 0.9,
    "first to last": 0.9,
    "alphabetical": 0.8,
    "sorting steps": 0.9,
    "following directions": 0.8
},

"AB_Category Flexibility": {
    "different": 0.9,
    "switch": 0.8,
    "flexible": 1.0,
    "variety": 0.9,
    "grouping differently": 0.9,
    "sorting in different ways": 0.9,
    "switching categories": 0.8,
    "reorganizing": 0.8
},

"AB_Originality": {
    "new": 1.0,
    "different idea": 0.9,
    "unique": 1.0,
    "unusual ideas": 0.9,
    "one of a kind": 0.9,
    "unlike others": 0.8,
    "creative twist": 0.9,
    "fresh perspective": 0.9
},

"AB_Visualization": {
    "imagine": 1.0,
    "picture": 0.9,
    "visual": 1.0,
    "mental picture": 0.9,
    "seeing in my head": 0.9,
    "imagining shapes": 0.9,
    "3D viewing": 0.8,
    "picturing outcomes": 0.8
},

"AB_Memorization": {
    "remember": 1.0,
    "memorize": 1.0,
    "revise": 0.8,
    "recalling": 0.9,
    "retaining info": 0.9,
    "flashcards": 0.8,
    "remembering names": 0.8,
    "learning by heart": 0.9
},

"AB_Written Comprehension": {
    "understand text": 1.0,
    "reading": 0.9,
    "paragraph": 0.8,
    "reading comprehension": 1.0,
    "understanding articles": 0.9,
    "getting the point of text": 0.9,
    "reading books": 0.8,
    "textbook study": 0.8
},

"AB_Perceptual Speed": {
    "fast": 0.9,
    "quick": 1.0,
    "notice": 0.9,
    "spot": 0.8,
    "fast scanning": 0.9,
    "spotting differences": 0.9,
    "quick search": 0.8,
    "quick glance": 0.8,
    "finding patterns fast": 0.9
},

"AB_Selective Attention": {
    "focus": 1.0,
    "concentrate": 1.0,
    "ignore distraction": 1.0,
    "blocking out noise": 0.9,
    "staying zoned in": 0.9,
    "not getting distracted": 1.0,
    "tunnel vision": 0.8,
    "studying in noisy places": 0.8
},

"AB_Fluency of Ideas": {
    "ideas": 1.0,
    "creative thinking": 1.0,
    "many ideas": 0.9,
    "brainstorming lists": 0.9,
    "coming up with options": 0.9,
    "lots of ideas": 0.9,
    "rapid ideas": 0.8,
    "stream of thoughts": 0.7
},

"AB_Oral Expression": {
    "speak": 1.0,
    "talk": 0.9,
    "present": 1.0,
    "explain": 0.9,
    "explaining clearly": 0.9,
    "public speaking": 0.9,
    "talking out loud": 0.8,
    "giving a speech": 0.9,
    "presenting projects": 0.9
},

"AB_Inductive Reasoning": {
    "pattern": 1.0,
    "trend": 0.9,
    "observe": 0.8,
    "conclusion": 0.9,
    "connecting dots": 0.9,
    "finding patterns": 1.0,
    "spotting clues": 0.8,
    "drawing conclusions": 0.9,
    "generalizing": 0.8
},

"AB_Number Facility": {
    "numbers": 1.0,
    "math": 1.0,
    "calculate": 0.9,
    "mental math": 1.0,
    "adding up quickly": 0.9,
    "handling budgets": 0.8,
    "basic math": 0.9,
    "quick calculations": 0.9
},

"AB_Oral Comprehension": {
    "listen": 1.0,
    "understand speech": 1.0,
    "conversation": 0.9,
    "listening carefully": 0.9,
    "understanding directions spoken": 0.9,
    "hearing and understanding": 1.0,
    "following audio instructions": 0.8
},

"AB_Written Expression": {
    "write": 1.0,
    "essay": 0.9,
    "paragraph": 0.8,
    "writing clearly": 0.9,
    "putting thoughts on paper": 0.9,
    "drafting emails": 0.8,
    "composing texts": 0.7,
    "good writer": 0.8
}
}
