"""Local FastAPI application. No image uploads leave this process."""

from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .io import MAX_UPLOAD, Project, data_url, decode_image, load_example
from .pipeline import render_project

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
EXAMPLES = ROOT / "examples"
app = FastAPI(title="Stillflow", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
render_slots = threading.BoundedSemaphore(1)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "NumPy", "version": "1.0.0"}


@app.post("/api/import")
async def import_image(file: UploadFile):
    try:
        content = await file.read(MAX_UPLOAD + 1)
        image = decode_image(content, resize=True)
        return {"image": data_url(image), "width": image.shape[1], "height": image.shape[0]}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        await file.close()


@app.get("/api/examples")
def list_examples():
    result = []
    for path in sorted(EXAMPLES.glob("*.json")):
        if path.name == "sources.json":
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(spec, dict) and "image_file" in spec:
            result.append({"id": path.stem, "name": spec["name"],
                           "description": spec.get("description", "")})
    return result


@app.get("/api/examples/{name}")
def example(name: str):
    allowed = {p.stem: p for p in EXAMPLES.glob("*.json") if p.name != "sources.json"}
    if name not in allowed:
        raise HTTPException(404, "Unknown example.")
    return load_example(allowed[name]).model_dump()


@app.post("/api/render")
def render(project: Project):
    if not render_slots.acquire(blocking=False):
        raise HTTPException(429, "A render is in progress. Please try again shortly.")
    try:
        gif, metrics, renderer, frames = render_project(project)
        h, w = renderer.mask.shape
        stride = max(16, min(w, h) // 14)
        vectors = [[x, y, float(renderer.flow[y, x, 0]), float(renderer.flow[y, x, 1])]
                   for y in range(stride//2, h, stride) for x in range(stride//2, w, stride)
                   if renderer.mask[y, x] > .05]
        return {"gif": "data:image/gif;base64," + base64.b64encode(gif).decode("ascii"),
                "metrics": metrics, "flow": vectors,
                "effective_mask": data_url((renderer.mask * 255).astype("uint8"))}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        render_slots.release()
