from fastapi import APIRouter
from ..models import OptimizationSettings

router = APIRouter()

_settings = OptimizationSettings()


@router.get("")
async def get_settings():
    return _settings.model_dump(by_alias=True)


@router.put("")
async def update_settings(settings: OptimizationSettings):
    global _settings
    _settings = settings
    return _settings.model_dump(by_alias=True)


@router.get("/schema")
async def settings_schema():
    return OptimizationSettings.model_json_schema(by_alias=True)
