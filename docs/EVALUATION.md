# Evaluation protocol

All numbers in `results/metrics.json` are produced by `scripts/evaluate.py`. They are descriptive measurements of this prototype, not literature results or a user study. The script also writes a CSV table and the figures used in the presentation.

## Data

There are three externally sourced public-domain National Park Service photographs: river rapids, a waterfall, and clouds above a landscape. Their exact sources, authors, dimensions, licenses, and preparation are recorded in `examples/sources.json`. The fourth image is a deterministic analytic texture generated in `scripts/prepare_examples.py`, with a moving stripe and a stationary grid. Its purpose is controlled testing, not photorealism.

Masks and arrows are project-created annotations stored as JSON recipes. They are reproducible and editable in the browser. No student-captured photographs, measured physical velocities, reference videos, or perceptual ratings are claimed. The source manifest is intentionally explicit about this distinction.

## Numerical and integration checks

The automated suite checks a constant displacement field, an IDW case computed by hand, anchor behavior, exact bilinear weights, affine-ramp interpolation, clamped borders, translation direction, identity flow, zero-mask behavior, inward feathering, unchanged static pixels, continuous endpoint equality, abrupt-reset behavior, and GIF frame consistency/timing. API tests cover a complete render, upload scaling, malformed inputs, empty masks, missing controls, dimension mismatches, and parameter limits.

`scripts/browser_check.py` exercises real browser controls: rendering, preview, download, brush/erase, arrows/anchors, undo/redo, project save/restore, example selection, image import, help, and mobile overflow. It records actual screenshots rather than a mockup.

## Ablations

Each case is rendered under four conditions, with all other recipe parameters fixed:

| Condition | Purpose |
|---|---|
| Full method | Proposed two-phase loop, inward feathering, default displacement |
| No blend | Test the abrupt temporal reset from a single moving warp |
| No feather | Isolate mask-edge smoothing while retaining the loop construction |
| Large motion | Double displacement to expose stretching and ghosting sensitivity |

For each case, the script retains actual GIFs. Visual assessment should compare a full loop and the same selected frames, not just an attractive still frame. The large-motion ablation is a stress case; no universal numerical realism metric is claimed.

## Metrics

Let `A={x : M0(x)>0}`. For two RGB frames, `d(F,G)` is the mean absolute difference over pixels in A and all three color channels, on the original 0–255 scale.

- **Seam MAE:** `d(F[N−1],F[0])`.
- **Median step MAE:** median of `d(F[k],F[k+1])`, k=0,…,N−2.
- **Seam ratio:** seam MAE divided by median step MAE. A value near one means the boundary transition is comparable to an ordinary step. It does not rule out artifacts elsewhere in the loop. A zero denominator is recorded as `null`, not an invented score.
- **Static max error:** maximum absolute RGB difference between any frame and the original at pixels with M0=0. The inward mask makes zero an exact, testable property before encoding.
- **Mean motion MAE:** mean change from the original in A over the sequence. This checks that nonzero animation was actually produced; it is not an accuracy score.
- **Boundary change MAE:** average change from the source on painted pixels next to an unpainted 4-neighbor, averaged across frames. It measures boundary disturbance, not segmentation quality or perceptual seams.

The diagnostic figures plot every frame transition for the river case, so a favorable last-to-first ratio cannot conceal a large transition during the cross-fade. All numerical image metrics use RGB frames **before** GIF quantization. The test suite separately checks that static decoded GIF pixels remain consistent between frames under a shared palette.

## Runtime and memory

The benchmark uses 24 frames and three arrows on the river photograph at maximum side lengths 256, 512, and 768. Displacements and control positions scale with resolution. It records preparation, frame rendering, metric calculation, GIF encoding, and end-to-end time. Python, NumPy, operating system, CPU description, logical cores, and system RAM are recorded alongside the measurements.

Resident memory is sampled every 5 ms with psutil. The recorded peak includes Python, imported libraries, frames, numerical buffers, and encoding. Very short peaks may be missed. Runs share a process and the allocator may retain memory; both baseline and peak are reported, and the chart must not be interpreted as isolated per-algorithm allocations. Each setting is measured once; rerun for the presentation machine rather than claiming a stable benchmark or confidence interval.

## What this evaluation does not establish

It does not establish physical correctness, superiority over the cited paper, generalization to all images, absence of ghosting, or user satisfaction. No PSNR/SSIM is reported because there is no real animated ground truth for the photographs. The analytic interpolation tests supply exact numerical oracles; the photograph examples supply visible end-to-end evidence.
