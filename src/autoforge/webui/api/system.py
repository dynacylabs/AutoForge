import torch
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/info")
async def system_info():
    mps_available = torch.backends.mps.is_available() if hasattr(torch.backends, "mps") else False
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        device = "cuda"
    elif mps_available:
        device = "mps"
    else:
        device = "cpu"
    return {
        "torchVersion": torch.__version__,
        "cudaAvailable": cuda_available,
        "mpsAvailable": mps_available,
        "device": device,
    }


@router.get("/device")
async def available_devices():
    devices = ["cpu"]
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            devices.append(f"cuda:{i}")
    return {"devices": devices}
