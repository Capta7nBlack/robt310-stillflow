"""End-to-end browser checks against a running local server.

Use an existing Chrome/Edge installation; no browser download is required.
Run with any Python environment that has Playwright installed.
"""

import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"figures"


def main():
    candidates=[os.environ.get("STILLFLOW_BROWSER",""),
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    executable=next((p for p in candidates if p and Path(p).exists()),None)
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=executable,headless=True)
        page=browser.new_page(viewport={"width":1440,"height":1100},device_scale_factor=1)
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto("http://127.0.0.1:8000",wait_until="networkidle")
        page.wait_for_function("document.getElementById('canvas').width === 768 && !document.getElementById('render').disabled")
        OUT.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(OUT/"editor.png"),full_page=True)
        page.get_by_role("button",name="Render loop",exact=False).click()
        page.wait_for_function("document.getElementById('renderTitle').textContent === 'Your loop is ready'",timeout=120000)
        assert page.locator("#preview").is_visible()
        assert page.locator("#download").is_enabled()
        assert page.locator("#metricStatic").inner_text()=="0 / 255"
        page.screenshot(path=str(OUT/"preview.png"),full_page=True)
        with page.expect_download() as downloaded:
            page.locator("#download").click()
        target=ROOT/"outputs"/"browser_download.gif"
        target.parent.mkdir(exist_ok=True)
        downloaded.value.save_as(str(target))
        assert target.read_bytes().startswith(b"GIF89a")
        # Paint, undo, redo, then add an arrow and an anchor.
        page.get_by_role("button",name="Edit",exact=True).click()
        before=page.evaluate("mask.toDataURL()")
        box=page.locator("#canvas").bounding_box()
        start=(box["x"]+box["width"]*.55,box["y"]+box["height"]*.35)
        page.mouse.move(*start);page.mouse.down();page.mouse.move(start[0]+30,start[1]+15,steps=8);page.mouse.up()
        after=page.evaluate("mask.toDataURL()")
        assert after!=before
        page.locator("#undo").click();assert page.evaluate("mask.toDataURL()")==before
        page.locator("#redo").click();assert page.evaluate("mask.toDataURL()")==after
        page.locator('[data-tool="erase"]').click()
        page.mouse.click(*start)
        assert page.evaluate("mask.toDataURL()")!=after
        page.locator('[data-tool="arrow"]').click()
        page.mouse.move(*start);page.mouse.down();page.mouse.move(start[0]+18,start[1]+20,steps=4);page.mouse.up()
        assert page.evaluate("state.arrows.length")==4
        page.locator('[data-tool="pin"]').click();page.mouse.click(start[0]+50,start[1])
        assert page.evaluate("state.arrows.length")==5
        assert page.locator("#download").is_disabled()
        # Save/open must restore actual embedded image, mask and vectors.
        with page.expect_download() as saved:
            page.locator("#saveProject").click()
        project_file=ROOT/"outputs"/"browser_project.json"
        saved.value.save_as(str(project_file))
        saved_data=json.loads(project_file.read_text())
        assert len(saved_data["arrows"])==5
        page.locator("#clear").click();assert page.evaluate("state.arrows.length")==0
        page.locator("#projectInput").set_input_files(str(project_file))
        page.wait_for_function("state.arrows.length === 5 && !state.busy")
        assert page.evaluate("mask.toDataURL()")==saved_data["mask"]
        # Test original view and a different preset.
        page.get_by_role("button",name="Original",exact=True).click()
        page.locator("#exampleSelect").select_option("clouds")
        page.wait_for_function("state.name === 'Cloud drift' && !state.busy")
        assert page.evaluate("canvas.width")==512
        # A real upload clears previous annotations and uses backend import.
        page.locator("#imageInput").set_input_files(str(ROOT/"examples"/"images"/"synthetic.png"))
        page.wait_for_function("state.name === 'synthetic' && !state.busy")
        assert page.evaluate("state.arrows.length")==0
        page.locator("#render").click()
        assert "arrow" in page.locator("#notice").inner_text()
        page.locator("#helpButton").click();assert page.locator("#helpDialog").is_visible()
        page.locator("#closeHelp").click()
        # Narrow screens should have no horizontal overflow.
        page.set_viewport_size({"width":390,"height":844})
        page.screenshot(path=str(OUT/"mobile.png"),full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert not errors, errors
        browser.close()
    checks=["render","preview","GIF download","brush","erase","arrows","anchors","undo/redo","save/open","presets","upload","help","responsive layout"]
    (ROOT/"results"/"browser-check.json").write_text(json.dumps({"passed":True,"checks":checks,"javascript_errors":errors,"timestamp":time.strftime("%Y-%m-%dT%H:%M:%S%z")},indent=2),encoding="utf-8")
    print("Browser checks passed: "+", ".join(checks)+".")


if __name__=="__main__":main()
