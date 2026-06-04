import os
import sys

# Ensure the root directory is in the python path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Vercel entry point requires 'app' at the top level
try:
    from app.main import app
except Exception as e:
    import traceback
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse
    
    app = FastAPI()
    error_trace = traceback.format_exc()
    
    @app.get("/{path:path}")
    async def debug_error(request: Request, path: str):
        return HTMLResponse(content=f"<h1>Startup Error (CareStance)</h1><hr><pre style='color:red'>{error_trace}</pre>", status_code=500)

# Explicitly ensure app is top-level
application = app
handler = app
