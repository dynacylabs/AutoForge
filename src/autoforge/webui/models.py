from __future__ import annotations
import re
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import datetime


def _to_camel(s: str) -> str:
    s = re.sub(r'_[a-z]', lambda m: m.group(0)[1].upper(), s)
    return s


class CamelCaseModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class Filament(CamelCaseModel):
    brand: str = ""
    name: str = ""
    color: str = "#ffffff"
    td: float = 0.0
    owned: bool = False
    uuid: str = ""
    filament_type: str = ""
    source: str = "user"


class ColorSliderConfig(CamelCaseModel):
    td: float = 5.0
    layer: int = 0
    depth_mm: float = 0.0
    filament_uuid: str = ""
    enabled: bool = False



class OptimizationSettings(CamelCaseModel):
    input_image: str = ""
    csv_file: str = ""
    json_file: str = ""
    output_folder: str = "output"
    iterations: int = 6000
    warmup_fraction: float = 1.0
    learning_rate_warmup_fraction: float = 0.01
    init_tau: float = 1.0
    final_tau: float = 0.01
    learning_rate: float = 0.015
    layer_height: float = 0.04
    max_layers: int = 75
    min_layers: int = 0
    background_height: float = 0.24
    background_color: str = "#000000"
    auto_background_color: bool = True
    stl_output_size: int = 150
    processing_reduction_factor: int = 2
    nozzle_diameter: float = 0.4
    early_stopping: int = 2000
    perform_pruning: bool = False
    fast_pruning: bool = True
    fast_pruning_percent: float = 0.25
    spike_removal: bool = True
    spike_threshold_layers: int = 1
    pruning_max_colors: int = 100
    pruning_max_swaps: int = 100
    pruning_max_layer: int = 75
    random_seed: int = 0
    mps: bool = False
    run_name: Optional[str] = None
    tensorboard: bool = False
    num_init_rounds: int = 16
    num_init_cluster_layers: int = -1
    disable_visualization_for_gradio: int = 1
    best_of: int = 1
    discrete_check: int = 100
    flatforge: bool = False
    cap_layers: int = 0
    init_heightmap_method: str = "kmeans"
    priority_mask: str = ""
    visualize: bool = False


class JobStatus(CamelCaseModel):
    job_id: str = ""
    status: str = "pending"
    progress: float = 0.0
    iteration: int = 0
    total_iterations: int = 0
    loss: Optional[float] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    preview_image: Optional[str] = None
    phase: Optional[str] = None


class PruningSettings(CamelCaseModel):
    pruning_max_colors: int = 100
    pruning_max_swaps: int = 100
    pruning_max_layer: int = 75


class StateSnapshot(CamelCaseModel):
    timestamp: float = 0.0
    label: str = ""
    active_filaments: list[Filament] = Field(default_factory=list)
    color_sliders: list[ColorSliderConfig] = Field(default_factory=list)
    settings: OptimizationSettings = Field(default_factory=OptimizationSettings)
    input_image: Optional[str] = None
    current_job_id: Optional[str] = None
    optimization_result_id: Optional[str] = None


class ProjectState(CamelCaseModel):
    color_sliders: list[ColorSliderConfig] = Field(default_factory=list)
    settings: OptimizationSettings = Field(default_factory=OptimizationSettings)
    active_filaments: list[Filament] = Field(default_factory=list)
