"""The three algorithms proposed in the interim report, implemented in NumPy.

No OpenCV, scipy.ndimage, Pillow transforms, learned models, or ready-made
resampling functions are used here. Coordinates are (x, y), arrays are [y, x].
Displacements are pixels per cycle, not pixels per second.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class Arrow:
    x: float
    y: float
    dx: float
    dy: float


def coordinate_grid(height: int, width: int) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.mgrid[:height, :width]
    return x.astype(np.float32), y.astype(np.float32)


def dense_flow(height: int, width: int, arrows: Iterable[Arrow],
               epsilon: float = 12.0) -> np.ndarray:
    """Regularized Shepard interpolation, equation (1), O(H W K).

    Pins are zero-displacement arrows. Regularization makes the field smooth;
    annotations are soft constraints, so a pin is not an exact frozen pixel.
    The painted mask is the hard constraint on which pixels may change.
    """
    if height < 1 or width < 1 or not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("Positive image dimensions and epsilon are required.")
    x, y = coordinate_grid(height, width)
    numerator = np.zeros((height, width, 2), dtype=np.float32)
    denominator = np.zeros((height, width), dtype=np.float32)
    for arrow in arrows:
        if not np.isfinite([arrow.x, arrow.y, arrow.dx, arrow.dy]).all():
            raise ValueError("Arrow coordinates must be finite.")
        weights = 1.0 / ((x - arrow.x)**2 + (y - arrow.y)**2 + epsilon**2)
        numerator[..., 0] += weights * arrow.dx
        numerator[..., 1] += weights * arrow.dy
        denominator += weights
    np.divide(numerator, denominator[..., None], out=numerator,
              where=denominator[..., None] > 0)
    return numerator


def bilinear_sample(image: np.ndarray, sx: np.ndarray,
                    sy: np.ndarray) -> np.ndarray:
    """Explicit four-neighbor interpolation with clamped border sampling.

    Returns float32, supports both scalar and multichannel images. Source
    coordinates may be arbitrary broadcast-compatible arrays.
    """
    image = np.asarray(image, dtype=np.float32)
    if image.ndim not in (2, 3) or min(image.shape[:2]) < 1:
        raise ValueError("Expected a nonempty H x W or H x W x C image.")
    sx, sy = np.broadcast_arrays(np.asarray(sx, dtype=np.float32),
                                 np.asarray(sy, dtype=np.float32))
    if not np.isfinite(sx).all() or not np.isfinite(sy).all():
        raise ValueError("Sampling coordinates must be finite.")
    height, width = image.shape[:2]
    sx = np.clip(sx, 0, width - 1)
    sy = np.clip(sy, 0, height - 1)
    x0, y0 = np.floor(sx).astype(np.int32), np.floor(sy).astype(np.int32)
    x1, y1 = np.minimum(x0 + 1, width - 1), np.minimum(y0 + 1, height - 1)
    u, v = sx - x0.astype(np.float32), sy - y0.astype(np.float32)
    if image.ndim == 3:
        u, v = u[..., None], v[..., None]
    return ((1-u)*(1-v)*image[y0, x0] + u*(1-v)*image[y0, x1]
            + (1-u)*v*image[y1, x0] + u*v*image[y1, x1]).astype(np.float32)


def resize_bilinear(image: np.ndarray, max_side: int = 768) -> np.ndarray:
    """Fit within max_side using our sampler; never upscale."""
    height, width = image.shape[:2]
    if max_side < 1:
        raise ValueError("max_side must be positive.")
    scale = min(1.0, max_side / max(height, width))
    new_w, new_h = max(1, round(width * scale)), max(1, round(height * scale))
    if (new_h, new_w) == (height, width):
        return image.copy()
    # Pixel-center convention; low-pass antialiasing is not implemented.
    x = (np.arange(new_w, dtype=np.float32) + .5) / (new_w / width) - .5
    y = (np.arange(new_h, dtype=np.float32) + .5) / (new_h / height) - .5
    sampled = bilinear_sample(image, x[None, :], y[:, None])
    return np.rint(np.clip(sampled, 0, 255)).astype(np.uint8)


def feather_mask(mask: np.ndarray, radius: int = 8) -> np.ndarray:
    """Separable Gaussian blur, clipped inward to preserve unpainted pixels.

    Unlike an unrestricted blur, min(mask, blur(mask)) cannot animate a pixel
    with original mask value zero. Radius is kernel support in pixels.
    """
    mask = np.asarray(mask, dtype=np.float32)
    if mask.ndim != 2 or not np.isfinite(mask).all():
        raise ValueError("Mask must be a finite H x W array.")
    if (mask < 0).any() or (mask > 1).any() or radius < 0:
        raise ValueError("Mask must be in [0, 1] and radius nonnegative.")
    if radius == 0:
        return mask.copy()
    radius = int(radius)
    sigma = max(radius / 2.5, .5)
    k = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-.5 * (k / sigma)**2)
    kernel /= kernel.sum()
    blurred = mask.copy()
    for axis in (0, 1):
        pads = [(0, 0), (0, 0)]
        pads[axis] = (radius, radius)
        padded = np.pad(blurred, pads, mode="edge")
        out = np.zeros_like(blurred)
        for i, weight in enumerate(kernel):
            selection = [slice(None), slice(None)]
            selection[axis] = slice(i, i + mask.shape[axis])
            out += weight * padded[tuple(selection)]
        blurred = out
    return np.minimum(mask, np.clip(blurred, 0, 1))


class Renderer:
    """Cache the grid, interpolated field and feathered mask between frames."""

    def __init__(self, image: np.ndarray, mask: np.ndarray,
                 arrows: Iterable[Arrow], *, intensity: float = 1.0,
                 feather: int = 8, blend: float = .35,
                 loop: bool = True, epsilon: float = 12.0):
        image = np.asarray(image)
        if image.ndim != 3 or image.shape[2] != 3 or mask.shape != image.shape[:2]:
            raise ValueError("RGB image and mask dimensions must agree.")
        if not np.isfinite(image).all() or (image < 0).any() or (image > 255).any():
            raise ValueError("Image values must be finite and in [0, 255].")
        if not np.isfinite(intensity) or intensity < 0 or not 0 < blend <= 1:
            raise ValueError("Intensity must be nonnegative and blend in (0, 1].")
        self.image = image.astype(np.float32)
        self.original = np.rint(image).astype(np.uint8)
        self.mask = feather_mask(mask, feather)
        self.flow = dense_flow(*mask.shape, arrows, epsilon) * intensity
        self.x, self.y = coordinate_grid(*mask.shape)
        self.blend, self.loop = blend, loop

    def warp(self, phase: float) -> np.ndarray:
        return bilinear_sample(self.image, self.x - phase * self.flow[..., 0],
                               self.y - phase * self.flow[..., 1])

    def frame(self, phase: float) -> np.ndarray:
        """Equations (2)-(5). Accept t=1 to test the continuous endpoint."""
        if not np.isfinite(phase) or not 0 <= phase <= 1:
            raise ValueError("Phase must be in [0, 1].")
        moving = self.warp(phase)
        if self.loop and phase > 1 - self.blend:
            s = np.clip((phase - 1 + self.blend) / self.blend, 0, 1)
            alpha = s * s * (3 - 2 * s)
            moving = (1 - alpha) * moving + alpha * self.warp(phase - 1)
        composed = self.image + self.mask[..., None] * (moving - self.image)
        return np.rint(np.clip(composed, 0, 255)).astype(np.uint8)

    def frames(self, count: int = 24):
        if count < 2:
            raise ValueError("A loop needs at least two frames.")
        # Do not duplicate t=1: that would create a pause at the seam.
        for index in range(count):
            yield self.frame(index / count)


def temporal_metrics(frames: list[np.ndarray], original: np.ndarray,
                     painted_mask: np.ndarray) -> dict:
    """Diagnostics on RGB frames before lossy GIF palette quantization.

    Seam ratio is a warning signal, not a perceptual quality score. Both
    numerator and denominator use only the painted region. Null means that
    the denominator is zero, so a meaningful ratio cannot be computed.
    """
    active = painted_mask > 0
    static = ~active
    def difference(a, b):
        delta = np.abs(a.astype(np.float32) - b.astype(np.float32))
        return float(delta[active].mean()) if active.any() else 0.0
    adjacent = [difference(a, b) for a, b in zip(frames, frames[1:])]
    seam = difference(frames[-1], frames[0])
    median = float(np.median(adjacent))
    leakage = max((int(np.abs(f.astype(np.int16) - original.astype(np.int16))[static].max())
                   if static.any() else 0) for f in frames)
    motion = float(np.mean([difference(f, original) for f in frames]))
    return {"seam_mae": seam, "median_step_mae": median,
            "seam_ratio": seam / median if median > 1e-8 else None,
            "static_max_error": leakage, "mean_motion_mae": motion,
            "adjacent_mae": adjacent, "mask_fraction": float(active.mean())}
