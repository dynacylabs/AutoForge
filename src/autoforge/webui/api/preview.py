import os

from fastapi import APIRouter, HTTPException

from ..config import config
from ..services.optimization_service import get_optimization_service
from ..services.filament_service import get_filament_service
from ..helpers.slider_render import render_with_sliders
from .ws import broadcast_preview

router = APIRouter()


def _latest_completed_job():
    svc = get_optimization_service()
    for job in svc.get_history():
        if job.status == "completed":
            return job
    return None


@router.post("/render-with-sliders")
async def render_preview(data: dict):
    """Recompute the composite preview + colored PLY for the most recent
    completed optimization job, using an edited color-slider stack.

    The per-pixel height solution from that job is unchanged — only the
    layer→material assignment (and therefore the compositing) is redone,
    so this is cheap enough to run on every slider drag/edit.
    """
    sliders = data.get("sliders", [])
    svc = get_optimization_service()
    filament_svc = get_filament_service()

    job = _latest_completed_job()
    if job is None:
        raise HTTPException(400, "No completed optimization result to render")

    pipeline_result = svc.get_pipeline_result(job.job_id)
    if not pipeline_result:
        raise HTTPException(400, "No optimization pipeline result found")

    filament_lookup = {f.uuid: f.model_dump() for f in filament_svc.list()}
    # The frontend also sends the currently active filament list, which may
    # include filaments not (yet) present in the saved library.
    for f in data.get("active_filaments", []) or []:
        uuid_ = str(f.get("uuid", ""))
        if uuid_ and uuid_ not in filament_lookup:
            filament_lookup[uuid_] = f

    output_dir = os.path.join(config.checkpoints_path, job.job_id)
    result = render_with_sliders(pipeline_result, sliders, filament_lookup, output_dir)
    if result is None:
        return {"status": "no_solution", "job_id": job.job_id}

    if result["image_b64"]:
        broadcast_preview(result["image_b64"], job_id=job.job_id, sliders=sliders)

    return {"status": "ok", "job_id": job.job_id, "slider_count": len(sliders)}
