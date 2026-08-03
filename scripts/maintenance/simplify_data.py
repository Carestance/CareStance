import os

# Shorten Class 12 / Above 12 questions to make Phase 4 less exhausting
for filename in ["data/questions_12th.py", "data/questions_above_12th.py"]:
    if not os.path.exists(filename): continue
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
    
    env = {}
    exec(content, env)
    var_name = [k for k in env.keys() if k.startswith('questions_')][0]
    shortened = env[var_name][:3] # Only keep 3 questions
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"{var_name} = [\n")
        for q in shortened:
            f.write("    {\n")
            for k, v in q.items():
                f.write(f"        '{k}': {repr(v)},\n")
            f.write("    },\n")
        f.write("]\n")

# Simplify Phase 3 scenarios to be more "user-oriented" and less fantasy-like
p3_file = "data/questions_phase3.py"
if os.path.exists(p3_file):
    with open(p3_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Tech scenarios
    content = content.replace("The Hidden Glitch", "Fixing a Critical Bug")
    content = content.replace("Let's imagine you are finalizing a critical project.", "You are finishing an important team project.")
    content = content.replace("The Uncharted Algorithm", "Solving a Complex Problem")
    content = content.replace("The Legacy Codebase", "Updating Old Software")
    content = content.replace("The Midnight Panic", "Last-Minute Emergency")

    # Art & Design scenarios
    content = content.replace("The Blank Canvas", "Starting a New Project")
    content = content.replace("The Architect of Dreams", "Designing a New Application")
    content = content.replace("The Silent Gallery", "Presenting Your Work")
    content = content.replace("The Collaborative Mural", "Team Brainstorming")
    content = content.replace("The Rejection Letter", "Handling Criticism")

    # Science scenarios
    content = content.replace("The Anomalous Result", "Unexpected Test Results")
    content = content.replace("The Late-Night Diagnosis", "Difficult Troubleshooting")
    
    # Business scenarios
    content = content.replace("The Sudden Departure", "Team Member Resigns")
    content = content.replace("The Budget Cut", "Handling Reduced Budget")
    content = content.replace("The Launch Day Crisis", "Release Day Issues")

    # General phrases
    content = content.replace("What does your gut tell you to do?", "What is your immediate reaction?")
    content = content.replace("How do you approach this blank slate?", "What is your first step?")

    with open(p3_file, "w", encoding="utf-8") as f:
        f.write(content)

print("Data shortened and simplified.")
