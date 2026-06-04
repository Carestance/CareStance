# ==========================================
# COUNSELLOR MODE: INTERACTIVE SCENARIOS
# Adapted for High School Students (16–18)
# Purpose: Personality & Self-Discovery
# ==========================================

# Category 1: Focused Specialist
# Theme: Depth, Precision, and Solitude
scenarios_focused_specialist = [
    {
        "id": "S1_TheBug",
        "title": "The Group Project Mistake",
        "story": "Your group just submitted a project and your teacher marked it 'done.' But scrolling through your notes, you spot a small error — something most people won't notice, but it's there. What do you do?",
        "options": [
            {
                "value": "A",
                "text": "I quietly fix it or mention it to the teacher myself. No need to make it a big drama.",
                "outcome_hint": "Efficiency over protocol."
            },
            {
                "value": "B",
                "text": "I tell my group first. We submitted it together, so we fix it together — the right way.",
                "outcome_hint": "Protocol over speed."
            }
        ]
    },
    {
        "id": "S2_TheWorkspace",
        "title": "Your Ideal Study Spot",
        "story": "Exams are coming. You can study anywhere you want. Which setup actually helps you do your best work?",
        "options": [
            {
                "value": "A",
                "text": "My room, door locked, headphones in, phone on airplane mode. Just me and my notes.",
                "outcome_hint": "Deep isolation."
            },
            {
                "value": "B",
                "text": "A study room or library with friends nearby — quiet, but not totally alone.",
                "outcome_hint": "Balanced environment."
            }
        ]
    },
    {
        "id": "S3_TheMastery",
        "title": "Your Future Self",
        "story": "Fast-forward 10 years. You've built a reputation in your field. Which version of 'successful you' feels more like YOU?",
        "options": [
            {
                "value": "A",
                "text": "The Go-To Expert. Everyone calls me for one specific thing, and I'm the best in the world at it.",
                "outcome_hint": "Niche depth."
            },
            {
                "value": "B",
                "text": "The All-Rounder. I'm respected and capable across a wide range of things in my field.",
                "outcome_hint": "Broad competence."
            }
        ]
    },
    {
        "id": "S4_TheDeadline",
        "title": "The Last-Minute Panic",
        "story": "It's Sunday night. A big assignment is due tomorrow and you've barely started. What's your survival instinct?",
        "options": [
            {
                "value": "A",
                "text": "I go into lockdown mode. Phone off, snacks ready, full focus — I work best alone under pressure.",
                "outcome_hint": "Individual focus."
            },
            {
                "value": "B",
                "text": "I call a friend. We split the sections and grind it out together on a video call.",
                "outcome_hint": "Delegation/Collaboration."
            }
        ]
    },
    {
        "id": "S5_TheReward",
        "title": "The Recognition",
        "story": "You solved a huge problem in a school event or competition and everyone knows it was you. How do you want to be thanked?",
        "options": [
            {
                "value": "A",
                "text": "Call me up on stage. Give me the moment — I earned it and I'm proud of it.",
                "outcome_hint": "Public recognition."
            },
            {
                "value": "B",
                "text": "A quiet 'well done' from the right person means more than any applause.",
                "outcome_hint": "Private reward."
            }
        ]
    }
]

