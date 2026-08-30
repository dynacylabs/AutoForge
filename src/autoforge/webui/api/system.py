import json
import re
import time
import urllib.error
import urllib.request
from importlib.metadata import PackageNotFoundError, version as pkg_version

import torch

from autoforge.Helper.DeviceUtils import (
    backend_of,
    cuda_is_available,
    describe_device,
    is_rocm,
    mps_is_available,
    resolve_device,
)
from fastapi import APIRouter

router = APIRouter()

_GITHUB_REPO = "hvoss-techfak/AutoForge"
_UPDATE_CACHE_TTL = 3600  # seconds — avoid hitting GitHub's API on every page load
_update_cache: dict = {"checked_at": 0.0, "data": None}


def _current_version() -> str:
    for name in ("autoforge", "AutoForge"):
        try:
            return pkg_version(name)
        except PackageNotFoundError:
            continue
    return "unknown"


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(re.sub(r"\D", "", part) or 0) for part in v.split("."))


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/version")
async def get_version():
    return {"version": _current_version(), "repo": _GITHUB_REPO}


@router.get("/update-check")
async def check_for_update():
    """Best-effort check against GitHub's latest-release API. Never raises —
    a network hiccup or rate limit just means no update badge, not a broken
    page. Cached briefly so repeated page loads don't hammer the API."""
    now = time.time()
    cached = _update_cache["data"]
    if cached is not None and (now - _update_cache["checked_at"]) < _UPDATE_CACHE_TTL:
        return cached

    current = _current_version()
    result = {
        "current_version": current,
        "latest_version": None,
        "update_available": False,
        "release_url": f"https://github.com/{_GITHUB_REPO}/releases/latest",
        "error": None,
    }
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "AutoForge-WebUI"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latest_tag = str(data.get("tag_name", "")).lstrip("v")
        result["latest_version"] = latest_tag or None
        result["release_url"] = data.get("html_url", result["release_url"])
        if latest_tag and current != "unknown":
            result["update_available"] = _version_tuple(latest_tag) > _version_tuple(current)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        result["error"] = str(e)

    _update_cache["data"] = result
    _update_cache["checked_at"] = now
    return result


@router.get("/info")
async def system_info():
    device = resolve_device()
    cuda_available = cuda_is_available()
    mps_available = mps_is_available()
    return {
        "torchVersion": torch.__version__,
        # PyTorch reports AMD GPUs through the CUDA API, so `cudaAvailable`
        # stays True on ROCm (existing clients depend on that); `backend`
        # is what actually distinguishes the two.
        "cudaAvailable": cuda_available,
        "mpsAvailable": mps_available,
        "rocmAvailable": cuda_available and is_rocm(),
        "backend": backend_of(device),
        "device": str(device),
        "deviceDescription": describe_device(device),
    }


@router.get("/device")
async def available_devices():
    """Every device the user could select, most capable first."""
    devices = []
    if cuda_is_available():
        for i in range(torch.cuda.device_count()):
            devices.append(f"cuda:{i}")
    if mps_is_available():
        devices.append("mps")
    devices.append("cpu")
    return {"devices": devices, "default": str(resolve_device())}
