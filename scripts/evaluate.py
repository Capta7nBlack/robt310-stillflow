"""Reproduce demo GIFs, diagnostic figures, ablations and measured benchmarks.

Run from the repository: python scripts/evaluate.py
All measurements come from actual rendering on the current machine.
"""

from __future__ import annotations

import csv
import json
import platform
import sys
import threading
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import psutil
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stillflow.engine import Arrow, Renderer, resize_bilinear, temporal_metrics
from stillflow.io import encode_gif, load_example, project_arrays

OUT = ROOT / "results"
plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10,
                     "axes.spines.top":False, "axes.spines.right":False,
                     "savefig.facecolor":"white", "figure.facecolor":"white"})


class MemorySampler:
    """Sample process resident memory every 5 ms; not an allocation profiler."""
    def __enter__(self):
        self.process = psutil.Process()
        self.baseline = self.process.memory_info().rss
        self.peak = self.baseline
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self.sample, daemon=True)
        self.worker.start()
        return self

    def sample(self):
        while not self.stop.wait(.005):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def __exit__(self, *args):
        self.peak = max(self.peak, self.process.memory_info().rss)
        self.stop.set()
        self.worker.join()


def measured_render(image, mask, arrows, settings):
    options = dict(settings)
    count, fps = options.pop("frames"), options.pop("fps")
    with MemorySampler() as memory:
        start = time.perf_counter()
        renderer = Renderer(image, mask, arrows, **options)
        prepared = time.perf_counter()
        frames = list(renderer.frames(count))
        rendered = time.perf_counter()
        metrics = temporal_metrics(frames, image, mask)
        measured = time.perf_counter()
        gif, timing = encode_gif(frames, fps)
        encoded = time.perf_counter()
    # How much did the innermost boundary change relative to the source?
    active = mask > 0
    pad = np.pad(active, 1, constant_values=False)
    interior = pad[:-2,1:-1]&pad[2:,1:-1]&pad[1:-1,:-2]&pad[1:-1,2:]
    boundary = active & ~interior
    boundary_change = float(np.mean([np.abs(f.astype(float)-image)[boundary].mean()
                                     if boundary.any() else 0 for f in frames]))
    metrics.update(timing)
    metrics.update({"width":image.shape[1], "height":image.shape[0], "frames":count,"fps":fps,
                    "prepare_seconds":prepared-start,"render_seconds":rendered-prepared,
                    "metrics_seconds":measured-rendered,"encode_seconds":encoded-measured,
                    "total_seconds":encoded-start,"gif_bytes":len(gif),
                    "rss_peak_mb":memory.peak/1024**2,"rss_baseline_mb":memory.baseline/1024**2,
                    "boundary_change_mae":boundary_change})
    return renderer, frames, gif, metrics


