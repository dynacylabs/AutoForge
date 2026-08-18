import os
from pathlib import Path
from pydantic_settings import BaseSettings

class WebUIConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    checkpoints_dir: str = "checkpoints"
    uploads_dir: str = "uploads"
    library_dir: str = "filament_library"

    model_config = {"env_prefix": "AUTOFORGE_WEBUI_"}

    @property
    def checkpoints_path(self) -> str:
        return os.path.abspath(self.checkpoints_dir)

    @property
    def uploads_path(self) -> str:
        return os.path.abspath(self.uploads_dir)

    @property
    def library_path(self) -> str:
        return os.path.abspath(self.library_dir)


config = WebUIConfig()
