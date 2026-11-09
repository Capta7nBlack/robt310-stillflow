"""Create editable recipes and an original deterministic diagnostic image."""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    examples = ROOT / "examples"
    sources = json.loads((examples / "sources.json").read_text(encoding="utf-8"))
    names = {"river":"River rapids", "clouds":"Cloud drift", "waterfall":"Waterfall"}
    descriptions = {"river":"Flowing water · 3 arrows · public-domain NPS photo", "clouds":"Subtle cloud motion · static landscape", "waterfall":"Downward flow · protected trees and foreground"}
    for source in sources:
        key = Path(source["file"]).stem
        arrows = [[x, y, endx-x, endy-y] for x, y, endx, endy in source["suggested_arrows_normalized"]]
        spec = {"name":names[key], "description":descriptions[key], "image_file":source["file"],
                "polygons":[source["suggested_mask_polygon_normalized"]], "arrows":arrows,
                "settings":{"frames":24,"fps":12,"intensity":1.0,"feather":12,"blend":.4,"loop":True}}
        (examples / f"{key}.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    # Original analytic scene: textured fluid stripe surrounded by an unmoving grid.
    # It is procedural test data, not a photograph or measured real-world motion.
    h, w = 384, 640
    y, x = np.mgrid[:h, :w].astype(np.float32)
    waves = .5 + .22*np.sin(x/12+y/21) + .17*np.cos(x/23-y/9) + .1*np.sin(x/4+y/8)
    water = np.stack([30+45*waves, 95+90*waves, 120+100*waves], axis=-1)
    grid = ((x.astype(int)//24+y.astype(int)//24)%2)*10
    base = np.stack([225+grid, 231+grid, 223+grid], axis=-1).astype(np.float32)
    inside = (y>85)&(y<300)
    base[inside] = water[inside]
    base[82:86] = [40,60,55]
    base[300:304] = [40,60,55]
    Image.fromarray(np.clip(base,0,255).astype(np.uint8)).save(examples/"images"/"synthetic.png")
    spec = {"name":"Synthetic flow test", "description":"Project-generated analytic texture · controlled diagnostics",
            "image_file":"images/synthetic.png", "polygons":[[[.08,.25],[.92,.25],[.92,.75],[.08,.75]]],
            "arrows":[[.25,.5,.04,0],[.5,.5,.04,0],[.75,.5,.04,0]],
            "settings":{"frames":24,"fps":12,"intensity":1,"feather":12,"blend":.4,"loop":True}}
    (examples/"synthetic.json").write_text(json.dumps(spec,indent=2),encoding="utf-8")
    print("Prepared 3 external-photo recipes and 1 project-generated diagnostic scene.")


if __name__ == "__main__":
    main()