def diagnostic_figure(name, image, mask, renderer, frames):
    fig, axes = plt.subplots(1,4,figsize=(14,4),constrained_layout=True)
    axes[0].imshow(image);axes[0].set_title("Input photograph" if name!="synthetic" else "Procedural test image")
    axes[1].imshow(image);axes[1].imshow(renderer.mask,cmap="Greens",vmin=0,vmax=1,alpha=renderer.mask*.6)
    axes[1].set_title("Painted region + inward feather")
    axes[2].imshow(image,alpha=.7)
    h,w=mask.shape;stride=max(18,min(h,w)//17)
    yy,xx=np.mgrid[stride//2:h:stride,stride//2:w:stride]
    keep=mask[yy,xx]>.05
    axes[2].quiver(xx[keep],yy[keep],renderer.flow[yy[keep],xx[keep],0],renderer.flow[yy[keep],xx[keep],1],
                   color="#e88139",angles="xy",scale_units="xy",scale=1,width=.006)
    axes[2].set_title("Dense IDW displacement field")
    axes[3].imshow(frames[len(frames)//2]);axes[3].set_title("Rendered frame at t = 0.5")
    for ax in axes:ax.axis("off")
    fig.savefig(OUT/"figures"/f"{name}_pipeline.png",dpi=150)
    plt.close(fig)
    chosen=[0,len(frames)//4,len(frames)//2,3*len(frames)//4,len(frames)-1]
    fig,axes=plt.subplots(1,5,figsize=(14,3.3),constrained_layout=True)
    for ax,index in zip(axes,chosen):
        ax.imshow(frames[index]);ax.set_title(f"t = {index/len(frames):.3f}");ax.axis("off")
    fig.savefig(OUT/"figures"/f"{name}_frames.png",dpi=140)
    plt.close(fig)


def main():
    (OUT/"figures").mkdir(parents=True,exist_ok=True)
    (OUT/"gifs").mkdir(exist_ok=True)
    environment={"timestamp":time.strftime("%Y-%m-%dT%H:%M:%S%z"),"python":platform.python_version(),
                 "platform":platform.platform(),"processor":platform.processor(),
                 "logical_cpus":psutil.cpu_count(),"ram_gb":round(psutil.virtual_memory().total/1024**3,1),
                 "numpy":np.__version__,"repeats":1,
                 "memory_method":"Process RSS sampled every 5 ms; includes interpreter, libraries, frames, encoder. Sequential runs reuse allocator memory; baseline and peak are both recorded.",
                 "metric_scope":"RGB frames before GIF quantization; seam metrics only inside painted mask. Runtime includes diagnostics and GIF encoding. Single-run descriptive results, not statistically stable performance claims."}
    rows=[];all_metrics={}
    for name in ["river","waterfall","clouds","synthetic"]:
        project=load_example(ROOT/"examples"/f"{name}.json")
        image,mask,arrows=project_arrays(project)
        variants={"full":{},"no_blend":{"loop":False},"no_feather":{"feather":0},"large_motion":{"intensity":2}}
        for variant,changes in variants.items():
            settings=project.settings.model_dump()|changes
            renderer,frames,gif,metrics=measured_render(image,mask,arrows,settings)
            key=f"{name}_{variant}"
            all_metrics[key]=metrics|{"settings":settings}
            rows.append({"example":name,"variant":variant,**{k:v for k,v in metrics.items() if not isinstance(v,list)}})
            (OUT/"gifs"/f"{key}.gif").write_bytes(gif)
            if variant=="full":diagnostic_figure(name,image,mask,renderer,frames)
            print(f"{key}: {metrics['total_seconds']:.2f}s, seam={metrics['seam_ratio']}, static={metrics['static_max_error']}",flush=True)
            del renderer,frames,gif
    benchmarks=[]
    project=load_example(ROOT/"examples"/"river.json")
    original,original_mask,original_arrows=project_arrays(project)
    for max_side in [256,512,768]:
        image=resize_bilinear(original,max_side)
        mask=resize_bilinear((original_mask*255).astype(np.uint8),max_side).astype(np.float32)/255
        scale=image.shape[1]/original.shape[1]
        arrows=[Arrow(a.x*scale,a.y*scale,a.dx*scale,a.dy*scale) for a in original_arrows]
        _,frames,_,metrics=measured_render(image,mask,arrows,project.settings.model_dump())
        benchmarks.append({"max_side":max_side,**metrics})
        del frames
    # Plot observed seam change, no blending vs proposed construction.
    names=["river","waterfall","clouds","synthetic"]
    fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    x=np.arange(4)
    for offset,variant,label,color in [(-.18,"no_blend","Abrupt reset","#df9b66"),(.18,"full","Cross-fade loop","#19846d")]:
        axes[0].bar(x+offset,[all_metrics[f"{n}_{variant}"]["seam_ratio"] or 0 for n in names],.36,label=label,color=color)
    axes[0].set_xticks(x,names);axes[0].set_ylabel("Seam / median adjacent-frame MAE");axes[0].set_title("Observed seam diagnostic (lower is smoother)");axes[0].legend(frameon=False)
    for variant,label,color in [("no_blend","Abrupt reset","#df9b66"),("full","Cross-fade loop","#19846d")]:
        m=all_metrics[f"river_{variant}"]
        axes[1].plot(range(1,25),m["adjacent_mae"]+[m["seam_mae"]],marker=".",label=label,color=color)
    axes[1].axvline(24,linestyle="--",color="#82918b",alpha=.5)
    axes[1].set_xlabel("Transition index (24 = last → first)");axes[1].set_ylabel("MAE in moving region (0–255)");axes[1].set_title("River: every frame transition");axes[1].legend(frameon=False)
    fig.savefig(OUT/"figures"/"loop_comparison.png",dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.7),constrained_layout=True)
    labels=[f"{b['width']}×{b['height']}" for b in benchmarks]
    axes[0].bar(labels,[b["render_seconds"] for b in benchmarks],color="#19846d",label="Frame rendering")
    axes[0].bar(labels,[b["total_seconds"]-b["render_seconds"] for b in benchmarks],bottom=[b["render_seconds"] for b in benchmarks],color="#c3ddcf",label="Preparation, metrics, GIF")
    axes[0].set_ylabel("Seconds, one measured run");axes[0].legend(frameon=False);axes[0].set_title("24 frames on this CPU")
    axes[1].bar(labels,[b["rss_peak_mb"] for b in benchmarks],color="#dba06e")
    axes[1].set_ylabel("Process RSS peak (MiB)");axes[1].set_title("Sampled resident memory, shared process")
    fig.savefig(OUT/"figures"/"performance.png",dpi=170);plt.close(fig)
    with (OUT/"metrics.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    data={"environment":environment,"examples":all_metrics,"benchmarks":benchmarks}
    (OUT/"metrics.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    print(f"Saved measured results to {OUT}")


if __name__=="__main__":main()
