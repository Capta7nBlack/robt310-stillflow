import io

import numpy as np
import pytest
from PIL import Image, ImageSequence

from stillflow.engine import (Arrow, Renderer, bilinear_sample, dense_flow,
                              feather_mask, resize_bilinear, temporal_metrics)
from stillflow.io import encode_gif


@pytest.fixture
def gradient():
    y, x = np.mgrid[:32, :48]
    return np.stack([x*4, y*6, x+y], axis=-1).astype(np.uint8)


def test_constant_field_from_single_arrow():
    field = dense_flow(11, 17, [Arrow(3, 5, 7, -4)])
    np.testing.assert_allclose(field[..., 0], 7, atol=1e-6)
    np.testing.assert_allclose(field[..., 1], -4, atol=1e-6)


def test_idw_matches_hand_calculation():
    # At x=2: weights are 1/5 and 1/10, so dx=(2/5+8/10)/(1/5+1/10)=4.
    field = dense_flow(1, 6, [Arrow(0, 0, 2, 0), Arrow(5, 0, 8, 0)], epsilon=1)
    assert field[0, 2, 0] == pytest.approx(4)


def test_zero_motion_anchor_reduces_local_flow():
    field = dense_flow(20, 40, [Arrow(3, 10, 10, 0), Arrow(35, 10, 0, 0)], epsilon=2)
    assert field[10, 35, 0] < .1
    assert field[10, 3, 0] > 9.9


def test_empty_arrows_return_zero_flow():
    assert not dense_flow(3, 8, []).any()


@pytest.mark.parametrize("epsilon", [0, -1, float("nan")])
def test_invalid_idw_epsilon(epsilon):
    with pytest.raises(ValueError):
        dense_flow(2, 2, [], epsilon)


def test_bilinear_four_neighbors():
    image = np.array([[0, 10], [20, 30]], dtype=np.float32)
    assert bilinear_sample(image, np.array([.25]), np.array([.75]))[0] == pytest.approx(17.5)


def test_bilinear_preserves_affine_ramp():
    y, x = np.mgrid[:10, :12]
    image = 3*x + 7*y + 5
    sx, sy = np.array([1.2, 5.7, 8.1]), np.array([2.4, 6.3, 1.5])
    np.testing.assert_allclose(bilinear_sample(image, sx, sy), 3*sx+7*sy+5, atol=1e-5)


def test_clamped_border_sampling():
    image = np.array([[1, 2], [3, 4]])
    np.testing.assert_array_equal(bilinear_sample(image, [-5, 7], [-2, 8]), [1, 4])


def test_single_pixel_image_is_valid():
    np.testing.assert_array_equal(bilinear_sample(np.array([[42]]), [0, 4], [-2, 0]), [42, 42])


def test_known_integer_translation_direction(gradient):
    renderer = Renderer(gradient, np.ones(gradient.shape[:2]), [Arrow(4, 4, 4, 0)], feather=0, loop=False)
    np.testing.assert_array_equal(renderer.frame(.5)[:, 2:], gradient[:, :-2])
    np.testing.assert_array_equal(renderer.frame(.5)[:, :2], np.repeat(gradient[:, :1], 2, axis=1))


def test_zero_displacement_is_identity(gradient):
    renderer = Renderer(gradient, np.ones(gradient.shape[:2]), [])
    for frame in renderer.frames(8):
        np.testing.assert_array_equal(frame, gradient)


def test_zero_mask_is_identity(gradient):
    renderer = Renderer(gradient, np.zeros(gradient.shape[:2]), [Arrow(2, 2, 8, 3)])
    np.testing.assert_array_equal(renderer.frame(.5), gradient)


def test_inward_feather_never_leaks():
    mask = np.zeros((30, 30), dtype=np.float32)
    mask[5:25, 5:25] = 1
    feathered = feather_mask(mask, 6)
    assert np.all(feathered[mask == 0] == 0)
    assert 0 < feathered[5, 5] < 1
    assert feathered[15, 15] == pytest.approx(1, abs=1e-6)


def test_gaussian_filter_preserves_constant_mask():
    np.testing.assert_allclose(feather_mask(np.ones((8, 8), dtype=np.float32), 5), 1, atol=1e-6)


def test_unpainted_pixels_remain_exact(gradient):
    mask = np.zeros(gradient.shape[:2], dtype=np.float32)
    mask[4:23, 10:30] = 1
    renderer = Renderer(gradient, mask, [Arrow(20, 12, 8, 3)])
    for frame in renderer.frames(16):
        np.testing.assert_array_equal(frame[mask == 0], gradient[mask == 0])


def test_continuous_loop_endpoints_match(gradient):
    renderer = Renderer(gradient, np.ones(gradient.shape[:2]), [Arrow(20, 12, 8, 3)])
    np.testing.assert_array_equal(renderer.frame(0), renderer.frame(1))


def test_raw_baseline_has_reset(gradient):
    renderer = Renderer(gradient, np.ones(gradient.shape[:2]), [Arrow(20, 12, 8, 3)], loop=False)
    assert np.mean(np.abs(renderer.frame(0).astype(float)-renderer.frame(1))) > 5


def test_blending_reduces_seam_on_controlled_image(gradient):
    mask = np.ones(gradient.shape[:2])
    arrows = [Arrow(20, 12, 8, 0)]
    raw = Renderer(gradient, mask, arrows, loop=False)
    looped = Renderer(gradient, mask, arrows, loop=True)
    raw_metrics = temporal_metrics(list(raw.frames(24)), gradient, mask)
    loop_metrics = temporal_metrics(list(looped.frames(24)), gradient, mask)
    assert loop_metrics["seam_mae"] < raw_metrics["seam_mae"] / 5


def test_no_motion_ratio_is_undefined(gradient):
    metrics = temporal_metrics([gradient, gradient], gradient, np.ones(gradient.shape[:2]))
    assert metrics["seam_ratio"] is None


def test_resize_preserves_aspect_and_limits(gradient):
    resized = resize_bilinear(gradient, 24)
    assert resized.shape == (16, 24, 3)
    np.testing.assert_array_equal(resize_bilinear(gradient, 768), gradient)


@pytest.mark.parametrize("phase", [-.1, 1.1, float("nan")])
def test_invalid_phase_rejected(gradient, phase):
    renderer = Renderer(gradient, np.ones(gradient.shape[:2]), [])
    with pytest.raises(ValueError):
        renderer.frame(phase)


def test_gif_preserves_frames_duration_and_static_pixels(gradient):
    mask = np.zeros(gradient.shape[:2])
    mask[5:25, 10:35] = 1
    frames = list(Renderer(gradient, mask, [Arrow(20, 12, 12, 0)]).frames(24))
    encoded, timing = encode_gif(frames, 12)
    with Image.open(io.BytesIO(encoded)) as gif:
        assert gif.n_frames == 24
        assert gif.info["loop"] == 0
        decoded = [np.asarray(f.convert("RGB")) for f in ImageSequence.Iterator(gif)]
        assert sum(f.info["duration"] for f in ImageSequence.Iterator(gif)) == 2000
        palette = Image.fromarray(frames[0]).quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        for source, frame in zip(frames, decoded):
            np.testing.assert_array_equal(frame[mask == 0], decoded[0][mask == 0])
            expected = Image.fromarray(source).quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
            np.testing.assert_array_equal(frame, np.asarray(expected))
    assert timing["duration_ms"] == 2000
