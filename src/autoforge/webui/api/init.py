import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_state = {"status": "idle", "preview_image": None}


@router.post("/run")
async def run_init():
    global _state
    if _state["status"] == "initializing":
        raise HTTPException(400, "Already initializing")
    _state = {"status": "initializing", "preview_image": None}

    def _run_stub():
        import time
        time.sleep(0.5)
        return None

    preview = await asyncio.to_thread(_run_stub)
    _state = {"status": "ready", "preview_image": preview}
    return {"status": "ready"}


@router.get("/status")
async def init_status():
    return _state


@router.get("/preview")
async def init_preview():
    if _state.get("preview_image"):
        return {"image": _state["preview_image"]}
    # Return a minimal transparent pixel so the frontend doesn't poll forever
    return {"image": None}
