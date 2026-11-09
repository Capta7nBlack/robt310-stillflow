"use strict";
const $ = (id) => document.getElementById(id);
const canvas = $("canvas"),
  ctx = canvas.getContext("2d");
const mask = document.createElement("canvas"),
  mctx = mask.getContext("2d", { willReadFrequently: true });
const tint = document.createElement("canvas"),
  tctx = tint.getContext("2d");
const state = {
  image: null,
  imageURL: null,
  name: "Untitled",
  arrows: [],
  tool: "paint",
  view: "edit",
  busy: false,
  dirty: true,
  gif: null,
  flow: [],
  undo: [],
  redo: [],
  drawing: false,
  start: null,
  last: null,
};
const toolHints = {
  paint: "Brush over the region you want to animate.",
  erase: "Erase to keep rocks, trees, and edges still.",
  arrow: "Drag in the direction of motion. Length sets travel per cycle.",
  pin: "Click to add a soft zero-motion anchor. Use the mask for exact protection.",
};

function notice(message, type = "") {
  $("notice").textContent = message;
  $("notice").className = "notice " + type;
}
function settings() {
  return {
    frames: +$("frames").value,
    fps: +$("fps").value,
    intensity: +$("intensity").value,
    feather: +$("feather").value,
    blend: +$("blend").value,
    loop: $("loop").checked,
  };
}
function project() {
  return {
    version: 1,
    name: state.name,
    image: state.imageURL,
    mask: mask.toDataURL("image/png"),
    arrows: structuredClone(state.arrows),
    settings: settings(),
  };
}
function updateLabels() {
  $("brushValue").textContent = $("brush").value + " px";
  $("intensityValue").textContent = (+$("intensity").value).toFixed(1) + "×";
  $("featherValue").textContent = $("feather").value + " px";
  $("blendValue").textContent = Math.round(+$("blend").value * 100) + "%";
  const s = settings();
  $("renderSubtitle").textContent =
    `${s.frames} frames · ${(s.frames / s.fps).toFixed(2)} second loop · ${s.fps} fps`;
}
function markDirty() {
  state.dirty = true;
  state.flow = [];
  $("download").disabled = true;
  $("renderTitle").textContent = state.gif
    ? "Settings changed · render again"
    : "Ready when you are";
}
function setBusy(value) {
  state.busy = value;
  $("loading").hidden = !value;
  document
    .querySelectorAll(
      ".controls button,.controls select,.controls input,.project-actions button,#render",
    )
    .forEach((e) => (e.disabled = value));
  $("download").disabled = value || state.dirty || !state.gif;
  $("undo").disabled = value || !state.undo.length;
  $("redo").disabled = value || !state.redo.length;
}
async function api(url, options = {}) {
  const response = await fetch(url, options);
  let value;
  try {
    value = await response.json();
  } catch {
    throw new Error(
      "The server returned an unreadable response. Check the terminal.",
    );
  }
  if (!response.ok) {
    let message = value.detail;
    if (Array.isArray(message)) message = message.map((x) => x.msg).join("; ");
    throw new Error(message || "The request failed.");
  }
  return value;
}
function readImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Could not load the image."));
    img.src = url;
  });
}
function saveSnapshot() {
  state.undo.push({
    mask: mctx.getImageData(0, 0, mask.width, mask.height),
    arrows: structuredClone(state.arrows),
  });
  if (state.undo.length > 20) state.undo.shift();
  state.redo = [];
  updateHistory();
}
function updateHistory() {
  $("undo").disabled = state.busy || !state.undo.length;
  $("redo").disabled = state.busy || !state.redo.length;
}
function history(direction) {
  if (state.busy || !state.image) return;
  const from = state[direction],
    to = state[direction === "undo" ? "redo" : "undo"];
  if (!from.length) return;
  to.push({
    mask: mctx.getImageData(0, 0, mask.width, mask.height),
    arrows: structuredClone(state.arrows),
  });
  const snapshot = from.pop();
  mctx.putImageData(snapshot.mask, 0, 0);
  state.arrows = snapshot.arrows;
  markDirty();
  updateHistory();
  setView("edit");
  draw();
}
function setTool(tool) {
  state.tool = tool;
  document
    .querySelectorAll("[data-tool]")
    .forEach((b) => b.classList.toggle("active", b.dataset.tool === tool));
  $("toolHint").textContent = toolHints[tool];
  setView("edit");
}
function setView(view) {
  if (view === "preview" && !state.gif) return;
  state.view = view;
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  canvas.hidden = view === "preview";
  $("preview").hidden = view !== "preview";
  $("stageTag").hidden = view !== "edit" || !$("showMask").checked;
  draw();
}
function arrow(x, y, dx, dy, color, line = 2) {
  const length = Math.hypot(dx, dy);
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = line;
  ctx.lineCap = "round";
  ctx.beginPath();
  if (length < 0.01) {
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.moveTo(x - 9, y);
    ctx.lineTo(x + 9, y);
    ctx.moveTo(x, y - 9);
    ctx.lineTo(x, y + 9);
    ctx.stroke();
    return;
  }
  ctx.moveTo(x, y);
  ctx.lineTo(x + dx, y + dy);
  ctx.stroke();
  const a = Math.atan2(dy, dx),
    head = Math.min(9, Math.max(5, length * 0.3));
  ctx.beginPath();
  ctx.moveTo(x + dx, y + dy);
  ctx.lineTo(
    x + dx - head * Math.cos(a - 0.55),
    y + dy - head * Math.sin(a - 0.55),
  );
  ctx.lineTo(
    x + dx - head * Math.cos(a + 0.55),
    y + dy - head * Math.sin(a + 0.55),
  );
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x, y, 3, 0, 2 * Math.PI);
  ctx.fill();
}
function draw() {
  if (!state.image) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(state.image, 0, 0);
  if (state.view === "original") return;
  if ($("showMask").checked) {
    const pixels = mctx.getImageData(0, 0, mask.width, mask.height),
      out = tctx.createImageData(mask.width, mask.height);
    for (let i = 0; i < pixels.data.length; i += 4) {
      out.data[i] = 37;
      out.data[i + 1] = 221;
      out.data[i + 2] = 162;
      out.data[i + 3] = Math.round(pixels.data[i] * 0.27);
    }
    tctx.putImageData(out, 0, 0);
    ctx.drawImage(tint, 0, 0);
  }
  if ($("showFlow").checked)
    for (const v of state.flow) arrow(...v, "#e4fcffb0", 1);
  for (const a of state.arrows)
    arrow(
      a.x,
      a.y,
      a.dx,
      a.dy,
      a.dx === 0 && a.dy === 0 ? "#ffb46c" : "#ffffff",
      2.5,
    );
  if (state.drawing && state.tool === "arrow" && state.last)
    arrow(
      state.start.x,
      state.start.y,
      state.last.x - state.start.x,
      state.last.y - state.start.y,
      "#ffdb87",
      3,
    );
  const n = state.arrows.filter((a) => a.dx !== 0 || a.dy !== 0).length,
    p = state.arrows.length - n;
  $("annotationSummary").textContent =
    `${n} motion arrow${n === 1 ? "" : "s"} · ${p} anchor${p === 1 ? "" : "s"} · ${canvas.width} × ${canvas.height} px`;
}
function point(event) {
  const r = canvas.getBoundingClientRect();
  return {
    x: Math.max(
      0,
      Math.min(
        canvas.width - 1,
        ((event.clientX - r.left) * canvas.width) / r.width,
      ),
    ),
    y: Math.max(
      0,
      Math.min(
        canvas.height - 1,
        ((event.clientY - r.top) * canvas.height) / r.height,
      ),
    ),
  };
}
function paint(a, b) {
  mctx.strokeStyle = state.tool === "erase" ? "black" : "white";
  mctx.fillStyle = mctx.strokeStyle;
  mctx.lineWidth = +$("brush").value;
  mctx.lineCap = "round";
  mctx.lineJoin = "round";
  mctx.beginPath();
  mctx.moveTo(a.x, a.y);
  mctx.lineTo(b.x, b.y);
  mctx.stroke();
  mctx.beginPath();
  mctx.arc(b.x, b.y, +$("brush").value / 2, 0, Math.PI * 2);
  mctx.fill();
}
canvas.addEventListener("pointerdown", (event) => {
  if (state.busy || state.view !== "edit" || !state.image || event.button !== 0)
    return;
  event.preventDefault();
  canvas.setPointerCapture(event.pointerId);
  saveSnapshot();
  state.start = state.last = point(event);
  state.drawing = true;
  if (state.tool === "pin") {
    state.arrows.push({ x: state.start.x, y: state.start.y, dx: 0, dy: 0 });
    state.drawing = false;
  } else if (state.tool !== "arrow") paint(state.start, state.start);
  markDirty();
  draw();
});
canvas.addEventListener("pointermove", (event) => {
  if (!state.drawing) return;
  const p = point(event);
  if (state.tool !== "arrow") paint(state.last, p);
  state.last = p;
  draw();
});
function endDrawing(event) {
  if (!state.drawing) return;
  const p = point(event);
  if (state.tool === "arrow") {
    const dx = p.x - state.start.x,
      dy = p.y - state.start.y;
    if (Math.hypot(dx, dy) >= 2) {
      state.arrows.push({ x: state.start.x, y: state.start.y, dx, dy });
      if (Math.hypot(dx, dy) > 0.12 * Math.max(canvas.width, canvas.height))
        notice(
          "This arrow is quite long. Short motions usually give a cleaner result.",
        );
    }
  }
  state.drawing = false;
  state.last = null;
  draw();
}
canvas.addEventListener("pointerup", endDrawing);
canvas.addEventListener("pointercancel", () => {
  state.drawing = false;
  draw();
});

