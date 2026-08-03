import re

with open("app/main.py", "r") as f:
    content = f.read()

# Add /assessment/api/phase2_mcqs endpoint before submit_phase2_mcqs
phase2_mcqs_code = """
@app.get("/assessment/api/phase2_mcqs")
async def get_phase2_mcqs(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    import json
    import os
    mcqs_path = os.path.join(os.path.dirname(__file__), "assessment_data", "phase2_mcqs.json")
    if os.path.exists(mcqs_path):
        with open(mcqs_path, "r", encoding="utf-8") as f:
            mcqs = json.load(f)
        return {"status": "success", "mcqs": mcqs}
    return {"status": "error", "detail": "Questions not found"}

"""

if "/assessment/api/phase2_mcqs" not in content:
    content = content.replace(
        '@app.post("/assessment/api/phase2/submit")',
        phase2_mcqs_code + '@app.post("/assessment/api/phase2/submit")'
    )

with open("app/main.py", "w") as f:
    f.write(content)
