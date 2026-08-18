import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..config import config

router = APIRouter()


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
