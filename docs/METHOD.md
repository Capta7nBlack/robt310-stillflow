# Method and implementation

The implementation follows the interim report's three proposed algorithms. It is an engineering prototype for small, user-directed motions in textured regions. It does not implement an automatic video generator or reproduce the full algorithm of Le et al. [1].

## Coordinates and inputs

An RGB image `I` has shape `(H, W, 3)` and values in `[0,255]`. A painted mask `M0` has shape `(H,W)` and values in `[0,1]`. All coordinates use `(x,y)`; array indexing uses `[y,x]`. Arrow `i` provides a start `p_i=(x_i,y_i)` and total-cycle displacement `a_i=(dx_i,dy_i)`. Positive x is rightward; positive y is downward. A soft anchor is an arrow whose displacement is zero. Motion strength scales the dense displacement; changing frame rate changes playback duration, not displacement per cycle.

Image decoding, EXIF orientation, and GIF encoding use Pillow. Canvas records the user's mask. Mask polygons in the bundled recipes are rasterized with Pillow as input preparation. The numerical warping, resizing, field construction, blur, and compositing are NumPy implementations.

## 1. Sparse controls to a dense flow field

For each pixel position `x`:

```math
w_i(x) = \frac{1}{\|x-p_i\|^2 + \epsilon^2},\qquad
D(x) = \frac{\sum_i w_i(x)a_i}{\sum_i w_i(x)}.
```

`epsilon=12` pixels regularizes the weights. A single arrow gives a uniform field. Multiple arrows blend smoothly; zero-motion anchors reduce nearby displacement. With no arrows, the mathematical routine returns zero flow, although the UI requires at least one nonzero arrow for animation.

This is a regularized Shepard-style interpolation [2]. Because epsilon is positive, controls are **soft**, not exactly interpolated in the presence of other arrows. An anchor does not guarantee a pixel remains still. The mask supplies that guarantee. The field has no fluid dynamics, divergence constraint, depth, or learned motion estimate.

Implementation: `dense_flow()` accumulates one control's contribution at a time, avoiding an H×W×K allocation. Cost: O(HWK), temporary storage O(HW).

## 2. Inverse mapping and bilinear reconstruction

At normalized time `t`, a destination pixel samples:

```math
A_t(x) = B(I, x-tD(x)).
```

Backward mapping assigns every destination pixel a source coordinate, avoiding holes from naive forward scattering. Wolberg [3, §3.1.2, p.44] provides the textbook background. A right-pointing arrow subtracts a positive source x offset, so the apparent texture moves to the right.

For source coordinates `(x0+u,y0+v)`, the sampler computes:

```math
B = (1-u)(1-v)I_{00} + u(1-v)I_{10}
    + (1-u)vI_{01} + uvI_{11}.
```

The four samples and weights are explicit array operations. See Wolberg [3, §5.4.2, p.127] for linear resampling and Heckbert [4] for filtering/aliasing considerations. Source coordinates clamp to the image boundary. Clamping avoids invalid memory reads but can visibly stretch edge textures. The input reduction uses the same sampler with pixel-center coordinates. It lacks a separate low-pass antialiasing filter, a documented limitation for severe reduction.

## 3. Loop construction and spatial compositing

A simple translation at `t=0,1/N,…,(N−1)/N` jumps when it returns to zero. Introduce a second phase:

```math
B_t(x)=B(I,x-(t-1)D(x)).
```

For a blend-window fraction `r`:

```math
s=\operatorname{clip}((t-1+r)/r,0,1),\qquad
\alpha=3s^2-2s^3,
```

```math
C_t=(1-\alpha)A_t+\alpha B_t,\qquad
F_t=I+M(C_t-I).
```

The presets use `r=0.4`, leaving the first 60% of the cycle as a single forward-moving phase. At the continuous endpoints, `C0=C1=I`. The finite last frame is at `(N−1)/N`, so it is **not** required to equal frame zero. Including both t=0 and t=1 in a GIF would duplicate an endpoint and create a pause. Endpoint equality is tested separately from the finite-frame seam diagnostic.

