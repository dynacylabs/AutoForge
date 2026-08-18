from fastapi import APIRouter
from ..services.optimization_service import get_optimization_service
from ..helpers.sliders import derive_sliders_from_result

router = APIRouter()

_DEFAULTS = {"sliders": [], "min_layer": 0, "max_layer": 75}


@router.get("/from-optimizer")
async def get_sliders_from_optimizer():
    """Return the slider stack derived from the most recent completed job.

    The response shape is ``{"sliders": [...], "min_layer": int, "max_layer":
    int}`` where ``sliders`` use snake_case keys matching the frontend
    ``ColorSliderConfig`` type, and ``min_layer``/``max_layer`` bound the
    per-pixel height layers of the solution.
    """
    svc = get_optimization_service()
    for job in svc.get_history():
        if job.status != "completed":
            continue
        result = svc.get_pipeline_result(job.job_id)
        if not result:
            continue
        derived = derive_sliders_from_result(result)
        if derived:
            return derived
        return _DEFAULTS
    return _DEFAULTS
