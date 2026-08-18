"""Pipeline runner for WebUI - runs the optimization pipeline in a background thread
with cancel/pause support.

Mirrors the pipeline in ``auto_forge.py`` but takes settings dicts instead of
argparse + CSV, and returns a state dict for later pruning/export.
"""

import argparse
import os
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading

import cv2
import numpy as np
import torch

from autoforge.Helper.AmpUtils import safe_autocast
from autoforge.Helper.FilamentHelper import hex_to_rgb
from autoforge.Helper.ImageHelper import imread, resize_image
from autoforge.Helper.OtherHelper import get_device, set_seed
from autoforge.Helper.OutputHelper import generate_stl
from autoforge.Modules.Optimizer import FilamentOptimizer
from autoforge.auto_forge import (
    _auto_select_background_color,
    _prepare_background_and_materials,
    _compute_pixel_sizes,
    _load_priority_mask,
    _initialize_heightmap,
    _prepare_processing_targets,
    _build_optimizer,
)
from autoforge.webui.helpers.colored_mesh import generate_colored_preview_mesh


# ---------------------------------------------------------------------------
# Defaults mirroring configargparse in auto_forge.py
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "input_image": "",
    "csv_file": "",
    "json_file": "",
    "output_folder": "output",
    "iterations": 6000,
    "warmup_fraction": 1.0,
    "learning_rate_warmup_fraction": 0.01,
    "init_tau": 1.0,
    "final_tau": 0.01,
    "learning_rate": 0.015,
    "layer_height": 0.04,
    "max_layers": 75,
    "min_layers": 0,
    "background_height": 0.24,
    "background_color": "#000000",
    "auto_background_color": True,
    "visualize": False,
    "stl_output_size": 150,
    "processing_reduction_factor": 2,
    "nozzle_diameter": 0.4,
    "early_stopping": 2000,
    "perform_pruning": False,
    "fast_pruning": True,
    "fast_pruning_percent": 0.25,
    "spike_removal": True,
    "spike_threshold_layers": 1,
    "pruning_max_colors": 100,
    "pruning_max_swaps": 100,
    "pruning_max_layer": 75,
    "random_seed": 0,
    "mps": False,
    "run_name": "",
    "tensorboard": False,
    "num_init_rounds": 32,
    "num_init_threads": 4,
    "num_init_cluster_layers": -1,
    "disable_visualization_for_gradio": 0,
    "best_of": 1,
    "discrete_check": 100,
    "flatforge": False,
    "cap_layers": 0,
    "init_heightmap_method": "kmeans",
    "priority_mask": "",
}


def _make_settings(overrides: dict) -> argparse.Namespace:
    """Build a namespace from a user-provided settings dict merged with defaults."""
    ns = argparse.Namespace(**(_DEFAULTS.copy()))
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


# ---------------------------------------------------------------------------
# Top-level pipeline (mirrors auto_forge.start())
# ---------------------------------------------------------------------------