# Category 2: The Curious Researcher
# Theme: Discovery, Data, and Observation
scenarios_curious_researcher = [
    {
        "id": "S1_TheLibrary",
        "title": "The Rabbit Hole",
        "story": "You're researching for an assignment and stumble across a fascinating article — totally off-topic, but genuinely interesting. Do you read it?",
        "options": [
            {"value": "A", "text": "Yes. Those random detours are where I learn the most interesting things.", "outcome_hint": "Intellectual Curiosity"},
            {"value": "B", "text": "No. I bookmark it for later and stay on track. Deadlines are deadlines.", "outcome_hint": "Focus/Discipline"}
        ]
    },
    {
        "id": "S2_ThePuzzle",
        "title": "The Mystery Data",
        "story": "A classmate dumps a messy, unlabeled spreadsheet on your desk and asks, 'Can you find anything useful in here?' How does that make you feel?",
        "options": [
            {"value": "A", "text": "Excited. It's like a puzzle — I immediately start looking for patterns.", "outcome_hint": "Pattern seeking"},
            {"value": "B", "text": "Frustrated. Without structure or context, I can't work properly.", "outcome_hint": "Rigorous standards"}
        ]
    },
    {
        "id": "S3_TheGroupProject",
        "title": "Pick Your Role",
        "story": "Your class is working on a big research project and two roles are still open. Which one do you grab?",
        "options": [
            {"value": "A", "text": "The Researcher. I want to dig into the sources and uncover the real story.", "outcome_hint": "Deep Research"},
            {"value": "B", "text": "The Presenter. I want to take the findings and make them clear and visual for everyone.", "outcome_hint": "Information Design"}
        ]
    },
    {
        "id": "S4_TheObservation",
        "title": "The Awkward Party",
        "story": "You're at a school social event and the music is loud. You don't really feel like talking to anyone right now. Where does your mind go?",
        "options": [
            {"value": "A", "text": "I start people-watching. I quietly observe the social dynamics going on around me.", "outcome_hint": "Observational analysis"},
            {"value": "B", "text": "I start mentally planning how to leave without it being weird.", "outcome_hint": "Strategic withdrawal"}
        ]
    },
    {
        "id": "S5_TheMystery",
        "title": "Choose Your Challenge",
        "story": "Two school competitions are open. Which one actually appeals to you?",
        "options": [
            {"value": "A", "text": "A semester-long deep research project with a full written report at the end.", "outcome_hint": "Long-term depth"},
            {"value": "B", "text": "A 48-hour hackathon where you have to solve a real problem under pressure.", "outcome_hint": "High-pressure problem solving"}
        ]
    }
]

# Category 3: The Bold Driver
# Theme: Action, Risk, and Leadership
scenarios_bold_driver = [
    {
        "id": "S1_ThePitch",
        "title": "The Elevator Moment",
        "story": "You end up alone in the lift with your school principal. You have a bold idea to improve something at school. Do you bring it up right now?",
        "options": [
            {"value": "A", "text": "Yes. I pitch it on the spot. This chance might not come again.", "outcome_hint": "High risk/aggression"},
            {"value": "B", "text": "No. I'll write it up properly and ask for a meeting. It deserves a proper hearing.", "outcome_hint": "Calculated/Professional"}
        ]
    },
    {
        "id": "S2_TheTeam",
        "title": "The Struggling Teammate",
        "story": "You're leading a group project and one teammate keeps missing deadlines. You need to talk to them. What's your approach?",
        "options": [
            {"value": "A", "text": "Direct. 'This is affecting the whole group. You need to fix it by tomorrow.'", "outcome_hint": "Performance driven"},
            {"value": "B", "text": "Supportive. 'Hey, what's going on? Let's figure this out together.'", "outcome_hint": "Supportive/Coaching"}
        ]
    },
    {
        "id": "S3_TheCompetition",
        "title": "The Rival School",
        "story": "A rival school just launched an identical version of your club's big initiative — months before you. What do you tell your team?",
        "options": [
            {"value": "A", "text": "'We go harder. We will out-execute them with better quality and more hustle.'", "outcome_hint": "Competitive/Sprint"},
            {"value": "B", "text": "'They beat us to it. Let's be smart and find a fresh angle they haven't touched.'", "outcome_hint": "Strategic pivot"}
        ]
    },
    {
        "id": "S4_TheSpotlight",
        "title": "The Podium",
        "story": "You just won Student of the Year. You're handed the mic. What does your speech look like?",
        "options": [
            {"value": "A", "text": "I take my full time. I share my vision for the school and own the moment.", "outcome_hint": "Charismatic/Visionary"},
            {"value": "B", "text": "I keep it short. I thank the people who helped me and get off stage quickly.", "outcome_hint": "Humble/Efficient"}
        ]
    },
    {
        "id": "S5_TheRisk",
        "title": "After School — What's Next?",
        "story": "Two paths sit in front of you after graduation. Which one makes your heart beat faster?",
        "options": [
            {"value": "A", "text": "Join a friend's scrappy startup. No pay yet, but wild potential if it works.", "outcome_hint": "High Risk/Reward"},
            {"value": "B", "text": "Land a structured internship at a well-known company. Stable, credible, and a great foundation.", "outcome_hint": "Stability/Impact"}
        ]
    }
]

