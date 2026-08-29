import io
import os
import zipfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from ..config import config
from ..services.optimization_service import get_optimization_service

router = APIRouter()

# Mirrors what the CLI leaves behind in its `--output-folder` after a run.
_EXPORT_FILES = [
    "final_model.stl",
    "final_model_colored.ply",
    "final_model.png",
    "swap_instructions.txt",
    "final_loss.txt",
    "project_file.hfp",
]


def _job_path(job_id: str, filename: str) -> str:
    return os.path.join(config.checkpoints_path, job_id, filename)


@router.get("/stl/{job_id}")
async def download_stl(job_id: str):
    path = _job_path(job_id, "final_model.stl")
    if not os.path.exists(path):
        raise HTTPException(404, "STL not found")
    return FileResponse(path, filename=f"{job_id}.stl")


@router.get("/preview/{job_id}")
async def download_preview(job_id: str):
    path = _job_path(job_id, "final_model.png")
    if not os.path.exists(path):
        raise HTTPException(404, "Preview not found")
    return FileResponse(path, filename=f"{job_id}_preview.png")


@router.get("/instructions/{job_id}")
async def download_instructions(job_id: str):
    path = _job_path(job_id, "swap_instructions.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "Instructions not found")
    return FileResponse(path, filename=f"{job_id}_instructions.txt")


@router.get("/project/{job_id}")
async def download_project(job_id: str):
    path = _job_path(job_id, "project_file.hfp")
    if not os.path.exists(path):
        raise HTTPException(404, "Project file not found")
    return FileResponse(path, filename=f"{job_id}_project.hfp")


@router.get("/colored-ply/{job_id}")
async def download_colored_ply(job_id: str):
    path = _job_path(job_id, "final_model_colored.ply")
    if not os.path.exists(path):
        raise HTTPException(404, "Colored PLY not found")
    return FileResponse(path, filename=f"{job_id}_colored.ply")


@router.get("/export/{job_id}")
async def export_project(job_id: str):
    """Zip up a completed job's output files — STL, colored PLY, preview
    PNG, swap instructions, project file — as one downloadable bundle,
    mirroring the CLI's `--output-folder` contents after a run."""
    svc = get_optimization_service()
    job = svc.get_job(job_id)
    if not job or job.status != "completed":
        raise HTTPException(400, "No completed optimization result to export")

    job_dir = os.path.join(config.checkpoints_path, job_id)
    if not os.path.isdir(job_dir):
        raise HTTPException(404, "Job output folder not found")

    buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in _EXPORT_FILES:
            path = os.path.join(job_dir, filename)
            if os.path.exists(path):
                zf.write(path, arcname=filename)
                added += 1
    if added == 0:
        raise HTTPException(404, "No output files found for this job")

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{job_id}_export.zip"'},
    )