def run_pipeline(
    input_image_path: str,
    active_filaments: List[Dict[str, Any]],
    output_dir: str,
    settings: dict,
    device: Optional[torch.device] = None,
    preview_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    cancel_event: Optional[threading.Event] = None,
    pause_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """Run the full optimization pipeline in the current thread.

    Parameters
    ----------
    input_image_path :
        Absolute path to the input image.
    active_filaments :
        List of filament dicts with keys ``color`` (hex ``#RRGGBB``),
        ``td`` (float), and ``name`` (str).
    output_dir :
        Directory for output artifacts (created if missing).
    settings :
        Arbitrary settings dict merged over defaults (see ``_DEFAULTS``).
    device :
        Torch device.  When ``None``, auto-detected via ``get_device()``.
    preview_callback :
        Called as ``preview_callback(optimizer, num_steps_done)`` periodically.
    cancel_event :
        When set, the optimization loop will exit at the next step boundary.
    pause_event :
        When set, the optimization loop will sleep in 100 ms intervals until
        cleared (or cancelled).

    Returns
    -------
    dict
        State dict with all intermediate data needed for ``export_results()``.
        Keys: ``optimizer, args, material_colors_np, material_TDs_np,
        material_names, colors_list, background, material_colors,
        material_TDs, device, alpha, output_target, focus_map_full,
        focus_map_proc, pixel_height_logits_init, global_logits_init,
        pixel_height_labels, processing_target, bg_rgb,
        num_init_cluster_layers, computed_output_size, cancelled``.
    """
    args = _make_settings(settings)
    args.input_image = input_image_path
    args.output_folder = output_dir

    if args.num_init_cluster_layers == -1:
        args.num_init_cluster_layers = args.max_layers

    # Skip CSV/JSON check in pipeline mode — we use active_filaments.
    # Override csv_file to prevent downstream errors from functions that read it.
    args.csv_file = ""
    args.json_file = ""

    if device is None:
        device = get_device(args)

    os.makedirs(args.output_folder, exist_ok=True)

    random_seed = set_seed(args)

    # --- Build material arrays from active_filaments list ---
    num_materials = len(active_filaments)
    material_colors_list = []
    material_TDs_list = []
    material_names_list = []
    colors_hex_list = []

    for f in active_filaments:
        rgb_norm = hex_to_rgb(f["color"])  # list of 3 floats in [0,1]
        td_val = float(f["td"])
        name = str(f.get("name", ""))
        material_colors_list.append(rgb_norm)
        material_TDs_list.append(td_val)
        material_names_list.append(name)
        colors_hex_list.append(f["color"])

    material_colors_np = np.array(material_colors_list, dtype=np.float64).reshape(
        -1, 3
    )
    material_TDs_np = np.array(material_TDs_list, dtype=np.float64)
    material_names = material_names_list
    colors_list = colors_hex_list
    material_uuids = [str(f.get("uuid", "")) for f in active_filaments]

    # --- Read input image ---
    img = imread(args.input_image, cv2.IMREAD_UNCHANGED)
    alpha = None
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
        alpha = alpha[..., None]
        img = img[:, :, :3]

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # --- Auto background color ---
    _auto_select_background_color(
        args, img_rgb, alpha, material_colors_np, material_names, colors_list
    )

    # --- Background & material tensors ---
    bg_rgb, background, material_colors, material_TDs = (
        _prepare_background_and_materials(
            args, device, material_colors_np, material_TDs_np
        )
    )

    # --- Sizes ---
    computed_output_size, computed_processing_size = _compute_pixel_sizes(args)

    # Resize alpha if present
    if alpha is not None:
        alpha = resize_image(alpha, computed_output_size)

    # Full-resolution target
    output_img_np = resize_image(img_rgb, computed_output_size)
    output_target = torch.tensor(output_img_np, dtype=torch.float32, device=device)

    # --- Priority mask (full-res) ---
    focus_map_full = _load_priority_mask(args, output_img_np, device)

    # --- Heightmap initialisation ---
    pixel_height_logits_init, global_logits_init, pixel_height_labels = (
        _initialize_heightmap(
            args,
            output_img_np,
            bg_rgb,
            material_colors_np,
            random_seed,
        )
    )

    # Apply alpha mask to full-res logits
    if alpha is not None:
        pixel_height_logits_init[alpha < 128] = -13.815512

    # --- Processing-resolution targets ---
    processing_img_np, processing_target, focus_map_proc, alpha_proc = (
        _prepare_processing_targets(
            output_img_np, computed_processing_size, device, focus_map_full,
            alpha_full=alpha,
        )
    )

    # Downscale initial logits/labels
    processing_pixel_height_logits_init = cv2.resize(
        src=pixel_height_logits_init,
        interpolation=cv2.INTER_NEAREST,
        dsize=(processing_target.shape[1], processing_target.shape[0]),
    )
    processing_pixel_height_labels = cv2.resize(
        src=pixel_height_labels,
        interpolation=cv2.INTER_NEAREST,
        dsize=(processing_target.shape[1], processing_target.shape[0]),
    )

    perception_loss_module = None

    # --- Build optimizer ---
    optimizer = _build_optimizer(
        args,
        processing_target,
        processing_pixel_height_logits_init,
        processing_pixel_height_labels,
        global_logits_init,
        material_colors,
        material_TDs,
        background,
        device,
        perception_loss_module,
        focus_map_proc,
        alpha_proc=alpha_proc,
    )

    # --- Run optimisation loop with cancel/pause support ---
    _run_optimization_loop(
        optimizer,
        args,
        device,
        preview_callback=preview_callback,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        pause_event=pause_event,
    )

    cancelled = (
        cancel_event.is_set() if cancel_event is not None else False
    )

    # --- Return everything for later export / inspection ---
    return {
        "optimizer": optimizer,
        "args": args,
        "material_colors_np": material_colors_np,
        "material_TDs_np": material_TDs_np,
        "material_names": material_names,
        "material_uuids": material_uuids,
        "colors_list": colors_list,
        "background": background,
        "material_colors": material_colors,
        "material_TDs": material_TDs,
        "device": device,
        "alpha": alpha,
        "output_target": output_target,
        "focus_map_full": focus_map_full,
        "focus_map_proc": focus_map_proc,
        "pixel_height_logits_init": pixel_height_logits_init,
        "global_logits_init": global_logits_init,
        "pixel_height_labels": pixel_height_labels,
        "processing_target": processing_target,
        "bg_rgb": bg_rgb,
        "num_init_cluster_layers": args.num_init_cluster_layers,
        "computed_output_size": computed_output_size,
        "cancelled": cancelled,
    }


# --- Optimisation loop with pause / cancel ---

def _run_optimization_loop(
    optimizer: FilamentOptimizer,
    args: argparse.Namespace,
    device: torch.device,
    preview_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    cancel_event: Optional[threading.Event] = None,
    pause_event: Optional[threading.Event] = None,
) -> None:
    """Run gradient-descent iterations, respecting cancel/pause events.

    Mirrors ``auto_forge._run_optimization_loop()`` but with cooperative
    cancellation and pausing, and optionally drives the preview callback
    from inside the loop (in addition to the optimizer's built-in callback).

    Parameters
    ----------
    progress_callback :
        Lightweight progress-only callback that fires every iteration.
        Should NOT do expensive work like image encoding.
    """
    from tqdm import tqdm

    tbar = tqdm(range(args.iterations))
    with safe_autocast(device):
        for i in tbar:
            # ---- pause support ----
            if pause_event is not None:
                while pause_event.is_set():
                    if cancel_event is not None and cancel_event.is_set():
                        break
                    time.sleep(0.1)

            # ---- cancel support ----
            if cancel_event is not None and cancel_event.is_set():
                print("\nOptimisation cancelled by user.")
                break

            loss_val = optimizer.step(record_best=i % args.discrete_check == 0)

            # Lightweight progress update every iteration — no image encoding
            if progress_callback is not None:
                try:
                    progress_callback(optimizer, optimizer.num_steps_done)
                except Exception:
                    traceback.print_exc()

            optimizer.visualize(interval=100)
            optimizer.log_to_tensorboard(interval=100)

            # Also drive external preview callback (for WebUI)
            # Fires every 25 iterations and includes image encoding
            if preview_callback is not None and (
                (i + 1) % 25 == 0 or i == args.iterations - 1
            ):
                try:
                    preview_callback(optimizer, optimizer.num_steps_done)
                except Exception:
                    traceback.print_exc()

            if (i + 1) % 100 == 0:
                tbar.set_description(
                    f"Iteration {i + 1}, Loss = {loss_val:.4f}, "
                    f"best validation Loss = {optimizer.best_discrete_loss:.4f}, "
                    f"learning_rate= {optimizer.current_learning_rate:.6f}"
                )

            if (
                optimizer.best_step is not None
                and optimizer.num_steps_done - optimizer.best_step
                > args.early_stopping
            ):
                print(
                    "Early stopping after",
                    args.early_stopping,
                    "steps without improvement.",
                )
                break


# ---------------------------------------------------------------------------
# Export: finalise and write all output files
# ---------------------------------------------------------------------------

def export_results(
    result: Dict[str, Any],
    cancel_event: Optional[threading.Event] = None,
    pause_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """Generate STL, preview PNG, swap instructions, project file and
    colored PLY mesh from the state dict produced by ``run_pipeline()``.

    Parameters
    ----------
    result : dict
        State dict from ``run_pipeline()``.

    Returns
    -------
    dict
        File paths keyed by type::

            {
                "preview_png": "...",
                "stl": "...",
                "colored_ply": "...",
                "swap_instructions": "...",
                "project_file": "...",
                "final_loss": float,
            }
    """
    optimizer: FilamentOptimizer = result["optimizer"]
    args: argparse.Namespace = result["args"]
    device: torch.device = result["device"]
    material_colors_np: np.ndarray = result["material_colors_np"]
    material_TDs_np: np.ndarray = result["material_TDs_np"]
    material_names: list = result["material_names"]
    alpha: Optional[np.ndarray] = result["alpha"]
    output_target: torch.Tensor = result["output_target"]
    focus_map_full: Optional[torch.Tensor] = result["focus_map_full"]
    focus_map_proc: Optional[torch.Tensor] = result["focus_map_proc"]
    pixel_height_logits_init: np.ndarray = result["pixel_height_logits_init"]
    pixel_height_labels: np.ndarray = result["pixel_height_labels"]

    post_opt_step = 0
    pruning_completed = True

    # Restore full-resolution logits & target
    optimizer.pixel_height_logits = torch.from_numpy(
        pixel_height_logits_init
    ).to(device)
    optimizer.best_params["pixel_height_logits"] = torch.from_numpy(
        pixel_height_logits_init
    ).to(device)
    optimizer.target = output_target
    optimizer.pixel_height_labels = torch.tensor(
        pixel_height_labels, dtype=torch.int32, device=device
    )
    if focus_map_proc is not None and focus_map_full is not None:
        optimizer.focus_map = focus_map_full

    with torch.no_grad():
        with safe_autocast(device):
            # ---- Pruning ----
            if args.perform_pruning:
                max_colors_for_pruning = args.pruning_max_colors
                if args.flatforge:
                    max_colors_for_pruning = max(1, args.pruning_max_colors - 2)
                else:
                    max_colors_for_pruning = max(1, args.pruning_max_colors - 1)

                pruning_completed = optimizer.prune(
                    max_colors_allowed=max_colors_for_pruning,
                    max_swaps_allowed=args.pruning_max_swaps,
                    min_layers_allowed=args.min_layers,
                    max_layers_allowed=args.pruning_max_layer,
                    search_seed=True,
                    fast_pruning=args.fast_pruning,
                    fast_pruning_percent=args.fast_pruning_percent,
                    cancel_event=cancel_event,
                    pause_event=pause_event,
                )

            disc_global, disc_height_image = optimizer.get_discretized_solution(
                best=True
            )

            # ---- Final loss ----
            from autoforge.Helper.PruningHelper import get_initial_loss

            final_loss = get_initial_loss(
                optimizer.best_params["global_logits"].shape[0], optimizer
            )
            with open(os.path.join(args.output_folder, "final_loss.txt"), "w") as f:
                f.write(f"{final_loss}")

            # ---- Preview PNG ----
            comp_disc = optimizer.get_best_discretized_image()
            args.max_layers = optimizer.max_layers

            comp_disc_np = comp_disc.cpu().numpy().astype(np.uint8)
            comp_disc_np = cv2.cvtColor(comp_disc_np, cv2.COLOR_RGB2BGR)
            preview_path = os.path.join(args.output_folder, "final_model.png")
            cv2.imwrite(preview_path, comp_disc_np)

            # ---- STL ----
            height_map_mm = (
                disc_height_image.cpu().numpy().astype(np.float32)
            ) * args.layer_height
            stl_path = os.path.join(args.output_folder, "final_model.stl")
            if args.flatforge:
                from autoforge.Helper.OutputHelper import generate_flatforge_stls

                generate_flatforge_stls(
                    disc_global.cpu().numpy(),
                    disc_height_image.cpu().numpy(),
                    material_colors_np,
                    material_names,
                    material_TDs_np,
                    args.layer_height,
                    args.background_height,
                    args.background_color,
                    args.stl_output_size,
                    args.output_folder,
                    cap_layers=args.cap_layers,
                    alpha_mask=alpha,
                )
            else:
                generate_stl(
                    height_map_mm,
                    stl_path,
                    args.background_height,
                    maximum_x_y_size=args.stl_output_size,
                    alpha_mask=alpha,
                )

            # ---- Colored PLY mesh ----
            color_image_np = cv2.cvtColor(comp_disc_np, cv2.COLOR_BGR2RGB)
            if color_image_np.shape[0] != height_map_mm.shape[0] or color_image_np.shape[1] != height_map_mm.shape[1]:
                from PIL import Image
                color_image_resized = np.array(
                    Image.fromarray(color_image_np).resize(
                        (height_map_mm.shape[1], height_map_mm.shape[0]),
                        Image.NEAREST,
                    ),
                    dtype=np.uint8,
                )
                if color_image_resized.shape[2] == 4:
                    color_image_resized = color_image_resized[:, :, :3]
                color_image_np = color_image_resized
            if color_image_np.shape[2] == 4:
                color_image_np = color_image_np[:, :, :3]
            color_image_np = np.ascontiguousarray(color_image_np)
            colored_mesh = generate_colored_preview_mesh(
                height_map=height_map_mm,
                color_image=color_image_np,
                background_height=args.background_height,
                maximum_x_y_size=args.stl_output_size,
                alpha_mask=alpha,
            )
            ply_path = os.path.join(args.output_folder, "final_model_colored.ply")
            colored_mesh.export(ply_path, encoding='binary')

            # ---- Swap instructions (traditional mode only) ----
            swap_path = None
            if not args.flatforge:
                from autoforge.Helper.OutputHelper import generate_swap_instructions

                background_layers = int(args.background_height // args.layer_height)
                swap_instructions = generate_swap_instructions(
                    disc_global.cpu().numpy(),
                    disc_height_image.cpu().numpy(),
                    args.layer_height,
                    background_layers,
                    args.background_height,
                    material_names,
                    getattr(args, "background_material_name", None),
                )
                swap_path = os.path.join(
                    args.output_folder, "swap_instructions.txt"
                )
                with open(swap_path, "w") as f:
                    for line in swap_instructions:
                        f.write(line + "\n")

            # ---- Project file (traditional mode only) ----
            project_path = None
            has_material_file = bool(args.csv_file) or bool(args.json_file)
            if not args.flatforge and has_material_file:
                from autoforge.Helper.OutputHelper import generate_project_file

                project_path = os.path.join(args.output_folder, "project_file.hfp")
                generate_project_file(
                    project_path,
                    args,
                    disc_global.cpu().numpy(),
                    disc_height_image.cpu().numpy(),
                    output_target.shape[1],
                    output_target.shape[0],
                    stl_path,
                    args.csv_file,
                )

            print("All done. Outputs in:", args.output_folder)

            return {
                "preview_png": preview_path,
                "stl": stl_path,
                "colored_ply": ply_path,
                "swap_instructions": swap_path,
                "project_file": project_path,
                "final_loss": final_loss,
                "pruning_completed": pruning_completed,
            }
