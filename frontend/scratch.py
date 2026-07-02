import random
mcqs = [{"options": [1, 2, 3, 4]}]
for q in mcqs:
    random.shuffle(q.get("options", []))
print(mcqs)
