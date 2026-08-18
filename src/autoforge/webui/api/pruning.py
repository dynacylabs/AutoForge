import os
import copy
import threading
import uuid
from fastapi import APIRouter, HTTPException
from ..models import PruningSettings
from ..services.optimization_service import get_optimization_service
from ..config import config

router = APIRouter()


@router.post("/start")
async def start_pruning(settings: PruningSettings):
    svc = get_optimization_service()

    # Find the last completed optimization job
    history = svc.get_history()
    completed_jobs = [j for j in history if j.status == "completed"]
    if not completed_jobs:
        raise HTTPException(400, "No completed optimization result to prune")

    # Use the most recent completed job
    latest_job = completed_jobs[0]
    job_id = latest_job.job_id

    # Create a pruning job via the public API
    import datetime
    from datetime import timezone

    prune_job_id = f"prune-{uuid.uuid4().hex[:8]}"
    svc.create_job({"iterations": 1}, job_id=prune_job_id)
    cancel_event = svc.cancel_event(prune_job_id)
    pause_event = svc.pause_event(prune_job_id)

    def _run():
        try:
            svc.update_status(prune_job_id, "running")

            # Get the pipeline result for the optimization job
            pipeline_result = svc.get_pipeline_result(job_id)
            if not pipeline_result:
                svc.update_status(prune_job_id, "failed",
                                  error="No optimization pipeline result found. Please run optimization first.")
                return

            from ..helpers.pipeline_runner import export_results

            # Copy args to avoid mutating the stored pipeline result
            args = copy.copy(pipeline_result["args"])
            args.pruning_max_colors = settings.pruning_max_colors
            args.pruning_max_swaps = settings.pruning_max_swaps
            args.pruning_max_layer = settings.pruning_max_layer
            args.perform_pruning = True

            output_dir = os.path.join(config.checkpoints_path, job_id)
            args.output_folder = output_dir
            os.makedirs(output_dir, exist_ok=True)

            pipeline_result = dict(pipeline_result)
            pipeline_result["args"] = args

            # Report pruning progress through the optimizer's preview callback
            # so the frontend can show it in the top progress bar. The raw
            # per-pass percentages from PruningHelper are stage-relative and
            # non-monotonic (mostly ≤0 during color/layer reduction, then a
            # jump to 90-99 for swap-position optimisation), so we map them
            # onto a monotonic 0-100 scale.
            optimizer = pipeline_result["optimizer"]
            _last = 0.0
            _min_seen = 0.0

            def _prune_progress(_optimizer, _percent, phase=None):
                nonlocal _last, _min_seen
                if _percent >= 90:
                    # Swap-position optimisation phase: report as-is (90-99).
                    p = float(_percent)
                elif _percent > 0:
                    # Swap reduction phase: roughly the middle of the work.
                    p = 55 + min(float(_percent), 100.0) * 0.30
                elif _percent >= _min_seen:
                    # Color/layer reduction phase: values climb from a very
                    # negative start toward 0 as materials/layers are merged.
                    _min_seen = min(_min_seen, float(_percent))
                    denom = max(1e-9, 0.0 - _min_seen)
                    p = 5 + 50.0 * ((float(_percent) - _min_seen) / denom)
                else:
                    _min_seen = float(_percent)
                    p = 5.0
                _last = max(_last, min(p, 100.0))
                svc.update_status(prune_job_id, "running", progress=_last, phase=phase)

            optimizer.preview_callback = _prune_progress

            outputs = export_results(
                pipeline_result,
                cancel_event=cancel_event,
                pause_event=pause_event,
            )

            # Push the pruned slider stack to the frontend so the color core
            # and sliders reflect the final (reduced) solution. Skipped when
            # cancelled — the user explicitly asked to stop, so their
            # current sliders shouldn't be force-overwritten by whatever
            # partial state pruning happened to reach.
            if outputs.get("pruning_completed", True):
                try:
                    from ..helpers.sliders import derive_sliders_from_result
                    from .ws import broadcast_preview

                    slider_data = derive_sliders_from_result(pipeline_result)
                    if slider_data and slider_data["sliders"]:
                        final_image = optimizer.get_best_discretized_image()
                        if final_image is not None:
                            import base64
                            import cv2
                            import numpy as np

                            img_np = final_image.cpu().numpy().astype(np.uint8)
                            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                            _ok, buf = cv2.imencode('.png', img_bgr)
                            b64 = base64.b64encode(buf.tobytes()).decode('utf-8')
                            broadcast_preview(
                                b64,
                                # The pruned PLY/preview were regenerated in
                                # place for the *original* optimization job
                                # (`job_id`), not the pruning job
                                # (`prune_job_id`) — a client matches
                                # broadcasts against currentJob.job_id, which
                                # stays the optimization job throughout.
                                job_id=job_id,
                                sliders=slider_data["sliders"],
                                min_layer=slider_data["min_layer"],
                                max_layer=slider_data["max_layer"],
                            )
                except Exception:
                    import traceback
                    traceback.print_exc()

            if outputs.get("pruning_completed", True):
                svc.update_status(prune_job_id, "completed", progress=100.0, phase=None)
            else:
                # Cancelled between phases — the solution as of the last
                # completed phase was still exported above, so the partial
                # result is real and usable, just not fully pruned.
                svc.update_status(prune_job_id, "cancelled", phase=None)
        except Exception as e:
            import traceback
            traceback.print_exc()
            svc.update_status(prune_job_id, "failed", error=str(e))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"job_id": prune_job_id, "status": "running"}
