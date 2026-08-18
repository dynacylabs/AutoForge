from fastapi import APIRouter, HTTPException
from ..models import StateSnapshot
from ..services.project_service import get_project_service
from ..services.optimization_service import get_optimization_service

router = APIRouter()


@router.post("/snapshot")
async def save_snapshot(snapshot: StateSnapshot):
    svc = get_project_service()
    sid = svc.save_snapshot(snapshot)
    return {"snapshot_id": sid}


@router.post("/restore")
async def restore_snapshot(request: dict):
    timestamp = request.get("timestamp")
    snapshot_id = request.get("snapshot_id")
    sid = str(snapshot_id or timestamp or "")
    svc = get_project_service()
    snapshot = svc.get_snapshot(sid)
    if not snapshot:
        raise HTTPException(404, "Snapshot not found")

    opt_svc = get_optimization_service()
    if snapshot.current_job_id:
        job = opt_svc.get_job(snapshot.current_job_id)
        if job and job.status in ("running", "paused"):
            opt_svc.cancel(snapshot.current_job_id)

    return snapshot.model_dump(by_alias=True)


@router.get("/history")
async def list_snapshots():
    svc = get_project_service()
    return [s.model_dump(by_alias=True) for s in svc.list_snapshots()]