Smoothstep has zero slope at both ends of its blend interval. This removes a hard reset, but cross-fading differently shifted textures can still create double edges or a temporary loss of contrast. Exact endpoint equality does not prove physically correct or perceptually seamless motion.

The mask uses a self-written separable Gaussian kernel with finite support `radius` and `sigma=max(radius/2.5,0.5)`:

```math
M=\min(M_0, G_\sigma * M_0).
```

This is an **inward** feather: pixels with `M0=0` keep `M=0`. It makes the static-region guarantee stronger than an unrestricted blur, which could animate pixels outside the painted region. It does not guarantee perfect appearance at every boundary. The application also supports feather radius zero as an ablation.

## Encoding and infrastructure

A single palette is computed from the first frame and reused for all GIF frames. Disabling dithering avoids frame-dependent noise; palette sharing prevents static colors from flickering due to independent quantization. The encoder retains the previous canvas (GIF disposal mode 1), allowing changed rectangles to be stored without repeating the static background. GIF still discards color detail. Frame durations are multiples of 10 ms, with rounding distributed over the sequence so that 24 frames at 12 fps encode a 2.00-second loop. Identical frames can be merged without changing total playback time.

FastAPI exposes import, example, and render endpoints. The frontend uses plain HTML/Canvas/JavaScript instead of React; this is an infrastructure simplification, not a change to the proposed image-processing method. No JavaScript build tools or external CDN are needed at runtime.

One request renders at a time. RGB frames are accumulated for diagnostics and GIF encoding. The cached flow/grid and one frame need O(HW) memory, but the full current pipeline needs **O(NHW)** memory. This corrects the interim report's tentative sequential-memory expectation. GIF encoding and validation are included in reported total latency.

## Relationship to prior work and the proposal

Le et al. [1] use preserve-curve warping and cycle warping. This project borrows the broad idea of annotation-controlled still-image animation, with a much simpler IDW displacement and two-phase cross-fade. It makes no novelty or faithful-reproduction claim.

The original course proposal concerned satellite image upscaling. The interim report changed to single-image animation; this repository implements that interim scope. The current scope is justified by direct control, inspectable classical algorithms, and a feasible CPU demonstration. The team must supply the historical reason and any instructor approval for the earlier change; none is asserted here.

## References

1. T.-N.-H. Le, C.-K. Yeh, Y.-C. Lin, and T.-Y. Lee, “Animating Still Natural Images Using Warping,” *ACM Transactions on Multimedia Computing, Communications, and Applications*, 19(1), article 4, pp. 1–24, 2023. [DOI:10.1145/3511894](https://doi.org/10.1145/3511894). [Authors' project and paper](https://cgvsl-ncku.github.io/AnimatingImages/index.html). The online-first record is 2022; the journal issue is January 2023.
2. D. Shepard, “A two-dimensional interpolation function for irregularly-spaced data,” *Proceedings of the 1968 23rd ACM National Conference*, pp.517–524, 1968. [DOI:10.1145/800186.810616](https://doi.org/10.1145/800186.810616).
3. G. Wolberg, *Digital Image Warping*. IEEE Computer Society Press, 1990. [Author's textbook contents](https://www-cs.ccny.cuny.edu/~wolberg/diw.html): §3.1.2 Inverse Mapping, p.44; §3.5.1 Bilinear Interpolation, p.58 (geometric transformations); §5.4.2 Linear Interpolation, p.127 (resampling).
4. P. S. Heckbert, “Fundamentals of Texture Mapping and Image Warping,” University of California, Berkeley, technical report UCB/CSD-89-516, June 1989. [University record](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1989/5504.html).
5. [FastAPI: request files](https://fastapi.tiangolo.com/tutorial/request-files/) and [Pillow: GIF file format documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif), accessed November 9, 2026, for infrastructure behavior only.
