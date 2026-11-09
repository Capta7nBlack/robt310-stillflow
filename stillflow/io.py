"""Image/project I/O and GIF encoding, kept separate from the numerical core."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .engine import Arrow, resize_bilinear

MAX_SIDE = 768
MAX_UPLOAD = 12 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 24_000_000


class MotionArrow(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    x: float = Field(ge=0, le=MAX_SIDE)
    y: float = Field(ge=0, le=MAX_SIDE)
    dx: float = Field(ge=-MAX_SIDE, le=MAX_SIDE)
    dy: float = Field(ge=-MAX_SIDE, le=MAX_SIDE)


class Settings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    frames: int = Field(default=24, ge=8, le=60)
    fps: int = Field(default=12, ge=4, le=24)
    intensity: float = Field(default=1, ge=0, le=2)
    feather: int = Field(default=10, ge=0, le=32)
    blend: float = Field(default=.35, ge=.1, le=.8)
    loop: bool = True


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    name: str = Field(default="Untitled", max_length=120)
    image: str = Field(max_length=20_000_000)
    mask: str = Field(max_length=8_000_000)
    arrows: list[MotionArrow] = Field(default_factory=list, max_length=64)
    settings: Settings = Field(default_factory=Settings)

    @field_validator("version")
    @classmethod
    def known_version(cls, value):
        if value != 1:
            raise ValueError("Unsupported project version; expected 1.")
        return value


def decode_image(data: bytes, *, grayscale=False, resize=False) -> np.ndarray:
    if len(data) > MAX_UPLOAD:
        raise ValueError("Image exceeds the 12 MB upload limit.")
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Please use a PNG, JPEG, or WebP still image.")
            if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError("Image exceeds the 24 megapixel input limit.")
            source = ImageOps.exif_transpose(source)
            if grayscale:
                image = np.asarray(source.convert("L"))
            else:
                # Transparent PNGs are consistently composited on white.
                if "A" in source.getbands() or "transparency" in source.info:
                    rgba = source.convert("RGBA")
                    white = Image.new("RGBA", rgba.size, "white")
                    source = Image.alpha_composite(white, rgba)
                image = np.asarray(source.convert("RGB"))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Could not decode this image.") from exc
    if resize:
        image = resize_bilinear(image, MAX_SIDE)
    elif max(image.shape[:2]) > MAX_SIDE:
        raise ValueError("Working image must be at most 768 pixels. Import it first.")
    return image


def png_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def data_url(array: np.ndarray) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes(array)).decode("ascii")


def from_data_url(value: str, *, grayscale=False) -> np.ndarray:
    if not value.startswith("data:image/") or ";base64," not in value:
        raise ValueError("Expected an embedded base64 image.")
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid image encoding.") from exc
    return decode_image(raw, grayscale=grayscale)


def project_arrays(project: Project):
    image = from_data_url(project.image)
    mask = from_data_url(project.mask, grayscale=True).astype(np.float32) / 255
    if mask.shape != image.shape[:2]:
        raise ValueError("Image and mask dimensions do not match.")
    h, w = mask.shape
    for arrow in project.arrows:
        if not 0 <= arrow.x < w or not 0 <= arrow.y < h:
            raise ValueError("An arrow starts outside the image.")
        if np.hypot(arrow.dx, arrow.dy) * project.settings.intensity > .4 * max(w, h):
            raise ValueError("Motion is too large. Shorten arrows or reduce intensity.")
    return image, mask, [Arrow(**a.model_dump()) for a in project.arrows]


def encode_gif(frames: list[np.ndarray], fps: int) -> tuple[bytes, dict]:
    """Use one palette for all frames to prevent palette-induced flicker.

    The GIF time unit is 10 ms. Distribute rounding error over frame durations
    rather than silently treating e.g. 12 fps as 12.5 fps.
    """
    if not frames or fps <= 0:
        raise ValueError("Frames and a positive frame rate are required.")
    palette = Image.fromarray(frames[0]).quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    images = [Image.fromarray(f).quantize(palette=palette, dither=Image.Dither.NONE)
              for f in frames]
    ticks = np.rint(np.arange(len(frames) + 1) * 100 / fps).astype(int)
    durations = (np.diff(ticks) * 10).tolist()
    buffer = io.BytesIO()
    # Keep the previous canvas so Pillow can store only changed rectangles.
    # A shared palette makes those delta frames color-consistent on playback.
    images[0].save(buffer, format="GIF", save_all=True, append_images=images[1:],
                   duration=durations, loop=0, optimize=False, disposal=1)
    return buffer.getvalue(), {"duration_ms": sum(durations), "frame_durations_ms": durations}


def load_example(path: Path) -> Project:
    """Example recipe paths are trusted repository files, never request paths."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    image = decode_image((path.parent / spec["image_file"]).read_bytes(), resize=True)
    h, w = image.shape[:2]
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    for polygon in spec["polygons"]:
        draw.polygon([(round(x * (w - 1)), round(y * (h - 1))) for x, y in polygon], fill=255)
    arrows = [MotionArrow(x=x*(w-1), y=y*(h-1), dx=dx*w, dy=dy*h)
              for x, y, dx, dy in spec["arrows"]]
    return Project(name=spec["name"], image=data_url(image), mask=data_url(np.asarray(mask)),
                   arrows=arrows, settings=Settings(**spec.get("settings", {})))