# Category 4: The Social Catalyst
# Theme: Connection, Empathy, and Energy
scenarios_social_catalyst = [
    {
        "id": "S1_TheEvent",
        "title": "The Big Request",
        "story": "Your best friend asks you to plan the entire end-of-year class celebration — 80 people, full decorations, music, the works — because 'you're just good at this.' How does that feel?",
        "options": [
            {"value": "A", "text": "I'm already making a playlist in my head. Let's go.", "outcome_hint": "Social Orchestrator"},
            {"value": "B", "text": "Flattering, but the thought of managing 80 people's expectations sounds exhausting.", "outcome_hint": "Intimate connector (not large scale)"}
        ]
    },
    {
        "id": "S2_TheVariety",
        "title": "Your Ideal Life",
        "story": "If you could design your lifestyle after school, which path feels more like you?",
        "options": [
            {"value": "A", "text": "Always moving. New cities, new people, new experiences every few months.", "outcome_hint": "Novelty/Breadth"},
            {"value": "B", "text": "Rooted. A close community where I know everyone and build something lasting.", "outcome_hint": "Depth/Ritual"}
        ]
    },
    {
        "id": "S3_TheInfluence",
        "title": "How People Describe You",
        "story": "When your friends recommend you to someone new, what do they say about you?",
        "options": [
            {"value": "A", "text": "'You have to meet them — they light up every room they walk into.'", "outcome_hint": "Public Figure"},
            {"value": "B", "text": "'They're the person who always knows the right person to connect you with.'", "outcome_hint": "Community Builder"}
        ]
    },
    {
        "id": "S4_TheNewcomer",
        "title": "The New Kid",
        "story": "A new student joins your class mid-year and is standing alone at lunch, looking lost. What do you do?",
        "options": [
            {"value": "A", "text": "I walk straight over. 'Hey, want to sit with us?' No hesitation.", "outcome_hint": "Proactive includer"},
            {"value": "B", "text": "I make eye contact and smile so they know I'm approachable, then wait for them to come over.", "outcome_hint": "Passive availability"}
        ]
    },
    {
        "id": "S5_TheBrainstorm",
        "title": "Naming the Project",
        "story": "Your group needs to come up with a name for a class project in the next hour. How do you want to do it?",
        "options": [
            {"value": "A", "text": "All together, talking out loud. Group energy is where the magic happens for me.", "outcome_hint": "Collaborative thinker"},
            {"value": "B", "text": "Give me 15 minutes alone first. I'll come back with three strong options.", "outcome_hint": "Independent/Dyad thinker"}
        ]
    }
]

# Category 5: The Adaptable Strategist
# Theme: Systems, Efficiency, and Flexibility
scenarios_adaptable_strategist = [
    {
        "id": "S1_TheMeeting",
        "title": "Running the Meeting",
        "story": "Your teacher puts you in charge of running today's group session. What does your style look like?",
        "options": [
            {"value": "A", "text": "I set the goal and the vibe, then let everyone handle their own part.", "outcome_hint": "Delegating Architect"},
            {"value": "B", "text": "I guide every step — I like keeping things on track and making sure no one gets lost.", "outcome_hint": "Hands-on Facilitator"}
        ]
    },
    {
        "id": "S2_TheBridge",
        "title": "The Translator",
        "story": "In group projects, you often end up translating between the 'ideas people' and the 'detail people.' How does that feel?",
        "options": [
            {"value": "A", "text": "Natural. I like being the one who makes everyone understand each other.", "outcome_hint": "Integrator"},
            {"value": "B", "text": "Tiring. I'd rather just have clear roles and fewer miscommunications from the start.", "outcome_hint": "Specialist preference"}
        ]
    },
    {
        "id": "S3_TheEnergy",
        "title": "After the Big Presentation",
        "story": "You just finished a high-stakes class presentation. It went well, but it was intense. What do you need right now?",
        "options": [
            {"value": "A", "text": "Quiet time alone. A walk, music, or just lying down. I need to decompress.", "outcome_hint": "Introverted recharge"},
            {"value": "B", "text": "I need to talk about it. I want to debrief with a friend immediately.", "outcome_hint": "Extroverted processing"}
        ]
    },
    {
        "id": "S4_TheStrategy",
        "title": "Crisis Mode",
        "story": "Your club's big event falls apart 3 days before it happens. You need a new plan fast. Where do you start?",
        "options": [
            {"value": "A", "text": "I think it through alone first. I need to map out the options before I involve anyone.", "outcome_hint": "Internal processor"},
            {"value": "B", "text": "Emergency group chat. I think better when I'm bouncing ideas off people in real time.", "outcome_hint": "External processor"}
        ]
    },
    {
        "id": "S5_TheOffice",
        "title": "The New Classroom Layout",
        "story": "Your school switches to an open-plan setup with some private study pods. What's your honest reaction?",
        "options": [
            {"value": "A", "text": "I love it. I can switch between social and solo mode depending on what I need.", "outcome_hint": "Flexible/Adaptive"},
            {"value": "B", "text": "It's the worst of both worlds — too noisy for real focus, too impersonal for real connection.", "outcome_hint": "Separation preference"}
        ]
    }
]

