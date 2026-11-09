"""Shared render path for the browser, CLI, tests, and evaluation script."""

from __future__ import annotations

import time

from .engine import Renderer, temporal_metrics
from .io import Project, encode_gif, project_arrays


def render_project(project: Project):
    started = time.perf_counter()
    image, mask, arrows = project_arrays(project)
    if not arrows or not any(a.dx != 0 or a.dy != 0 for a in arrows):
        raise ValueError("Draw at least one motion arrow before rendering.")
    if not (mask > 0).any():
        raise ValueError("Paint a region to animate before rendering.")
    settings = project.settings.model_dump()
    count, fps = settings.pop("frames"), settings.pop("fps")
    renderer = Renderer(image, mask, arrows, **settings)
    prepared = time.perf_counter()
    frames = list(renderer.frames(count))
    rendered = time.perf_counter()
    metrics = temporal_metrics(frames, image, mask)
    gif, timing = encode_gif(frames, fps)
    finished = time.perf_counter()
    metrics.update(timing)
    metrics.update({"width": image.shape[1], "height": image.shape[0], "frames": count,
                    "fps": fps, "prepare_seconds": prepared - started,
                    "render_seconds": rendered - prepared,
                    "total_seconds": finished - started, "gif_bytes": len(gif)})
    return gif, metrics, renderer, frames
