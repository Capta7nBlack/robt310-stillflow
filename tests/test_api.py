import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from stillflow.io import data_url
from stillflow.server import app

client = TestClient(app)


@pytest.fixture
def payload():
    y, x = np.mgrid[:32, :48]
    image = np.stack([x*4, y*6, x+y], axis=-1).astype(np.uint8)
    mask = np.zeros((32, 48), dtype=np.uint8)
    mask[6:26, 8:40] = 255
    return {"version":1, "name":"test", "image":data_url(image), "mask":data_url(mask),
            "arrows":[{"x":20,"y":16,"dx":8,"dy":0}], "settings":{"frames":8,"fps":8}}


def test_health_and_editor():
    assert client.get("/api/health").json()["engine"] == "NumPy"
    assert "Stillflow" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_render_roundtrip(payload):
    response = client.post("/api/render", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["gif"].startswith("data:image/gif;base64,")
    assert result["metrics"]["static_max_error"] == 0
    assert result["metrics"]["frames"] == 8
    assert result["flow"]


def test_import_resizes_and_decodes():
    buffer = io.BytesIO()
    Image.new("RGB", (1200, 600), "navy").save(buffer, format="PNG")
    response = client.post("/api/import", files={"file":("large.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 200
    assert (response.json()["width"], response.json()["height"]) == (768, 384)


def test_invalid_upload_is_rejected():
    assert client.post("/api/import", files={"file":("bad.png", b"not an image", "image/png")}).status_code == 400


@pytest.mark.parametrize("field,value", [("frames",500),("fps",0),("intensity",-1),("blend",0),("feather",-5)])
def test_settings_limits(payload, field, value):
    payload["settings"][field] = value
    assert client.post("/api/render", json=payload).status_code == 422


def test_empty_mask_rejected(payload):
    payload["mask"] = data_url(np.zeros((32,48), dtype=np.uint8))
    response = client.post("/api/render", json=payload)
    assert response.status_code == 400
    assert "Paint" in response.json()["detail"]


def test_mismatched_mask_rejected(payload):
    payload["mask"] = data_url(np.ones((10,10), dtype=np.uint8))
    assert client.post("/api/render", json=payload).status_code == 400


def test_no_arrows_rejected(payload):
    payload["arrows"] = []
    assert client.post("/api/render", json=payload).status_code == 400


def test_outside_arrow_rejected(payload):
    payload["arrows"][0]["x"] = 100
    assert client.post("/api/render", json=payload).status_code == 400


def test_excessive_motion_rejected(payload):
    payload["arrows"][0]["dx"] = 100
    assert client.post("/api/render", json=payload).status_code == 400


def test_missing_example_is_404():
    assert client.get("/api/examples/does-not-exist").status_code == 404


def test_future_project_version_is_rejected(payload):
    payload["version"] = 9
    assert client.post("/api/render", json=payload).status_code == 422
