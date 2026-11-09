# Presentation rehearsal and handoff

Presenters: **Sayat Mushkin, Yerassyl Myngtay, Amir Ussembayev**. The deck has an author block and real outputs. It is a progress presentation, not an unreviewed replacement for the professor's final-report template.

## Before class

1. Open `progress.pptx` or the matching `progress.pdf`. Check that the names are spelled as you use them academically.
2. Run `start.bat` on Windows (or `sh start.sh`). Open `http://127.0.0.1:8000`, render the river preset once, and leave that tab open.
3. Keep `results/demo_river.mp4` and `results/gifs/river_full.gif` available as offline backups. Slides contain still figures; use the live browser or video to show motion.
4. Each presenter should run an example, inspect `stillflow/engine.py`, and be able to explain one algorithm. Assign speaking roles yourselves; names do not imply completed technical contributions.
5. If available, import a photograph your group actually captured, paint a suitable region, draw short arrows, render, and save the project. This directly improves the own-data evidence. Do not describe NPS photographs as your photographs.

The historical reason for changing from satellite-image upscaling, any instructor approval for that change, individual contributions, and short biographies are not supplied. Record the actual facts in `team.json`. The slides state the original and current scopes and the current technical rationale without inventing that history. Add real contributions and bios to the final report in the required course template.

## Suggested seven-minute flow

**0:00–0:45 — Goal and scope.** Introduce the team. Explain that the original proposal was satellite upscaling, while the interim/current implementation is interactive single-image animation. Give the real reason for the switch if confirmed. The present scope is small, controllable texture motion with classical algorithms.

**0:45–1:30 — Show the application.** Start with the river example and its completed loop. Explain the painted region and arrow length. The code now uploads, edits, renders, previews, saves projects, and exports GIFs. The source is public and the examples are reproducible.

**1:30–3:15 — Explain the three algorithms.** The flow field blends sparse arrows using regularized inverse-distance weighting. Backward mapping samples a source location for each output pixel; four neighboring pixels give the bilinear value. Two phase-shifted warps are blended near the cycle boundary, then composited with the inward-feathered mask.

**3:15–4:30 — Evidence.** Show the frame/flow figures and ablation chart. Read actual values from the generated table. Explain what seam ratio means and that it does not measure realism. Static error is exactly zero outside the original mask before encoding. Show the abrupt-reset comparison if time permits.

**4:30–5:30 — Correctness and cost.** Mention the automated numerical/API checks and browser verification. Explain that the runtime includes encoding; the memory number is process RSS rather than just NumPy allocations. Avoid implying a statistical benchmark from one run.

**5:30–6:30 — Limitations.** Cross-fading ghosts at high displacement; clamping stretches borders; no occluded content is generated. The examples are externally sourced photos with project-created annotations, plus a procedural diagnostic. There is no user study or measured physical ground truth.

**6:30–7:00 — Next work and code handoff.** Add genuine own-photo examples, improve masks, confirm actual contributions/bios, and prepare the final report in the required template. Share the repository link.

## Live demo sequence

1. Select **River rapids** → **Render loop** → **Original** → **Preview**.
2. Click **Edit**, show the mask, and enable the dense-flow overlay.
3. Draw one short arrow in the water. Undo it, redo it, then render.
4. Turn off **Blend the loop boundary** and render the baseline. Point out the last-to-first jump and compare the seam value.
5. Turn blending back on. Save the project and download the GIF. Explain that opening the project restores the annotations, not merely a screenshot.

Use a two-second, 24-frame preset for reliability. A 60-frame setting is supported, but it is unnecessary for a short presentation. Avoid drawing very long arrows or including rocks inside a moving-water mask.

## Likely questions

**What did you implement yourselves in the numerical pipeline?** The source explicitly implements IDW accumulation, coordinate grids, inverse mapping, the four bilinear weights, separable Gaussian mask feathering, smoothstep blending, and compositing. Pillow handles decoding/encoding and prepared example-mask rasterization; FastAPI serves the local interface. The project was developed with AI coding assistance; describe actual team understanding and contributions accurately.

**Why not optical flow?** There is only one input photograph, so there are no observed inter-frame correspondences. The arrows specify desired apparent motion rather than estimating true motion.

**Why backward warping?** It asks where each output pixel should obtain its value, avoiding holes from naive forward scattering. It still needs interpolation and a border policy.

**Is an anchor guaranteed to stay still?** No. The regularized IDW controls are soft. The mask gives the exact guarantee: an unpainted pixel has alpha zero. Erase the region if exact protection matters.

**Why does the output loop?** At t=0 the first phase is the source; at t=1 the second phase is the source. Smoothstep changes the blend weight smoothly. Finite frames omit t=1 to avoid a duplicate endpoint, so the last-to-first step is measured separately.

**Does seamless mean realistic?** No. Seam ratio measures only the temporal reset relative to ordinary changes. Cross-fade ghosting, texture stretching, and incorrect motion can remain even with a low seam ratio. The transition plot also exposes changes inside the fade window.

**Does the memory match the interim report?** One-frame working memory is O(HW), but the implementation retains N frames for diagnostics and GIF encoding, so the whole pipeline is O(NHW). The documentation states this correction explicitly.

**Are the images your own?** The three photographs are public-domain NPS reference data. The masks/arrows and analytic procedural scene are project-created. Do not claim own photographs unless the group adds actual captured data.

**Why no PSNR/SSIM?** There is no true animated reference for these still photographs. Numerical routines are checked against exact analytic cases, while visual artifacts and temporal/static diagnostics evaluate the outputs.

**How is this related to Le et al.?** Their paper motivates user-guided natural-image animation but uses preserve-curve warping. This simpler IDW prototype is not a reproduction and claims no algorithmic novelty. Wolberg and Heckbert support the sampling fundamentals.

**Why did the project topic change?** State the real team decision and any instructor discussion. The current scope rationale is controllable classical processing with a feasible prototype. Do not present that rationale as a confirmed historical event unless it is true.

## Group workflow

Clone the public repository, install requirements, and run the tests before editing. Use branches for changes. Saved personal projects and generated scratch outputs belong in the ignored `outputs/` folder. Commit only photographs you have permission to redistribute. Rebuild figures with `scripts/evaluate.py` and the deck with `scripts/build_presentation.py` after changing the method or demo parameters.

Do not fabricate a week of commit history, individual work assignments, bios, experiments, or approval from the instructor. The working code and measured results are the evidence.