async function applyProject(p) {
  if (p.version !== 1 || !Array.isArray(p.arrows) || p.arrows.length > 64)
    throw new Error("Not a supported Stillflow project (version 1).");
  const img = await readImage(p.image);
  if (Math.max(img.width, img.height) > 768)
    throw new Error(
      "Project image exceeds 768 pixels. Import the photograph instead.",
    );
  const maskImg = await readImage(p.mask);
  if (maskImg.width !== img.width || maskImg.height !== img.height)
    throw new Error("Project mask dimensions do not match the image.");
  if (!p.arrows.every((a) => [a.x, a.y, a.dx, a.dy].every(Number.isFinite)))
    throw new Error("Project contains invalid arrows.");
  state.image = img;
  state.imageURL = p.image;
  state.name = p.name || "Untitled";
  state.arrows = structuredClone(p.arrows);
  canvas.width = mask.width = tint.width = img.width;
  canvas.height = mask.height = tint.height = img.height;
  mctx.fillStyle = "black";
  mctx.fillRect(0, 0, mask.width, mask.height);
  mctx.drawImage(maskImg, 0, 0);
  for (const [key, val] of Object.entries(p.settings || {})) {
    const el = $(key);
    if (!el) continue;
    if (el.type === "checkbox") el.checked = !!val;
    else {
      if (
        el.tagName === "SELECT" &&
        ![...el.options].some((o) => o.value === String(val))
      )
        el.add(new Option(val, val));
      el.value = val;
    }
  }
  state.undo = [];
  state.redo = [];
  state.gif = null;
  state.flow = [];
  $("preview").removeAttribute("src");
  document.querySelector('[data-view="preview"]').disabled = true;
  $("projectName").textContent = state.name;
  $("dimensions").textContent = `${img.width} × ${img.height}`;
  for (const id of ["metricTime", "metricSeam", "metricStatic", "metricSize"])
    $(id).textContent = "—";
  updateLabels();
  markDirty();
  setView("edit");
  updateHistory();
}
async function loadExample(name) {
  if (!name || state.busy) return;
  setBusy(true);
  try {
    const p = await api("/api/examples/" + encodeURIComponent(name));
    await applyProject(p);
    notice(
      "Example loaded with a painted mask and motion arrows. Render it, or edit the annotations.",
    );
  } catch (e) {
    notice(e.message, "error");
  } finally {
    setBusy(false);
  }
}
async function render() {
  if (state.busy || !state.image) return;
  if (!state.arrows.some((a) => Math.hypot(a.dx, a.dy) > 0)) {
    notice("Draw at least one motion arrow first.", "error");
    return;
  }
  setBusy(true);
  notice("Rendering on your CPU. Your photograph stays on this computer.");
  try {
    const result = await api("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(project()),
    });
    state.gif = result.gif;
    state.flow = result.flow;
    state.dirty = false;
    $("preview").src = result.gif;
    document.querySelector('[data-view="preview"]').disabled = false;
    const m = result.metrics;
    $("metricTime").textContent = m.total_seconds.toFixed(2) + " s";
    $("metricSeam").textContent =
      m.seam_ratio === null ? "N/A" : m.seam_ratio.toFixed(2) + "×";
    $("metricStatic").textContent = m.static_max_error + " / 255";
    $("metricSize").textContent =
      (m.gif_bytes / 1024 / 1024).toFixed(2) + " MB";
    $("metricDuration").textContent =
      (m.duration_ms / 1000).toFixed(2) + " s encoded duration";
    $("renderTitle").textContent = "Your loop is ready";
    let message =
      "Loop rendered. Download the GIF or save the project to continue later.";
    if (m.seam_ratio !== null && m.seam_ratio > 2)
      message +=
        " The loop seam is stronger than a typical frame step; try shorter arrows or a wider cross-fade.";
    if (m.mean_motion_mae < 0.01)
      message =
        "Almost no visible motion was measured. Increase motion strength or paint a textured region.";
    notice(message, "success");
    setView("preview");
  } catch (e) {
    notice(e.message, "error");
  } finally {
    setBusy(false);
  }
}
function download(url, name) {
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
}
function safeName() {
  return state.name.replace(/[^a-z0-9_-]/gi, "_").slice(0, 70) || "stillflow";
}
$("render").addEventListener("click", render);
$("download").addEventListener("click", () => {
  if (state.gif && !state.dirty) download(state.gif, safeName() + ".gif");
});
$("uploadButton").addEventListener("click", () => $("imageInput").click());
$("imageInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  if (file.size > 12 * 1024 * 1024) {
    notice("Please choose an image under 12 MB.", "error");
    e.target.value = "";
    return;
  }
  setBusy(true);
  try {
    const form = new FormData();
    form.append("file", file);
    const result = await api("/api/import", { method: "POST", body: form });
    const blank = document.createElement("canvas");
    blank.width = result.width;
    blank.height = result.height;
    const bc = blank.getContext("2d");
    bc.fillStyle = "black";
    bc.fillRect(0, 0, blank.width, blank.height);
    await applyProject({
      version: 1,
      name: file.name.replace(/\.[^.]+$/, ""),
      image: result.image,
      mask: blank.toDataURL(),
      arrows: [],
      settings: settings(),
    });
    $("exampleSelect").value = "";
    $("exampleDescription").textContent =
      "Your photograph · scaled to a maximum of 768 px";
    notice(
      "Image loaded. Paint a moving region, then draw a short motion arrow.",
    );
  } catch (err) {
    notice(err.message, "error");
  } finally {
    e.target.value = "";
    setBusy(false);
  }
});
$("saveProject").addEventListener("click", () => {
  if (!state.image) return;
  const blob = new Blob([JSON.stringify(project(), null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  download(url, safeName() + ".stillflow.json");
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  notice(
    "Project saved with its image, mask, arrows, and settings.",
    "success",
  );
});
$("openProject").addEventListener("click", () => $("projectInput").click());
$("projectInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  setBusy(true);
  try {
    if (file.size > 28 * 1024 * 1024)
      throw new Error("Project file is too large.");
    await applyProject(JSON.parse(await file.text()));
    $("exampleSelect").value = "";
    $("exampleDescription").textContent = "Saved project";
    notice("Project restored. Render to generate its preview.", "success");
  } catch (err) {
    notice(err.message, "error");
  } finally {
    e.target.value = "";
    setBusy(false);
  }
});
$("undo").addEventListener("click", () => history("undo"));
$("redo").addEventListener("click", () => history("redo"));
$("clear").addEventListener("click", () => {
  if (!state.image) return;
  saveSnapshot();
  mctx.fillStyle = "black";
  mctx.fillRect(0, 0, mask.width, mask.height);
  state.arrows = [];
  markDirty();
  setView("edit");
  draw();
});
document
  .querySelectorAll("[data-tool]")
  .forEach((b) => b.addEventListener("click", () => setTool(b.dataset.tool)));
document
  .querySelectorAll("[data-view]")
  .forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
for (const id of [
  "brush",
  "intensity",
  "feather",
  "frames",
  "fps",
  "blend",
  "loop",
])
  $(id).addEventListener("input", () => {
    updateLabels();
    if (id !== "brush") markDirty();
  });
for (const id of ["showMask", "showFlow"])
  $(id).addEventListener("change", () => {
    setView("edit");
    draw();
  });
$("helpButton").addEventListener("click", () => $("helpDialog").showModal());
$("closeHelp").addEventListener("click", () => $("helpDialog").close());
$("helpDialog").addEventListener("click", (e) => {
  if (e.target === $("helpDialog")) $("helpDialog").close();
});
$("apiLink").href = "/docs";
window.addEventListener("keydown", (e) => {
  if (
    state.busy ||
    ["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName) ||
    $("helpDialog").open
  )
    return;
  const key = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && key === "z") {
    e.preventDefault();
    history(e.shiftKey ? "redo" : "undo");
    return;
  }
  if (e.ctrlKey || e.metaKey) return;
  const tools = { m: "paint", e: "erase", a: "arrow", p: "pin" };
  if (tools[key]) setTool(tools[key]);
});
async function init() {
  updateLabels();
  try {
    const examples = await api("/api/examples");
    $("exampleSelect").replaceChildren(new Option("Choose an example…", ""));
    for (const item of examples)
      $("exampleSelect").add(new Option(item.name, item.id));
    $("exampleSelect").addEventListener("change", (e) => {
      const item = examples.find((x) => x.id === e.target.value);
      $("exampleDescription").textContent = item?.description || "";
      loadExample(e.target.value);
    });
    if (examples.length) {
      const first = examples.find((x) => x.id === "river") || examples[0];
      $("exampleSelect").value = first.id;
      $("exampleDescription").textContent = first.description;
      await loadExample(first.id);
    } else notice("Upload a photograph to begin.");
  } catch (e) {
    notice("Cannot reach the local server: " + e.message, "error");
  }
}
init();
