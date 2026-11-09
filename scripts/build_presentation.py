"""Build an editable PowerPoint and a matching offline PDF from real results."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"presentation"
RESULTS=ROOT/"results"
W,H=1920,1080
SCALE=144
INK="#183138";MUTED="#687e80";TEAL="#167a68";PAPER="#f5f7f3";LINE="#dce4dd";ORANGE="#d48f58"
prs=Presentation();prs.slide_width=Inches(13.333333);prs.slide_height=Inches(7.5)
rasters=[]


def rgb(value):return RGBColor.from_string(value.lstrip("#"))


def font(size,bold=False):
    choices=([Path(r"C:\Windows\Fonts\segoeuib.ttf")] if bold else [Path(r"C:\Windows\Fonts\segoeui.ttf")])
    choices += [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for path in choices:
        if path.exists():return ImageFont.truetype(str(path),round(size*2))
    return ImageFont.load_default(size=round(size*2))


class Slide:
    def __init__(self,title,kicker="ROBT310 / GROUP 2",dark=False):
        self.slide=prs.slides.add_slide(prs.slide_layouts[6])
        self.bg=INK if dark else PAPER
        self.slide.background.fill.solid();self.slide.background.fill.fore_color.rgb=rgb(self.bg)
        self.image=Image.new("RGB",(W,H),self.bg);self.draw=ImageDraw.Draw(self.image)
        self.dark=dark
        self.text(.55,.35,12,.3,kicker,10,"#8bd1b1" if dark else TEAL,bold=True)
        self.text(.55,.85,12.1,1,title,30,"#ffffff" if dark else INK,bold=True)
        self.text(.55,7.12,11,.18,"STILLFLOW  /  Single-image animation using flow-field warping",8,"#a9c3bf" if dark else MUTED)
        self.text(12.15,7.08,.5,.22,f"{len(prs.slides):02d}",10,"#a9c3bf" if dark else MUTED)
        rasters.append(self.image)

    def rect(self,x,y,w,h,fill,line=None):
        shape=self.slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x),Inches(y),Inches(w),Inches(h))
        shape.fill.solid();shape.fill.fore_color.rgb=rgb(fill)
        shape.line.fill.background() if not line else None
        if line:shape.line.color.rgb=rgb(line)
        self.draw.rectangle((round(x*SCALE),round(y*SCALE),round((x+w)*SCALE),round((y+h)*SCALE)),fill=fill,outline=line)

    def text(self,x,y,w,h,text,size=18,color=INK,bold=False):
        ft=font(size,bold)
        lines=[]
        for paragraph in str(text).split("\n"):
            current=""
            for word in paragraph.split(" "):
                candidate=(current+" "+word).strip()
                if ft.getlength(candidate)>w*SCALE and current:
                    lines.append(current);current=word
                else:current=candidate
            lines.append(current)
        rendered="\n".join(lines)
        box=self.slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
        tf=box.text_frame;tf.word_wrap=False
        tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
        for i,line in enumerate(lines):
            p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
            p.text=line;p.font.name="Segoe UI";p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=rgb(color)
            p.space_after=Pt(size*.17);p.line_spacing=1.05
        self.draw.multiline_text((round(x*SCALE),round(y*SCALE)),rendered,font=ft,fill=color,spacing=round(size*.4))

    def picture(self,path,x,y,w,h):
        with Image.open(path) as original:
            im=original.convert("RGB")
        ratio=min(w*SCALE/im.width,h*SCALE/im.height)
        width,height=im.width*ratio/SCALE,im.height*ratio/SCALE
        x+=(w-width)/2;y+=(h-height)/2
        self.slide.shapes.add_picture(str(path),Inches(x),Inches(y),width=Inches(width),height=Inches(height))
        im=im.resize((round(width*SCALE),round(height*SCALE)),Image.Resampling.LANCZOS)
        self.image.paste(im,(round(x*SCALE),round(y*SCALE)))

    def notes(self,text):self.slide.notes_slide.notes_text_frame.text=text


def metric_table(slide,metrics,x,y):
    widths=[2.3,1.5,1.5,1.8]
    headers=["CASE","RESET SEAM","LOOP SEAM","STATIC ERROR"]
    cursor=x
    for width,header in zip(widths,headers):slide.text(cursor,y,width,.3,header,10,TEAL,bold=True);cursor+=width
    for i,name in enumerate(["river","waterfall","clouds","synthetic"]):
        full=metrics[f"{name}_full"];raw=metrics[f"{name}_no_blend"]
        values=[name.title(),f"{raw['seam_ratio']:.2f}×",f"{full['seam_ratio']:.2f}×",str(full["static_max_error"])]
        cursor=x
        for width,value in zip(widths,values):slide.text(cursor,y+.35+i*.38,width,.3,value,14,INK);cursor+=width


def main():
    data=json.loads((RESULTS/"metrics.json").read_text(encoding="utf-8"))
    m=data["examples"];team=json.loads((OUT/"team.json").read_text(encoding="utf-8"))
    names="  ·  ".join(person["name"] for person in team["members"])
    count=None
    report=ROOT/"outputs"/"test-report.xml"
    if report.exists():
        suite=ET.parse(report).getroot().find("testsuite")
        count=int(suite.attrib["tests"])
        if int(suite.attrib.get("failures",0))+int(suite.attrib.get("errors",0)):
            raise RuntimeError("Do not build a success deck from failing tests.")
    elif (RESULTS/"test-summary.json").exists():
        count=json.loads((RESULTS/"test-summary.json").read_text(encoding="utf-8"))["tests"]
    else:
        raise RuntimeError("Run python -m pytest -q --junitxml=outputs/test-report.xml first.")
    (RESULTS/"test-summary.json").write_text(json.dumps({"tests":count,"failures":0,"command":"python -m pytest -q","browser_check":"See scripts/browser_check.py and actual editor/preview screenshots."},indent=2),encoding="utf-8")

    s=Slide("A still image.\nA little controlled motion.","IMPLEMENTATION PROGRESS  /  10 NOVEMBER 2026",dark=True)
    s.text(.6,2.6,5.5,1.2,"Interactive single-image animation\nusing flow-field warping",22,"#c2dfd0")
    s.text(.6,4.2,5.4,1.2,"Sayat Mushkin\nYerassyl Myngtay\nAmir Ussembayev",17,"#ffffff")
    s.text(.6,6.15,5.3,.45,"ROBT310 · Nazarbayev University · Group 2",12,"#a9c3bf")
    s.picture(ROOT/"examples/images/river.jpg",6.2,2.1,6.5,4.7)
    s.notes("Introduce all three members by name. State the engineering goal: give a user control over small texture motion in one image. This is a working classical prototype, not a trained generative model. Title image: public-domain NPS photograph, North Cascades National Park Service Complex.")

    s=Slide("From a proposed method to an end-to-end prototype")
    s.rect(.55,1.8,5.9,4.85,"#e5eee7");s.rect(6.65,1.8,6.1,4.85,"#ffffff")
    s.text(.85,2.08,5.3,.45,"Scope change, stated explicitly",19,TEAL,bold=True)
    s.text(.85,2.8,5.2,1.2,"Original proposal: satellite image upscaling.\nInterim and current implementation: user-guided single-image animation.",17)
    s.text(.85,4.5,5.1,1.4,"Current technical rationale: three inspectable image-processing algorithms, direct visual control, and a feasible CPU demonstration.",17)
    s.text(7,2.08,5.4,.45,"Now implemented and reviewable",19,TEAL,bold=True)
    s.text(7,2.85,5.1,3.1,"01   Image upload, mask painting and arrows\n02   NumPy flow interpolation and warping\n03   Loop preview and GIF export\n04   Saved projects, examples and tests\n05   Reproducible measurements and figures",17)
    s.notes("Acknowledge the original proposal and the change. The slide explains the current technical rationale; the team must supply the true historical reason and approval status. Do not pretend those were confirmed. The interim was design-only. Demonstrate implemented work now. React was replaced by plain Canvas/JavaScript to keep setup small; the planned FastAPI/NumPy engine is retained.")

    s=Slide("The whole pipeline is visible")
    labels=[("01","Sparse arrows → dense flow"),("02","Inverse warp + bilinear sample"),("03","Cross-fade + mask composite")]
    for i,(number,label) in enumerate(labels):
        x=.6+i*4.23;s.rect(x,1.9,3.95,.85,"#e4eee6");s.text(x+.18,2.03,.4,.3,number,14,TEAL,bold=True);s.text(x+.7,2.03,3.02,.5,label,14,INK,bold=True)
    s.picture(RESULTS/"figures/river_pipeline.png",.55,3.05,12.25,3.1)
    s.text(.65,6.3,12,.45,"Pillow handles file I/O and GIF encoding. NumPy implements the field, sampling, feathering and frame synthesis.",14,MUTED)
    s.notes("Walk left to right through the actual input, mask, dense field, and rendered frame. The arrows represent total displacement over a cycle. White controls in the browser are sparse inputs; the dense field is computed, not hand-drawn. No OpenCV remap or optical-flow call is hidden in the code.")

    s=Slide("From a few arrows to moving pixels")
    s.text(.65,1.9,5.9,.45,"1 / Regularized inverse-distance weighting",18,TEAL,bold=True)
    s.text(.65,2.7,5.8,1.2,"wᵢ(x) = 1 / (‖x − pᵢ‖² + ε²)\nD(x) = Σ wᵢ(x) aᵢ / Σ wᵢ(x)",22)
    s.text(.65,4.15,5.6,1.7,"Nearby arrows have more influence.\nε = 12 pixels prevents singularities.\nZero-motion anchors are soft constraints.\nThe mask gives exact static protection.",17)
    s.text(7,1.9,5.6,.45,"2 / Backward mapping + bilinear sampling",18,TEAL,bold=True)
    s.text(7,2.7,5.6,.7,"Aₜ(x) = sample(I, x − tD(x))",22)
    s.text(7,3.65,5.5,1.35,"Four neighboring source pixels are blended by fractional x/y distances. Every destination pixel receives a value.",18)
    s.text(7,5.35,5.3,.9,"Clamped borders avoid invalid reads, but can stretch edge textures.",17,MUTED)
    s.text(.65,6.45,12,.3,"Background: Shepard (1968); Wolberg, Digital Image Warping (1990), inverse mapping and reconstruction.",11,MUTED)
    s.notes("Use the simple example of an arrow dx=8: at half-cycle the output samples four pixels to the left, so the visible feature moves right. Explain regularization means an arrow is not an exact interpolation constraint when other arrows are present. Bilinear sampling is tested against hand-computed weights and affine ramps.")

    s=Slide("Make the loop continuous, and keep the background still")
    s.rect(.6,1.9,7.4,4.55,"#ffffff")
    s.text(.9,2.2,6.85,2,"Bₜ(x) = sample(I, x − (t−1)D(x))\ns = clip((t−1+r)/r, 0, 1)\nα = 3s² − 2s³\nCₜ = (1−α)Aₜ + αBₜ",21)
    s.text(.9,4.9,6.8,.8,"Fₜ = I + M(Cₜ − I)\nM = min(M₀, GaussianBlur(M₀))",21)
    s.text(8.45,2.1,4.15,1.3,"C₀ = C₁ = I\nContinuous-time endpoint equality",20,TEAL,bold=True)
    s.text(8.45,3.75,4.1,2.3,"Render t = 0 … (N−1)/N; do not duplicate the endpoint.\n\nInward feathering keeps every unpainted RGB pixel unchanged.\n\nCross-fading can still ghost.",17)
    s.notes("The second warp is displaced in the opposite phase and takes over near the end. Smoothstep has zero slope at each end of the blending window. Endpoint equality is a mathematical property, while the last-to-first GIF step is measured separately. Explain that inward feathering was chosen to stop blur from leaking animation outside the painted region.")

    s=Slide("Rendered frames from four reproducible cases")
    for i,(name,label) in enumerate([("river","River rapids"),("waterfall","Waterfall"),("clouds","Cloud drift"),("synthetic","Procedural test")]):
        poster=RESULTS/f"figures/{name}_result.png"
        with Image.open(RESULTS/f"gifs/{name}_full.gif") as animation:
            animation.seek(animation.n_frames//2)
            animation.convert("RGB").save(poster)
        x=.6+i*3.2;s.picture(poster,x,1.95,2.9,3.8)
        s.text(x,6.0,2.9,.35,label,15,TEAL,bold=True)
    s.text(.65,6.55,12,.3,"External public-domain NPS photographs; project-created masks and arrows. Original procedural data is also included.",11,MUTED)
    s.notes("These slides show still photographs; show the actual animation in the browser or the bundled MP4/GIF files. Credit NPS Staff / North Cascades for river and waterfall; NPS/Cathy Bell for clouds. Do not call these student-shot photographs. The procedural scene is project-generated and supports controlled testing.")

    s=Slide("Ablation: the loop boundary is measurably less abrupt")
    s.picture(RESULTS/"figures/loop_comparison.png",.55,1.8,12.2,3.4)
    metric_table(s,m,.75,5.15)
    s.notes("All values are produced by scripts/evaluate.py. Seam ratio is the last-to-first moving-region MAE divided by the median adjacent-frame MAE. A lower ratio means a less exceptional seam, not more physical realism. Point to the right-hand plot: it shows all transitions so cross-fade artifacts are not hidden by a single seam metric. No-feather and doubled-motion runs are also saved.")

    s=Slide(f"{count} automated tests pass; CPU cost is measured")
    s.picture(RESULTS/"figures/performance.png",.55,1.9,8.2,4.6)
    s.text(9.1,2.05,3.55,.55,"Correctness checks",19,TEAL,bold=True)
    s.text(9.1,2.9,3.5,2.8,"Known IDW weights\nBilinear interpolation\nTranslation direction\nStatic-pixel invariance\nLoop endpoint equality\nGIF timing and palette\nUpload / render validation",16)
    s.text(.65,6.55,12,.3,"Single-run measurements on the recorded machine. Memory is sampled process RSS, including libraries and retained frames.",11,MUTED)
    s.notes("These are measured prototype costs, not a claim about all computers. Read the exact 768-side timing from the chart, and explain the difference between frame rendering and GIF encoding. The browser workflow was also exercised: editing, save/restore, actual download, upload, and responsive layout. Core complexity is O(PK+NP); this implementation retains N frames, so total memory is O(NP).")

    s=Slide("What works, what remains limited")
    for x,title,body in [(.65,"Demonstrated","End-to-end user control\nDeterministic NumPy algorithms\nRepeatable examples and metrics\nExact unpainted-pixel preservation"),(4.9,"Current limitations","Ghosting during cross-fades\nStretching for large displacements\nNo occlusion reconstruction\nNo physical motion estimation"),(9.0,"Next practical work","Add team-captured photographs\nRefine masks near rocks / edges\nCompare smaller motion settings\nConfirm roles and scope rationale")]:
        width=3.7 if x<9 else 3.65;s.text(x,2.05,width,.5,title,20,TEAL,bold=True);s.text(x,3.05,width,2.65,body,17)
    s.rect(.65,6,12,.55,"#e5eee7");s.text(.9,6.1,11.5,.35,"The deliverable is a controllable classical prototype; no new animation theory or human study is claimed.",13,INK)
    s.notes("Be explicit about the limits. The source photos are external; original analytic data does not replace an own-photo collection if the instructor requires it. Ask the team to add genuine contributions and short biographies for the final report. Disclose AI coding assistance according to course requirements, and be ready to explain and modify the code.")

    s=Slide("Live demonstration: image → annotations → loop",dark=True)
    s.text(.7,2.05,6.4,3.9,"01   Open the River rapids example\n02   Render, then compare with Original\n03   Edit a short arrow or erase a boundary\n04   Toggle loop blending for the baseline\n05   Download GIF and save the project",20,"#ffffff")
    s.text(7.65,2.1,4.9,.5,"Offline fallback",20,"#8bd1b1",bold=True)
    s.text(7.65,3.0,4.7,1.4,"results/demo_river.mp4\nresults/gifs/river_full.gif\nresults/gifs/river_no_blend.gif",16,"#d0e1d8")
    s.text(.7,6.15,12,.5,"github.com/Capta7nBlack/robt310-stillflow",20,"#8bd1b1",bold=True)
    s.notes("Keep this slide while demonstrating. Start the server before class with start.bat, and keep the browser tab open. If the server or display fails, play the MP4 or GIF files locally. The final public repository should be verified before sharing. Explain the source can run without an online hosting service.")

    s=Slide("References and source credits","APPENDIX / METHOD BACKGROUND")
    references=["Le et al. (2023). Animating Still Natural Images Using Warping. ACM TOMM 19(1), article 4. DOI: 10.1145/3511894.","Shepard (1968). A two-dimensional interpolation function for irregularly-spaced data. ACM National Conference, pp. 517–524. DOI: 10.1145/800186.810616.","Wolberg (1990). Digital Image Warping. IEEE Computer Society Press. §3.1.2 inverse mapping; §5.4.2 linear reconstruction.","Heckbert (1989). Fundamentals of Texture Mapping and Image Warping. UC Berkeley technical report UCB/CSD-89-516.","Photographs: NPS Staff / North Cascades National Park Service Complex; NPS / Cathy Bell. Individual public-domain asset pages are recorded in examples/sources.json."]
    for i,reference in enumerate(references):s.text(.75,1.9+i*.91,11.9,.8,f"[{i+1}]  {reference}",15)
    s.notes("Le et al. provide motivation, but use more sophisticated preserve-curve warping. Do not call our IDW implementation a reproduction. Wolberg is an actual textbook reference for the fundamentals. All web references and provenance links are in docs/METHOD.md and examples/sources.json.")

    OUT.mkdir(exist_ok=True)
    prs.save(OUT/"progress.pptx")
    rasters[0].save(OUT/"progress.pdf",save_all=True,append_images=rasters[1:],resolution=144)
    preview=Image.new("RGB",(960,540*len(rasters)//2+540),"white")
    for i,im in enumerate(rasters):preview.paste(im.resize((480,270)),((i%2)*480,(i//2)*270))
    preview=preview.crop((0,0,960,((len(rasters)+1)//2)*270))
    preview.save(OUT/"slide_overview.jpg",quality=90)
    # Insert measured observations, without manual transcription of numbers.
    lines=["| Case | Full render + encoding | Reset seam ratio | Blended seam ratio | Static max error |","|---|---:|---:|---:|---:|"]
    for name in ["river","waterfall","clouds","synthetic"]:
        full=m[f"{name}_full"];raw=m[f"{name}_no_blend"]
        lines.append(f"| {name.title()} | {full['total_seconds']:.2f} s | {raw['seam_ratio']:.2f} | {full['seam_ratio']:.2f} | {full['static_max_error']} |")
    lines += ["",f"**{count} numerical/API tests pass.** Measurements below use the bundled 24-frame recipes. Full machine details and per-transition values are in [results/metrics.json](results/metrics.json)."]
    readme=ROOT/"README.md";text=readme.read_text(encoding="utf-8")
    start="<!-- MEASURED_RESULTS_START -->";end="<!-- MEASURED_RESULTS_END -->"
    before,rest=text.split(start);_,after=rest.split(end)
    readme.write_text(before+start+"\n"+"\n".join(lines)+"\n"+end+after,encoding="utf-8")
    print(f"Built {len(rasters)} named, illustrated slides: progress.pptx + progress.pdf")


if __name__=="__main__":main()