# Category 6: The Versatile Seeker
# Theme: Novelty, Breadth, and Creativity
scenarios_versatile_seeker = [
    {
        "id": "S1_TheHobby",
        "title": "Your Hobby List",
        "story": "If someone asked you to list your hobbies or interests, what would that look like?",
        "options": [
            {"value": "A", "text": "A long, random list — photography, gaming, cooking, painting... I get obsessed with new things.", "outcome_hint": "Polymath/Dabbler"},
            {"value": "B", "text": "One or two things I've been doing for years and genuinely love deeply.", "outcome_hint": "Deep or indefinable"}
        ]
    },
    {
        "id": "S2_TheStartup",
        "title": "The Everything Role",
        "story": "A school startup team needs one person to handle social media, logistics, AND budgeting all at once. Does that excite you?",
        "options": [
            {"value": "A", "text": "Yes! I get to touch every part of it. That's the most interesting version of the job.", "outcome_hint": "Generalist thrive"},
            {"value": "B", "text": "No thanks. I'd rather do one thing really well than three things badly.", "outcome_hint": "Specialist preference"}
        ]
    },
    {
        "id": "S3_TheCollaboration",
        "title": "Creating Something New",
        "story": "Your class is designing a short film together. How do you like to create?",
        "options": [
            {"value": "A", "text": "With a partner. I love the back-and-forth — two minds are better than one.", "outcome_hint": "Collaborative creation"},
            {"value": "B", "text": "Alone first. I want to develop my own vision before anyone else's ideas get in the way.", "outcome_hint": "Solo creation"}
        ]
    },
    {
        "id": "S4_ThePrototype",
        "title": "The Rough Draft",
        "story": "You've built a rough but working version of an app idea for a school hackathon. What do you want to do next?",
        "options": [
            {"value": "A", "text": "Hand it off. The exciting part was figuring it out. The polishing feels like a slog.", "outcome_hint": "Starter/Inventor"},
            {"value": "B", "text": "Keep going. I'm not done until it actually looks and feels great.", "outcome_hint": "Finisher/Polisher"}
        ]
    },
    {
        "id": "S5_TheLearning",
        "title": "Learning Something New",
        "story": "You need to learn a complex new tool or skill for a class project. How do you approach it?",
        "options": [
            {"value": "A", "text": "I find a YouTube tutorial or ask a friend to show me. Learning by doing with others is my thing.", "outcome_hint": "Social/Active learner"},
            {"value": "B", "text": "I read the docs or watch a full course on my own. I need to understand the logic first.", "outcome_hint": "Solitary/Theory learner"}
        ]
    }
]

# Lookup map matching database 'phase_2_category' strings
CATEGORY_SCENARIOS_MAP = {
    "Focused Specialist": scenarios_focused_specialist,
    "Quiet Explorer": scenarios_curious_researcher,       # Maps to "The Curious Researcher"
    "Visionary Leader": scenarios_bold_driver,            # Maps to "The Bold Driver"
    "Adaptive Explorer": scenarios_social_catalyst,       # Maps to "The Social Catalyst"
    "Strategic Builder": scenarios_adaptable_strategist,  # Maps to "The Adaptable Strategist"
    "Dynamic Generalist": scenarios_versatile_seeker      # Maps to "The Versatile Seeker"
}