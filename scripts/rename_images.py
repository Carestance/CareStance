import os
import shutil

directory = "/Users/rahulmanchanda/Desktop/Next Step/static/images/assessment"
files = os.listdir(directory)

for filename in files:
    if filename.endswith(".png") and " " in filename:
        parts = filename.split(" ")
        if len(parts) == 2:
            number = parts[0]
            option = parts[1].replace(".png", "")
            new_name = f"q{number}_{option}.png"
            old_path = os.path.join(directory, filename)
            new_path = os.path.join(directory, new_name)
            os.rename(old_path, new_path)
            print(f"Renamed: {filename} -> {new_name}")

# Handle missing 4 b.png by copying 4 a.png (now q4_a.png) if it exists
q4_a_path = os.path.join(directory, "q4_a.png")
q4_b_path = os.path.join(directory, "q4_b.png")

if os.path.exists(q4_a_path) and not os.path.exists(q4_b_path):
    shutil.copy(q4_a_path, q4_b_path)
    print(f"Created placeholder: {q4_b_path} from {q4_a_path}")
