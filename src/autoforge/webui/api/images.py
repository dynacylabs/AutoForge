from fastapi import APIRouter, UploadFile, File, HTTPException
from ..services.image_service import get_image_service

router = APIRouter()


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    svc = get_image_service()
    data = await file.read()
    filename = file.filename or "image.png"
    image_id = svc.save_upload(filename, data)
    url = svc.get_url(image_id)
    return {"filename": image_id, "url": url}


@router.get("/{filename}")
async def get_image(filename: str):
    svc = get_image_service()
    path = svc.get_path(filename)
    if not path:
        raise HTTPException(404, "Image not found")
    from fastapi.responses import FileResponse
    return FileResponse(path)
