import os
import asyncio

def _get_app():
    # Import here so app package can use env vars set before run
    from app import main as appmod
    return appmod.app


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    dev_reload = os.getenv("DEV_RELOAD", "false").strip().lower() in ("1", "true", "yes")

    app = _get_app()

    # Windows stability fix for ProactorEventLoop and SSL issues
    import sys
    if sys.platform == 'win32':
        import asyncio
        from asyncio import WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
        print("DEBUG: Using WindowsSelectorEventLoopPolicy for stability", flush=True)

    try:
        from hypercorn.asyncio import serve
        from hypercorn.config import Config

        cfg = Config()
        cfg.bind = [f"{host}:{port}"]
        cfg.reload = dev_reload

        print(f"DEBUG: Starting server on {host}:{port}", flush=True)
        asyncio.run(serve(app, cfg))
    except ImportError as e:
        raise RuntimeError("Hypercorn is required to run this app without uvicorn. Install it with `pip install hypercorn`.") from e