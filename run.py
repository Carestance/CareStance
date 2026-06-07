
import os
import asyncio


def _get_app():
    # Import here so app package can use env vars set before run
    from app import main as appmod
    return appmod.app


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    dev_reload = os.getenv("DEV_RELOAD", "false").strip().lower() in ("1", "true", "yes")

    app = _get_app()

    # Start with Hypercorn only, no uvicorn fallback.
    try:
        from hypercorn.asyncio import serve
        from hypercorn.config import Config

        cfg = Config()
        cfg.bind = [f"{host}:{port}"]
        cfg.reload = dev_reload

        asyncio.run(serve(app, cfg))
    except ImportError as e:
        raise RuntimeError("Hypercorn is required to run this app without uvicorn. Install it with `pip install hypercorn`.") from e
