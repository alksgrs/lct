import time

import pytest
from fastapi.testclient import TestClient

import api
from tests.paths import PARKOVAYA, TEST_DXF


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    api.RUNS_DIR = tmp_path_factory.mktemp("runs")
    return TestClient(api.app)


def wait(client, run_id, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get(f"/runs/{run_id}").json()
        if status["status"] in ("completed", "failed"):
            return status
        time.sleep(0.2)
    raise AssertionError("расчёт не завершился")


def upload(client, path):
    with open(path, "rb") as file:
        response = client.post("/runs", files={"file": ("plan.dxf", file, "application/dxf")})
    assert response.status_code == 200
    return response.json()["id"]


@pytest.fixture(scope="module")
def run(client):
    run_id = upload(client, TEST_DXF)
    assert wait(client, run_id)["status"] == "completed"
    return run_id


def test_rejects_non_dxf(client):
    response = client.post("/runs", files={"file": ("plan.txt", b"x", "text/plain")})
    assert response.status_code == 400


def test_result_shape(client, run):
    result = client.get(f"/runs/{run}/result").json()
    assert result["summary"]["trees"] > 0
    assert result["summary"]["shrubs"] > 0
    assert {p["species_type"] for p in result["placements"]} == {"tree", "shrub"}
    assert result["site"]["geometry"]["type"] in ("Polygon", "MultiPolygon")
    rule = result["rules"][0]
    for key in ("rule_id", "act", "clause", "state", "limit_m"):
        assert key in rule
    assert all(r["rule_id"] for r in result["pending_rules"])
    greening = result["greening"]
    assert result["summary"]["lawn_m2"] == greening["lawn_area_m2"] > 0
    assert greening["lawn"]["type"] in ("Polygon", "MultiPolygon")
    assert set(greening["lawn_offsets_m"]) >= {"ROAD", "PAVEMENT", "BUILDING"}
    assert result["summary"]["flowerbeds"] == len(greening["flowerbeds"])


def test_check_point_returns_norms(client, run):
    result = client.get(f"/runs/{run}/result").json()
    placement = result["placements"][0]
    response = client.post(f"/runs/{run}/check", json={
        "x": placement["x"], "y": placement["y"], "species_type": placement["species_type"],
        "id": placement["id"],
    })
    data = response.json()
    assert data["valid"]
    assert data["checks"]
    ids = {rule["rule_id"] for rule in result["rules"]}
    assert all(check["rule_id"] in ids for check in data["checks"])


def test_moving_outside_is_rejected(client, run):
    result = client.get(f"/runs/{run}/result").json()
    placement = result["placements"][0]
    response = client.post(f"/runs/{run}/validate-edits", json={
        "placements": [{"id": placement["id"], "x": placement["x"] + 100000, "y": placement["y"]}],
    })
    data = response.json()
    assert not data["valid"]
    assert data["issues"][0]["code"] == "outside_site"
    assert client.post(f"/runs/{run}/save-edits", json={
        "placements": [{"id": placement["id"], "x": placement["x"] + 100000, "y": placement["y"]}],
    }).status_code == 422


def test_spacing_conflict_is_reported(client, run):
    result = client.get(f"/runs/{run}/result").json()
    trees = [p for p in result["placements"] if p["species_type"] == "tree"]
    first, second = trees[0], trees[1]
    response = client.post(f"/runs/{run}/validate-edits", json={
        "placements": [{"id": first["id"], "x": second["x"] + 0.1, "y": second["y"]}],
    })
    codes = {issue["code"] for issue in response.json()["issues"]}
    assert codes & {"plant_spacing", "norm"}


def test_save_and_download(client, run):
    result = client.get(f"/runs/{run}/result").json()
    placement = result["placements"][-1]
    response = client.post(f"/runs/{run}/save-edits", json={
        "placements": [{"id": placement["id"], "x": placement["x"], "y": placement["y"]}],
    })
    assert response.status_code == 200
    original = client.get(f"/runs/{run}/original-dxf")
    assert original.status_code == 200
    assert b"PLANTING_LAWN" in original.content
    assert client.get(f"/runs/{run}/edited-dxf").status_code == 200
    report = client.get(f"/runs/{run}/report")
    assert report.status_code == 200
    data = report.json()
    assert len(data["placements"]) == len(result["placements"])
    assert all("checks" in p for p in data["placements"])
    assert data["greening"]["lawn_area_m2"] > 0


def test_layer_override_reruns(client):
    run_id = upload(client, PARKOVAYA)
    first = wait(client, run_id)
    assert first["status"] == "completed"
    result = client.get(f"/runs/{run_id}/result").json()
    unresolved = [l["layer"] for l in result["layers"] if l["kind"] is None]
    assert unresolved

    bad = client.post(f"/runs/{run_id}/layers", json={"overrides": {unresolved[0]: "NONSENSE"}})
    assert bad.status_code == 422

    response = client.post(f"/runs/{run_id}/layers", json={"overrides": {unresolved[0]: "ANNOTATION"}})
    assert response.status_code == 200
    assert wait(client, run_id)["status"] == "completed"
    rerun = client.get(f"/runs/{run_id}/result").json()
    layer = next(l for l in rerun["layers"] if l["layer"] == unresolved[0])
    assert layer["kind"] == "ANNOTATION"
    assert layer["method"] == "override"
    assert rerun["overrides"] == {unresolved[0]: "ANNOTATION"}


def test_add_and_remove_points(client, run):
    result = client.get(f"/runs/{run}/result").json()
    shrubs = [p for p in result["placements"] if p["species_type"] == "shrub"]
    victim = shrubs[0]
    response = client.post(f"/runs/{run}/save-edits", json={
        "removed": [victim["id"]],
        "added": [{"id": "shrub-u1", "x": victim["x"], "y": victim["y"], "species_type": "shrub"}],
    })
    assert response.status_code == 200
    ids = {p["id"] for p in response.json()["placements"]}
    assert victim["id"] not in ids
    assert "shrub-u1" in ids

    duplicate = client.post(f"/runs/{run}/validate-edits", json={
        "added": [{"id": "shrub-u1", "x": 0, "y": 0, "species_type": "shrub"}],
    })
    assert duplicate.status_code == 422


def test_visualize_without_key(client, run, monkeypatch):
    for name in ("FUSIONBRAIN_KEY", "FUSIONBRAIN_SECRET", "YANDEX_API_KEY", "YANDEX_FOLDER_ID", "YANDEX_OAUTH_TOKEN",
                 "YANDEX_IAM_TOKEN", "GIGACHAT_AUTH_KEY", "GIGACHAT_CREDENTIALS", "GREENPLAN_AI_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("POLLINATIONS", "0")
    assert client.get("/visualize/status").json()["available"] is False
    response = client.post(f"/runs/{run}/visualize", json={"season": "summer"})
    assert response.status_code == 503


def test_visualize_with_mocked_generator(client, run, monkeypatch):
    from greenplan import visual

    def fake_generate(summary, site_method, objects, season, seed, provider=None):
        assert summary["trees"] > 0
        assert provider == "gigachat"
        return visual.Picture(image=b"\x89PNG\r\n\x1a\nxx", mime="image/png", provider="gigachat",
                              prompt=visual.build_prompt(summary, site_method, objects, season),
                              meta={"failed": ["YandexART: доступ запрещён"]})

    monkeypatch.setattr(visual, "generate", fake_generate)
    response = client.post(f"/runs/{run}/visualize", json={"season": "winter", "provider": "gigachat"})
    assert response.status_code == 200
    data = response.json()
    assert data["image"].startswith("data:image/png;base64,")
    assert "зимний" in data["prompt"]
    assert data["provider_name"] == "GigaChat"
    assert data["skipped"] == ["YandexART: доступ запрещён"]
    assert client.post(f"/runs/{run}/visualize", json={"provider": "midjourney"}).status_code == 422


def test_dxf_is_written_on_first_download(client):
    run_id = upload(client, TEST_DXF)
    assert wait(client, run_id)["status"] == "completed"
    job_dir = api.RUNS_DIR / run_id
    assert not (job_dir / "result.dxf").exists()
    response = client.get(f"/runs/{run_id}/original-dxf")
    assert response.status_code == 200
    assert (job_dir / "result.dxf").exists()
    assert b"PLANTING_TREES" in response.content
