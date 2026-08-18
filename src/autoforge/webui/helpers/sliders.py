"""Derive the ColorSlider stack from a discrete optimization solution.

The WebUI represents the print as a HueForge-style stack of up to 15 material
"sliders".  Each slider is a filament (material) occupying a contiguous range
of print layers; the slider's ``layer`` value is the top layer of its range.
The stack is read off the optimizer's discrete solution:

* ``disc_global`` is a 1D array of material indices, one per print layer.
* ``disc_height_image`` is the per-pixel height map (in layers); its
  min/max bound the layer range the sliders are allowed to occupy.
"""

import numpy as np

DEFAULT_MAX_SLIDERS = 15


def _slider_dict(
    material: int,
    end_layer: int,
    layer_height: float,
    material_tds: np.ndarray,
    material_uuids: list,
) -> dict:
    return {
        "td": float(material_tds[material]) if material < len(material_tds) else 5.0,
        "layer": int(end_layer),
        "depth_mm": round(float(end_layer) * float(layer_height), 2),
        "filament_uuid": (
            material_uuids[material] if material < len(material_uuids) else ""
        ),
        "enabled": True,
    }


def derive_sliders_from_optimizer(
    optimizer,
    material_tds: np.ndarray,
    material_uuids: list,
    layer_height: float,
    max_sliders: int = DEFAULT_MAX_SLIDERS,
):
    """Return ``{"sliders": [...], "min_layer": int, "max_layer": int}``.

    The sliders use snake_case keys matching the frontend ``ColorSliderConfig``
    type.  Returns ``None`` when the optimizer has no discretized solution yet.
    """
    disc_global, disc_height_image = optimizer.get_discretized_solution(best=True)
    if disc_global is None or disc_height_image is None:
        return None

    disc_global = disc_global.detach().cpu().numpy().reshape(-1).astype(int)
    height_map = disc_height_image.detach().cpu().numpy()
    min_layer = int(height_map.min())
    max_layer = int(height_map.max())

    if max_layer <= 0:
        return {"sliders": [], "min_layer": min_layer, "max_layer": max_layer}

    # Walk the printed stack (print layers 1..max_layer) and group
    # consecutive layers that use the same material into segments.
    n_stack = min(int(disc_global.shape[0]), max_layer)
    segments: list[list[int]] = []  # [material, start_layer, end_layer]
    current_material = None
    start = 1
    for layer in range(1, n_stack + 1):
        material = int(disc_global[layer - 1])
        if material != current_material:
            if current_material is not None:
                segments.append([current_material, start, layer - 1])
            current_material = material
            start = layer
    if current_material is not None:
        segments.append([current_material, start, n_stack])

    # Merge the smallest adjacent segments until we fit within the UI columns.
    while len(segments) > max_sliders:
        smallest = None
        best_span = float("inf")
        for i in range(len(segments) - 1):
            span = segments[i + 1][2] - segments[i][1] + 1
            if span < best_span:
                best_span = span
                smallest = i
        if smallest is None:
            break
        left = segments[smallest]
        right = segments[smallest + 1]
        left_span = left[2] - left[1] + 1
        right_span = right[2] - right[1] + 1
        # Keep the material of the larger span; the merged region spans both.
        if right_span > left_span:
            merged = [right[0], left[1], right[2]]
        else:
            merged = [left[0], left[1], right[2]]
        segments[smallest : smallest + 2] = [merged]

    sliders = [
        _slider_dict(material, end, layer_height, material_tds, material_uuids)
        for material, _start, end in segments
    ]

    return {"sliders": sliders, "min_layer": min_layer, "max_layer": max_layer}


def derive_sliders_from_result(result: dict, max_sliders: int = DEFAULT_MAX_SLIDERS):
    """Derive sliders from a pipeline result dict (see ``run_pipeline``)."""
    optimizer = result["optimizer"]
    material_tds = result.get("material_TDs_np")
    material_uuids = result.get("material_uuids", [])
    args = result.get("args")
    layer_height = float(getattr(args, "layer_height", 0.04)) if args else 0.04
    if material_tds is None:
        num_materials = int(optimizer.material_colors.shape[0])
        material_tds = np.zeros(num_materials, dtype=np.float64)
    return derive_sliders_from_optimizer(
        optimizer, material_tds, material_uuids, layer_height, max_sliders
    )
