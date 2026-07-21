"""AutoForge Web UI — FastAPI server with WebSocket progress streaming."""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import io
import json
import os
import tempfile
import threading
import traceback
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import cv2
import numpy as np
import torch
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="AutoForge Web UI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Only one GPU job runs at a time.
_executor = ThreadPoolExecutor(max_workers=1)
_jobs: Dict[str, "Job"] = {}


# ---------------------------------------------------------------------------
# Job model
# ---------------------------------------------------------------------------

class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class Job:
    def __init__(self, job_id: str, output_dir: str) -> None:
        self.job_id = job_id
        self.output_dir = output_dir
        self.status: str = JobStatus.PENDING
        self.error_msg: str = ""
        self.step: int = 0
        self.total_steps: int = 0
        self.preview_b64: Optional[str] = None
        self.messages: List[dict] = []   # replay buffer for late WebSocket connects
        self.queue: Optional[asyncio.Queue] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.cancel_event: threading.Event = threading.Event()
        self.output_files: List[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _push(job: Job, msg: dict) -> None:
    """Thread-safe: buffer the message and forward it to any open WebSocket."""
    job.messages.append(msg)
    if job.loop is not None and job.queue is not None:
        try:
            job.loop.call_soon_threadsafe(job.queue.put_nowait, msg)
        except Exception:
            pass


class _QueueWriter(io.TextIOBase):
    """Redirect print() / tqdm stdout/stderr output into the job message queue."""

    def __init__(self, job: Job) -> None:
        self._job = job
        self._buf = ""

    def write(self, text: str) -> int:  # type: ignore[override]
        for ch in text:
            if ch == "\n":
                line = self._buf.strip()
                self._buf = ""
                if line:
                    _push(self._job, {"type": "log", "message": line})
            elif ch == "\r":
                # tqdm-style carriage-return overwrite — discard current line
                self._buf = ""
            else:
                self._buf += ch
        return len(text)

    def flush(self) -> None:  # noqa: D401
        pass

    def fileno(self) -> int:
        raise io.UnsupportedOperation("fileno")

    @property
    def closed(self) -> bool:  # type: ignore[override]
        return False


# ---------------------------------------------------------------------------
# Worker (runs in a thread-pool thread)
# ---------------------------------------------------------------------------

def _worker(job: Job, args: argparse.Namespace) -> None:
    from autoforge.auto_forge import start as _run  # local import avoids cycles

    def preview_cb(optimizer, value: int) -> None:
        if job.cancel_event.is_set():
            raise RuntimeError("Job cancelled by user.")

        # During optimization the value is the step number (can exceed 100).
        # During pruning it is a 0-100 integer percentage.
        # We distinguish by comparing against a threshold.
        total = max(job.total_steps, 1)
        if isinstance(value, int) and value > 100:
            # Optimization step
            step = value
            job.step = step
            _push(job, {
                "type": "progress",
                "phase": "optimizing",
                "step": step,
                "total": total,
                "percent": min(100, int(step / total * 100)),
                "loss": float(getattr(optimizer, "loss", 0) or 0),
                "best_loss": float(getattr(optimizer, "best_discrete_loss", 0) or 0),
            })
        else:
            # Pruning percentage
            _push(job, {
                "type": "progress",
                "phase": "pruning",
                "percent": int(value),
            })

        # Encode and broadcast the current best discretized preview image.
        try:
            if optimizer.best_params is not None:
                with torch.no_grad():
                    img = optimizer.get_best_discretized_image()
                if img is not None:
                    img_np = img.cpu().numpy().astype(np.uint8)
                    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                    h, w = img_bgr.shape[:2]
                    if max(h, w) > 512:
                        scale = 512 / max(h, w)
                        img_bgr = cv2.resize(
                            img_bgr, (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_AREA,
                        )
                    _, buf = cv2.imencode(
                        ".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80]
                    )
                    b64 = base64.b64encode(buf.tobytes()).decode()
                    job.preview_b64 = b64
                    _push(job, {"type": "preview", "image": b64})
        except Exception:
            pass

    writer = _QueueWriter(job)

    try:
        job.status = JobStatus.RUNNING
        job.total_steps = args.iterations
        _push(job, {"type": "status", "status": JobStatus.RUNNING})
        _push(job, {"type": "log", "message": "Starting AutoForge pipeline…"})

        with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
            _run(args, preview_callback=preview_cb)

        # Collect generated output files (exclude uploaded inputs).
        job.output_files = sorted(
            f for f in os.listdir(job.output_dir)
            if os.path.isfile(os.path.join(job.output_dir, f))
            and not f.startswith("input_")
            and not f.startswith("filaments")
            and not f.startswith("priority_mask_")
            and f != "_results.zip"
        )
        job.status = JobStatus.DONE
        _push(job, {"type": "status", "status": JobStatus.DONE})
        _push(job, {"type": "done", "files": job.output_files})
        _push(job, {"type": "log", "message": "✓ Done! Click Download to get your results."})

    except RuntimeError as exc:
        if "cancelled" in str(exc).lower():
            job.status = JobStatus.CANCELLED
            _push(job, {"type": "status", "status": JobStatus.CANCELLED})
            _push(job, {"type": "log", "message": "Job was cancelled."})
        else:
            _handle_error(job, exc)

    except Exception as exc:
        _handle_error(job, exc)

    finally:
        # Signal to the WebSocket consumer that the stream is finished.
        _end = {"type": "__end__"}
        if job.loop is not None and job.queue is not None:
            try:
                job.loop.call_soon_threadsafe(job.queue.put_nowait, _end)
            except Exception:
                pass


def _handle_error(job: Job, exc: Exception) -> None:
    tb = traceback.format_exc()
    job.status = JobStatus.ERROR
    job.error_msg = str(exc)
    _push(job, {"type": "error", "message": str(exc)})
    _push(job, {"type": "log", "message": f"ERROR: {exc}"})
    _push(job, {"type": "log", "message": tb})
    _push(job, {"type": "status", "status": JobStatus.ERROR})


# ---------------------------------------------------------------------------
# Arg builder
# ---------------------------------------------------------------------------

def _build_args(
    output_dir: str,
    image_path: str,
    filament_ext: str,
    filament_path: str,
    pm_path: Optional[str],
    p: dict,
) -> argparse.Namespace:
    def _bool(key: str, default: bool) -> bool:
        v = p.get(key, default)
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes")

    def _int(key: str, default: int) -> int:
        try:
            return int(p.get(key, default))
        except (TypeError, ValueError):
            return default

    def _float(key: str, default: float) -> float:
        try:
            return float(p.get(key, default))
        except (TypeError, ValueError):
            return default

    def _str(key: str, default: str = "") -> str:
        return str(p.get(key, default))

    return argparse.Namespace(
        input_image=image_path,
        csv_file=filament_path if filament_ext == ".csv" else "",
        json_file=filament_path if filament_ext == ".json" else "",
        output_folder=output_dir,
        iterations=_int("iterations", 6000),
        warmup_fraction=_float("warmup_fraction", 1.0),
        learning_rate_warmup_fraction=_float("learning_rate_warmup_fraction", 0.01),
        init_tau=_float("init_tau", 1.0),
        final_tau=_float("final_tau", 0.01),
        learning_rate=_float("learning_rate", 0.015),
        layer_height=_float("layer_height", 0.04),
        max_layers=_int("max_layers", 75),
        min_layers=_int("min_layers", 0),
        background_height=_float("background_height", 0.24),
        background_color=_str("background_color", "#000000"),
        auto_background_color=_bool("auto_background_color", True),
        visualize=False,
        stl_output_size=_int("stl_output_size", 150),
        processing_reduction_factor=_int("processing_reduction_factor", 2),
        nozzle_diameter=_float("nozzle_diameter", 0.4),
        early_stopping=_int("early_stopping", 2000),
        perform_pruning=_bool("perform_pruning", True),
        fast_pruning=_bool("fast_pruning", True),
        fast_pruning_percent=_float("fast_pruning_percent", 0.25),
        spike_removal=_bool("spike_removal", True),
        spike_threshold_layers=_int("spike_threshold_layers", 1),
        spike_removal_passes=_int("spike_removal_passes", 4),
        pruning_max_colors=_int("pruning_max_colors", 100),
        pruning_max_swaps=_int("pruning_max_swaps", 100),
        pruning_max_layer=_int("pruning_max_layer", 75),
        pruning_batch_size=_int("pruning_batch_size", 8),
        random_seed=_int("random_seed", 0),
        mps=_bool("mps", False),
        run_name=_str("run_name", ""),
        tensorboard=_bool("tensorboard", False),
        num_init_rounds=_int("num_init_rounds", 64),
        num_init_threads=_int("num_init_threads", 4),
        num_init_cluster_layers=_int("num_init_cluster_layers", -1),
        disable_visualization_for_gradio=1,
        best_of=_int("best_of", 1),
        discrete_check=_int("discrete_check", 100),
        flatforge=_bool("flatforge", False),
        cap_layers=_int("cap_layers", 0),
        init_heightmap_method=_str("init_heightmap_method", "kmeans"),
        priority_mask=pm_path or "",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    html_path = os.path.join(STATIC_DIR, "index.html")
    with open(html_path, encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.post("/api/jobs", response_class=JSONResponse)
async def create_job(
    image: UploadFile = File(...),
    filament_file: UploadFile = File(...),
    params: str = Form("{}"),
    priority_mask: Optional[UploadFile] = File(None),
) -> JSONResponse:
    try:
        p: dict = json.loads(params)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid params JSON"}, status_code=400)

    job_id = str(uuid.uuid4())
    output_dir = tempfile.mkdtemp(prefix=f"autoforge_{job_id}_")

    # Save input image
    image_fname = image.filename or "input.jpg"
    image_path = os.path.join(output_dir, "input_" + image_fname)
    with open(image_path, "wb") as fh:
        fh.write(await image.read())

    # Save filament library (CSV or JSON)
    fil_ext = os.path.splitext(filament_file.filename or "filaments.csv")[1].lower()
    if fil_ext not in (".csv", ".json"):
        fil_ext = ".csv"
    filament_path = os.path.join(output_dir, "filaments" + fil_ext)
    with open(filament_path, "wb") as fh:
        fh.write(await filament_file.read())

    # Optional priority mask
    pm_path: Optional[str] = None
    if (
        priority_mask is not None
        and priority_mask.filename
        and priority_mask.filename.strip()
    ):
        pm_fname = priority_mask.filename
        pm_path = os.path.join(output_dir, "priority_mask_" + pm_fname)
        with open(pm_path, "wb") as fh:
            fh.write(await priority_mask.read())

    args = _build_args(output_dir, image_path, fil_ext, filament_path, pm_path, p)
    job = Job(job_id, output_dir)
    _jobs[job_id] = job
    _executor.submit(_worker, job, args)

    return JSONResponse({"job_id": job_id})


@app.get("/api/jobs/{job_id}", response_class=JSONResponse)
async def get_job_status(job_id: str) -> JSONResponse:
    job = _jobs.get(job_id)
    if job is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({
        "job_id": job_id,
        "status": job.status,
        "step": job.step,
        "total": job.total_steps,
        "files": job.output_files,
        "error": job.error_msg,
        "has_preview": job.preview_b64 is not None,
    })


@app.get("/api/jobs/{job_id}/preview")
async def get_preview(job_id: str):
    """Return the most recent preview JPEG (for reconnecting clients)."""
    from fastapi.responses import Response
    job = _jobs.get(job_id)
    if job is None or job.preview_b64 is None:
        return JSONResponse({"error": "No preview available"}, status_code=404)
    data = base64.b64decode(job.preview_b64)
    return Response(content=data, media_type="image/jpeg")


@app.post("/api/jobs/{job_id}/cancel", response_class=JSONResponse)
async def cancel_job(job_id: str) -> JSONResponse:
    job = _jobs.get(job_id)
    if job is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    job.cancel_event.set()
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_id}/download")
async def download_job(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    if job.status != JobStatus.DONE:
        return JSONResponse({"error": "Job not complete yet"}, status_code=400)

    zip_path = os.path.join(job.output_dir, "_results.zip")
    if not os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname in job.output_files:
                full = os.path.join(job.output_dir, fname)
                if os.path.isfile(full):
                    zf.write(full, fname)

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="autoforge_results.zip",
    )


@app.websocket("/ws/{job_id}")
async def ws_endpoint(ws: WebSocket, job_id: str) -> None:
    await ws.accept()

    job = _jobs.get(job_id)
    if job is None:
        await ws.send_json({"type": "error", "message": "Job not found"})
        await ws.close()
        return

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    job.loop = loop
    job.queue = queue

    # Replay buffered history so a late-connecting client sees everything.
    for msg in list(job.messages):
        await ws.send_json(msg)

    if job.status in (JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELLED):
        await ws.close()
        return

    try:
        while True:
            recv_task = asyncio.create_task(ws.receive_text())
            send_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                {recv_task, send_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

            if recv_task in done:
                try:
                    data = json.loads(recv_task.result())
                    if data.get("type") == "cancel":
                        job.cancel_event.set()
                except Exception:
                    pass

            if send_task in done:
                msg = send_task.result()
                if msg.get("type") == "__end__":
                    break
                await ws.send_json(msg)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        job.queue = None
        job.loop = None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_server(host: str = "0.0.0.0", port: int = 7860) -> None:
    """Start the uvicorn ASGI server."""
    import uvicorn  # imported here so the module can be imported without uvicorn installed
    uvicorn.run(app, host=host, port=port)


def main_cli() -> None:
    """``autoforge-webui`` command-line entry point."""
    import argparse as _ap

    parser = _ap.ArgumentParser(description="AutoForge Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860, help="Port (default: 7860)")
    a = parser.parse_args()
    print(f"Starting AutoForge Web UI at http://{a.host}:{a.port}")
    run_server(a.host, a.port)


if __name__ == "__main__":
    main_cli()
